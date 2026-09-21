package com.example.besu.output

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import androidx.core.app.ActivityCompat

// Captures one voice recording for a Quick Actions prompt. AudioRecord
// setup mirrors AmbientAudioAnalyzer's (DBMediaRecorder.kt) -- same
// UNPROCESSED-with-VOICE_RECOGNITION-fallback source selection -- but
// captures full PCM into a buffer for storage/playback rather than
// sampling RMS for a dB meter.
//
// Capture runs on its own background thread once start() succeeds; stop()
// joins that thread and hands back the raw PCM (before noise reduction --
// callers run AudioDsp.reduceNoise on the result themselves). The UI polls
// currentDurationMs() on its own timer to show a live counter rather than
// this class pushing updates across threads into Compose state.
class VoiceRecorder {
    companion object {
        const val SAMPLE_RATE = 16000
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
        // A Quick Actions prompt is a short phrase, not a memo -- caps a
        // recording from growing without bound if someone forgets to stop.
        const val MAX_DURATION_MS = 15_000L
    }

    private var audioRecord: AudioRecord? = null
    private var recordingThread: Thread? = null
    private val buffer = mutableListOf<Short>()
    private val bufferLock = Any()

    @Volatile
    var isRecording = false
        private set

    fun start(context: Context): Boolean {
        if (isRecording) return false
        if (ActivityCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            return false
        }

        val minBufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        if (minBufferSize <= 0) return false

        val audioSource = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            MediaRecorder.AudioSource.UNPROCESSED
        } else {
            MediaRecorder.AudioSource.VOICE_RECOGNITION
        }

        var record = tryCreate(audioSource, minBufferSize)
        if (record == null || record.state != AudioRecord.STATE_INITIALIZED) {
            record?.release()
            record = tryCreate(MediaRecorder.AudioSource.VOICE_RECOGNITION, minBufferSize)
        }
        if (record == null || record.state != AudioRecord.STATE_INITIALIZED) {
            record?.release()
            return false
        }

        synchronized(bufferLock) { buffer.clear() }
        audioRecord = record

        try {
            record.startRecording()
        } catch (e: Exception) {
            record.release()
            audioRecord = null
            return false
        }

        isRecording = true

        val thread = Thread {
            val chunk = ShortArray(2048)
            while (isRecording) {
                val read = try {
                    record.read(chunk, 0, chunk.size)
                } catch (e: Exception) {
                    -1
                }
                if (read > 0) {
                    synchronized(bufferLock) {
                        for (i in 0 until read) buffer.add(chunk[i])
                    }
                    if (currentDurationMs() >= MAX_DURATION_MS) {
                        isRecording = false
                    }
                }
            }
        }
        recordingThread = thread
        thread.start()
        return true
    }

    private fun tryCreate(source: Int, bufferSize: Int): AudioRecord? = try {
        AudioRecord(source, SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT, bufferSize)
    } catch (e: Exception) {
        null
    }

    fun currentDurationMs(): Long =
        synchronized(bufferLock) { buffer.size }.toLong() * 1000L / SAMPLE_RATE

    // Stops capture and returns the raw PCM captured so far.
    fun stop(): ShortArray {
        isRecording = false
        recordingThread?.join(1000)
        recordingThread = null
        try {
            audioRecord?.stop()
        } catch (_: IllegalStateException) {
            // Already stopped.
        }
        audioRecord?.release()
        audioRecord = null
        return synchronized(bufferLock) { buffer.toShortArray() }
    }

    // Stops capture and throws away whatever was recorded -- the user
    // backed out before accepting it.
    fun discard() {
        isRecording = false
        recordingThread?.join(1000)
        recordingThread = null
        try {
            audioRecord?.stop()
        } catch (_: IllegalStateException) {
        }
        audioRecord?.release()
        audioRecord = null
        synchronized(bufferLock) { buffer.clear() }
    }
}
