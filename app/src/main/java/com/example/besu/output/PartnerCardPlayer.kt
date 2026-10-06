// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.output

import android.content.Context
import android.content.Intent
import com.example.besu.core.ActiveScript
import com.example.besu.core.PartnerCard
import com.example.besu.core.PartnerCardSettings
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
 *    core/HelpWalkthroughText.kt); otherwise the English card. The question that asks first shows the same words ([rows]); the person's own sentences are said as written, in no language of ours.
 *  - **What is said is the person's choice**: the sentences that are on in [PartnerCardSettings] (their own included, exactly as written). It reads no storage and writes none: the choice is
 *    passed in, so what the question showed is what is played.
 */
object PartnerCardPlayer {
    private fun words(context: Context): ResourceText {
        val translated = PartnerCard.speaksInterfaceLanguage(AssistPrefs.speechLanguage(context), ActiveScript.tag, Locale.getDefault().language)
        return ResourceText(if (translated) context else EnglishResources.context(context))
    }

    /** All seven sentences as they will be said now, with the person's choice, for the question that asks first. */
    fun rows(context: Context, settings: PartnerCardSettings): List<PartnerCard.Row> = PartnerCard.rows(words(context), settings)

    /**
     * Sends the card now: the sentences that are on, as one message. Called only from the question's PLAY IT button. Says nothing and sends nothing when no sentence is on (the question does not
     * offer PLAY IT then, so this is only a second guard).
     */
    fun play(context: Context, settings: PartnerCardSettings) {
        val message = PartnerCard.message(words(context), settings)
        if (message.isEmpty()) return
        val intent = Intent(context, OutputService::class.java).apply {
            putExtra("phrase", message)
            putExtra("robotic", false)
            putExtra("source", PartnerCard.SOURCE)
            putExtra("full_text", true)
        }
        context.startService(intent)
    }
}
