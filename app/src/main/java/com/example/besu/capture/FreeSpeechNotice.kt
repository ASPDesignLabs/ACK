// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

/**
 * What RECORD FREE SPEECH says about other people. It records everything the microphone hears, so anyone nearby is recorded too,
 * and neither the home screen nor the setup screen used to say so. Plain Kotlin (no `android.*`) so the words are tested without
 * a phone; the screens only show them.
 *
 * Text only, by design: the capture screens make no sound and no vibration while the microphone is open (a buzz would land in the
 * recording), so this is never a dialog, a toast or a standard button. The minutes come from [CaptureConstants.MAX_FREE_SESSION_S],
 * so the notice cannot say a limit the engine does not enforce.
 */
object FreeSpeechNotice {
    /** On the free-speech setup screen, in the BEFORE YOU START block, ahead of START QUIET CHECK. Free speech only. */
    val SETUP: String =
        "FREE SPEECH RECORDS EVERYTHING THE MICROPHONE HEARS, INCLUDING ANYONE NEARBY, " +
            "FOR UP TO ${CaptureConstants.MAX_FREE_SESSION_S / 60} MINUTES. TELL THEM FIRST, OR RECORD SOMEWHERE ELSE."

    /** On the RECORD TRAINING DATA home screen, under the free-speech description. */
    const val HOME = "IT ALSO RECORDS ANYONE NEARBY."

    /** In the HELP walkthrough's free-speech step (which is written in sentence case). */
    const val HELP = "It also records anyone nearby."
}
