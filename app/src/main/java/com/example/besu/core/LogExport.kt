// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DecimalStyle
import java.util.Locale

/** One entry of the Terminal log as the exporter sees it: a plain copy of data/TerminalLogStore.LogEntry, so core/ stays free of Android classes. */
data class LogLine(val epochMillis: Long, val type: String, val msg: String, val replayText: String?)

/** One message as it goes into the file. [from] is where it was sent from (a deck, the watch, the Terminal), as the log wrote it. */
data class LoggedMessage(val epochMillis: Long, val type: String, val from: String, val text: String)

/**
 * SAVE MESSAGE LOG TO A FILE (tracker row C2): what goes into the file and how it is written. Plain Kotlin (no `android.*`) so every rule is tested without a
 * phone. The words of the header are string resources (`log_export_*`) supplied through a [TextSource]; the warning shown before saving is core/LogExportContents.kt.
 *
 * Rules that must stay true:
 *  - **Messages only** (the developer's choice): a line is a message when it is an OUT or EMERGENCY line **and** carries replay text, which only a real
 *    communicated phrase does (OutputService). System lines, path-trace lines, command replies and tutorial narration are never written, because they can mention
 *    places, contacts and settings. What a message itself says is written in full: that is the point, and the warning says so.
 *  - **Only what the log still keeps.** A message older than the person's retention window is left out even if the live buffer has not been pruned yet.
 *  - **A message can never forge a record.** Every line break, tab and backslash in a message (and in its source) is escaped, so the file is one record per line and
 *    the four columns are separated by tabs only. Any other control character is written as \uXXXX.
 *  - **Latin digits, an explicit UTC offset on every line.** The time is this phone's local time, written with its offset so a change of time zone or daylight saving
 *    cannot make two lines ambiguous, whatever language or digits the phone uses.
 *  - **Nothing is logged about what was said**, by this file or by the code that writes it.
 */
object LogExport {
    const val TYPE_OUT = "OUT"
    const val TYPE_EMERGENCY = "EMERGENCY"

    /** Where a message typed at the Terminal prompt came from; a modifier it carried ([Q] quiet, [S] sticky, [E] emergency) is added after it. */
    const val FROM_TERMINAL = "TERMINAL"

    /** Where a line came from when the log did not say. */
    const val FROM_UNKNOWN = "UNKNOWN"

    /** The Terminal log's own rolling window, in milliseconds per day (data/TerminalLogStore keeps entries no older than the retention setting). */
    const val DAY_MILLIS = 24L * 60L * 60L * 1000L

    // Resource names, not words.
    const val FILE_TITLE = "log_export_file_title"
    const val FILE_WARNING = "log_export_file_warning"
    const val ESCAPES = "log_export_escapes"
    const val COLUMNS = "log_export_columns"
    private const val SAVED_AT = "log_export_saved_at"
    private const val SUMMARY = "log_export_summary"

    /** The marker at the start of every header line. A message line starts with a digit, never with this. */
    const val HEADER_MARK = "# "
    const val TAB = "\t"

    /** What the first or last time reads as when there are no messages. */
    private const val NONE = "-"

    private val promptFlags = Regex("""^\$ ((?:\[[QSE]\])*) """)

    /** A message is an OUT or EMERGENCY line that carries replay text. Nothing else is ever exported. */
    fun isMessage(line: LogLine): Boolean = (line.type == TYPE_OUT || line.type == TYPE_EMERGENCY) && line.replayText != null

    /**
     * Where a message was sent from, read from the log line's own text: the deck or channel tag the log wrote before ` > "` (`MTX/IDENTITY`, `QUICK_ACTION`,
     * `HW/WATCH`), or [FROM_TERMINAL] (with any modifier tags) for a line typed at the Terminal prompt, which the log writes as `$ ` and the phrase. This is only a
     * label: the message's words always come from the line's replay text, never from here.
     */
    fun fromOf(msg: String): String {
        if (msg.startsWith("\$ ")) {
            val flags = promptFlags.find(msg)?.groupValues?.get(1).orEmpty()
            return if (flags.isEmpty()) FROM_TERMINAL else "$FROM_TERMINAL $flags"
        }
        val at = msg.indexOf(" > \"")
        return if (at > 0) msg.substring(0, at) else FROM_UNKNOWN
    }

