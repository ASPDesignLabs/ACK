// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DecimalStyle
import java.util.Locale

/**
 * SAVE USAGE SUMMARY TO A FILE: what the file holds and how it is written (docs/USAGE_SUMMARY_DESIGN.md, section 9). Plain Kotlin so every rule is tested without a phone.
 *
 * Rules that must stay true:
 *  - **Counts only.** Every value is a date, an hour, a fixed channel name, a fixed kind name or a number, so nothing in the file ever needs escaping and no word of a
 *    message can be in it. The names in the columns are the stored names (MATRIX, YES), never translated.
 *  - One line per counted cell, oldest first (date, hour, channel, kind), tab-separated, after header lines that each start with `# ` (a header translation with a line
 *    break is flattened). Only counts inside the kept window are written.
 *  - **Latin digits**, whatever the phone's language: the count and the date are written as text.
 */
object UsageSummaryFile {
    const val HEADER_MARK = "# "
    const val TAB = "\t"

    /** SAVED: ... is the saved-message-log header's own sentence, reused, so the two files say it the same way. */
    private const val SAVED_AT = "log_export_saved_at"

    private fun clock(zone: ZoneId): DateTimeFormatter =
        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss xxx", Locale.ROOT).withDecimalStyle(DecimalStyle.STANDARD).withZone(zone)

    private fun oneLine(text: String): String = text.replace(Regex("""[\r\n\u0085  ]+"""), " ")

    /** The cells that go in the file: inside the window ending [today], with a positive count, in the order they are written. */
    fun rows(counts: Map<UsageCell, Int>, today: LocalDate): List<Pair<UsageCell, Int>> {
        val cutoff = UsageTally.oldestKept(today)
        return counts.filter { (cell, n) -> cell.date >= cutoff && n > 0 }.toList()
            .sortedWith(compareBy({ it.first.date }, { it.first.hour }, { it.first.channel.ordinal }, { it.first.kind.ordinal }))
    }

    fun render(counts: Map<UsageCell, Int>, text: TextSource, zone: ZoneId, savedAtMillis: Long): String {
        val today = Instant.ofEpochMilli(savedAtMillis).atZone(zone).toLocalDate()
        val rows = rows(counts, today)
        val summary = UsageTally.summarise(counts, today)
        val out = StringBuilder()
        fun header(line: String) { out.append(HEADER_MARK).append(oneLine(line)).append('\n') }
        header(text.get(UsageSummaryText.FILE_TITLE))
        header(text.get(SAVED_AT, clock(zone).format(Instant.ofEpochMilli(savedAtMillis))))
        header(
            text.get(
                UsageSummaryText.FILE_SUMMARY,
                summary.daysWithCounts.toString(),
                summary.messages.toString(),
                summary.firstDate?.toString() ?: "-",
                summary.lastDate?.toString() ?: "-",
            )
        )
        header(text.get(UsageSummaryText.FILE_WARNING))
        header(text.get(UsageSummaryText.FILE_COLUMNS))
        for ((cell, n) in rows) {
            out.append(cell.date).append(TAB).append(cell.hour.toString().padStart(2, '0')).append(TAB)
                .append(cell.channel.name).append(TAB).append(cell.kind.name).append(TAB).append(n.toString()).append('\n')
        }
        return out.toString()
    }

    /** A name for the file the picker suggests: `ack_usage_2026-10-06_140302.txt`, in this phone's local time. */
    fun fileName(nowMillis: Long, zone: ZoneId): String =
        "ack_usage_" + DateTimeFormatter.ofPattern("yyyy-MM-dd_HHmmss", Locale.ROOT).withDecimalStyle(DecimalStyle.STANDARD).withZone(zone).format(Instant.ofEpochMilli(nowMillis)) + ".txt"
}
