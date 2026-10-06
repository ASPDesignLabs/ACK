// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

/** How much room is left on the phone: whole megabytes free, and about how many minutes of recording fit before the reserve is touched. */
data class DiskRoom(val megabytes: Long, val minutes: Long)

/**
 * What the engines, the microphone and the recording screen tell the person, carried as a kind with the numbers and the technical detail it needs, **never as a sentence**. The words are chosen where the notice
 * is drawn (core/CaptureText.kt), in the language the person chose, so nothing here has a word in it and nothing compares a drawn word. Plain Kotlin (no `android.*`).
 *
 * A `detail` is the sentence the storage layer or the system gave (an exception's message): it is shown as it came, inside a sentence of ours, and is null when there was none.
 */
sealed interface CaptureNotice {
    // ---- from the engines (the engines are told what happened; they say nothing) ----------------------------------------------------------------------
    /** A write failed. */
    data class CouldNotSave(val detail: String?) : CaptureNotice
    /** A script session paused because the phone is nearly full; the kept clips are safe. */
    data class OutOfRoomKeptClipsSafe(val room: DiskRoom) : CaptureNotice
    /** A free recording stopped because the phone is nearly full; what was recorded is saved. */
    data class OutOfRoomRecordingSaved(val room: DiskRoom) : CaptureNotice
    /** Nobody spoke for [seconds] seconds, so the session paused. */
    data class NothingHeard(val seconds: Int) : CaptureNotice
    /** A free recording reached its longest allowed length ([minutes] minutes) and was saved. */
    data class LongestRecording(val minutes: Int) : CaptureNotice

    // ---- from the microphone ----------------------------------------------------------------------------------------------------------------------------
    /** The app has no permission to use the microphone (seen when it was opened). */
    object MicNotAllowed : CaptureNotice
    /** The person turned the permission down when asked; they can allow it in the phone's settings and try again. */
    object MicDenied : CaptureNotice
    object MicCouldNotOpen : CaptureNotice
    /** Something failed in the audio handler while recording ([detail] is the exception's message or its class). */
    data class MicTrouble(val detail: String) : CaptureNotice
    /** The microphone stopped; [errorCode] is what the system returned (a negative number). */
    data class MicStopped(val errorCode: Int) : CaptureNotice

    // ---- from the recording screen --------------------------------------------------------------------------------------------------------------
    /** Not enough room to start: [room] is what there is, [needMegabytes] what a session needs. */
    data class NotEnoughRoomToStart(val room: DiskRoom, val needMegabytes: Long) : CaptureNotice
    object ScriptGone : CaptureNotice
    data class ScriptUnreadable(val detail: String?) : CaptureNotice
    data class CouldNotStart(val detail: String?) : CaptureNotice
}
