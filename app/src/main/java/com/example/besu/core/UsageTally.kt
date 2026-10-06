// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

/** Where a counted message came from. A fixed list: a deck's or a button's own name is never kept (see [UsageKinds.channelOf]). */
enum class UsageChannel { MATRIX, QUICK_ACTIONS, EMERGENCY, TERMINAL, MANUAL_OVERRIDE, COMPOSER, REPLAY, WATCH, SHORTCUT, PEOPLE, OTHER }

/** What kind of message was sent: the ten kinds of ACK's own starter phrases (core/StarterSets.kt), or OTHER. A fixed list. */
enum class UsageKind { YES, NO, UNSURE, HELP, REPAIR, TURN_HOLDING, NAME_OR_ID, BREAK, BOUNDARY, SOCIAL, OTHER }

/**
 * One counted cell: a local date, an hour of that day, a channel and a kind. **There is no text field here, and none may be added**: the usage summary never holds a
 * word of a message (UsageSummaryWiringTest fails if a text-like field appears). [storageKey] is the name the count is stored under.
 */
data class UsageCell(val date: LocalDate, val hour: Int, val channel: UsageChannel, val kind: UsageKind) {
    init {
        require(hour in 0..23) { "hour $hour is not an hour of the day" }
    }

    /** `2026-10-06|14|MATRIX|YES`: Latin digits, every part from a fixed list. */
    val storageKey: String get() = "$date|${hour.toString().padStart(2, '0')}|${channel.name}|${kind.name}"

    companion object {
        /** Reads a stored name back, or null for anything that is not exactly one (never throws: a damaged key is simply not a count). */
        fun parse(key: String): UsageCell? {
            val parts = key.split('|')
            if (parts.size != 4) return null
            return try {
                val hourText = parts[1]
                if (hourText.length != 2 || !hourText.all { it in '0'..'9' }) return null
                if (parts[0].length != 10) return null // exactly yyyy-MM-dd: a signed or longer year is damage, not a date we wrote
                val date = LocalDate.parse(parts[0])
                if (date.toString() != parts[0]) return null
                UsageCell(date, hourText.toInt(), UsageChannel.valueOf(parts[2]), UsageKind.valueOf(parts[3]))
            } catch (e: Exception) {
                null
            }
        }
    }
}

/** One day's total, for the last-days list. */
data class UsageDay(val date: LocalDate, val messages: Long)

/** What SETTINGS shows: totals for the kept period, by kind, channel and hour of the day, and the last days one by one. */
class UsageSummary(
    val messages: Long,
    /** How many different dates have any count. */
    val daysWithCounts: Int,
    val firstDate: LocalDate?,
    val lastDate: LocalDate?,
    val byKind: Map<UsageKind, Long>,
    val byChannel: Map<UsageChannel, Long>,
    /** 24 totals, hour 0 first. */
    val byHour: List<Long>,
    /** The last [UsageTally.RECENT_DAYS] days, today first, a day with nothing counted included as zero. */
    val recent: List<UsageDay>,
)

/**
 * The usage summary's rules (tracker row C1; the design is docs/USAGE_SUMMARY_DESIGN.md): which date and hour a message falls in, how long counts are kept, how
 * big the store may grow, and the totals SETTINGS and the saved file show. Plain Kotlin (no `android.*`) so every rule is tested without a phone.
 *
 * Rules that must stay true:
 *  - **Counts only.** Nothing here can hold a word of a message, a name, a place or an exact time (the hour is the finest it gets).
 *  - **Kept for [RETENTION_DAYS] days**: today and the days before it. Older counts are dropped as new ones are added. If the store ever passed [MAX_ROWS], the oldest
 *    whole days go first.
 *  - **Local time**: the date and hour are the phone's own at the moment the message was sent.
 */
object UsageTally {
    /** The preference file the counts live in (data/UsageTallyRepository.kt keeps the same literal, which the storage scan needs; a test keeps them equal). */
    const val PREFS_FILE = "ack_usage_tally"

