// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context
import android.net.Uri
import com.example.besu.backup.ExportResult
import com.example.besu.core.UsageCell

// Stubs of data/UsageTallyRepository.kt and data/UsageSummaryExporter.kt (they read and write storage and are not staged), written from their real signatures.
object UsageTallyRepository {
    fun recordMessage(context: Context, source: String, text: String, nowMillis: Long = 0L) {}
    fun load(context: Context): Map<UsageCell, Int> = emptyMap()
    fun messageCount(context: Context): Long = 0L
    fun forgetAll(context: Context): Boolean = true
}
object UsageSummaryExporter {
    const val REASON_PREPARE = "usage_save_fail_prepare"
    fun write(context: Context, uri: Uri, nowMillis: Long = 0L): ExportResult = ExportResult.Success(0)
    fun report(context: Context, result: ExportResult) {}
}
