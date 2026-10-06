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
import com.example.besu.core.UsageSummaryFile
import com.example.besu.core.UsageSummaryText
import java.io.IOException
import java.time.ZoneId

/**
 * The one place the usage summary is written to a file the person chose (SETTINGS > USAGE SUMMARY > SAVE USAGE SUMMARY TO A FILE). What goes in the file is
 * core/UsageSummaryFile.kt; this reads the counts, writes the bytes and reports. Shaped like data/LogExporter.kt and reusing the backup's result type.
 *
 * Rules that must stay true (UsageSummaryWiringTest holds them):
 *  - **Only the system file picker's document is written** (the screen uses CreateDocument): no share sheet, no Intent that hands the file to another app, no network.
 *  - **A failed write never leaves a half-made file**: the document the picker just made is deleted (best effort) and the failure says nothing was saved.
 *  - Nothing is logged about the counts beyond how many rows and bytes were written. Reading changes nothing.
 */
object UsageSummaryExporter {
    private const val TAG = "ACK_USAGE_EXPORT"

    /** A reason a save can fail, as a string resource name. The others are BackupExporter's. */
    const val REASON_PREPARE = UsageSummaryText.SAVE_FAIL_PREPARE

    fun write(context: Context, uri: Uri, nowMillis: Long = System.currentTimeMillis()): ExportResult {
        val resolver = context.contentResolver
        fun discard() {
            try {
                DocumentsContract.deleteDocument(resolver, uri)
            } catch (_: Exception) {
                // Best effort only: not every provider can delete, and the failure itself is what gets reported.
            }
        }
        fun failed(reason: String, error: Throwable? = null): ExportResult {
            Log.e(TAG, "usage summary not saved: $reason", error)
            discard()
            return ExportResult.Failure(reason)
        }

        return try {
            val counts = UsageTallyRepository.load(context)
            val bytes = UsageSummaryFile.render(counts, ResourceText(context), ZoneId.systemDefault(), nowMillis).toByteArray(Charsets.UTF_8)
            val out = resolver.openOutputStream(uri, "w") ?: return failed(BackupExporter.REASON_OPEN)
            out.use {
                it.write(bytes)
                it.flush()
            }
            Log.i(TAG, "usage summary written: ${counts.size} rows, ${bytes.size} bytes")
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
            is ExportResult.Success -> UsageSummaryText.saveDone(text) to "CMD"
            is ExportResult.Failure -> UsageSummaryText.saveFailed(text, result.reason) to "CMD_ERR"
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
