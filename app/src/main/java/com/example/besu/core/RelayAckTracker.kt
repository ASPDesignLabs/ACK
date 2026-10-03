// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

// How long the phone waits for the watch to say it is playing, before it plays the message itself: a fixed
// part plus a part per chunk of audio sent. These are first guesses, to be tuned on a real watch.
private const val RELAY_BASE_TIMEOUT_MS = 3_000L
private const val RELAY_PER_CHUNK_TIMEOUT_MS = 400L

fun relayTimeoutMs(totalChunks: Int): Long = RELAY_BASE_TIMEOUT_MS + RELAY_PER_CHUNK_TIMEOUT_MS * totalChunks

/**
 * Remembers which watch transfers are waiting for the watch's "I am playing" confirmation. Plain Kotlin (java.util.concurrent
 * only), so it is tested without a phone or a watch.
 *
 * The order that matters: [expect] must be called BEFORE any chunk is sent, because the watch's confirmation can arrive
 * before the sender has started waiting. A confirmation for an id nobody expects is ignored (it must not be remembered, or
 * it would pre-release a later transfer that happens to reuse the id). [await] always removes the entry when it returns.
 */
class RelayAckTracker {
    private val waiting = ConcurrentHashMap<Int, CountDownLatch>()

    /** Registers [transferId] as waiting for a confirmation. Call before sending the first chunk. */
    fun expect(transferId: Int) {
        waiting[transferId] = CountDownLatch(1)
    }

    /** Called when the watch's confirmation arrives. Ignored if nothing is waiting for [transferId]. */
    fun onAck(transferId: Int) {
        waiting[transferId]?.countDown()
    }

    /**
     * Blocks until the confirmation for [transferId] has arrived (it may already have) or [timeoutMs] passes. True if it
     * arrived. The entry is removed either way. Never call this on the main thread.
     */
    fun await(transferId: Int, timeoutMs: Long): Boolean {
        val latch = waiting[transferId] ?: return false
        try {
            return latch.await(timeoutMs, TimeUnit.MILLISECONDS)
        } finally {
            waiting.remove(transferId)
        }
    }

    /** Drops a transfer that will never be awaited (for example, sending it threw). */
    fun forget(transferId: Int) {
        waiting.remove(transferId)
    }

    /** How many transfers are being waited for. For tests. */
    fun pendingCount(): Int = waiting.size
}
