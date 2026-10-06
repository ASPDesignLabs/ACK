// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit
import java.util.Random
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/** The usage summary's rules (core/UsageTally.kt): the cell a message counts in, the window, the cap, and the totals. */
class UsageTallyTest {

    private fun day(iso: String) = LocalDate.parse(iso)
    private fun millis(iso: String) = Instant.parse(iso).toEpochMilli()
    private fun cell(date: String, hour: Int = 9, channel: UsageChannel = UsageChannel.MATRIX, kind: UsageKind = UsageKind.OTHER) = UsageCell(day(date), hour, channel, kind)

    // ---- the stored name ---------------------------------------------------------------------------------------------------------------

    @Test
    fun aCellIsStoredUnderADateHourChannelAndKind_inLatinDigits() {
        assertEquals("2026-10-06|14|MATRIX|YES", cell("2026-10-06", 14, UsageChannel.MATRIX, UsageKind.YES).storageKey)
        assertEquals("2026-01-02|00|WATCH|TURN_HOLDING", cell("2026-01-02", 0, UsageChannel.WATCH, UsageKind.TURN_HOLDING).storageKey)
        assertEquals("2026-12-31|23|QUICK_ACTIONS|NAME_OR_ID", cell("2026-12-31", 23, UsageChannel.QUICK_ACTIONS, UsageKind.NAME_OR_ID).storageKey)
    }

    @Test
    fun everyPossibleCellReadsBackAsItself() {
        for (channel in UsageChannel.values()) for (kind in UsageKind.values()) for (hour in listOf(0, 1, 9, 10, 23)) {
            val c = cell("2026-10-06", hour, channel, kind)
            assertEquals(c, UsageCell.parse(c.storageKey))
        }
    }

    @Test
    fun anHourOutsideTheDayIsRefused_andTheEdgesAreAccepted() {
        cell("2026-10-06", 0)
        cell("2026-10-06", 23)
        for (bad in listOf(-1, 24, 99)) {
            try { cell("2026-10-06", bad); fail("hour $bad was accepted") } catch (e: IllegalArgumentException) { /* wanted */ }
        }
    }

    @Test
    fun anythingThatIsNotExactlyAStoredNameIsNotACount_andNothingThrows() {
        for (bad in listOf(
            "", "|", "||||", "a|b|c|d", "2026-10-06|14|MATRIX", "2026-10-06|14|MATRIX|YES|", "2026-10-06|7|MATRIX|YES", "2026-10-06|007|MATRIX|YES",
            "2026-10-06|24|MATRIX|YES", "2026-10-06|-1|MATRIX|YES", "2026-10-06|ab|MATRIX|YES", "2026-10-06|1a|MATRIX|YES", "2026-13-01|14|MATRIX|YES",
            "2026-02-30|14|MATRIX|YES", "2026-1-1|14|MATRIX|YES", "20261006|14|MATRIX|YES", "+12026-10-06|14|MATRIX|YES", "2026-10-06|14|matrix|YES",
            "2026-10-06|14|MATRIX|yes", "2026-10-06|14|NOPE|YES", "2026-10-06|14|MATRIX|NOPE", " 2026-10-06|14|MATRIX|YES", "2026-10-06|14|MATRIX|YES ",
            "2026-10-06|١٤|MATRIX|YES", // Arabic-Indic digits
        )) {
            assertNull("'$bad' was read as a count", UsageCell.parse(bad))
        }
    }

    @Test
    fun randomTextNeverThrowsAndIsNeverACount() {
        val rnd = Random(20261006)
        val alphabet = "0123456789|-ABCDEFMNOPQSTUWXYZ_ abc١".toList()
        repeat(5000) {
            val s = (0 until rnd.nextInt(40)).joinToString("") { alphabet[rnd.nextInt(alphabet.size)].toString() }
            val parsed = UsageCell.parse(s)
            if (parsed != null) assertEquals("a name that reads must be exactly a stored name: '$s'", s, parsed.storageKey)
        }
    }

    // ---- which date and hour ---------------------------------------------------------------------------------------------------------------

    private fun at(iso: String, zone: ZoneId) = UsageTally.cellFor(millis(iso), zone, UsageChannel.OTHER, UsageKind.OTHER)

    @Test
    fun theDateAndHourAreThePhonesOwn_forTheZoneItIsSetTo() {
        assertEquals(cell("2026-10-06", 12, UsageChannel.OTHER), at("2026-10-06T12:00:00Z", ZoneOffset.UTC))
        assertEquals(cell("2026-10-06", 14, UsageChannel.OTHER), at("2026-10-06T12:00:00Z", ZoneId.of("Europe/Berlin")))
        assertEquals(cell("2026-10-06", 17, UsageChannel.OTHER), at("2026-10-06T12:00:00Z", ZoneId.of("Asia/Kolkata"))) // +05:30: 17:30 is hour 17
        assertEquals(cell("2026-10-06", 9, UsageChannel.OTHER), at("2026-10-06T12:00:00Z", ZoneId.of("America/St_Johns"))) // -02:30: 09:30 is hour 9
        assertEquals(cell("2026-10-07", 2, UsageChannel.OTHER), at("2026-10-06T12:00:00Z", ZoneId.of("Pacific/Kiritimati")))
    }

