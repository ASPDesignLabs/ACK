// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The partner card (tracker row C3, docs/PARTNER_CARD.md): a short message, in the person's own voice, that tells someone talking with them how they talk. A tap on the
 * header icon asks first, then sends it through ACK's **normal** output path: it is spoken and shown like any message, follows the person's audio routing, and is silent when
 * silent output is on. Plain Kotlin (no `android.*`) so what it says and how it is chosen are tested without a phone; the words are string resources (`partner_card_*`).
 *
 * Rules that must stay true:
 *  - **The wording is the developer's choice, and a draft for a speech-language pathologist.** The five sentences below are first person, plain words, and make no clinical
 *    claim. A sentence is only true for some people ("I can hear you"), so the developer picked them; do not reword them, add one or fold a clinical suggestion in without asking.
 *  - **It is never an Emergency message.** The Emergency path always speaks on the phone and ignores silent output; the card must obey both (the developer's rule), so it is
 *    sent with no emergency flag. A test fails if the card's code sets one.
 *  - **What is said is what is shown.** The card is one message; the dialog that asks first shows the same words.
 */
object PartnerCard {
    /** The tag the card's message carries (OutputService's `source`); the Terminal log, the saved log and the usage summary read it. */
    const val SOURCE = "PARTNER/CARD"

    /** The feature's name: the header icon's description starts with it, and the usage summary names the card as a place. */
    const val NAME = "partner_card_name"

    /** What a screen reader says for the header icon (it has no text of its own). */
    const val ICON_DESCRIPTION = "partner_card_icon"

    const val ASK_TITLE = "partner_card_ask_title"
    const val ASK_INTRO = "partner_card_ask_intro"

    /** Takes the silent-mode button's name (`%1$s`), so it follows PLAIN WORDS. */
    const val ASK_SILENT = "partner_card_ask_silent"
    const val ASK_PLAY = "partner_card_ask_play"

    /** The five sentences, in order. */
    val SENTENCES: List<String> = listOf("partner_card_1", "partner_card_2", "partner_card_3", "partner_card_4", "partner_card_5")

    /** The sentences as the words of [text] give them, one per line, for the dialog. */
    fun lines(text: TextSource): List<String> = SENTENCES.map { text.get(it) }

    /** The card as one message: the five sentences with a space between. This is what is spoken, shown on the screen and written to the Terminal log. */
    fun message(text: TextSource): String = lines(text).joinToString(" ")

    /**
     * Whether the translated card may be spoken: the same rule as the HELP walkthrough's spoken guide, so a voice is never asked to read a language it is not set to speak.
     * Only when SPEECH LANGUAGE follows the phone **and** the screens are in the phone's own language; every other case says (and shows) the English card.
     */
    fun speaksInterfaceLanguage(speech: SpeechLanguage, interfaceTag: String, deviceLanguage: String): Boolean =
        HelpWalkthroughText.speaksInterfaceLanguage(speech, interfaceTag, deviceLanguage)
}
