// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.IllformedLocaleException
import java.util.Locale

/**
 * The safety copies ACK makes before a one-time data upgrade (files in `auto_backups`), and what DATA PORT says about them. A
 * copy holds the same data as an export, with the voice recordings and the Emergency card, and is not encrypted, so the person is
 * told it exists and can delete it. Plain Kotlin (no `android.*`) so the rules are tested without a phone; the words are string resources
 * (`safety_copy_*`), read through a [TextSource]; the screens only show them.
 */
object SafetyCopyPolicy {
    // Files are named "<label>_<epoch ms>.json" by TransferManager.writeInternalSnapshot. 12+ digits is a time in milliseconds
    // (11 digits ends in 1973), which keeps an unrelated number in a name from being read as a date.
    private val STAMP = Regex("_(\\d{12,})\\.json$")

    /** When a copy was made: the time in its name, else the file's own last-modified time. */
    fun createdAtMs(fileName: String, lastModifiedMs: Long): Long =
        STAMP.find(fileName)?.groupValues?.get(1)?.toLongOrNull()?.takeIf { it > 0L } ?: lastModifiedMs

    /** Whether an export was saved after the copy was made. [lastBackupAtMs] is null if none ever was. Strictly newer. */
    fun hasNewerExport(lastBackupAtMs: Long?, copyCreatedAtMs: Long): Boolean =
        lastBackupAtMs != null && lastBackupAtMs > copyCreatedAtMs

    /**
     * "21 SEP 2026": the day, the language's short month and the year, in capitals like the rest of the app. The zone is a parameter so the test does not
     * depend on the machine it runs on, and the language is the words' own ([TextSource.languageTag]). Digits are always the Latin ones, like every other number
     * DELETE DATA shows: `DateTimeFormatter.ofPattern` uses java.time's standard decimal style whatever numbering the locale asks for (only `localizedBy` would
     * follow it), and a test pins that. A tag Java cannot read gives English rather than a crash.
     */
    fun dateText(text: TextSource, ms: Long, zone: ZoneId): String {
        val locale = try {
            Locale.Builder().setLanguageTag(text.languageTag).build()
        } catch (e: IllformedLocaleException) {
            Locale.ENGLISH
        }
        return DateTimeFormatter.ofPattern("d MMM yyyy", locale).withZone(zone).format(Instant.ofEpochMilli(ms)).uppercase(locale)
    }

    private const val ROW = "safety_copy_row"
    private const val FIRST = "safety_copy_first"
    private const val NEWER_EXPORT = "safety_copy_newer_export"
    private const val NO_NEWER_EXPORT = "safety_copy_no_newer_export"
    private const val DELETE_ANYWAY = "safety_copy_delete_anyway"
    private const val CONTINUE = "common_continue"

    fun rowText(text: TextSource, dateText: String, sizeText: String): String = text.get(ROW, dateText, sizeText)

    /** Only when no export has been saved since the copy was made: then an export is the way to keep something you control. */
    fun offersExportFirst(hasNewerExport: Boolean): Boolean = !hasNewerExport

    /** The first confirmation's forward button: it says plainly when it is going ahead without a newer export. */
    fun proceedLabel(text: TextSource, hasNewerExport: Boolean): String = text.get(if (hasNewerExport) CONTINUE else DELETE_ANYWAY)

    fun firstConfirmation(text: TextSource, dateText: String, sizeText: String, hasNewerExport: Boolean): List<String> = listOf(
        text.get(FIRST, dateText, sizeText),
        text.get(if (hasNewerExport) NEWER_EXPORT else NO_NEWER_EXPORT),
        text.get(StorageCatalogue.NOT_ELSEWHERE),
    )
}
