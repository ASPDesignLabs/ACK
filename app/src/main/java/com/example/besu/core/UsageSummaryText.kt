// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Everything the usage summary says (docs/USAGE_SUMMARY_DESIGN.md): the SETTINGS section, the first-time question, the warning before saving, the two questions
 * before forgetting, the Terminal's quiet line and the results. Plain Kotlin (no `android.*`) so what is said is tested without a phone; the words are string
 * resources (`usage_*` in strings.xml, in the chosen language) supplied through a [TextSource]. The screens only display what is here.
 *
 * Rules that must stay true:
 *  - **It never claims more than it does.** It counts messages. It says so, says it never keeps the words, and says a saved file still shows a daily pattern.
 *  - **Turning it on asks first**, and says what is counted, what never is, where it stays, and that the Terminal shows a line while it is on.
 *  - **Forgetting asks twice** and says first to save the summary to a file (it is not in EXPORT .JSON, so that is the way to keep it).
 *  - A name of a button inside a sentence (the save button's) is an argument, not a literal. Numbers are handed in as text, so a phone set to Arabic or Hindi still
 *    shows Latin digits.
 *  - The two safety sentences about a saved file (not protected, where to save) are the EXPORT .JSON warning's own, so the warnings can never disagree.
 */
object UsageSummaryText {
    // Resource names, not words.
    const val TITLE = "usage_title"
    const val EMPTY = "usage_empty"
    const val HEAD_KIND = "usage_head_kind"
    const val HEAD_CHANNEL = "usage_head_channel"
    const val HEAD_HOURS = "usage_head_hours"
    const val SAVE_BUTTON = "usage_save_button"
    const val FORGET_BUTTON = "usage_forget_button"
    const val ON_TITLE = "usage_on_title"
    const val ON_CONFIRM = "usage_on_confirm"
    const val SAVE_NONE = "usage_save_none"
    const val SAVE_CONTAINS_HEADING = "usage_save_contains_heading"
    const val SAVE_NOT_INCLUDED = "usage_save_not_included"
    const val SAVE_PATTERN = "usage_save_pattern"
    const val SAVE_COPY_TOO = "usage_save_copy_too"
    const val SAVE_FAIL_PREPARE = "usage_save_fail_prepare"
    const val FORGET_TITLE = "usage_forget_title"
    const val FORGET_FINAL_TITLE = "usage_forget_final_title"
    const val FORGET_DELETE = "usage_forget_delete"
    const val FORGET_DONE = "usage_forget_done"
    const val FILE_TITLE = "usage_file_title"
    const val FILE_WARNING = "usage_file_warning"
    const val FILE_COLUMNS = "usage_file_columns"
    private const val EXPLANATION = "usage_explanation"
    private const val SWITCH_ON = "usage_switch_on"
    private const val SWITCH_OFF = "usage_switch_off"
    private const val TOTAL_LINE = "usage_total_line"
    private const val HEAD_DAYS = "usage_head_days"
    private const val ROW = "usage_row"
    private const val TERMINAL_LINE = "usage_terminal_line"
    private const val ON_COUNTS = "usage_on_counts"
    private const val ON_NEVER = "usage_on_never"
    private const val ON_STAYS = "usage_on_stays"
    private const val SAVE_COUNT_LINE = "usage_save_count_line"
    private const val SAVE_CAT_COUNTS = "usage_save_cat_counts"
    private const val SAVE_DONE = "usage_save_done"
    private const val SAVE_FAILED = "usage_save_failed"
    private const val FORGET_BODY = "usage_forget_body"
    private const val FORGET_FINAL_BODY = "usage_forget_final_body"
    const val FILE_SUMMARY = "usage_file_summary"

    /** The two safety sentences are the EXPORT .JSON warning's own. */
    const val NOT_PROTECTED = ExportContents.NOT_PROTECTED
    const val WHERE_TO_SAVE = ExportContents.WHERE_TO_SAVE

    /** The names of a kind and of a channel as the screen shows them. The saved file keeps the fixed names (YES, MATRIX), never these words. */
    fun kindName(text: TextSource, kind: UsageKind): String = text.get("usage_kind_${kind.name.lowercase()}")
    fun channelName(text: TextSource, channel: UsageChannel): String = text.get("usage_channel_${channel.name.lowercase()}")

    /** Every resource that names a kind or a channel, for a test that checks each exists in every language. */
    val kindResources: List<String> = UsageKind.values().map { "usage_kind_${it.name.lowercase()}" }
    val channelResources: List<String> = UsageChannel.values().map { "usage_channel_${it.name.lowercase()}" }

    fun explanation(text: TextSource): String = text.get(EXPLANATION, UsageTally.RETENTION_DAYS.toString())
    fun switchLabel(text: TextSource, on: Boolean): String = text.get(if (on) SWITCH_ON else SWITCH_OFF)
    fun totalLine(text: TextSource, messages: Long): String = text.get(TOTAL_LINE, messages.toString())
    fun headDays(text: TextSource): String = text.get(HEAD_DAYS, UsageTally.RECENT_DAYS.toString())

    /** One line of a list: a name and its count, e.g. `YES: 12`. */
    fun row(text: TextSource, label: String, count: Long): String = text.get(ROW, label, count.toString())

    /** A row's label for an hour of the day, `07:00`: digits only, whatever the phone's language. */
    fun hourLabel(hour: Int): String = hour.toString().padStart(2, '0') + ":00"

    /** The Terminal's one quiet line while the summary is on. */
    fun terminalLine(text: TextSource): String = text.get(TERMINAL_LINE)

    /** The three paragraphs of the first-time question, in the order they are read. */
    fun onQuestion(text: TextSource): List<String> =
        listOf(text.get(ON_COUNTS), text.get(ON_NEVER), text.get(ON_STAYS, UsageTally.RETENTION_DAYS.toString()))

    // --- saving -------------------------------------------------------------------------------------------------------------

    fun saveCountLine(text: TextSource, messages: Long): String = text.get(SAVE_COUNT_LINE, messages.toString())
    fun saveContains(text: TextSource): String = text.get(SAVE_CAT_COUNTS)
    fun saveDone(text: TextSource): String = text.get(SAVE_DONE)

    /** After a failed save: that it failed, why in words, and that nothing was saved. [reason] is the NAME of a reason string, never any data. */
    fun saveFailed(text: TextSource, reason: String): String = text.get(SAVE_FAILED, text.get(reason))

    /** The warning's body as plain text, in the order the screen shows it (a test reads this, and the screen draws the same lines). */
    fun saveDialogText(text: TextSource, messages: Long): String = buildString {
        appendLine(saveCountLine(text, messages))
        appendLine()
        appendLine(text.get(SAVE_CONTAINS_HEADING))
        appendLine("- ${saveContains(text)}")
        appendLine(text.get(SAVE_NOT_INCLUDED))
        appendLine(text.get(SAVE_PATTERN))
        appendLine()
        appendLine(text.get(NOT_PROTECTED))
        appendLine(text.get(SAVE_COPY_TOO))
        appendLine()
        append(text.get(WHERE_TO_SAVE))
    }

    // --- forgetting ---------------------------------------------------------------------------------------------------------

    /** The first question. [saveButtonName] is SAVE USAGE SUMMARY TO A FILE as the screen shows it. */
    fun forgetFirst(text: TextSource, saveButtonName: String): String = text.get(FORGET_BODY, saveButtonName)

    /** The last question: what exactly will be deleted. */
    fun forgetFinal(text: TextSource, messages: Long): String = text.get(FORGET_FINAL_BODY, messages.toString(), UsageTally.RETENTION_DAYS.toString())
}
