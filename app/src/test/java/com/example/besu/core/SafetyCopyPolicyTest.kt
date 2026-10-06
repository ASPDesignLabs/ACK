// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId

class SafetyCopyPolicyTest {

    // --- when a copy was made: from its name, else from the file ---

    @Test
    fun theTimeIsReadFromTheFileName() {
        assertEquals(1_700_000_000_000L, SafetyCopyPolicy.createdAtMs("pre_migration_1700000000000.json", 5L))
        assertEquals(1_700_000_000_123L, SafetyCopyPolicy.createdAtMs("some_other_label_1700000000123.json", 5L))
    }

    @Test
    fun aNameWithoutAUsableTimeFallsBackToTheFilesOwnTime() {
        assertEquals(77L, SafetyCopyPolicy.createdAtMs("weird.json", 77L))
        assertEquals(77L, SafetyCopyPolicy.createdAtMs("pre_migration_.json", 77L))
        assertEquals(77L, SafetyCopyPolicy.createdAtMs("x_123.json", 77L))                       // too short to be a time in ms
        assertEquals(77L, SafetyCopyPolicy.createdAtMs("x_1700000000000.txt", 77L))              // not a .json
        assertEquals(77L, SafetyCopyPolicy.createdAtMs("x_99999999999999999999999.json", 77L))   // does not fit a Long
    }

    @Test
    fun theTwelveDigitFloorIsExact() {
        assertEquals(100_000_000_000L, SafetyCopyPolicy.createdAtMs("x_100000000000.json", 5L))  // 12 digits: accepted
        assertEquals(5L, SafetyCopyPolicy.createdAtMs("x_10000000000.json", 5L))                 // 11 digits: not a time in ms
    }

    // --- is there an export newer than the copy ---

    @Test
    fun noExportAtAllMeansNoNewerExport() {
        assertFalse(SafetyCopyPolicy.hasNewerExport(null, 1_000L))
    }

    @Test
    fun anExportMustBeStrictlyNewerThanTheCopy() {
        assertFalse(SafetyCopyPolicy.hasNewerExport(999L, 1_000L))
        assertFalse(SafetyCopyPolicy.hasNewerExport(1_000L, 1_000L))
        assertTrue(SafetyCopyPolicy.hasNewerExport(1_001L, 1_000L))
    }

    // --- the words ---

    @Test
    fun theDateIsShortCapitalsInTheGivenZone() {
        val instant = 1_790_000_000_000L // 2026-09-21T14:13:20Z
        assertEquals("21 SEP 2026", SafetyCopyPolicy.dateText(EnglishText, instant, ZoneId.of("UTC")))
        // Late in the evening UTC is already the next day in Tokyo.
        val lateUtc = 1_790_204_400_000L // 2026-09-23T23:00:00Z
        assertEquals("23 SEP 2026", SafetyCopyPolicy.dateText(EnglishText, lateUtc, ZoneId.of("UTC")))
        assertEquals("24 SEP 2026", SafetyCopyPolicy.dateText(EnglishText, lateUtc, ZoneId.of("Asia/Tokyo")))
    }

    /** The English words with another language's tag: only the date's language changes. */
    private class Tagged(private val tag: String) : TextSource by EnglishText {
        override val languageTag: String get() = tag
    }

    @Test
    fun theDateIsInTheLanguageOfTheWords_withLatinDigitsLikeEveryOtherNumberHere() {
        // Month names come from the JDK's own data and differ between versions, so this pins what must not: the day and the year are written
        // with Latin digits in every language (never Arabic-Indic or Devanagari), the date is not empty, and it has three parts.
        val instant = 1_790_000_000_000L // 2026-09-21T14:13:20Z
        for (tag in listOf("es", "pt", "af", "hi", "ar", "es-MX", "pt-BR", "ar-EG")) {
            val date = SafetyCopyPolicy.dateText(Tagged(tag), instant, ZoneId.of("UTC"))
            assertTrue("$tag: $date", date.startsWith("21 ") && date.endsWith(" 2026") && date.split(" ").size == 3)
        }
    }

