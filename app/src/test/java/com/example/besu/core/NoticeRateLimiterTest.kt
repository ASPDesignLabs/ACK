// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NoticeRateLimiterTest {
    private val minute = 60_000L

    @Test
    fun theFirstNoticeForAKeyIsAlwaysShown() {
        assertTrue(NoticeRateLimiter(minute).shouldNotify("display", 0L))
        assertTrue(NoticeRateLimiter(minute).shouldNotify("display", 123_456_789L))
    }

    @Test
    fun aRepeatInsideTheIntervalIsSuppressed() {
        val limiter = NoticeRateLimiter(minute)
        assertTrue(limiter.shouldNotify("display", 1_000L))
        assertFalse(limiter.shouldNotify("display", 1_001L))
        assertFalse(limiter.shouldNotify("display", 30_000L))
    }

    @Test
    fun theExactBoundary_oneMillisecondUnderIsSuppressed_exactlyOneIntervalIsShown() {
        val limiter = NoticeRateLimiter(minute)
        assertTrue(limiter.shouldNotify("display", 0L))
        assertFalse(limiter.shouldNotify("display", minute - 1))
        assertTrue(limiter.shouldNotify("display", minute))
    }

    @Test
    fun theWaitIsMeasuredFromTheLastNoticeThatWasShown_notFromTheLastAttempt() {
        val limiter = NoticeRateLimiter(minute)
        assertTrue(limiter.shouldNotify("display", 0L))
        assertFalse(limiter.shouldNotify("display", 59_999L))      // a suppressed attempt must not push the next notice back
        assertTrue(limiter.shouldNotify("display", 60_000L))
        assertFalse(limiter.shouldNotify("display", 60_001L))      // and the clock restarts from the one just shown
        assertTrue(limiter.shouldNotify("display", 120_000L))
    }

    @Test
    fun differentKeysDoNotSuppressEachOther() {
        val limiter = NoticeRateLimiter(minute)
        assertTrue(limiter.shouldNotify("display", 0L))
        assertTrue(limiter.shouldNotify("silent", 1L))
        assertFalse(limiter.shouldNotify("display", 2L))
        assertFalse(limiter.shouldNotify("silent", 3L))
    }

    @Test
    fun aClockThatGoesBackwardsDoesNotMuteTheNoticeForLongerThanOneInterval() {
        val limiter = NoticeRateLimiter(minute)
        assertTrue(limiter.shouldNotify("display", 500_000L))
        assertTrue(limiter.shouldNotify("display", 100_000L))      // earlier than the last one shown: show it, start again from here
        assertFalse(limiter.shouldNotify("display", 100_001L))
        assertTrue(limiter.shouldNotify("display", 160_000L))
    }
}