    @Test
    fun midnightFallsOnTheRightSide_downToTheMillisecond() {
        assertEquals(cell("2026-10-06", 23, UsageChannel.OTHER), UsageTally.cellFor(millis("2026-10-07T00:00:00Z") - 1, ZoneOffset.UTC, UsageChannel.OTHER, UsageKind.OTHER))
        assertEquals(cell("2026-10-07", 0, UsageChannel.OTHER), UsageTally.cellFor(millis("2026-10-07T00:00:00Z"), ZoneOffset.UTC, UsageChannel.OTHER, UsageKind.OTHER))
        assertEquals(cell("2026-12-31", 23, UsageChannel.OTHER), at("2026-12-31T23:59:59Z", ZoneOffset.UTC))
        assertEquals(cell("2027-01-01", 0, UsageChannel.OTHER), at("2027-01-01T00:00:00Z", ZoneOffset.UTC))
    }

    @Test
    fun anHourEdgeFallsOnTheRightSide() {
        assertEquals(13, at("2026-10-06T13:59:59Z", ZoneOffset.UTC).hour)
        assertEquals(14, at("2026-10-06T14:00:00Z", ZoneOffset.UTC).hour)
        // India is +05:30, so its hours change on the half hour of UTC.
        assertEquals(17, at("2026-10-06T12:29:59Z", ZoneId.of("Asia/Kolkata")).hour)
        assertEquals(18, at("2026-10-06T12:30:00Z", ZoneId.of("Asia/Kolkata")).hour)
        assertEquals(18, at("2026-10-06T13:00:00Z", ZoneId.of("Asia/Kolkata")).hour)
        assertEquals(19, at("2026-10-06T13:30:00Z", ZoneId.of("Asia/Kolkata")).hour)
    }

    @Test
    fun aDaylightSavingChangeNeverGivesAnImpossibleHour_andTheRepeatedHourJoinsOneCell() {
        val berlin = ZoneId.of("Europe/Berlin")
        // Spring: 01:59:59 +01:00 is followed by 03:00:00 +02:00; hour 2 never happens.
        assertEquals(1, at("2026-03-29T00:59:59Z", berlin).hour)
        assertEquals(3, at("2026-03-29T01:00:00Z", berlin).hour)
        // Autumn: 02:30 happens twice. Both fall in hour 2 of the same date, so they count in one cell (the finest the summary keeps is the hour).
        assertEquals(at("2026-10-25T00:30:00Z", berlin), at("2026-10-25T01:30:00Z", berlin))
        assertEquals(2, at("2026-10-25T00:30:00Z", berlin).hour)
    }

    // ---- how long counts are kept -----------------------------------------------------------------------------------------------------------

    @Test
    fun theWindowIsExactlyNinetyDays_todayAndTheEightyNineBeforeIt() {
        val today = day("2026-10-06")
        val oldest = UsageTally.oldestKept(today)
        assertEquals(today.minusDays(89), oldest)
        assertEquals(90L, ChronoUnit.DAYS.between(oldest, today) + 1)
        assertEquals(90, UsageTally.RETENTION_DAYS)
    }

    @Test
    fun aCountOnTheOldestKeptDayStays_andOneDayOlderGoes() {
        val today = day("2026-10-06")
        val oldest = cell(UsageTally.oldestKept(today).toString())
        val tooOld = cell(UsageTally.oldestKept(today).minusDays(1).toString())
        val gone = UsageTally.keysToRemove(listOf(oldest.storageKey, tooOld.storageKey, cell("2026-10-06").storageKey), today)
        assertEquals(setOf(tooOld.storageKey), gone)
    }

    @Test
    fun theWindowMovesWithTodayAcrossAMonthAndAYearEnd() {
        val gone = UsageTally.keysToRemove(listOf(cell("2025-10-09").storageKey, cell("2025-10-10").storageKey, cell("2025-12-31").storageKey), day("2026-01-07"))
        // Jan 7 minus 89 days is Oct 10 (Oct 10 to Jan 7 inclusive is 90 days).
        assertEquals(setOf(cell("2025-10-09").storageKey), gone)
    }

    @Test
    fun aLeapDayIsCountedLikeAnyOther() {
        val gone = UsageTally.keysToRemove(listOf(cell("2028-02-29").storageKey), day("2028-03-01"))
        assertTrue(gone.isEmpty())
    }