    @Test
    fun aTagThatAsksForOtherDigitsStillGetsLatinOnes() {
        // A phone set to Arabic or Hindi "with their own digits" must not change how the numbers look next to the sizes and counts (which are Latin).
        val instant = 1_790_000_000_000L
        for (tag in listOf("ar-u-nu-arab", "ar-EG-u-nu-arab", "hi-u-nu-deva", "bn-u-nu-beng")) {
            val date = SafetyCopyPolicy.dateText(Tagged(tag), instant, ZoneId.of("UTC"))
            assertTrue("$tag: $date", date.startsWith("21 ") && date.endsWith(" 2026"))
        }
    }

    @Test
    fun aLanguageTagJavaCannotReadGivesEnglishNotACrash() {
        val instant = 1_790_000_000_000L
        assertEquals("21 SEP 2026", SafetyCopyPolicy.dateText(Tagged("not a tag!!"), instant, ZoneId.of("UTC")))
        assertEquals("21 SEP 2026", SafetyCopyPolicy.dateText(Tagged(""), instant, ZoneId.of("UTC")))
    }

    @Test
    fun theRowSaysWhatItIsWhenAndHowBigAndThatItIsNotEncrypted() {
        val row = SafetyCopyPolicy.rowText(EnglishText, "21 SEP 2026", "1.4 MB")
        assertEquals(
            "ACK MADE A PRIVATE SAFETY COPY BEFORE A DATA UPGRADE ON 21 SEP 2026 (1.4 MB). " +
                "IT HOLDS THE SAME DATA AS AN EXPORT AND IS NOT ENCRYPTED.",
            row,
        )
        assertEquals(row.uppercase(), row)
    }

    @Test
    fun exportFirstIsOfferedOnlyWhenThereIsNoNewerExport() {
        assertTrue(SafetyCopyPolicy.offersExportFirst(hasNewerExport = false))
        assertFalse(SafetyCopyPolicy.offersExportFirst(hasNewerExport = true))
    }

    @Test
    fun theProceedButtonSaysDeleteAnywayWhenThereIsNoNewerExport() {
        assertEquals("DELETE ANYWAY", SafetyCopyPolicy.proceedLabel(EnglishText, hasNewerExport = false))
        assertEquals("CONTINUE", SafetyCopyPolicy.proceedLabel(EnglishText, hasNewerExport = true))
    }

    @Test
    fun theFirstConfirmationSaysWhetherAnExportIsNewerAndThatSavedFilesStay() {
        val without = SafetyCopyPolicy.firstConfirmation(EnglishText, "21 SEP 2026", "1.4 MB", hasNewerExport = false)
        val with = SafetyCopyPolicy.firstConfirmation(EnglishText, "21 SEP 2026", "1.4 MB", hasNewerExport = true)
        assertTrue(without.first().contains("21 SEP 2026") && without.first().contains("1.4 MB"))
        assertTrue(without.any { it.contains("NOT SAVED AN EXPORT") })
        assertTrue(with.any { it.contains("HAVE SAVED AN EXPORT") })
        assertFalse(with.any { it.contains("NOT SAVED AN EXPORT") })
        for (list in listOf(without, with)) {
            assertTrue(EnglishText.get(StorageCatalogue.NOT_ELSEWHERE) in list)
            assertTrue(list.all { it == it.uppercase() })
        }
    }

    @Test
    fun sizesUseTheSameWordsAsDeleteData() {
        assertEquals("UNDER 1 KB", StorageCatalogue.describeSize(EnglishText, 0))
        assertEquals("UNDER 1 KB", StorageCatalogue.describeSize(EnglishText, 1023))
        assertEquals("1 KB", StorageCatalogue.describeSize(EnglishText, 1024))
        assertEquals("1023 KB", StorageCatalogue.describeSize(EnglishText, 1024L * 1024L - 1))
        assertEquals("1.0 MB", StorageCatalogue.describeSize(EnglishText, 1024L * 1024L))
    }
}
