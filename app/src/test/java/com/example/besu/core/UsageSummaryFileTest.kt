// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZoneOffset
import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The saved usage summary (core/UsageSummaryFile.kt): counts only, one line per cell, header lines marked, Latin digits. */
class UsageSummaryFileTest {

    private val berlin = ZoneId.of("Europe/Berlin")
    private fun millis(iso: String) = Instant.parse(iso).toEpochMilli()
    private fun cell(date: String, hour: Int, channel: UsageChannel, kind: UsageKind) = UsageCell(LocalDate.parse(date), hour, channel, kind)

    @Test
    fun theFileIsExactlyThisInEnglish() {
        val counts = mapOf(
            cell("2026-10-06", 14, UsageChannel.MATRIX, UsageKind.YES) to 3,
            cell("2026-10-05", 9, UsageChannel.QUICK_ACTIONS, UsageKind.HELP) to 2,
            cell("2026-10-06", 9, UsageChannel.WATCH, UsageKind.OTHER) to 1,
        )
        val expected = listOf(
            "# ACK USAGE SUMMARY",
            "# SAVED: 2026-10-06 16:10:02 +02:00",
            "# DAYS: 2. MESSAGES: 6. FROM: 2026-10-05. TO: 2026-10-06.",
            "# THIS FILE IS NOT ENCRYPTED AND HAS NO PASSWORD. IT HOLDS COUNTS ONLY, NEVER THE WORDS OF A MESSAGE.",
            "# DATE\tHOUR\tCHANNEL\tKIND\tCOUNT",
            "2026-10-05\t09\tQUICK_ACTIONS\tHELP\t2",
            "2026-10-06\t09\tWATCH\tOTHER\t1",
            "2026-10-06\t14\tMATRIX\tYES\t3",
        ).joinToString("\n", postfix = "\n")
        assertEquals(expected, UsageSummaryFile.render(counts, EnglishText, berlin, millis("2026-10-06T14:10:02Z")))
    }

    @Test
    fun rowsAreOrderedByDateThenHourThenChannelThenKind_whateverOrderTheyWereInserted() {
        val a = cell("2026-10-05", 23, UsageChannel.WATCH, UsageKind.YES)
        val b = cell("2026-10-06", 0, UsageChannel.MATRIX, UsageKind.NO)
        val c = cell("2026-10-06", 0, UsageChannel.MATRIX, UsageKind.YES)
        val d = cell("2026-10-06", 0, UsageChannel.WATCH, UsageKind.YES)
        val e = cell("2026-10-06", 1, UsageChannel.MATRIX, UsageKind.YES)
        val today = LocalDate.parse("2026-10-06")
        val shuffled = listOf(e, d, b, a, c).associateWith { 1 }
        assertEquals(listOf(a, c, b, d, e), UsageSummaryFile.rows(shuffled, today).map { it.first })
    }

    @Test
    fun onlyCountsInsideTheWindowAndAbovezeroAreWritten_andTheEdgeIsKept() {
        val today = LocalDate.parse("2026-10-06")
        val oldest = UsageTally.oldestKept(today)
        val counts = mapOf(
            UsageCell(oldest, 1, UsageChannel.MATRIX, UsageKind.YES) to 1,
            UsageCell(oldest.minusDays(1), 1, UsageChannel.MATRIX, UsageKind.YES) to 9,
            cell("2026-10-06", 2, UsageChannel.MATRIX, UsageKind.YES) to 0,
            cell("2026-10-06", 3, UsageChannel.MATRIX, UsageKind.YES) to -4,
        )
        val rows = UsageSummaryFile.rows(counts, today)
        assertEquals(1, rows.size)
        assertEquals(oldest, rows.single().first.date)
    }

    @Test
    fun everyRecordIsFiveFixedFields_dateHourChannelKindCount_soNoWordCanBeInIt() {
        val counts = HashMap<UsageCell, Int>()
        for (channel in UsageChannel.values()) for (kind in UsageKind.values()) counts[cell("2026-10-06", 5, channel, kind)] = Int.MAX_VALUE
        val lines = UsageSummaryFile.render(counts, EnglishText, ZoneOffset.UTC, millis("2026-10-06T20:00:00Z")).trimEnd('\n').split("\n")
        val records = lines.filterNot { it.startsWith("# ") }
        assertEquals(UsageChannel.values().size * UsageKind.values().size, records.size)
        for (r in records) {
            val f = r.split("\t")
            assertEquals(r, 5, f.size)
            assertTrue(f[0], Regex("""\d{4}-\d{2}-\d{2}""").matches(f[0]))
            assertTrue(f[1], Regex("""\d{2}""").matches(f[1]))
            assertTrue(f[2], f[2] in UsageChannel.values().map { it.name })
            assertTrue(f[3], f[3] in UsageKind.values().map { it.name })
            assertEquals(Int.MAX_VALUE.toString(), f[4])
        }
    }

