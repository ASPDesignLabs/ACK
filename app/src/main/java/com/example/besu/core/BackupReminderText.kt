// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the backup reminder says: the banner (Terminal and Settings), the dialog the header's save icon opens, and the switch in
 * DATA PORT all show these words. Plain Kotlin (no `android.*`) so they are tested without a phone. Capitals, like the rest of
 * the app. It is a reminder only: ACK never says, or does, a backup by itself.
 */
object BackupReminderText {
    const val BACK_UP_NOW = "BACK UP NOW"
    const val NOT_NOW = "NOT NOW"
    const val DIALOG_TITLE = "BACKUP DUE"

    /** What a screen reader says for the header's save icon (it has no text of its own). */
    const val ICON_DESCRIPTION = "BACKUP DUE"

    const val SWITCH_EXPLANATION =
        "REMINDS YOU TO BACK UP WHEN SOMETHING HAS CHANGED AND 7 DAYS HAVE PASSED. IN ACK ONLY, AND NO FILE IS MADE FOR YOU. " +
            "CHECKED WHEN ACK STARTS."

    fun switchLabel(enabled: Boolean): String = if (enabled) "BACKUP REMINDER: ON" else "BACKUP REMINDER: OFF"

    fun message(daysSince: Int, neverBackedUp: Boolean): String =
        if (neverBackedUp) {
            "YOU HAVE NOT MADE A BACKUP YET, AND THINGS HAVE CHANGED."
        } else {
            "BACKUP DUE: YOUR LAST BACKUP WAS ${days(daysSince)} AGO, AND SETTINGS OR DECKS HAVE CHANGED SINCE."
        }

    private fun days(n: Int): String = if (n == 1) "1 DAY" else "$n DAYS"
}