    @Test
    fun aCountDatedInTheFutureIsKept_soAClockSetBackNeverDeletesAnything() {
        assertTrue(UsageTally.keysToRemove(listOf(cell("2030-01-01").storageKey), day("2026-10-06")).isEmpty())
    }

    @Test
    fun anUnreadableNameIsRemoved_soTheFileCannotFillWithGarbage() {
        val today = day("2026-10-06")
        val gone = UsageTally.keysToRemove(listOf("junk", "", cell("2026-10-06").storageKey, "2026-10-06|99|MATRIX|YES"), today)
        assertEquals(setOf("junk", "", "2026-10-06|99|MATRIX|YES"), gone)
    }

    // ---- the size cap -----------------------------------------------------------------------------------------------------------------------

    private fun rowsOn(date: String, n: Int) = (0 until n).map { cell(date, it % 24, UsageChannel.values()[it / 24 % UsageChannel.values().size]).storageKey }

    @Test
    fun exactlyAtTheCapNothingIsRemoved_andOneOverRemovesTheWholeOldestDay() {
        val today = day("2026-10-06")
        val oldDay = rowsOn("2026-10-04", 3)
        val midDay = rowsOn("2026-10-05", 3)
        val newDay = rowsOn("2026-10-06", 3)
        assertTrue(UsageTally.keysToRemove(oldDay + midDay + newDay, today, maxRows = 9).isEmpty())
        assertEquals(oldDay.toSet(), UsageTally.keysToRemove(oldDay + midDay + newDay, today, maxRows = 8))
    }

    @Test
    fun theCapRemovesWholeDaysFromTheOldestUntilTheRestFit_neverHalfADay() {
        val today = day("2026-10-06")
        val a = rowsOn("2026-10-03", 4)
        val b = rowsOn("2026-10-04", 4)
        val c = rowsOn("2026-10-05", 4)
        val d = rowsOn("2026-10-06", 4)
        assertEquals((a + b).toSet(), UsageTally.keysToRemove(a + b + c + d, today, maxRows = 8))
        assertEquals((a + b + c).toSet(), UsageTally.keysToRemove(a + b + c + d, today, maxRows = 7))
        // A cap smaller than one day still never cuts a day in half: it removes the lot.
        assertEquals((a + b + c + d).toSet(), UsageTally.keysToRemove(a + b + c + d, today, maxRows = 3))
    }

    @Test
    fun theRealCapIsFarAboveAnyRealUse_andAFullNinetyDaysOfEveryCombinationFitsUnderIt() {
        // The largest a day can be: 24 hours x 12 channels x 11 kinds. Real use is a tiny fraction.
        val perDay = 24 * UsageChannel.values().size * UsageKind.values().size
        assertEquals(3168, perDay)
        assertTrue("the cap must stay above a realistic ninety days (a few hundred rows a day at the very most)", UsageTally.MAX_ROWS >= 90 * 200)
        assertEquals(20_000, UsageTally.MAX_ROWS)
    }

    // ---- counting ---------------------------------------------------------------------------------------------------------------------------

    @Test
    fun oneMoreMessageAddsOne_stopsAtTheLargestNumber_andRepairsADamagedValue() {
        assertEquals(1, UsageTally.increment(0))
        assertEquals(6, UsageTally.increment(5))
        assertEquals(Int.MAX_VALUE, UsageTally.increment(Int.MAX_VALUE - 1))
        assertEquals(Int.MAX_VALUE, UsageTally.increment(Int.MAX_VALUE))
        assertEquals(1, UsageTally.increment(-1))
        assertEquals(1, UsageTally.increment(Int.MIN_VALUE))
    }

    // ---- the totals -------------------------------------------------------------------------------------------------------------------------

    @Test
    fun totalsAreByKindChannelAndHour_andEveryMessageIsInEachOfThem() {
        val today = day("2026-10-06")
        val counts = mapOf(
            cell("2026-10-06", 9, UsageChannel.MATRIX, UsageKind.YES) to 3,
            cell("2026-10-06", 9, UsageChannel.QUICK_ACTIONS, UsageKind.YES) to 2,
            cell("2026-10-05", 14, UsageChannel.MATRIX, UsageKind.HELP) to 4,
            cell("2026-10-05", 14, UsageChannel.WATCH, UsageKind.OTHER) to 1,
        )
        val s = UsageTally.summarise(counts, today)
        assertEquals(10L, s.messages)
        assertEquals(mapOf(UsageKind.YES to 5L, UsageKind.HELP to 4L, UsageKind.OTHER to 1L), s.byKind)
        assertEquals(mapOf(UsageChannel.MATRIX to 7L, UsageChannel.QUICK_ACTIONS to 2L, UsageChannel.WATCH to 1L), s.byChannel)
        assertEquals(24, s.byHour.size)
        assertEquals(5L, s.byHour[9]); assertEquals(5L, s.byHour[14]); assertEquals(0L, s.byHour[0])
        assertEquals(s.messages, s.byKind.values.sum()); assertEquals(s.messages, s.byChannel.values.sum()); assertEquals(s.messages, s.byHour.sum())
        assertEquals(2, s.daysWithCounts); assertEquals(day("2026-10-05"), s.firstDate); assertEquals(day("2026-10-06"), s.lastDate)
    }

