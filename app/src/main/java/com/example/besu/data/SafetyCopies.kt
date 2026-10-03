// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.util.Log
import com.example.besu.core.SafetyCopyPolicy
import java.io.File

/**
 * The private safety copies ACK writes before a one-time data upgrade (TransferManager.writeInternalSnapshot, called from
 * ComputerRepository's legacy-target migration) into `auto_backups`. Until now nothing listed, mentioned or deleted them. A copy
 * holds the same data as an export (voice recordings and the Emergency card included) and is not encrypted, so DATA PORT lists
 * them and lets the person delete one, after the confirmations in settings/SafetyCopyDialogs.kt. DELETE DATA > SAFETY COPIES
 * clears the whole folder.
 *
 * Listing reads file names, sizes and times only, never what is inside a copy.
 */
object SafetyCopies {
    private const val TAG = "ACK_SAFETY_COPIES"

    class Copy(val file: File, val createdAtMs: Long, val sizeBytes: Long)

    private fun folder(context: Context) = File(context.filesDir, "auto_backups")

    /** The copies, newest first. Empty if there are none (the folder may not even exist). */
    fun list(context: Context): List<Copy> {
        val files = folder(context).listFiles { f -> f.isFile && f.name.endsWith(".json") } ?: return emptyList()
        return files
            .map { Copy(it, SafetyCopyPolicy.createdAtMs(it.name, it.lastModified()), it.length()) }
            .sortedByDescending { it.createdAtMs }
    }

    /** Removes one copy. Returns true if it is gone. Refuses anything that is not directly inside the safety-copy folder. */
    fun delete(context: Context, copy: Copy): Boolean {
        return try {
            if (copy.file.parentFile?.canonicalFile != folder(context).canonicalFile) {
                Log.e(TAG, "refused to delete a file outside the safety-copy folder")
                return false
            }
            !copy.file.exists() || copy.file.delete()
        } catch (e: Exception) {
            Log.e(TAG, "could not delete a safety copy", e)
            false
        }
    }
}
