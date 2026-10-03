// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.backup

import android.content.Context

/**
 * This phone's own notes for the backup reminder: when ACK first ran, when the last good export was made and what it held, when a
 * snooze ends, and whether reminders are on. Per-device state: it is NOT part of AckBackup and never travels in a backup (a
 * restored phone has its own history), and restoring a backup never marks one as made (a restore merges, so the result is not
 * necessarily what any file holds).
 *
 * Fingerprints here are only ever compared, never shown or logged in full. The decisions are in core/BackupReminderPolicy.kt.
 * Wiped with the SETTINGS area of DELETE DATA (see core/StorageCatalogue.kt).
 */
object BackupState {
    private const val PREFS = "ack_backup_state"
    private const val KEY_FIRST_RUN_AT = "first_run_at"
    private const val KEY_LAST_BACKUP_AT = "last_backup_at"
    private const val KEY_LAST_BACKUP_FINGERPRINT = "last_backup_fingerprint"
    private const val KEY_BASELINE_FINGERPRINT = "baseline_fingerprint"
    private const val KEY_SNOOZED_UNTIL = "snoozed_until"
    private const val KEY_REMINDERS_ENABLED = "reminders_enabled"

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun firstRunAt(context: Context): Long? = prefs(context).takeIf { it.contains(KEY_FIRST_RUN_AT) }?.getLong(KEY_FIRST_RUN_AT, 0L)
    fun lastBackupAt(context: Context): Long? = prefs(context).takeIf { it.contains(KEY_LAST_BACKUP_AT) }?.getLong(KEY_LAST_BACKUP_AT, 0L)
    fun lastBackupFingerprint(context: Context): String? = prefs(context).getString(KEY_LAST_BACKUP_FINGERPRINT, null)
    fun baselineFingerprint(context: Context): String? = prefs(context).getString(KEY_BASELINE_FINGERPRINT, null)
    fun snoozedUntil(context: Context): Long = prefs(context).getLong(KEY_SNOOZED_UNTIL, 0L)

    /** On unless the person switched it off in DATA PORT. */
    fun remindersEnabled(context: Context): Boolean = prefs(context).getBoolean(KEY_REMINDERS_ENABLED, true)

    fun setRemindersEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_REMINDERS_ENABLED, enabled).commit()
    }

    /**
     * Creates the state the first time: when ACK first ran here, and what the data looked like then (the baseline a phone that
     * has never exported is compared with). Does nothing if it already exists. [baselineFingerprint] may be null if it could not be
     * worked out; the first check that can will adopt one.
     */
    fun initialise(context: Context, nowMs: Long, baselineFingerprint: String?) {
        val p = prefs(context)
        if (p.contains(KEY_FIRST_RUN_AT)) return
        val editor = p.edit().putLong(KEY_FIRST_RUN_AT, nowMs)
        if (baselineFingerprint != null) editor.putString(KEY_BASELINE_FINGERPRINT, baselineFingerprint)
        editor.commit()
    }

    /** A phone that never exported keeps comparing with the baseline; this adopts one if the first attempt had none. */
    fun adoptBaseline(context: Context, fingerprint: String) {
        prefs(context).edit().putString(KEY_BASELINE_FINGERPRINT, fingerprint).commit()
    }

    /**
     * Records a good export: when, and the fingerprint of the data it held. [fingerprint] null (it could not be worked out) is
     * kept as "unknown", which the reminder treats as "changed", the safe direction. Ends any snooze, since the reminder is met.
     */
    fun markBackedUp(context: Context, nowMs: Long, fingerprint: String?) {
        val p = prefs(context)
        val editor = p.edit().putLong(KEY_LAST_BACKUP_AT, nowMs).putLong(KEY_SNOOZED_UNTIL, 0L)
        if (!p.contains(KEY_FIRST_RUN_AT)) editor.putLong(KEY_FIRST_RUN_AT, nowMs)
        if (fingerprint != null) editor.putString(KEY_LAST_BACKUP_FINGERPRINT, fingerprint) else editor.remove(KEY_LAST_BACKUP_FINGERPRINT)
        editor.commit()
    }

    fun snoozeUntil(context: Context, untilMs: Long) {
        prefs(context).edit().putLong(KEY_SNOOZED_UNTIL, untilMs).commit()
    }
}
