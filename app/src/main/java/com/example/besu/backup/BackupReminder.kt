// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.backup

import android.content.Context
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.example.besu.core.BackupReminderPolicy
import com.example.besu.core.BackupReminderPolicy.Decision
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Whether a backup reminder is showing right now, and the checks that set it. Reminder only: ACK never writes a backup file by
 * itself. In-app only: no notification, sound, vibration or animation, and no permission is asked for.
 *
 * [due] is what the screens read (the banner on Terminal/Settings, the save icon in the header and the dialog it opens). It
 * changes only through [refresh] (once, at startup), [snooze], [markBackedUp] and [clear], never on a timer.
 *
 * The rule itself is core/BackupReminderPolicy.kt (tested); what counts as "changed" is core/BackupFingerprint.kt.
 */
object BackupReminder {
    private const val TAG = "ACK_BACKUP"

    /** Non-null while a reminder should show. */
    var due: Decision.Due? by mutableStateOf(null)
        private set

    /** Checks once, off the main thread, and updates [due]. Cheap unless a reminder could actually be due. */
    suspend fun refresh(context: Context) {
        val decision = withContext(Dispatchers.IO) { evaluate(context) }
        due = decision as? Decision.Due
    }

    /** NOT NOW: hides it for 24 hours. */
    fun snooze(context: Context) {
        BackupState.snoozeUntil(context, System.currentTimeMillis() + BackupReminderPolicy.SNOOZE_MS)
        due = null
    }

    /** Called by BackupExporter after a good export. */
    fun markBackedUp(context: Context, fingerprint: String?) {
        BackupState.markBackedUp(context, System.currentTimeMillis(), fingerprint)
        due = null
    }

    /** Hides it without touching the stored state (the switch was turned off). */
    fun clear() {
        due = null
    }

    // Blocking. Never throws: a problem here must only ever mean "no reminder", never a crash at startup.
    private fun evaluate(context: Context): Decision {
        return try {
            val now = System.currentTimeMillis()
            val firstRun = BackupState.firstRunAt(context)
            if (firstRun == null) {
                // The first time on this phone: remember what the data looks like now. Nothing is due yet.
                BackupState.initialise(context, now, TransferManager.backupFingerprint(context))
                return Decision.None
            }

            val lastBackupAt = BackupState.lastBackupAt(context)
            val base = BackupReminderPolicy.Input(
                nowMs = now,
                firstRunAtMs = firstRun,
                lastBackupAtMs = lastBackupAt,
                changedSinceBackup = true,
                snoozedUntilMs = BackupState.snoozedUntil(context),
                enabled = BackupState.remindersEnabled(context),
            )
            // The cheap gate: nothing is computed unless a reminder could be due (on, not snoozed, long enough, clock sane).
            if (BackupReminderPolicy.decide(base) == Decision.None) return Decision.None

            val current = TransferManager.backupFingerprint(context) ?: return Decision.None
            val changed = if (lastBackupAt != null) {
                // Compared with what the last export held. If that was not recorded, assume changed: the safe direction.
                BackupState.lastBackupFingerprint(context)?.let { it != current } ?: true
            } else {
                // Never exported: compared with how the data looked when ACK first ran here.
                val baseline = BackupState.baselineFingerprint(context)
                if (baseline == null) {
                    BackupState.adoptBaseline(context, current)
                    return Decision.None
                }
                baseline != current
            }
            // A short prefix only, never content.
            Log.i(TAG, "reminder check: data fingerprint ${current.take(8)}, changed=$changed")
            BackupReminderPolicy.decide(base.copy(changedSinceBackup = changed))
        } catch (e: Exception) {
            Log.e(TAG, "reminder check failed; no reminder", e)
            Decision.None
        }
    }
}
