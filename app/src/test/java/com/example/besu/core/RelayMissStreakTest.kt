// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RelayMissStreakTest {
    @Test
    fun theHintComesOnTheThirdMissInARow_notBefore() {
        val streak = RelayMissStreak()
        assertFalse(streak.onMiss())
        assertFalse(streak.onMiss())
        assertTrue(streak.onMiss())
    }

    @Test
    fun itComesAgainEveryThirdMissAfterThat_notOnEveryMissInBetween() {
        val streak = RelayMissStreak()
        val hints = (1..9).map { streak.onMiss() }
        assertTrue(hints == listOf(false, false, true, false, false, true, false, false, true))
    }

    @Test
    fun aDeliveredMessageStartsTheCountAgain() {
        val streak = RelayMissStreak()
        streak.onMiss(); streak.onMiss()
        streak.onDelivered()
        assertFalse(streak.onMiss())             // 1 in a row, not 3
        assertFalse(streak.onMiss())
        assertTrue(streak.onMiss())
    }
}
