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
        assertEquals("21 SEP 2026", SafetyCopyPolicy.dateText(instant, ZoneId.of("UTC")))
        // Late in the evening UTC is already the next day in Tokyo.
        val lateUtc = 1_790_204_400_000L // 2026-09-23T23:00:00Z
        assertEquals("23 SEP 2026", SafetyCopyPolicy.dateText(lateUtc, ZoneId.of("UTC")))
        assertEquals("24 SEP 2026", SafetyCopyPolicy.dateText(lateUtc, ZoneId.of("Asia/Tokyo")))
    }

    @Test
    fun theRowSaysWhatItIsWhenAndHowBigAndThatItIsNotEncrypted() {
        val row = SafetyCopyPolicy.rowText("21 SEP 2026", "1.4 MB")
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
        assertEquals("DELETE ANYWAY", SafetyCopyPolicy.proceedLabel(hasNewerExport = false))
        assertEquals("CONTINUE", SafetyCopyPolicy.proceedLabel(hasNewerExport = true))
    }

    @Test
    fun theFirstConfirmationSaysWhetherAnExportIsNewerAndThatSavedFilesStay() {
        val without = SafetyCopyPolicy.firstConfirmation("21 SEP 2026", "1.4 MB", hasNewerExport = false)
        val with = SafetyCopyPolicy.firstConfirmation("21 SEP 2026", "1.4 MB", hasNewerExport = true)
        assertTrue(without.first().contains("21 SEP 2026") && without.first().contains("1.4 MB"))
        assertTrue(without.any { it.contains("NOT SAVED AN EXPORT") })
        assertTrue(with.any { it.contains("HAVE SAVED AN EXPORT") })
        assertFalse(with.any { it.contains("NOT SAVED AN EXPORT") })
        for (list in listOf(without, with)) {
            assertTrue(StorageCatalogue.NOT_ELSEWHERE in list)
            assertTrue(list.all { it == it.uppercase() })
        }
    }

    @Test
    fun sizesUseTheSameWordsAsDeleteData() {
        assertEquals("UNDER 1 KB", StorageCatalogue.describeSize(0))
        assertEquals("UNDER 1 KB", StorageCatalogue.describeSize(1023))
        assertEquals("1 KB", StorageCatalogue.describeSize(1024))
        assertEquals("1023 KB", StorageCatalogue.describeSize(1024L * 1024L - 1))
        assertEquals("1.0 MB", StorageCatalogue.describeSize(1024L * 1024L))
    }
}