    @Test
    fun theLastFourteenDaysAreListedTodayFirst_withZeroForADayWithNothing() {
        val today = day("2026-10-06")
        val s = UsageTally.summarise(mapOf(cell("2026-10-06") to 2, cell("2026-10-01") to 5, cell("2026-09-23") to 7), today)
        assertEquals(UsageTally.RECENT_DAYS, s.recent.size)
        assertEquals(day("2026-10-06"), s.recent.first().date)
        assertEquals(day("2026-09-23"), s.recent.last().date)
        assertEquals(2L, s.recent.first().messages)
        assertEquals(5L, s.recent.first { it.date == day("2026-10-01") }.messages)
        assertEquals(7L, s.recent.last().messages)
        assertEquals(0L, s.recent.first { it.date == day("2026-10-03") }.messages)
        // Exactly fourteen days back: Oct 6 minus 13 is Sep 23, so Sep 22 is not listed (but is still counted in the totals).
        val older = UsageTally.summarise(mapOf(cell("2026-09-22") to 9), today)
        assertEquals(0L, older.recent.sumOf { it.messages })
        assertEquals(9L, older.messages)
    }

    @Test
    fun aCountOlderThanTheWindowOrOfZeroIsIgnored() {
        val today = day("2026-10-06")
        val oldest = UsageTally.oldestKept(today)
        val s = UsageTally.summarise(mapOf(cell(oldest.toString()) to 2, cell(oldest.minusDays(1).toString()) to 50, cell("2026-10-06") to 0, cell("2026-10-05") to -3), today)
        assertEquals(2L, s.messages)
        assertEquals(1, s.daysWithCounts)
    }

    @Test
    fun anEmptySummaryIsAllZeros_withNoDates() {
        val s = UsageTally.summarise(emptyMap(), day("2026-10-06"))
        assertEquals(0L, s.messages); assertEquals(0, s.daysWithCounts)
        assertNull(s.firstDate); assertNull(s.lastDate)
        assertTrue(s.byKind.isEmpty() && s.byChannel.isEmpty())
        assertEquals(List(24) { 0L }, s.byHour)
        assertEquals(UsageTally.RECENT_DAYS, s.recent.size)
    }

    @Test
    fun totalsAreLongs_soTwoFullCellsDoNotOverflow() {
        val s = UsageTally.summarise(mapOf(cell("2026-10-06", 1) to Int.MAX_VALUE, cell("2026-10-06", 2) to Int.MAX_VALUE), day("2026-10-06"))
        assertEquals(2L * Int.MAX_VALUE, s.messages)
        assertTrue(s.messages > Int.MAX_VALUE)
    }

    // ---- no words, ever ------------------------------------------------------------------------------------------------------------------------

    @Test
    fun noTypeThatHoldsCountsHasAFieldThatCouldHoldAWord() {
        // The summary never keeps a word of a message. A String (or any text-like) field on these types would be the first step to doing so.
        val allowed = setOf(LocalDate::class.java, Int::class.javaPrimitiveType, Long::class.javaPrimitiveType, UsageChannel::class.java, UsageKind::class.java, List::class.java, Map::class.java)
        for (type in listOf(UsageCell::class.java, UsageDay::class.java, UsageSummary::class.java)) {
            for (field in type.declaredFields.filterNot { it.isSynthetic || java.lang.reflect.Modifier.isStatic(it.modifiers) }) {
                assertTrue("${type.simpleName}.${field.name} is a ${field.type.name}: counts hold no text", field.type in allowed)
            }
        }
        assertTrue(UsageCell::class.java.declaredFields.none { it.type == String::class.java || it.type == CharSequence::class.java })
    }

    @Test
    fun theStoredNameHoldsOnlyFixedParts_soNoCustomTextCanReachIt() {
        // Whatever a message or a deck is called, the stored name is built from a date, an hour and two enum names.
        for (channel in UsageChannel.values()) for (kind in UsageKind.values()) {
            val key = cell("2026-10-06", 5, channel, kind).storageKey
            assertTrue(key, Regex("""\d{4}-\d{2}-\d{2}\|\d{2}\|[A-Z_]+\|[A-Z_]+""").matches(key))
        }
    }
}
