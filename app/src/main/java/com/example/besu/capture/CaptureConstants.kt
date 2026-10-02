// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

// The numbers the training-capture format is built on (docs/ACK_TRAINING_CAPTURE_FORMAT.md, section 11).
//
// Nothing in this package imports android.*: it is plain Kotlin on purpose, so every rule can be run by an ordinary unit test
// against the same shared test cases (tools/freeform_studio/tests/data/ack_capture/) that the Python side is held to.
// CaptureConstantsTest compares this object with the document's constants block, so the two cannot drift apart.
object CaptureConstants {
    const val HOP_S = 0.01
    const val MAX_CLIP_S = 11.5
    const val MIN_CLIP_S = 1.0
    const val THRESH_DEFAULT_DB = -45.0
    const val THRESH_OFFSET_DB = 10.0
    const val THRESH_MIN_DB = -55.0
    const val THRESH_MAX_DB = -30.0
    const val NOISE_CHECK_S = 2.0
    const val REGION_MIN_SILENCE_S = 0.3
    const val REGION_MIN_LEN_S = 0.1
    const val DEFAULT_PACE_WPS = 2.6
    const val PACE_MIN_WPS = 1.5
    const val PACE_MAX_WPS = 4.0
    const val PACE_MIN_CLIPS = 5
    const val TARGET_S = 9.5
    const val MAX_EST_S = 11.0
    const val MIN_CARD_WORDS = 3
    const val MIN_SPLIT_WORDS = 4
    const val MAX_CARD_CHARS = 600
    const val PRE_ROLL_HOPS = 50
    const val START_RUN_HOPS = 10
    const val END_SILENCE_HOPS = 120
    const val TAIL_HOPS = 40
    const val NO_SPEECH_TIMEOUT_HOPS = 2000
    const val HARD_CLIP_HOPS = 3000
    const val CUT_AFTER_S = 8.0
    const val FORCE_AT_S = 11.0
    const val FORCE_WINDOW_S = 2.0
    const val MIN_SEG_S = 1.0
    const val PAD_LEAD_S = 0.15
    const val PAD_TAIL_S = 0.25
    const val GAP_S = 0.4
    const val MAX_PACKAGE_BYTES = 2_000_000_000L
    const val MAX_ENTRIES = 20_000
    const val MAX_MANIFEST_BYTES = 8_388_608
    const val MAX_SESSIONS = 200
    const val MAX_CLIPS_PER_SESSION = 5_000
    const val MAX_FREE_SESSION_S = 5_400

    // Whole-hop forms of the lengths above, worked out the same way as the reference code (seconds / 0.01, rounded).
    const val REGION_MIN_SILENCE_HOPS = 30
    const val REGION_MIN_LEN_HOPS = 10
    const val CUT_AFTER_HOPS = 800
    const val FORCE_AT_HOPS = 1100
    const val FORCE_WINDOW_HOPS = 200
    const val MIN_SEG_HOPS = 100
    const val PAD_LEAD_HOPS = 15
    const val PAD_TAIL_HOPS = 25

    /** Every constant that appears in the document's block, by the document's name, for the test that compares them. */
    fun asMap(): Map<String, Double> = linkedMapOf(
        "HOP_S" to HOP_S, "MAX_CLIP_S" to MAX_CLIP_S, "MIN_CLIP_S" to MIN_CLIP_S, "THRESH_DEFAULT_DB" to THRESH_DEFAULT_DB,
        "THRESH_OFFSET_DB" to THRESH_OFFSET_DB, "THRESH_MIN_DB" to THRESH_MIN_DB, "THRESH_MAX_DB" to THRESH_MAX_DB,
        "NOISE_CHECK_S" to NOISE_CHECK_S, "REGION_MIN_SILENCE_S" to REGION_MIN_SILENCE_S, "REGION_MIN_LEN_S" to REGION_MIN_LEN_S,
        "DEFAULT_PACE_WPS" to DEFAULT_PACE_WPS, "PACE_MIN_WPS" to PACE_MIN_WPS, "PACE_MAX_WPS" to PACE_MAX_WPS,
        "PACE_MIN_CLIPS" to PACE_MIN_CLIPS.toDouble(), "TARGET_S" to TARGET_S, "MAX_EST_S" to MAX_EST_S,
        "MIN_CARD_WORDS" to MIN_CARD_WORDS.toDouble(), "MIN_SPLIT_WORDS" to MIN_SPLIT_WORDS.toDouble(),
        "MAX_CARD_CHARS" to MAX_CARD_CHARS.toDouble(), "PRE_ROLL_HOPS" to PRE_ROLL_HOPS.toDouble(),
        "START_RUN_HOPS" to START_RUN_HOPS.toDouble(), "END_SILENCE_HOPS" to END_SILENCE_HOPS.toDouble(),
        "TAIL_HOPS" to TAIL_HOPS.toDouble(), "NO_SPEECH_TIMEOUT_HOPS" to NO_SPEECH_TIMEOUT_HOPS.toDouble(),
        "HARD_CLIP_HOPS" to HARD_CLIP_HOPS.toDouble(), "CUT_AFTER_S" to CUT_AFTER_S, "FORCE_AT_S" to FORCE_AT_S,
        "FORCE_WINDOW_S" to FORCE_WINDOW_S, "MIN_SEG_S" to MIN_SEG_S, "PAD_LEAD_S" to PAD_LEAD_S, "PAD_TAIL_S" to PAD_TAIL_S,
        "GAP_S" to GAP_S, "MAX_PACKAGE_BYTES" to MAX_PACKAGE_BYTES.toDouble(), "MAX_ENTRIES" to MAX_ENTRIES.toDouble(),
        "MAX_MANIFEST_BYTES" to MAX_MANIFEST_BYTES.toDouble(), "MAX_SESSIONS" to MAX_SESSIONS.toDouble(),
        "MAX_CLIPS_PER_SESSION" to MAX_CLIPS_PER_SESSION.toDouble(), "MAX_FREE_SESSION_S" to MAX_FREE_SESSION_S.toDouble(),
    )
}