    @Test
    fun anEmptySummaryIsOnlyTheHeader_withDashesForTheDates() {
        val text = UsageSummaryFile.render(emptyMap(), EnglishText, ZoneOffset.UTC, millis("2026-10-06T20:00:00Z"))
        val lines = text.trimEnd('\n').split("\n")
        assertEquals(5, lines.size)
        assertTrue(lines.all { it.startsWith("# ") })
        assertEquals("# DAYS: 0. MESSAGES: 0. FROM: -. TO: -.", lines[2])
    }

    @Test
    fun theWindowFollowsThePhonesLocalDateWhenItWasSaved() {
        // 2026-10-06T23:30Z is already the 7th in Berlin, so the window ends on the 7th and starts 89 days earlier.
        val savedAt = millis("2026-10-06T23:30:00Z")
        val seventh = LocalDate.parse("2026-10-07")
        val first = UsageTally.oldestKept(seventh)
        val counts = mapOf(UsageCell(first, 1, UsageChannel.MATRIX, UsageKind.YES) to 1, UsageCell(first.minusDays(1), 1, UsageChannel.MATRIX, UsageKind.YES) to 1)
        val berlinFile = UsageSummaryFile.render(counts, EnglishText, berlin, savedAt).lines().filter { it.isNotEmpty() && !it.startsWith("# ") }
        assertEquals(1, berlinFile.size)
        val utcFile = UsageSummaryFile.render(counts, EnglishText, ZoneOffset.UTC, savedAt).lines().filter { it.isNotEmpty() && !it.startsWith("# ") }
        assertEquals("in UTC it is still the 6th, so the earlier day is kept too", 2, utcFile.size)
    }

    @Test
    fun aHeaderTranslationWithALineBreakCannotStartANonHeaderLine() {
        val breaking = object : TextSource {
            override fun get(name: String, vararg args: Any) = "first\nsecond\r\nthird fourth"
            override fun count(name: String, quantity: Int) = name
        }
        val text = UsageSummaryFile.render(emptyMap(), breaking, ZoneOffset.UTC, 0)
        assertEquals(5, text.trimEnd('\n').split("\n").size)
        assertTrue(text.trimEnd('\n').split("\n").all { it.startsWith("# ") })
    }

    @Test
    fun everyHeaderLineStartsWithTheMark_andTheColumnLineHasFiveColumns_inEveryLanguage() {
        val counts = mapOf(cell("2026-10-06", 5, UsageChannel.MATRIX, UsageKind.YES) to 3)
        for (tag in StringsXml.translations().keys) {
            val text = UsageSummaryFile.render(counts, FileText(tag), berlin, millis("2026-10-06T12:00:00Z"))
            val lines = text.trimEnd('\n').split("\n")
            assertEquals("$tag: five header lines and one record", 6, lines.size)
            assertTrue("$tag: a header line without the mark", lines.take(5).all { it.startsWith("# ") })
            assertEquals("$tag: the column line has five columns", 5, lines[4].removePrefix("# ").split("\t").size)
            assertEquals("$tag: the record", "2026-10-06\t05\tMATRIX\tYES\t3", lines[5])
            assertFalse("$tag: a resource name leaked", text.contains("usage_"))
        }
    }

    @Test
    fun theHeaderIsTranslated_notEnglish_inEveryLanguage() {
        val english = UsageSummaryFile.render(emptyMap(), EnglishText, ZoneOffset.UTC, 0).lines().take(5)
        for (tag in StringsXml.translations().keys) {
            val other = UsageSummaryFile.render(emptyMap(), FileText(tag), ZoneOffset.UTC, 0).lines().take(5)
            for (i in english.indices) assertNotEquals("$tag line $i is still English", english[i], other[i])
        }
    }

    @Test
    fun aPhoneSetToArabicOrHindiStillWritesLatinDigits() {
        val saved = Locale.getDefault()
        try {
            for (locale in listOf(Locale("ar", "SA"), Locale("hi", "IN"), Locale("fa", "IR"), Locale("bn", "BD"))) {
                Locale.setDefault(locale)
                val counts = mapOf(cell("2026-10-06", 5, UsageChannel.MATRIX, UsageKind.YES) to 1234567)
                val text = UsageSummaryFile.render(counts, EnglishText, berlin, millis("2026-10-06T12:00:00Z"))
                assertTrue("$locale: ${text.lines().take(4)}", text.all { it.code < 128 })
                assertTrue(text.contains("2026-10-06\t05\tMATRIX\tYES\t1234567"))
                assertEquals("ack_usage_2026-10-06_140000.txt", UsageSummaryFile.fileName(millis("2026-10-06T12:00:00Z"), berlin))
            }
        } finally {
            Locale.setDefault(saved)
        }
    }

    @Test
    fun theFileNameIsPlainAndSafe() {
        val name = UsageSummaryFile.fileName(millis("2026-10-06T12:03:22Z"), berlin)
        assertEquals("ack_usage_2026-10-06_140322.txt", name)
        assertTrue(Regex("""[A-Za-z0-9_.\-]+""").matches(name))
    }
}
