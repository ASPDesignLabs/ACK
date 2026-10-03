// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.voicecapture

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import androidx.core.content.ContextCompat
import com.example.besu.capture.CardSplitter
import com.example.besu.capture.ClipState
import com.example.besu.capture.SpeechSpan
import com.example.besu.capture.TrainingStore
import java.io.File
import java.util.Locale

// The Android-only edges of training-data capture. Everything that decides what is recorded, cut, kept and written lives in
// com.example.besu.capture (plain Kotlin, unit tested on a JVM); this file only reaches the phone: where files go, the microphone,
// a few remembered settings. Keep it thin.
object TrainingCapture {
    /** The logcat tag for everything here. Lines carry counts, rates and reasons only: never audio and never what a script says. */
    const val LOG_TAG = "ACK_TRAIN"
    private const val PREFS = "ack_training_capture"
    private const val KEY_SEEN_HELP_OFFER = "seen_help_offer"
    private const val KEY_LAST_LABEL = "last_label"
    private const val KEY_END_WAIT_HOPS = "end_wait_hops"

    /** The end-of-card wait the person can choose, in hops (10 ms each): 0.8 s to 2.5 s. */
    const val END_WAIT_MIN_HOPS = 80
    const val END_WAIT_MAX_HOPS = 250

    @Volatile
    private var shared: TrainingStore? = null

    /** One store for the whole app, so its locks cover every screen that touches the files. */
    fun store(context: Context): TrainingStore {
        val root = File(context.applicationContext.filesDir, "training_capture")
        shared?.let { return it }
        return synchronized(this) { shared ?: TrainingStore(root).also { shared = it } }
    }

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun hasSeenHelpOffer(context: Context): Boolean = prefs(context).getBoolean(KEY_SEEN_HELP_OFFER, false)

    fun markHelpOfferSeen(context: Context) {
        prefs(context).edit().putBoolean(KEY_SEEN_HELP_OFFER, true).apply()
    }

    fun lastLabel(context: Context): String = prefs(context).getString(KEY_LAST_LABEL, "") ?: ""

    fun setLastLabel(context: Context, label: String) {
        prefs(context).edit().putString(KEY_LAST_LABEL, label.take(120)).apply()
    }

    fun endWaitHops(context: Context): Int =
        prefs(context).getInt(KEY_END_WAIT_HOPS, 120).coerceIn(END_WAIT_MIN_HOPS, END_WAIT_MAX_HOPS)

    fun setEndWaitHops(context: Context, hops: Int) {
        prefs(context).edit().putInt(KEY_END_WAIT_HOPS, hops.coerceIn(END_WAIT_MIN_HOPS, END_WAIT_MAX_HOPS)).apply()
    }

    /** Free space on the storage the recordings are kept on. */
    fun usableBytes(context: Context): Long = context.applicationContext.filesDir.usableSpace

    /** The phone model, as the package may carry it (the format allows nothing else about the phone but the Android version). */
    fun deviceModel(): String = Build.MODEL ?: ""

    fun androidVersion(): Int = Build.VERSION.SDK_INT

    fun appVersion(context: Context): String = try {
        @Suppress("DEPRECATION")
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: ""
    } catch (e: Exception) {
        ""
    }

    /** A language code in the form the format wants (en-US), from the phone's own setting. */
    fun defaultLanguage(): String {
        val l = Locale.getDefault()
        return if (l.country.isNotEmpty()) "${l.language}-${l.country}" else l.language.ifEmpty { "en-US" }
    }

    /** How fast the person reads, from the clips they have kept (words per second), or null until there are enough. */
    fun measuredPace(store: TrainingStore): Double? {
        val clips = store.listSessions().items.flatMap { s ->
            s.clips.filter { it.state == ClipState.DONE }.map { c ->
                val a = c.speechStartS
                val b = c.speechEndS
                c.text to (if (a != null && b != null) SpeechSpan(a, b) else null)
            }
        }
        return CardSplitter.measurePace(clips)
    }

