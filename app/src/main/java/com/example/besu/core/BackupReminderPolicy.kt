// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * When ACK reminds the person to make a backup. It is a reminder only: ACK never writes a backup file by itself, so the
 * person keeps control of where a backup goes and no extra unprotected copy is made. Plain Kotlin (no `android.*`) so every
 * edge is tested without a phone; the caller passes the time in.
 *
 * Due only when ALL of these hold:
 *  - reminders are switched on;
 *  - no snooze is running;
 *  - at least [Input.intervalMs] (7 days) have passed since the last export, or since the first run if there has never been one;
 *  - the backed-up data has changed since then.
 *
 * Two clock rules: a clock that reads earlier than the reference time gives no reminder, and a snooze that ends further away
 * than one snooze length is not one this app could have made (the clock was set back), so it is ignored rather than allowed to
 * silence the reminder for as long as the clock was moved.
 */
object BackupReminderPolicy {
    const val INTERVAL_MS: Long = 7L * 24L * 60L * 60L * 1000L
    const val SNOOZE_MS: Long = 24L * 60L * 60L * 1000L
    private const val DAY_MS: Long = 24L * 60L * 60L * 1000L

    class Input(
        val nowMs: Long,
        val firstRunAtMs: Long,
        /** When the last good export finished, or null if there never was one. */
        val lastBackupAtMs: Long?,
        val changedSinceBackup: Boolean,
        /** Until when a snooze runs; 0 (or any past time) for none. */
        val snoozedUntilMs: Long,
        val enabled: Boolean,
        val intervalMs: Long = INTERVAL_MS,
    ) {
        fun copy(
            nowMs: Long = this.nowMs,
            changedSinceBackup: Boolean = this.changedSinceBackup,
            intervalMs: Long = this.intervalMs,
        ) = Input(nowMs, firstRunAtMs, lastBackupAtMs, changedSinceBackup, snoozedUntilMs, enabled, intervalMs)
    }

    sealed interface Decision {
        data object None : Decision
        data class Due(val daysSince: Int, val neverBackedUp: Boolean) : Decision
    }

    fun decide(input: Input): Decision {
        if (!input.enabled) return Decision.None

        val snoozeRunning = input.snoozedUntilMs > input.nowMs && input.snoozedUntilMs - input.nowMs <= SNOOZE_MS
        if (snoozeRunning) return Decision.None

        val reference = input.lastBackupAtMs ?: input.firstRunAtMs
        if (input.nowMs < reference) return Decision.None

        val elapsed = input.nowMs - reference
        if (elapsed < input.intervalMs) return Decision.None

        if (!input.changedSinceBackup) return Decision.None
        return Decision.Due(daysSince = (elapsed / DAY_MS).toInt(), neverBackedUp = input.lastBackupAtMs == null)
    }
}
