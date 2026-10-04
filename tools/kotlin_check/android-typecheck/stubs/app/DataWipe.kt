// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context
import androidx.compose.runtime.snapshots.SnapshotStateList
import com.example.besu.core.StorageCatalogue
import com.example.besu.core.StorageCatalogue.Area
import com.example.besu.core.TextSource

// Stubs of data/DataWipe.kt and the Terminal's LogEntry (they read and delete storage and are not staged), written from their real signatures.
class LogEntry
object DataWipe {
    class Amount(val bytes: Long, val items: Int) {
        fun text(text: TextSource): String = StorageCatalogue.describeAmount(text, bytes, items)
    }
    class Result(val deleted: List<String>, val failed: List<String>) {
        val allOk: Boolean get() = failed.isEmpty()
    }
    fun measure(context: Context, area: Area): Amount = Amount(0, 0)
    fun measureEverything(context: Context): Amount = Amount(0, 0)
    fun wipe(context: Context, selected: List<Area>, everything: Boolean, logs: SnapshotStateList<LogEntry>): Result = Result(emptyList(), emptyList())
    fun logResult(context: Context, result: Result) {}
}
