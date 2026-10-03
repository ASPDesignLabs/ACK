// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RelayAckTrackerTest {
    @Test
    fun anAckThatArrivesBeforeAwaitStillReturnsTrue() {
        val tracker = RelayAckTracker()
        tracker.expect(7)
        tracker.onAck(7)                         // the watch was quicker than the phone's own waiting
        assertTrue(tracker.await(7, 10))
    }

    @Test
    fun awaitReturnsFalseAtTheTimeout_andReallyWaitsForIt() {
        val tracker = RelayAckTracker()
        tracker.expect(7)
        val start = System.nanoTime()
        assertFalse(tracker.await(7, 60))
        val waitedMs = (System.nanoTime() - start) / 1_000_000
        assertTrue("returned after only $waitedMs ms", waitedMs >= 55)
    }

    @Test
    fun anAckThatArrivesWhileWaitingReleasesItEarly() {
        val tracker = RelayAckTracker()
        tracker.expect(7)
        Thread { Thread.sleep(40); tracker.onAck(7) }.start()
        val start = System.nanoTime()
        assertTrue(tracker.await(7, 5_000))
        val waitedMs = (System.nanoTime() - start) / 1_000_000
        assertTrue("took $waitedMs ms; should have been released by the ack at about 40 ms", waitedMs < 2_000)
    }

    @Test
    fun anAckForAnUnknownIdChangesNothing_andDoesNotPreReleaseALaterTransferWithThatId() {
        val tracker = RelayAckTracker()
        tracker.onAck(99)                        // nobody is waiting for 99
        assertEquals(0, tracker.pendingCount())
        tracker.expect(99)                       // a later transfer happens to reuse the id
        assertFalse(tracker.await(99, 30))       // the stray ack must not have counted
    }

    @Test
    fun theEntryIsRemovedAfterwards_whetherTheAckCameOrNot() {
        val tracker = RelayAckTracker()
        tracker.expect(1)
        tracker.onAck(1)
        assertTrue(tracker.await(1, 10))
        assertEquals(0, tracker.pendingCount())
        assertFalse(tracker.await(1, 10))        // a second wait on the same id has nothing to wait for

        tracker.expect(2)
        assertFalse(tracker.await(2, 10))
        assertEquals(0, tracker.pendingCount())
    }

    @Test
    fun twoIdsAtOnceDoNotCross() {
        val tracker = RelayAckTracker()
        tracker.expect(1)
        tracker.expect(2)
        tracker.onAck(2)
        assertFalse(tracker.await(1, 30))
        assertTrue(tracker.await(2, 30))
    }

    @Test
    fun forgetRemovesATransferThatWillNeverBeAwaited() {
        val tracker = RelayAckTracker()
        tracker.expect(5)
        assertEquals(1, tracker.pendingCount())
        tracker.forget(5)
        assertEquals(0, tracker.pendingCount())
    }

    @Test
    fun theTimeoutGrowsWithTheChunkCount() {
        assertEquals(3_400L, relayTimeoutMs(1))
        assertEquals(5_400L, relayTimeoutMs(6))
        assertEquals(3_000L, relayTimeoutMs(0))
        for (chunks in 1..50) assertTrue(relayTimeoutMs(chunks + 1) > relayTimeoutMs(chunks))
    }

    @Test
    fun theTimeoutDoesNotOverflowForAnAbsurdlyLargeChunkCount() {
        assertTrue(relayTimeoutMs(Int.MAX_VALUE) > relayTimeoutMs(1_000))
    }
}
