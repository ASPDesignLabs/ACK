// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.output

import android.content.Context
import android.content.Intent
import com.example.besu.core.ActiveScript
import com.example.besu.core.PartnerCard
import com.example.besu.data.AssistPrefs
import com.example.besu.data.EnglishResources
import com.example.besu.data.ResourceText
import java.util.Locale

/**
 * Sends the partner card (core/PartnerCard.kt) the way any message is sent: an intent to [OutputService] on the **normal** path. So it is spoken and shown like any message,
 * follows the person's audio routing, is silent when silent output is on, and appears in the Terminal log as a normal message.
 *
 * Rules that must stay true (PartnerCardWiringTest holds them):
 *  - **Never the Emergency path.** No `emergency_mode` extra is ever set: Emergency always speaks on the phone and ignores silent output, and the card must obey both.
 *  - **Not tutorial narration** (`robotic` false), so it is logged, counted by the usage summary if that is on, and replayable like a message.
 *  - **`full_text`**: the whole card is shown on screen whatever the display preset says, so it is never cut to a few words while it is spoken in full.
 *  - **Spoken and shown in the language the voice speaks**: the translated card only when SPEECH LANGUAGE follows the phone and the screens are in the phone's language (the HELP rule,
 *    core/HelpWalkthroughText.kt); otherwise the English card. The dialog that asks first shows the same words ([lines]).
 *  - It reads no storage and writes none.
 */
object PartnerCardPlayer {
    private fun words(context: Context): ResourceText {
        val translated = PartnerCard.speaksInterfaceLanguage(AssistPrefs.speechLanguage(context), ActiveScript.tag, Locale.getDefault().language)
        return ResourceText(if (translated) context else EnglishResources.context(context))
    }

    /** The card's sentences as they will be spoken, for the question that asks first. */
    fun lines(context: Context): List<String> = PartnerCard.lines(words(context))

    /** Sends the card now. Called only from the question's PLAY IT button. */
    fun play(context: Context) {
        val intent = Intent(context, OutputService::class.java).apply {
            putExtra("phrase", PartnerCard.message(words(context)))
            putExtra("robotic", false)
            putExtra("source", PartnerCard.SOURCE)
            putExtra("full_text", true)
        }
        context.startService(intent)
    }
}
