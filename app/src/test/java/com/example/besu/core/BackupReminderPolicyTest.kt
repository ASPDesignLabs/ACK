// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import com.example.besu.core.BackupReminderPolicy.Decision
import com.example.besu.core.BackupReminderPolicy.Input
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BackupReminderPolicyTest {
    private val day = 24L * 60L * 60L * 1000L
    private val interval = 7 * day
    private val t0 = 1_700_000_000_000L

    // A phone that last backed up at t0, has data changed since, reminders on, no snooze.
    private fun input(
        now: Long,
        firstRunAt: Long = t0 - 100 * day,
        lastBackupAt: Long? = t0,
        changed: Boolean = true,
        snoozedUntil: Long = 0L,
        enabled: Boolean = true,
    ) = Input(
        nowMs = now, firstRunAtMs = firstRunAt, lastBackupAtMs = lastBackupAt, changedSinceBackup = changed,
        snoozedUntilMs = snoozedUntil, enabled = enabled,
    )

    private fun decide(i: Input) = BackupReminderPolicy.decide(i)

    // --- the 7-day boundary ---

    @Test
    fun exactlySevenDaysIsDue() {
        val d = decide(input(now = t0 + interval))
        assertTrue(d is Decision.Due)
        assertEquals(7, (d as Decision.Due).daysSince)
    }

    @Test
    fun sevenDaysLessOneMillisecondIsNotDue() {
        assertEquals(Decision.None, decide(input(now = t0 + interval - 1)))
    }

    @Test
    fun sevenDaysPlusOneMillisecondIsDue() {
        assertTrue(decide(input(now = t0 + interval + 1)) is Decision.Due)
    }

    @Test
    fun daysSinceCountsWholeDays() {
        assertEquals(7, (decide(input(now = t0 + 7 * day + day - 1)) as Decision.Due).daysSince)
        assertEquals(8, (decide(input(now = t0 + 8 * day)) as Decision.Due).daysSince)
        assertEquals(30, (decide(input(now = t0 + 30 * day + 5)) as Decision.Due).daysSince)
    }

    @Test
    fun theIntervalIsTheOneInTheInputNotAFixedSeven() {
        val i = input(now = t0 + 3 * day).copy(intervalMs = 3 * day)
        assertTrue(decide(i) is Decision.Due)
        assertEquals(Decision.None, decide(i.copy(nowMs = t0 + 3 * day - 1)))
    }

    // --- changed or not ---

    @Test
    fun nothingChangedMeansNoReminderHoweverLongItHasBeen() {
        assertEquals(Decision.None, decide(input(now = t0 + 365 * day, changed = false)))
    }

    // --- off, and snoozed ---

    @Test
    fun switchedOffMeansNoReminder() {
        assertEquals(Decision.None, decide(input(now = t0 + 30 * day, enabled = false)))
    }

    @Test
    fun aSnoozeInTheFutureSuppressesItAndOneInThePastDoesNot() {
        val now = t0 + 10 * day
        assertEquals(Decision.None, decide(input(now = now, snoozedUntil = now + 1)))
        // Until exactly now is over: the snooze has ended.
        assertTrue(decide(input(now = now, snoozedUntil = now)) is Decision.Due)
        assertTrue(decide(input(now = now, snoozedUntil = now - 1)) is Decision.Due)
        assertTrue(decide(input(now = now, snoozedUntil = 0L)) is Decision.Due)
    }

    @Test
    fun aSnoozeFurtherAwayThanOneSnoozeLengthIsIgnoredSoAClockSetBackCannotSilenceItForLong() {
        val now = t0 + 10 * day
        // Exactly one snooze length ahead still suppresses; one millisecond more is not a snooze this app could have made.
        assertEquals(Decision.None, decide(input(now = now, snoozedUntil = now + BackupReminderPolicy.SNOOZE_MS)))
        assertTrue(decide(input(now = now, snoozedUntil = now + BackupReminderPolicy.SNOOZE_MS + 1)) is Decision.Due)
    }

    @Test
    fun theSnoozeLengthIsTwentyFourHours() {
        assertEquals(24L * 60L * 60L * 1000L, BackupReminderPolicy.SNOOZE_MS)
        assertEquals(7L * 24L * 60L * 60L * 1000L, BackupReminderPolicy.INTERVAL_MS)
    }

    // --- never backed up: counted from the first run ---

    @Test
    fun neverBackedUpCountsFromTheFirstRun() {
        val first = t0
        val base = input(now = first + interval - 1, firstRunAt = first, lastBackupAt = null)
        assertEquals(Decision.None, decide(base))
        val due = decide(base.copy(nowMs = first + interval))
        assertTrue(due is Decision.Due)
        due as Decision.Due
        assertTrue(due.neverBackedUp)
        assertEquals(7, due.daysSince)
    }

    @Test
    fun aRealBackupIsNotCountedFromTheFirstRun() {
        val d = decide(input(now = t0 + interval, firstRunAt = t0 - 400 * day, lastBackupAt = t0))
        assertTrue(d is Decision.Due)
        assertEquals(false, (d as Decision.Due).neverBackedUp)
        assertEquals(7, d.daysSince)
    }

    @Test
    fun neverBackedUpButNothingChangedStaysQuiet() {
        assertEquals(Decision.None, decide(input(now = t0 + 90 * day, firstRunAt = t0, lastBackupAt = null, changed = false)))
    }

    // --- the clock ---

    @Test
    fun aClockMovedBackwardsGivesNoReminder() {
        assertEquals(Decision.None, decide(input(now = t0 - 1)))
        assertEquals(Decision.None, decide(input(now = t0 - 30 * day)))
        // Never backed up: before the first run counts as backwards too.
        assertEquals(Decision.None, decide(input(now = t0 - 1, firstRunAt = t0, lastBackupAt = null)))
    }

    @Test
    fun theSameMomentIsNotYetDue() {
        assertEquals(Decision.None, decide(input(now = t0)))
    }
}
