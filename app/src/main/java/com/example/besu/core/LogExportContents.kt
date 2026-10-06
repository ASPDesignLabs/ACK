// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What SAVE MESSAGE LOG TO A FILE tells the person before it saves anything, and what it says afterwards. Plain Kotlin (no `android.*`) so what is said is tested
 * without a phone; the words are string resources (`log_export_*` in strings.xml, in the chosen language) supplied through a [TextSource]. The screen
 * (settings/LogExportDialog.kt) only displays what is here, in the same way as the EXPORT .JSON warning (core/ExportContents.kt), whose two safety sentences
 * (not protected, where to save) it reuses word for word so the two warnings can never disagree.
 *
 * Rules that must stay true:
 *  - **It warns first and saves nothing until the person has chosen where.** Cancelling opens no picker.
 *  - **It says plainly what is in the file**, including that a message's own words are in it (names, addresses, numbers, if they were said), and what is not.
 *  - **It says the file is not protected**, and that a screenshot or photo of the log is a copy too.
 *  - A name of a screen or button inside a sentence (the log's own name) is an argument, not a literal, so it follows PLAIN WORDS and the language.
 *  - Numbers are handed in as text, so a phone set to Arabic or Hindi still shows Latin digits.
 */
object LogExportContents {
    // Resource names, not words.
    const val BUTTON = "log_export_button"
    const val CONTAINS_HEADING = "log_export_contains_heading"
    const val COPY_TOO = "log_export_copy_too"
    const val NOT_INCLUDED = "log_export_not_included"
    const val NONE_NOW = "log_export_none"
    const val DONE = "log_export_done"
    const val FAIL_PREPARE = "log_export_fail_prepare"
    private const val BUTTON_DESC = "log_export_button_desc"
    private const val CAT_MESSAGES = "log_export_cat_messages"
    private const val CAT_NAMES = "log_export_cat_names"
    private const val COUNT_LINE = "log_export_count_line"
    private const val FAILED = "log_export_failed"

    /** The two safety sentences are the EXPORT .JSON warning's own, so the two never differ. */
    const val NOT_PROTECTED = ExportContents.NOT_PROTECTED
    const val WHERE_TO_SAVE = ExportContents.WHERE_TO_SAVE

    /** What the line under the SETTINGS button says. [logName] is the Terminal log's name as the screen shows it (it follows PLAIN WORDS). */
    fun buttonDescription(text: TextSource, logName: String): String = text.get(BUTTON_DESC, logName)

    /** The bullets of "the file will contain", in the order they are read. */
    fun contains(text: TextSource, logName: String): List<String> = listOf(text.get(CAT_MESSAGES, logName), text.get(CAT_NAMES))

    /** How many messages the file would hold right now. */
    fun countLine(text: TextSource, count: Int): String = text.get(COUNT_LINE, count.toString())

    /** What the toast and the Terminal say after a good save. */
    fun doneText(text: TextSource): String = text.get(DONE)

    /** After a failed one: that it failed, why in words, and that nothing was saved. [reason] is the NAME of a reason string, never any of the person's data. */
    fun failedText(text: TextSource, reason: String): String = text.get(FAILED, text.get(reason))

    /** The warning dialog's body as plain text, in the order the screen shows it (a test reads this, and the screen draws the same lines). */
    fun dialogText(text: TextSource, logName: String, count: Int): String = buildString {
        appendLine(countLine(text, count))
        appendLine()
        appendLine(text.get(CONTAINS_HEADING))
        contains(text, logName).forEach { appendLine("- $it") }
        appendLine(text.get(NOT_INCLUDED))
        appendLine()
        appendLine(text.get(NOT_PROTECTED))
        appendLine(text.get(COPY_TOO))
        appendLine()
        append(text.get(WHERE_TO_SAVE))
    }
}