    const val RETENTION_DAYS = 90
    const val RECENT_DAYS = 14

    /** A hard ceiling on the number of stored counts. A real person stays far below it; it only stops a fault from growing the file without end. */
    const val MAX_ROWS = 20_000

    /** The cell a message sent at [epochMillis] counts in, on a phone set to [zone]. */
    fun cellFor(epochMillis: Long, zone: ZoneId, channel: UsageChannel, kind: UsageKind): UsageCell {
        val time = Instant.ofEpochMilli(epochMillis).atZone(zone)
        return UsageCell(time.toLocalDate(), time.hour, channel, kind)
    }

    /** The oldest date still kept when today is [today]: today and the [RETENTION_DAYS] - 1 days before it. A count on that date is kept; one a day older is not. */
    fun oldestKept(today: LocalDate): LocalDate = today.minusDays((RETENTION_DAYS - 1).toLong())

    /**
     * One more message in a cell that already holds [current]. It stops at the largest whole number rather than wrapping to a negative count, and a damaged
     * (negative) stored value starts again from one.
     */
    fun increment(current: Int): Int = when {
        current < 0 -> 1
        current >= Int.MAX_VALUE -> Int.MAX_VALUE
        else -> current + 1
    }

    /**
     * The stored names to remove now: any that is not a readable count, any older than the window, and then, if more than [maxRows] remain, whole days from the
     * oldest until the rest fit. A day is never cut in half, so a day that is shown is complete.
     */
    fun keysToRemove(keys: Collection<String>, today: LocalDate, maxRows: Int = MAX_ROWS): Set<String> {
        val remove = HashSet<String>()
        val cutoff = oldestKept(today)
        val keep = ArrayList<Pair<LocalDate, String>>()
        for (key in keys) {
            val cell = UsageCell.parse(key)
            if (cell == null || cell.date < cutoff) remove += key else keep += cell.date to key
        }
        if (keep.size > maxRows) {
            var left = keep.size
            for ((_, group) in keep.groupBy({ it.first }, { it.second }).toSortedMap()) {
                if (left <= maxRows) break
                remove += group
                left -= group.size
            }
        }
        return remove
    }

    /** The totals for the counts that fall in the window ending [today]. [counts] may hold anything; a cell older than the window is ignored. */
    fun summarise(counts: Map<UsageCell, Int>, today: LocalDate): UsageSummary {
        val cutoff = oldestKept(today)
        val kept = counts.filter { (cell, n) -> cell.date >= cutoff && n > 0 }
        val byKind = LinkedHashMap<UsageKind, Long>()
        val byChannel = LinkedHashMap<UsageChannel, Long>()
        val byHour = LongArray(24)
        val byDate = HashMap<LocalDate, Long>()
        var total = 0L
        for ((cell, n) in kept) {
            val count = n.toLong()
            total += count
            byKind[cell.kind] = (byKind[cell.kind] ?: 0L) + count
            byChannel[cell.channel] = (byChannel[cell.channel] ?: 0L) + count
            byHour[cell.hour] += count
            byDate[cell.date] = (byDate[cell.date] ?: 0L) + count
        }
        val recent = (0 until RECENT_DAYS).map { back -> today.minusDays(back.toLong()).let { UsageDay(it, byDate[it] ?: 0L) } }
        return UsageSummary(
            messages = total,
            daysWithCounts = byDate.size,
            firstDate = byDate.keys.minOrNull(),
            lastDate = byDate.keys.maxOrNull(),
            byKind = UsageKind.values().filter { byKind.containsKey(it) }.associateWith { byKind.getValue(it) },
            byChannel = UsageChannel.values().filter { byChannel.containsKey(it) }.associateWith { byChannel.getValue(it) },
            byHour = byHour.toList(),
            recent = recent,
        )
    }
}
