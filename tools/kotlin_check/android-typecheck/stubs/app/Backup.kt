// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.backup
import android.content.Context
import android.net.Uri
import com.example.besu.core.BackupReminderPolicy

// Stubs of backup/BackupExporter.kt and backup/BackupReminder.kt (they read storage and are not staged), written from their real signatures.
sealed interface ExportResult {
    data class Success(val bytes: Long) : ExportResult
    data class Failure(val reason: String) : ExportResult
}
object BackupExporter {
    fun writeBackup(context: Context, uri: Uri): ExportResult = ExportResult.Success(0)
    fun report(context: Context, result: ExportResult) {}
}
object BackupReminder {
    var due: BackupReminderPolicy.Decision.Due? = null
    fun snooze(context: Context) {}
}
