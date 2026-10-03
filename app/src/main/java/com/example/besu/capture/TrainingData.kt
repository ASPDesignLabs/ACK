// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import kotlinx.serialization.Serializable

// What the phone keeps on disk for training-data capture. Everything here is plain Kotlin and plain JSON: no Android classes, so
// the store that reads and writes it (TrainingStore) can be tested on an ordinary JVM. Every field a later version might add has a
// default, and unknown fields are ignored on reading, so an older file always opens in a newer app.

/** A text the person will read aloud. The cards are worked out from [text] when needed; they are not stored. */
@Serializable
data class TrainingScript(
    val id: String,
    val title: String,
    val text: String,
    /** "join": a line break is a space and a blank line ends a paragraph. "keep": every line is its own paragraph. */
    val lines: String = "join",
    val language: String = "en-US",
    val createdAt: Long = 0L,
    val updatedAt: Long = 0L,
)

/** Where a stored clip is in its life. Only [DONE] clips go into a package. */
object ClipState {
    /** Being recorded right now, or the app closed before it could finish. */
    const val OPEN = "OPEN"
    /** Finished and kept. */
    const val DONE = "DONE"
    /** The person redid the card; this attempt is kept on disk but not packaged. */
    const val REDONE = "REDONE"
    /** Found unfinished after the app closed unexpectedly and repaired. Not packaged until the person says to keep it. */
    const val RECOVERED = "RECOVERED"
}

@Serializable
data class StoredClip(
    val index: Int,
    val card: Int,
    val attempt: Int,
    val text: String,
    val recorded: String,
    val state: String = ClipState.OPEN,
    val durationS: Double = 0.0,
    val speechStartS: Double? = null,
    val speechEndS: Double? = null,
    val peakDbfs: Double = -120.0,
    val rmsDbfs: Double = -120.0,
    val clippedSamples: Int = 0,
    val flags: List<String> = emptyList(),
)

/** A piece of a free-speech recording that the phone suggests, with its loudness notes. */
@Serializable
data class StoredPiece(
    val startS: Double,
    val endS: Double,
    val endKind: String,
    val peakDbfs: Double = -120.0,
    val rmsDbfs: Double = -120.0,
    val clippedSamples: Int = 0,
)

@Serializable
data class StoredRecording(
    val state: String = ClipState.OPEN,
    val durationS: Double = 0.0,
    val peakDbfs: Double = -120.0,
    val rmsDbfs: Double = -120.0,
    val clippedSamples: Int = 0,
    val pieces: List<StoredPiece> = emptyList(),
)

@Serializable
data class StoredSession(
    val id: String,
    /** "script" or "free". */
    val mode: String,
    val label: String = "",
    val started: String,
    val ended: String? = null,
    /** False while the session is being recorded; true once it was ended on purpose or repaired after a crash. */
    val closed: Boolean = false,
    val language: String = "en-US",
    val sampleRate: Int,
    val source: String,
    val sourceRequested: String,
    val noiseFloorDbfs: Double? = null,
    val thresholdDbfs: Double,
    val deviceModel: String? = null,
    val deviceSdk: Int? = null,
    val scriptId: String? = null,
    val scriptTitle: String? = null,
    val cardsTotal: Int = 0,
    val paceWps: Double = CaptureConstants.DEFAULT_PACE_WPS,
    val clips: List<StoredClip> = emptyList(),
    val topic: String = "",
    val recording: StoredRecording? = null,
)

/** Notes the phone adds to a clip by itself, and the marks the person may add (format document, section 4.5). */
object ClipFlags {
    /** The marks a person can set on a clip. The first four exclude the piece from training on the PC until a reviewer clears them. */
    val PERSON = linkedSetOf("noise", "unclear", "laugh", "cough", "stumble")

    fun automatic(durationS: Double, endedByLimit: Boolean): List<String> {
        val out = mutableListOf<String>()
        if (durationS > CaptureConstants.MAX_CLIP_S) out.add("long")
        if (durationS < CaptureConstants.MIN_CLIP_S) out.add("short")
        if (endedByLimit) out.add("no_end")
        return out
    }
}

/** How much room the phone needs before and while recording. Audio is 96 KB per second at 48 kHz; running out of space mid-card must never lose a clip. */
object DiskGuard {
    const val MIN_FREE_TO_START_BYTES = 300L * 1024 * 1024
    const val MIN_FREE_WHILE_RECORDING_BYTES = 100L * 1024 * 1024

    fun canStart(usableBytes: Long): Boolean = usableBytes >= MIN_FREE_TO_START_BYTES

    fun mustStop(usableBytes: Long): Boolean = usableBytes < MIN_FREE_WHILE_RECORDING_BYTES

    /** Whole minutes of recording that fit before the reserve is touched. */
    fun minutesLeft(usableBytes: Long, sampleRate: Int): Long {
        val perMinute = sampleRate.toLong() * 2 * 60
        return maxOf(0L, usableBytes - MIN_FREE_WHILE_RECORDING_BYTES) / perMinute
    }

    fun describe(usableBytes: Long, sampleRate: Int): String {
        val mb = usableBytes / (1024 * 1024)
        return "${mb} MB free, room for about ${minutesLeft(usableBytes, sampleRate)} minutes of recording"
    }
}
