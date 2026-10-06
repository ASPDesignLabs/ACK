// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words around WORD SUGGESTIONS (SETTINGS, FORGET WORDS and the one-time offer in the Statement Composer), read through a [TextSource] so they are in the
 * chosen language. What is decided here is which sentence is said and how they are put together; a test holds the English to what the feature really does. The
 * names of buttons and screens a sentence points to (EXPORT .JSON, TARGET COMPUTER, FORGET WORDS) are passed in as arguments, so a sentence and the button it
 * names cannot read differently. The two sentences DELETE DATA also says are read from the same resources (`storage_cannot_undo`, `storage_not_elsewhere`),
 * so they cannot differ.
 */
object WordSuggestionText {
    const val SWITCH_ON = "words_switch_on"
    const val SWITCH_OFF = "words_switch_off"
    const val FORGET_BUTTON = "words_forget_button"
    const val TARGET_COMPUTER_LABEL = "label_target_computer"

    private const val EXPLAIN_WHEN_ON = "words_explain_when_on"
    private const val EXPLAIN_TAP = "words_explain_tap"
    private const val EXPLAIN_LEARNS = "words_explain_learns"
    private const val EXPLAIN_NEVER = "words_explain_never"
    private const val EXPLAIN_KEPT = "words_explain_kept"
    private const val COUNT_NONE = "words_count_none"
    private const val COUNT = "words_count"
    private const val USED = "words_used"
    private const val FORGET_REMOVES = "words_forget_removes"
    private const val FORGET_SAVED = "words_forget_saved"
    private const val FORGET_NAMES = "words_forget_names"
    private const val FORGET_STAYS = "words_forget_stays"

    /** ON or OFF said in words, not only by colour. */
    fun switchLabel(text: TextSource, on: Boolean): String = text.get(if (on) SWITCH_ON else SWITCH_OFF)

    /** What it offers, that nothing is added without a tap, what it learns from and never learns from, and where the words are kept: five sentences, joined here. */
    fun explanation(text: TextSource): String = listOf(
        text.get(EXPLAIN_WHEN_ON),
        text.get(EXPLAIN_TAP),
        text.get(EXPLAIN_LEARNS, text.get(TARGET_COMPUTER_LABEL)),
        text.get(EXPLAIN_NEVER),
        text.get(EXPLAIN_KEPT, text.get(StorageCatalogue.EXPORT_JSON_LABEL), text.get(FORGET_BUTTON)),
    ).joinToString(" ")

    // ---- FORGET WORDS (SETTINGS) ----------------------------------------------------------------------------------------------

    fun countLine(text: TextSource, count: Int): String = if (count <= 0) text.get(COUNT_NONE) else text.get(COUNT, count)

    /** How often a word was used; the word for "time" has the forms each language needs. */
    fun usedLine(text: TextSource, times: Int): String = text.count(USED, times)

    /** Asking about all of them: says what is removed (with the count), the backup first, what is not touched, and what stays as it is. Five sentences, shown one after another. */
    fun forgetAllFirstConfirmation(text: TextSource, count: Int): List<String> = listOf(
        text.count(FORGET_REMOVES, count),
        text.get(FORGET_SAVED, text.get(StorageCatalogue.EXPORT_JSON_LABEL)),
        text.get(FORGET_NAMES, text.get(TARGET_COMPUTER_LABEL)),
        text.get(FORGET_STAYS),
        notElsewhere(text),
    )

    /** The second confirmation: the same sentence DELETE DATA says. */
    fun forgetAllSecond(text: TextSource): String = text.get(StorageCatalogue.CANNOT_UNDO)

    /** Files saved elsewhere are not deleted: the same sentence DELETE DATA says. */
    fun notElsewhere(text: TextSource): String = text.get(StorageCatalogue.NOT_ELSEWHERE)
}
