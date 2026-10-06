// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.DocumentsContract
import android.util.Log
import android.widget.Toast
import com.example.besu.backup.BackupExporter
import com.example.besu.backup.ExportResult
import com.example.besu.core.LogExport
import com.example.besu.core.LogExportContents
import com.example.besu.core.LogLine
import com.example.besu.core.LoggedMessage
import java.io.IOException
import java.time.ZoneId

/**
 * The one place the Terminal log's messages are written to a file the person chose (SETTINGS > SAVE MESSAGE LOG TO A FILE). What goes in the file and how it is
 * escaped is core/LogExport.kt; this only reads the log, writes the bytes and reports. Shaped like backup/BackupExporter.kt and reusing its result type.
 *
 * Rules that must stay true (LogExportWiringTest holds them):
 *  - **Only the system file picker's document is written** (the screen uses CreateDocument): no share sheet, no Intent that hands the file to another app, no network.
 *  - **A failed write never leaves a half-made file**: the document the picker just made is deleted (best effort), and the failure says nothing was saved.
 *  - **Nothing the person said is ever logged** here, in an error or anywhere else: a log line holds a fixed sentence, a reason, a count or a size, never a message.
 *  - Reading the log changes nothing: it is not pruned, rewritten or marked.
 */
object LogExporter {
    private const val TAG = "ACK_LOG_EXPORT"

    /** A reason a save can fail, as a string resource name (core/LogExportContents says it in words). The others are BackupExporter's. */
    const val REASON_PREPARE = LogExportContents.FAIL_PREPARE

    /** The messages that would be written now: only messages, only those the retention window still keeps, oldest first. */
    fun messagesNow(context: Context, entries: List<LogEntry>, nowMillis: Long = System.currentTimeMillis()): List<LoggedMessage> {
        val lines = entries.map { LogLine(it.epochMillis, it.type, it.msg, it.replayText) }
        return LogExport.messages(lines, LogExport.keptSince(nowMillis, TerminalLogStore.getRetentionDays(context)))
    }

    fun write(context: Context, uri: Uri, entries: List<LogEntry>, nowMillis: Long = System.currentTimeMillis()): ExportResult {
        val resolver = context.contentResolver
        fun discard() {
            try {
                DocumentsContract.deleteDocument(resolver, uri)
            } catch (_: Exception) {
                // Best effort only: not every provider can delete, and the failure itself is what gets reported.
            }
        }
        fun failed(reason: String, error: Throwable? = null): ExportResult {
            // The kind of failure only, never any of what was said.
            Log.e(TAG, "message log not saved: $reason", error)
            discard()
            return ExportResult.Failure(reason)
        }

        return try {
            val messages = messagesNow(context, entries, nowMillis)
            val bytes = LogExport.render(messages, ResourceText(context), ZoneId.systemDefault(), nowMillis).toByteArray(Charsets.UTF_8)
            val out = resolver.openOutputStream(uri, "w") ?: return failed(BackupExporter.REASON_OPEN)
            out.use {
                it.write(bytes)
                it.flush()
            }
            Log.i(TAG, "message log written: ${messages.size} messages, ${bytes.size} bytes")
            ExportResult.Success(bytes.size.toLong())
        } catch (e: SecurityException) {
            failed(BackupExporter.REASON_NOT_ALLOWED, e)
        } catch (e: IOException) {
            failed(BackupExporter.REASON_WRITE, e)
        } catch (e: Exception) {
            failed(REASON_PREPARE, e)
        }
    }

    /** A toast and a Terminal line (the same ACK_LOG broadcast the Terminal's own command feedback uses). Both outcomes are shown; a failure says nothing was saved. */
    fun report(context: Context, result: ExportResult) {
        val text = ResourceText(context)
        val (message, type) = when (result) {
            is ExportResult.Success -> LogExportContents.doneText(text) to "CMD"
            is ExportResult.Failure -> LogExportContents.failedText(text, result.reason) to "CMD_ERR"
        }
        Toast.makeText(context, message, if (result is ExportResult.Failure) Toast.LENGTH_LONG else Toast.LENGTH_SHORT).show()
        context.sendBroadcast(
            Intent("ACK_LOG").apply {
                setPackage(context.packageName)
                putExtra("type", type)
                putExtra("msg", message)
            }
        )
    }
}
