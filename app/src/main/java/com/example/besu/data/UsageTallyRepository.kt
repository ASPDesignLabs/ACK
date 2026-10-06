// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.util.Log
import com.example.besu.core.UsageCell
import com.example.besu.core.UsageKinds
import com.example.besu.core.UsageTally
import java.time.LocalDate
import java.time.ZoneId
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * The usage summary's counts, on this phone only (docs/USAGE_SUMMARY_DESIGN.md). The thin Android edge over core/UsageTally.kt, which holds every rule.
 *
 * Rules that must stay true (UsageSummaryWiringTest holds them):
 *  - **Nothing is written while the switch is off.** [recordMessage] checks it first.
 *  - **Counting can never change what is spoken.** The caller hands over the message's source tag and words and gets control back at once: the cell is worked out
 *    there (the words are compared in memory with the starter phrases and not kept), and the write happens on one background thread. Any failure is swallowed and
 *    logged as a fixed sentence, never a message. A thread that dies from an uncaught error would crash ACK, so the worker catches everything.
 *  - **The words are never kept**, not in a field, a queue, a log line or an error: only the cell (a date, an hour, a channel and a kind) goes to the worker.
 *  - **One whole number per cell**, stored under the cell's own name in a preference file of its own (core/UsageTally.PREFS_FILE). Old and unreadable counts are removed
 *    once a day, as counting goes on, by the core's rule.
 *  - **Reading changes nothing. Only [forgetAll] deletes,** and it is called only from the second confirmation.
 */
object UsageTallyRepository {
    private const val TAG = "ACK_USAGE"

    // Literal on purpose: the storage scan (StorageCatalogueTest) finds preference files by their literal names; a test keeps this equal to core/UsageTally.PREFS_FILE.
    private const val PREFS = "ack_usage_tally"

    private val lock = Any()
    private var worker: ExecutorService? = null
    private var lastPrunedOn: LocalDate? = null

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun executor(): ExecutorService = synchronized(lock) {
        worker ?: Executors.newSingleThreadExecutor { task -> Thread(task, "ack-usage-tally").apply { isDaemon = true } }.also { worker = it }
    }

    /**
     * Counts one message that was sent, if the switch is on. [source] is the tag the message carries (OutputService's `source`) and [text] its words, which are only
     * compared with the starter phrases here and then dropped. Never throws and never waits for the write.
     */
    fun recordMessage(context: Context, source: String, text: String, nowMillis: Long = System.currentTimeMillis()) {
        try {
            val app = context.applicationContext
            if (!AssistPrefs.isUsageSummaryOn(app)) return
            val cell = UsageTally.cellFor(nowMillis, ZoneId.systemDefault(), UsageKinds.channelOf(source), UsageKinds.kindOf(source, text))
            executor().execute {
                try {
                    add(app, cell)
                } catch (e: Throwable) {
                    Log.w(TAG, "a count could not be saved")
                }
            }
        } catch (e: Throwable) {
            Log.w(TAG, "a count was skipped")
        }
    }

    private fun add(context: Context, cell: UsageCell) {
        synchronized(lock) {
            val prefs = prefs(context)
            val key = cell.storageKey
            val edit = prefs.edit()
            edit.putInt(key, UsageTally.increment(prefs.getInt(key, 0)))
            // Once a day (and once after the process starts): drop what is older than the window or unreadable, and keep the store under its cap.
            if (lastPrunedOn != cell.date) {
                for (stale in UsageTally.keysToRemove(prefs.all.keys + key, cell.date)) edit.remove(stale)
                lastPrunedOn = cell.date
            }
            edit.apply()
        }
    }

    /** Every count, read from the file. A name that is not a count, or a value that is not a whole number, is skipped. Changes nothing. */
    fun load(context: Context): Map<UsageCell, Int> = synchronized(lock) {
        val counts = LinkedHashMap<UsageCell, Int>()
        for ((key, value) in prefs(context).all) {
            val cell = UsageCell.parse(key) ?: continue
            val n = value as? Int ?: continue
            counts[cell] = n
        }
        counts
    }

    /** How many counted messages the summary would show now, for a screen that asks only whether there is anything. */
    fun messageCount(context: Context): Long = UsageTally.summarise(load(context), LocalDate.now()).messages

    /**
     * Deletes every count. Called only from the second FORGET confirmation (and by DELETE DATA's own wipe, which clears the file itself). commit(), so it is gone
     * before the screen says so. Returns whether the file is empty afterwards.
     */
    fun forgetAll(context: Context): Boolean = synchronized(lock) {
        lastPrunedOn = null
        val p = prefs(context)
        p.edit().clear().commit() && p.all.isEmpty()
    }
}
