// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Counts messages in a row that the watch did not confirm, so that a watch app which was never updated (and so never
 * confirms anything) is noticed, not just put up with. The caller already says "WATCH DID NOT CONFIRM" for each miss; this
 * decides when to add the hint, once per [hintEvery] misses in a row so it does not repeat on every message.
 */
class RelayMissStreak(private val hintEvery: Int = 3) {
    private var misses = 0

    /** A message was confirmed: the streak starts again. */
    @Synchronized
    fun onDelivered() {
        misses = 0
    }

    /** A message was not confirmed. True on the 3rd, 6th, 9th... miss in a row: log the "is the watch app updated?" hint. */
    @Synchronized
    fun onMiss(): Boolean {
        misses++
        return misses % hintEvery == 0
    }
}