    /** The oldest time a message may have and still be kept, for a retention window of [retentionDays] ending at [nowMillis]. A message exactly on it is kept. */
    fun keptSince(nowMillis: Long, retentionDays: Int): Long = nowMillis - retentionDays * DAY_MILLIS

    /**
     * The messages to write, oldest first. [lines] are in the order the Terminal keeps them, **newest first**, so equal times keep the order the messages were
     * written. A message older than [notBeforeMillis] is left out.
     */
    fun messages(lines: List<LogLine>, notBeforeMillis: Long = Long.MIN_VALUE): List<LoggedMessage> =
        lines.asReversed()
            .filter { isMessage(it) && it.epochMillis >= notBeforeMillis }
            .map { LoggedMessage(it.epochMillis, it.type, fromOf(it.msg), it.replayText ?: "") }
            .sortedBy { it.epochMillis }

    /**
     * One field made safe for a line of tab-separated text. A line break (CRLF, LF, CR, NEL, LS or PS) becomes `\n`, a tab `\t`, a backslash `\\`, and any other
     * control character `\uXXXX`. Everything else, an emoji or Arabic included, is kept exactly.
     */
    fun escape(field: String): String {
        val out = StringBuilder(field.length + 8)
        var i = 0
        while (i < field.length) {
            val c = field[i]
            when {
                c == '\r' && i + 1 < field.length && field[i + 1] == '\n' -> { out.append("\\n"); i++ }
                c == '\n' || c == '\r' || c == '\u0085' || c == ' ' || c == ' ' -> out.append("\\n")
                c == '\t' -> out.append("\\t")
                c == '\\' -> out.append("\\\\")
                c < ' ' || c == '\u007f' -> out.append("\\u").append(String.format(Locale.ROOT, "%04x", c.code))
                else -> out.append(c)
            }
            i++
        }
        return out.toString()
    }

    /** A header sentence made safe: a line break in a translation must not start a line that is not a header line. */
    private fun oneLine(text: String): String = text.replace(Regex("""[\r\n\u0085  ]+"""), " ")

    private fun clock(zone: ZoneId): DateTimeFormatter =
        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss xxx", Locale.ROOT).withDecimalStyle(DecimalStyle.STANDARD).withZone(zone)

    /** The text of the file: a header (each line starts with [HEADER_MARK]), then one line per message, oldest first, each ending with a line break. */
    fun render(messages: List<LoggedMessage>, text: TextSource, zone: ZoneId, savedAtMillis: Long): String {
        val time = clock(zone)
        fun at(millis: Long) = time.format(Instant.ofEpochMilli(millis))
        val first = messages.firstOrNull()?.let { at(it.epochMillis) } ?: NONE
        val last = messages.lastOrNull()?.let { at(it.epochMillis) } ?: NONE
        val out = StringBuilder()
        fun header(line: String) { out.append(HEADER_MARK).append(oneLine(line)).append('\n') }
        header(text.get(FILE_TITLE))
        header(text.get(SAVED_AT, at(savedAtMillis)))
        // The count goes in as text, not as a number, so a phone set to Arabic or Hindi still writes Latin digits.
        header(text.get(SUMMARY, messages.size.toString(), first, last))
        header(text.get(FILE_WARNING))
        header(text.get(ESCAPES))
        header(text.get(COLUMNS))
        for (m in messages) {
            out.append(at(m.epochMillis)).append(TAB).append(m.type).append(TAB).append(escape(m.from)).append(TAB).append(escape(m.text)).append('\n')
        }
        return out.toString()
    }

    /** A name for the file the picker suggests, with the time it was made in this phone's local time: `ack_messages_2026-10-06_140302.txt`. */
    fun fileName(nowMillis: Long, zone: ZoneId): String =
        "ack_messages_" + DateTimeFormatter.ofPattern("yyyy-MM-dd_HHmmss", Locale.ROOT).withDecimalStyle(DecimalStyle.STANDARD).withZone(zone).format(Instant.ofEpochMilli(nowMillis)) + ".txt"
}
