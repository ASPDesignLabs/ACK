// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the backup reminder says: the banner (Terminal and Settings), the dialog the header's save icon opens, and the switch in
 * DATA PORT all show these words. Plain Kotlin (no `android.*`) so what is said is tested without a phone; the words are string resources
 * (`backup_reminder_*` in strings.xml, in the chosen language) supplied through a [TextSource]. Capitals, like the rest of the app, wherever the
 * script has them. It is a reminder only: ACK never says, or does, a backup by itself.
 */
object BackupReminderText {
    // Resource names, not words.
    const val BACK_UP_NOW = "backup_reminder_back_up_now"
    const val NOT_NOW = "backup_reminder_not_now"
    const val DIALOG_TITLE = "backup_reminder_dialog_title"

    /** What a screen reader says for the header's save icon (it has no text of its own): the same words as the dialog's title. */
    const val ICON_DESCRIPTION = DIALOG_TITLE

    const val SWITCH_EXPLANATION = "backup_reminder_switch_explanation"
    private const val SWITCH_ON = "backup_reminder_switch_on"
    private const val SWITCH_OFF = "backup_reminder_switch_off"
    private const val MESSAGE_NEVER = "backup_reminder_message_never"
    private const val MESSAGE_DAYS = "backup_reminder_message"
    private const val DAYS = "backup_reminder_days"

    fun switchLabel(text: TextSource, enabled: Boolean): String = text.get(if (enabled) SWITCH_ON else SWITCH_OFF)

    fun message(text: TextSource, daysSince: Int, neverBackedUp: Boolean): String =
        if (neverBackedUp) {
            text.get(MESSAGE_NEVER)
        } else {
            // The number of days is a plural in the languages that have them (one is 1 DAY, the others N DAYS; Arabic has more forms).
            text.get(MESSAGE_DAYS, text.count(DAYS, daysSince))
        }
}
