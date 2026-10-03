// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Lets a repeating notice through at most once per [intervalMs], per key, so a burst of messages cannot flood the log or
 * pile up toasts. Plain Kotlin (no `android.*`) so it is tested without a phone; the caller passes the time in (on the phone,
 * a monotonic clock) so the tests control it.
 */
class NoticeRateLimiter(private val intervalMs: Long) {
    private val lastShownAt = HashMap<String, Long>()

    /**
     * True if the notice for [key] should be shown now, and records that it was. The wait is measured from the last notice
     * that was actually shown, not from the last attempt. A first notice is always shown, and so is one whose clock reads
     * earlier than the last (the clock was set back): it must never silence a warning for longer than one interval.
     */
    @Synchronized
    fun shouldNotify(key: String, nowMs: Long): Boolean {
        val last = lastShownAt[key]
        if (last == null || nowMs < last || nowMs - last >= intervalMs) {
            lastShownAt[key] = nowMs
            return true
        }
        return false
    }
}
