// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

/**
 * What RECORD FREE SPEECH says about other people. It records everything the microphone hears, so anyone nearby is recorded too.
 *
 * The two sentences the capture screens show (the setup screen's paragraph and the home screen's line) are string resources in the chosen language
 * (`capture_free_notice_setup`, `capture_free_notice_home`; core/CaptureText.freeNoticeSetup). They are text only, by design: the capture screens make no sound
 * and no vibration while the microphone is open (a buzz would land in the recording), so this is never a dialog, a toast or a standard button. The minutes in the
 * setup sentence come from [CaptureConstants.MAX_FREE_SESSION_S], so the notice cannot say a limit the engine does not enforce.
 *
 * Only the HELP walkthrough's sentence is still a constant here, because the walkthroughs' own text is English (and written in sentence case).
 */
object FreeSpeechNotice {
    /**
     * The English of the last sentence of the HELP walkthrough's free-speech step (written in sentence case). The step itself is a string resource now (`helpmod_record_training_data_free_body`);
     * FreeSpeechNoticeTest holds the English step to end with this sentence and every translation to end with the home screen's own notice.
     */
    const val HELP = "It also records anyone nearby."
}
