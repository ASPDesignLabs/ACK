// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the Terminal says in its own voice that is decided, not just drawn: the /help list, the replies to typed commands, and the small counts and lines on the STATUSBOX.
 * Plain Kotlin (no `android.*`) so it is tested without a phone; the words are string resources (`term_*`, in the chosen language) read through a [TextSource].
 *
 * **Typed commands are logic and are never translated.** `/help /q /n /s /e /v /t /cls /backup /repair /info /m` and the word CONFIRM in "/cls CONFIRM" stay exactly as typed, inside every
 * translated sentence; [HELP_COMMANDS] holds the commands as typed and the resource that says what each does. A command the person typed that is not known is echoed exactly as typed.
 * Lines other parts of ACK write into the Terminal (the output service, the watch, Geo, the path trace) arrive as English text through the `ACK_LOG` broadcast and are not part of this file.
 */
object TerminalText {
    /** The command column of /help is this wide (the command, then spaces), so every description starts in the same column in a monospace font. */
    const val HELP_COMMAND_WIDTH = 17

    /** Each command exactly as it is typed (never translated), beside the string resource that says what it does. The order is the order /help shows. */
    val HELP_COMMANDS: List<Pair<String, String>> = listOf(
        "/help, /?" to "term_help_help",
        "/q, /quiet" to "term_help_quiet",
        "/n, /nosave" to "term_help_nosave",
        "/s, /sticky" to "term_help_sticky",
        "/e, /emergency" to "term_help_emergency",
        "/v" to "term_help_variables",
        "/t" to "term_help_targets",
        "/cls" to "term_help_cls",
        "/b, /backup" to "term_help_backup",
        "/repair" to "term_help_repair",
        "/info" to "term_help_info",
        "/m" to "term_help_manual",
    )

    /** The /help list: a heading, then one line per command (the command padded to [HELP_COMMAND_WIDTH], then what it does). One entry per line, in the order above. */
    fun helpLines(text: TextSource): List<String> =
        listOf(text.get("term_help_header")) + HELP_COMMANDS.map { (command, resource) -> command.padEnd(HELP_COMMAND_WIDTH) + text.get(resource) }

    /** What /cls says before it will clear the log: the question and its warning, then how to proceed (`/cls CONFIRM`, typed as it is), on two lines. */
    fun clearConfirmation(text: TextSource): String = text.get("term_cls_question") + "\n" + text.get("term_cls_type")

    /** The reply to a slash command that is not known. [token] is what the person typed, exactly as typed. */
    fun unknownCommand(text: TextSource, token: String): String = text.get("term_unknown_command", token)

    /** The warning when /e is typed and the active deck is not an Emergency deck. The labels follow PLAIN WORDS (the deck type, then DECK). */
    fun noEmergencyDeck(text: TextSource, emergencyLabel: String, deckLabel: String): String = text.get("term_no_emergency_deck", emergencyLabel, deckLabel)

    /** "12 CHARS" under the TYPING strip, in the language's plural form for that number. */
    fun charCount(text: TextSource, count: Int): String = text.count("term_chars", count)

    /** A variable picker chip: the tag, a colon, then the value, or the language's word for EMPTY when there is none. */
    fun variableChip(text: TextSource, tag: String, value: String, hasValue: Boolean): String = "$tag:" + if (hasValue) value else text.get("common_empty")

    /** The note under a line being saved to a memory bank when it is already there: the tags it is saved under, as they were typed, joined by commas. */
    fun alreadySaved(text: TextSource, tags: List<String>): String = text.get("term_already_saved", tags.joinToString(", "))
}
