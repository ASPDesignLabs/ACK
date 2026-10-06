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
 *  - **The person chooses what the card says, each time.** Every sentence has its own ON/OFF in the question that asks first (the choice is remembered, and the question always shows it), so the
 *    whole paragraph is not recited when one sentence will do. There are also [OWN_SLOTS] slots for a sentence of the person's own. Those are their words, said and shown exactly as written (only
 *    tidied: one line, no control characters, at most [MAX_OWN_LENGTH] characters, and a full stop added when there is no sentence ending, so the voice pauses), never translated, and never
 *    anything a clinician or this code wrote for them. The card says nothing when every sentence is off.
 *  - **One play is one message, and its usage kind is PARTNER_CARD** (core/UsageKinds.kt: the kind comes from the tag, never from the wording), however many sentences were on.
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

    /** The card as one message: the five sentences with a space between. With nothing chosen this is what the card says; see [message] with settings for the person's choice. */
    fun message(text: TextSource): String = lines(text).joinToString(" ")

    /** The built-in sentences are slots 0 to 4; the person's own are slots 5 and 6. */
    const val BUILT_IN_COUNT = 5

    /** How many sentences of their own the person can write: one or two (the developer's choice). */
    const val OWN_SLOTS = 2

    const val SLOT_COUNT = BUILT_IN_COUNT + OWN_SLOTS

    /**
     * The longest own sentence, in characters. A card sentence is read at a glance and spoken in a breath, and the whole card is shown on one screen; this is far above a sentence and well
     * below the backup's 2000-character phrase ceiling (the backup's check uses this constant, so it can never reject what the screen allows).
     */
    const val MAX_OWN_LENGTH = 200

    /** The usage summary's name for the card, and the words its sentence rows share. */
    const val OWN_LABEL = "partner_card_own_label"
    const val OWN_EMPTY = "partner_card_own_empty"
    const val WRITE = "partner_card_write"
    const val EDIT = "partner_card_edit"
    const val NONE_ON = "partner_card_none_on"
    const val EDIT_HINT = "partner_card_edit_hint"
    const val EDIT_PLACEHOLDER = "partner_card_edit_placeholder"
    const val CLEAR = "partner_card_clear"
    const val CLEAR_TITLE = "partner_card_clear_title"
    const val CLEAR_BODY = "partner_card_clear_body"
    const val CLEAR_CONFIRM = "partner_card_clear_confirm"

    /**
     * One own sentence as it is kept: line breaks and runs of spaces become one space, control characters go, the ends are trimmed, and it is cut to [MAX_OWN_LENGTH] without splitting a
     * character that takes two code units (an emoji). Nothing else is changed: the words are the person's own.
     */
    fun cleanOwn(raw: String): String {
        val out = StringBuilder()
        var gap = false
        var i = 0
        while (i < raw.length) {
            val cp = raw.codePointAt(i)
            i += Character.charCount(cp)
            when {
                // U+0085 (next line) is a control character Java does not call white space, but it is a line break like any other: it must separate words, not join them.
                Character.isWhitespace(cp) || Character.isSpaceChar(cp) || cp == 0x85 -> gap = true
                Character.getType(cp) == Character.CONTROL.toInt() -> Unit
                else -> {
                    if (gap && out.isNotEmpty()) out.append(' ')
                    gap = false
                    out.appendCodePoint(cp)
                }
            }
        }
        var cut = out.toString()
        if (cut.length > MAX_OWN_LENGTH) {
            var end = MAX_OWN_LENGTH
            if (Character.isHighSurrogate(cut[end - 1])) end -= 1
            cut = cut.substring(0, end).trimEnd(' ')
        }
        return cut
    }

    /** What the text box keeps while the person types: no more than [MAX_OWN_LENGTH] characters, never ending on half of an emoji. Nothing else is changed until SAVE. */
    fun limitDraft(raw: String): String {
        if (raw.length <= MAX_OWN_LENGTH) return raw
        val end = if (Character.isHighSurrogate(raw[MAX_OWN_LENGTH - 1])) MAX_OWN_LENGTH - 1 else MAX_OWN_LENGTH
        return raw.substring(0, end)
    }

    /** Said when a choice or a sentence could not be saved: nothing was changed. */
    const val SAVE_FAILED = "partner_card_save_failed"

    private const val SENTENCE_ENDINGS = ".!?\u2026\u3002\uFF01\uFF1F\u0964\u0965\u061F\u06D4"
    private const val CLOSERS = "\"'\u201D\u2019)]\u00BB"

    /**
     * A sentence the voice can end: as written when it already ends in a full stop, a question or exclamation mark, an ellipsis, a danda or an Arabic full stop or question mark (a closing quote
     * or bracket after it does not matter), otherwise with a full stop added. Without one the engine would run an own sentence straight into the next one.
     */
    fun terminated(sentence: String): String {
        if (sentence.isEmpty()) return sentence
        val core = sentence.trimEnd { it in CLOSERS }
        return if (core.isNotEmpty() && core.last() in SENTENCE_ENDINGS) sentence else "$sentence."
    }

    /** One sentence of the question: its slot, its words as they will be said, whether it is the person's own, whether anything is written, and whether it is on. */
    class Row(val slot: Int, val text: String, val own: Boolean, val written: Boolean, val on: Boolean)

    /** All seven sentences, in order, for the question that asks first. An own slot with nothing written has empty [Row.text] and is never on. */
    fun rows(text: TextSource, settings: PartnerCardSettings): List<Row> =
        SENTENCES.mapIndexed { slot, name -> Row(slot, text.get(name), own = false, written = true, on = settings.isOn(slot)) } +
            (0 until OWN_SLOTS).map { n ->
                val written = settings.own[n]
                Row(BUILT_IN_COUNT + n, terminated(written), own = true, written = written.isNotEmpty(), on = settings.isOn(BUILT_IN_COUNT + n))
            }

    /** The sentences that are on, in order, as they will be said. Empty when none is. */
    fun spoken(text: TextSource, settings: PartnerCardSettings): List<String> = rows(text, settings).filter { it.written && it.on }.map { it.text }

    /** What the card says now: the sentences that are on with a space between. Empty when none is (the card then plays nothing). This is spoken, shown and written to the Terminal log. */
    fun message(text: TextSource, settings: PartnerCardSettings): String = spoken(text, settings).joinToString(" ")

    /**
     * Whether the translated card may be spoken: the same rule as the HELP walkthrough's spoken guide, so a voice is never asked to read a language it is not set to speak.
     * Only when SPEECH LANGUAGE follows the phone **and** the screens are in the phone's own language; every other case says (and shows) the English card.
     */
    fun speaksInterfaceLanguage(speech: SpeechLanguage, interfaceTag: String, deviceLanguage: String): Boolean =
        HelpWalkthroughText.speaksInterfaceLanguage(speech, interfaceTag, deviceLanguage)
}
