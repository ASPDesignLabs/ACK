package com.example.besu.data

import com.example.besu.ui.*
import android.content.Context
import androidx.compose.runtime.snapshots.SnapshotStateList
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

// A previously communicated phrase (OUT/EMERGENCY) carries replayText so
// TerminalView can offer it back for playback -- system and path-trace
// lines never do. epochMillis backs the rolling retention window below --
// the HH:mm:ss display string alone can't tell entries from different days
// apart once the log survives an app restart.
@Serializable
data class LogEntry(
    val time: String,
    val type: String,
    val msg: String,
    val replayText: String? = null,
    val epochMillis: Long = System.currentTimeMillis()
)

// Persists the Terminal log across app restarts -- it used to reset on
// every launch -- and keeps it from growing without bound: entries fall
// off once they're older than the user's chosen retention window (a true
// rolling window measured continuously from "now", not a calendar-day
// bucket that snaps at midnight) or once the buffer exceeds MAX_ENTRIES,
// whichever comes first.
object TerminalLogStore {
    private const val PREFS = "ack_prefs"
    private const val KEY_LOG = "TERMINAL_LOG_ENTRIES"
    private const val KEY_RETENTION_DAYS = "TERMINAL_LOG_RETENTION_DAYS"
    private const val KEY_HIDE_SYSTEM = "TERMINAL_HIDE_SYSTEM_MSGS"
    private const val KEY_HIDE_PATH = "TERMINAL_HIDE_PATH_TRACE"
    private const val KEY_MONOSPACE = "TERMINAL_MONOSPACE_ENABLED"

    const val MAX_ENTRIES = 400
    const val MIN_RETENTION_DAYS = 1
    const val MAX_RETENTION_DAYS = 30
    const val DEFAULT_RETENTION_DAYS = 7

    private const val DAY_MILLIS = 24L * 60L * 60L * 1000L

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun getRetentionDays(context: Context): Int =
        prefs(context).getInt(KEY_RETENTION_DAYS, DEFAULT_RETENTION_DAYS)

    private fun setRetentionDays(context: Context, days: Int) {
        prefs(context).edit()
            .putInt(KEY_RETENTION_DAYS, days.coerceIn(MIN_RETENTION_DAYS, MAX_RETENTION_DAYS))
            .apply()
    }

    fun getHideSystemMessages(context: Context): Boolean =
        prefs(context).getBoolean(KEY_HIDE_SYSTEM, false)

    fun setHideSystemMessages(context: Context, hide: Boolean) {
        prefs(context).edit().putBoolean(KEY_HIDE_SYSTEM, hide).apply()
    }

    fun getHidePathTrace(context: Context): Boolean =
        prefs(context).getBoolean(KEY_HIDE_PATH, false)

    fun setHidePathTrace(context: Context, hide: Boolean) {
        prefs(context).edit().putBoolean(KEY_HIDE_PATH, hide).apply()
    }

    // Off by default -- the terminal keeps its existing (non-monospace)
    // look unless explicitly opted into from PROTOCOL.
    fun getMonospaceEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_MONOSPACE, false)

    fun setMonospaceEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_MONOSPACE, enabled).apply()
    }

    // Loads the persisted log, applying the current retention window so a
    // long-closed app doesn't reopen with a stretch of stale entries still
    // showing. Re-persists immediately when pruning actually drops anything.
    fun load(context: Context): List<LogEntry> {
        val raw = prefs(context).getString(KEY_LOG, null) ?: return emptyList()
        val decoded = try {
            json.decodeFromString<List<LogEntry>>(raw)
        } catch (e: Exception) {
            emptyList()
        }
        val pruned = pruneList(decoded, getRetentionDays(context))
        if (pruned.size != decoded.size) {
            persist(context, pruned)
        }
        return pruned
    }

    fun persist(context: Context, entries: List<LogEntry>) {
        prefs(context).edit().putString(KEY_LOG, json.encodeToString(entries)).apply()
    }

    // Prunes the live buffer in place (newest-first, so anything past
    // retention lives at the tail) and writes the result back to disk.
    // Called after every new entry so the on-disk copy never drifts far
    // from what's on screen.
    fun pruneAndPersist(context: Context, logs: SnapshotStateList<LogEntry>) {
        pruneInPlace(logs, getRetentionDays(context))
        persist(context, logs.toList())
    }

    // The retention slider on the Terminal screen calls this directly so a
    // shortened window takes effect immediately instead of waiting for the
    // next log line.
    fun applyRetention(context: Context, logs: SnapshotStateList<LogEntry>, days: Int) {
        setRetentionDays(context, days)
        pruneAndPersist(context, logs)
    }

    // /cls -- wipes the in-memory buffer and the on-disk copy together so
    // a cleared log actually stays cleared across a restart, not just
    // until the next addLog re-persists the old contents.
    fun clearAll(context: Context, logs: SnapshotStateList<LogEntry>) {
        logs.clear()
        persist(context, emptyList())
    }

    private fun pruneInPlace(logs: SnapshotStateList<LogEntry>, retentionDays: Int) {
        val cutoffMillis = System.currentTimeMillis() - retentionDays * DAY_MILLIS
        while (logs.isNotEmpty() && logs.last().epochMillis < cutoffMillis) {
            logs.removeAt(logs.lastIndex)
        }
        while (logs.size > MAX_ENTRIES) {
            logs.removeAt(logs.lastIndex)
        }
    }

    private fun pruneList(entries: List<LogEntry>, retentionDays: Int): List<LogEntry> {
        val cutoffMillis = System.currentTimeMillis() - retentionDays * DAY_MILLIS
        return entries.asSequence()
            .filter { it.epochMillis >= cutoffMillis }
            .take(MAX_ENTRIES)
            .toList()
    }
}
