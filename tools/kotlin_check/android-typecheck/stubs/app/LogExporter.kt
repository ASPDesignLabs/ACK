// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context
import android.net.Uri
import com.example.besu.backup.ExportResult
import com.example.besu.core.LoggedMessage

// Stub of data/LogExporter.kt (it reads the Terminal log and writes a file and is not staged), written from its real signatures. LogEntry is stubbed in DataWipe.kt.
object LogExporter {
    const val REASON_PREPARE = "log_export_fail_prepare"
    fun messagesNow(context: Context, entries: List<LogEntry>, nowMillis: Long = 0L): List<LoggedMessage> = emptyList()
    fun write(context: Context, uri: Uri, entries: List<LogEntry>, nowMillis: Long = 0L): ExportResult = ExportResult.Success(0)
    fun report(context: Context, result: ExportResult) {}
}
