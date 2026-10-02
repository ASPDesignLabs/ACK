// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.File
import java.time.Instant
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.util.Locale

/** Loudness notes for one clip or one recording (format document, section 5.1). */
data class CaptureMetrics(val peakDbfs: Double, val rmsDbfs: Double, val clippedSamples: Int) {
    companion object {
        fun of(m: ClipMetrics) = CaptureMetrics(m.peakDbfs, m.rmsDbfs, m.clippedSamples)
    }
}

/** The microphone settings a session was recorded with. [source] is what the system really used; [sourceRequested] is what was asked for. */
data class AudioSettings(val sampleRate: Int, val source: String, val sourceRequested: String)

/** Only the phone model and Android version; the format allows nothing else about the person or the phone (section 4.2). */
data class DeviceNote(val model: String, val sdk: Int)

data class ScriptNote(val id: String, val title: String, val cardsTotal: Int)

/** One kept clip of a script session. Times are UTC text, `YYYY-MM-DDTHH:MM:SSZ` (see [CaptureTime]). */
data class ScriptClip(
    val index: Int, val card: Int, val attempt: Int, val text: String, val recorded: String, val durationS: Double,
    val speech: SpeechSpan?, val metrics: CaptureMetrics, val flags: List<String>, val wav: File,
)

/** A suggested piece of a free-speech recording, with its loudness notes. The audio itself is never cut on the phone. */
data class ProposedPiece(val startS: Double, val endS: Double, val endKind: String, val metrics: CaptureMetrics)

/** What a session records, whichever mode it was in. Everything the package needs is here; nothing else about the person is. */
sealed class CaptureSession {
    abstract val id: String
    abstract val label: String
    abstract val started: String
    abstract val ended: String
    abstract val language: String
    abstract val audio: AudioSettings
    abstract val noiseFloorDbfs: Double?
    abstract val thresholdDbfs: Double
    abstract val device: DeviceNote?
}

data class ScriptSession(
    override val id: String, override val label: String, override val started: String, override val ended: String,
    override val language: String, override val audio: AudioSettings, override val noiseFloorDbfs: Double?,
    override val thresholdDbfs: Double, override val device: DeviceNote?, val script: ScriptNote, val clips: List<ScriptClip>,
) : CaptureSession()

data class FreeSession(
    override val id: String, override val label: String, override val started: String, override val ended: String,
    override val language: String, override val audio: AudioSettings, override val noiseFloorDbfs: Double?,
    override val thresholdDbfs: Double, override val device: DeviceNote?, val topic: String, val wav: File, val durationS: Double,
    val metrics: CaptureMetrics, val proposed: List<ProposedPiece>,
) : CaptureSession()

/** Times and names the way the format wants them. Always the Root locale, so digits stay 0-9 whatever the phone's language is. */
object CaptureTime {
    /** UTC, whole seconds: `2026-10-02T18:04:11Z`. */
    fun utc(epochMillis: Long): String = Instant.ofEpochSecond(Math.floorDiv(epochMillis, 1000L)).toString()

    /** `s20261002-180411-a3f9`: the time (UTC) and four hex digits to tell apart two sessions begun in the same second. */
    fun sessionId(epochMillis: Long, random: Int): String {
        val t = ZonedDateTime.ofInstant(Instant.ofEpochMilli(epochMillis), ZoneOffset.UTC)
        return String.format(
            Locale.ROOT, "s%04d%02d%02d-%02d%02d%02d-%04x",
            t.year, t.monthValue, t.dayOfMonth, t.hour, t.minute, t.second, random and 0xffff,
        )
    }

    /** `ack-training-20261002-183000.zip` */
    fun packageFileName(epochMillis: Long, part: Int = 1): String {
        val t = ZonedDateTime.ofInstant(Instant.ofEpochMilli(epochMillis), ZoneOffset.UTC)
        val base = String.format(Locale.ROOT, "ack-training-%04d%02d%02d-%02d%02d%02d", t.year, t.monthValue, t.dayOfMonth, t.hour, t.minute, t.second)
        return if (part <= 1) "$base.zip" else String.format(Locale.ROOT, "%s-part%d.zip", base, part)
    }
}

/** Entry names inside a package (format document, section 2). */
object PackageNames {
    const val MANIFEST = "manifest.json"
    const val README = "README.txt"
    val SESSION_ID = Regex("^s\\d{8}-\\d{6}-[0-9a-f]{4}$")
    val AUDIO_PATH = Regex("^sessions/(s\\d{8}-\\d{6}-[0-9a-f]{4})/(clips/(\\d{4,5})\\.wav|session\\.wav)$")
    val DIRECTORY = Regex("^sessions/(?:s\\d{8}-\\d{6}-[0-9a-f]{4}/(?:clips/)?)?$")

    fun clip(sessionId: String, index: Int): String = String.format(Locale.ROOT, "sessions/%s/clips/%04d.wav", sessionId, index)
    fun recording(sessionId: String): String = "sessions/$sessionId/session.wav"
}
