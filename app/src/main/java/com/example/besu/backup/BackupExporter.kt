// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.backup

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.DocumentsContract
import android.util.Log
import android.widget.Toast
import com.example.besu.core.ExportContents
import com.example.besu.data.ResourceText
import java.io.IOException

/** What happened when a backup was written. [Failure.reason] is the NAME of a string resource (plain language, never any of the person's data); [BackupExporter.report] shows its text. */
sealed interface ExportResult {
    data class Success(val bytes: Long) : ExportResult
    data class Failure(val reason: String) : ExportResult
}

/**
 * The one place a full JSON backup is written to a file the person chose. EXPORT .JSON (settings) and the Terminal's
 * /backup confirm both call [writeBackup], so a failure is reported the same way from either: before this, the settings
 * button swallowed every error and a null output stream wrote nothing and said nothing.
 *
 * A failed write never leaves a half-made file behind: the document the system picker just created is deleted (the same
 * thing the training-package export does). That delete is best effort; if the storage provider refuses it, nothing more
 * can be done from here and the failure is still reported.
 */
object BackupExporter {
    private const val TAG = "ACK_BACKUP"

    // The reasons a backup can fail, as string resource names (strings.xml has the words in every language).
    const val REASON_OPEN = "backup_fail_open"
    const val REASON_NOT_ALLOWED = "backup_fail_not_allowed"
    const val REASON_WRITE = "backup_fail_write"
    const val REASON_MEMORY = "backup_fail_memory"
    const val REASON_PREPARE = "backup_fail_prepare"

    fun writeBackup(context: Context, uri: Uri): ExportResult {
        val resolver = context.contentResolver
        fun discard() {
            try {
                DocumentsContract.deleteDocument(resolver, uri)
            } catch (_: Exception) {
                // Best effort only: not every provider can delete, and the failure itself is what gets reported.
            }
        }
        fun failed(reason: String, error: Throwable? = null): ExportResult {
            // Log the kind of failure, never any backup content.
            Log.e(TAG, "export failed: $reason", error)
            discard()
            return ExportResult.Failure(reason)
        }

        return try {
            val generated = TransferManager.generateBackup(context)
            val bytes = generated.json.toByteArray(Charsets.UTF_8)
            val out = resolver.openOutputStream(uri, "w")
                ?: return failed(REASON_OPEN)
            out.use {
                it.write(bytes)
                it.flush()
            }
            // Only after a good write: record when, and what the file held (the fingerprint of the very data just written),
            // for the backup reminder. A short prefix is logged, never content.
            // Its own try: a problem with this note must never be reported as a failed export, and must never delete a good file.
            try {
                BackupReminder.markBackedUp(context, generated.fingerprint)
            } catch (e: Exception) {
                Log.e(TAG, "the export was written but its time could not be recorded", e)
            }
            Log.i(TAG, "export written: ${bytes.size} bytes, data fingerprint ${generated.fingerprint?.take(8)}")
            ExportResult.Success(bytes.size.toLong())
        } catch (e: SecurityException) {
            failed(REASON_NOT_ALLOWED, e)
        } catch (e: IOException) {
            failed(REASON_WRITE, e)
        } catch (e: OutOfMemoryError) {
            failed(REASON_MEMORY, e)
        } catch (e: Exception) {
            // The old export code caught everything; keep that, so an unexpected error is reported rather than crashing
            // the screen that asked for the backup.
            failed(REASON_PREPARE, e)
        }
    }

    /**
     * Tells the person what happened: a Toast, and a line in the Terminal (the same ACK_LOG broadcast the Terminal's own
     * command feedback uses). Both outcomes are shown; a failure says plainly that nothing was saved.
     */
    fun report(context: Context, result: ExportResult) {
        val text = ResourceText(context)
        val (message, type) = when (result) {
            is ExportResult.Success -> ExportContents.exportedText(text) to "CMD"
            is ExportResult.Failure -> ExportContents.failedText(text, result.reason) to "CMD_ERR"
        }
        Toast.makeText(
            context,
            message,
            if (result is ExportResult.Failure) Toast.LENGTH_LONG else Toast.LENGTH_SHORT
        ).show()
        context.sendBroadcast(
            Intent("ACK_LOG").apply {
                setPackage(context.packageName)
                putExtra("type", type)
                putExtra("msg", message)
            }
        )
    }
}