    fun hasMicPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
}

// The microphone, opened the way training data needs it and no other way: 48 kHz if the phone allows it (else 44.1 kHz), 16-bit,
// mono, and the UNPROCESSED source so the system does not clean up, level or compress the voice (falling back to VOICE_RECOGNITION
// where a phone has no unprocessed source; the session notes say which was used). It hands every sample to [sink] on its own
// thread and does nothing else with them.
class TrainingMicrophone {
    var sampleRate = 0
        private set
    var sourceUsed = ""
        private set

    /** Where audio goes. Set to null to drop it. Called on the microphone's thread. */
    @Volatile
    var sink: ((ShortArray, Int) -> Unit)? = null

    /** Set when the microphone stopped working after it had started, in words for the person. */
    @Volatile
    var failure: String? = null
        private set

    @Volatile
    private var running = false
    private var record: AudioRecord? = null
    private var thread: Thread? = null

    val isOpen: Boolean get() = running

    /** Opens the microphone. Returns null on success, or a message saying why not. */
    fun open(context: Context): String? {
        if (running) return null
        if (!TrainingCapture.hasMicPermission(context)) return "THE MICROPHONE IS NOT ALLOWED. ALLOW IT IN THE PHONE'S SETTINGS FOR ACK."
        for (rate in intArrayOf(48_000, 44_100)) {
            val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            if (min <= 0) continue
            val bytes = maxOf(min * 4, rate * 2)                       // at least a second of headroom, so a slow disk write never loses audio
            for ((source, name) in listOf(MediaRecorder.AudioSource.UNPROCESSED to "UNPROCESSED", MediaRecorder.AudioSource.VOICE_RECOGNITION to "VOICE_RECOGNITION")) {
                val rec = try {
                    AudioRecord(source, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, bytes)
                } catch (e: Exception) {
                    null
                }
                if (rec == null || rec.state != AudioRecord.STATE_INITIALIZED) {
                    Log.w(TrainingCapture.LOG_TAG, "microphone: $name at $rate Hz was not available")
                    rec?.release()
                    continue
                }
                try {
                    rec.startRecording()
                } catch (e: Exception) {
                    Log.w(TrainingCapture.LOG_TAG, "microphone: $name at $rate Hz would not start (${e.javaClass.simpleName})")
                    rec.release()
                    continue
                }
                Log.i(TrainingCapture.LOG_TAG, "microphone open: $rate Hz, source $name, buffer $bytes bytes")
                record = rec
                sampleRate = rate
                sourceUsed = name
                failure = null
                running = true
                val buf = ShortArray(rate / 100 * 4)
                thread = Thread({
                    while (running) {
                        val n = try { rec.read(buf, 0, buf.size) } catch (e: Exception) { -1 }
                        if (n > 0) {
                            try {
                                sink?.invoke(buf, n)
                            } catch (e: Exception) {
                                failure = "SOMETHING WENT WRONG WHILE RECORDING: ${e.message ?: e.javaClass.simpleName}"
                                Log.e(TrainingCapture.LOG_TAG, "recording failed in the audio handler", e)
                                running = false
                            }
                        } else if (n < 0) {
                            failure = "THE MICROPHONE STOPPED (ERROR $n). ANOTHER APP MAY BE USING IT."
                            Log.e(TrainingCapture.LOG_TAG, "microphone read returned $n")
                            running = false
                        }
                    }
                }, "ack-training-mic").also { it.start() }
                return null
            }
        }
        Log.e(TrainingCapture.LOG_TAG, "microphone: no combination of rate and source could be opened")
        return "THE MICROPHONE COULD NOT BE OPENED. ANOTHER APP MAY BE USING IT."
    }

    fun close() {
        running = false
        sink = null
        thread?.join(1000)
        thread = null
        try { record?.stop() } catch (_: IllegalStateException) { }
        record?.release()
        record = null
    }
}
