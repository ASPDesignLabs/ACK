// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import kotlinx.serialization.Serializable

/**
 * What the person chose for the partner card (core/PartnerCard.kt): which of its seven sentences are on, and the words of the one or two sentences they wrote themselves. Plain Kotlin (no
 * `android.*`) so every rule is tested without a phone; data/PartnerCardRepository.kt keeps it in `ack_partner_card`.
 *
 * Rules that must stay true:
 *  - **Nothing stored means the card as it always was**: all five built-in sentences on, no own sentence. A person who never opens the choice hears exactly the card they chose.
 *  - **An own sentence is on when it is written** (a new or changed sentence is turned on, so the person never writes one and finds it silent), and can be turned off like any other.
 *  - **A slot with nothing written is never on**, whatever is stored, and toggling it does nothing.
 *  - **Stored values are read strictly and never throw**: a damaged "off" list or an overlong sentence is cleaned, not trusted and not a crash.
 */
class PartnerCardSettings private constructor(
    /** The own sentences, always [PartnerCard.OWN_SLOTS] long, each already cleaned ([PartnerCard.cleanOwn]); an empty string is an empty slot. */
    val own: List<String>,
    /** The slots (0 to [PartnerCard.SLOT_COUNT] - 1) the person turned off. */
    val off: Set<Int>,
) {
    fun isOn(slot: Int): Boolean = when {
        slot !in 0 until PartnerCard.SLOT_COUNT -> false
        slot in off -> false
        slot >= PartnerCard.BUILT_IN_COUNT -> own[slot - PartnerCard.BUILT_IN_COUNT].isNotEmpty()
        else -> true
    }

    /** Whether anything at all would be said: at least one sentence that is written and on. */
    val anyOn: Boolean get() = (0 until PartnerCard.SLOT_COUNT).any { isOn(it) }

    /** This slot turned on if it was off and off if it was on. An own slot with nothing written is left as it is. */
    fun toggled(slot: Int): PartnerCardSettings = when {
        slot !in 0 until PartnerCard.SLOT_COUNT -> this
        slot >= PartnerCard.BUILT_IN_COUNT && own[slot - PartnerCard.BUILT_IN_COUNT].isEmpty() -> this
        slot in off -> PartnerCardSettings(own, off - slot)
        else -> PartnerCardSettings(own, off + slot)
    }

    /** Own slot [slot] (5 or 6) holding [raw], cleaned. A sentence that changes is turned on; an emptied slot is left off, so the next sentence written there starts on. */
    fun withOwn(slot: Int, raw: String): PartnerCardSettings {
        if (slot !in PartnerCard.BUILT_IN_COUNT until PartnerCard.SLOT_COUNT) return this
        val n = slot - PartnerCard.BUILT_IN_COUNT
        val cleaned = PartnerCard.cleanOwn(raw)
        if (cleaned == own[n]) return this
        val next = own.toMutableList().also { it[n] = cleaned }
        return PartnerCardSettings(next, off - slot)
    }

    /** The values to store: `own_1`, `own_2` and `off` (the off slots as comma-separated numbers). Nothing else. */
    fun toStored(): Map<String, String> = mapOf(KEY_OWN_1 to own[0], KEY_OWN_2 to own[1], KEY_OFF to formatOff(off))

    companion object {
        const val PREFS_FILE = "ack_partner_card"
        const val KEY_OWN_1 = "own_1"
        const val KEY_OWN_2 = "own_2"
        const val KEY_OFF = "off"

        /** What nothing stored means: the five built-in sentences on, no sentence of the person's own. */
        val DEFAULT = PartnerCardSettings(List(PartnerCard.OWN_SLOTS) { "" }, emptySet())

        private fun make(own: List<String>, off: Set<Int>): PartnerCardSettings =
            PartnerCardSettings(
                List(PartnerCard.OWN_SLOTS) { PartnerCard.cleanOwn(own.getOrNull(it).orEmpty()) },
                off.filterTo(HashSet()) { it in 0 until PartnerCard.SLOT_COUNT },
            )

        /** Reads what is stored, each value optional. Anything that is not a clean value is cleaned or ignored; this never throws. */
        fun fromStored(own1: String?, own2: String?, off: String?): PartnerCardSettings = make(listOf(own1.orEmpty(), own2.orEmpty()), parseOff(off))

        /** "0,3,5" as a set of slots. Anything that is not a whole slot number is skipped. */
        fun parseOff(stored: String?): Set<Int> {
            if (stored.isNullOrBlank()) return emptySet()
            val slots = HashSet<Int>()
            for (part in stored.split(',')) {
                val t = part.trim()
                if (t.length in 1..2 && t.all { it in '0'..'9' }) t.toInt().takeIf { it in 0 until PartnerCard.SLOT_COUNT }?.let { slots += it }
            }
            return slots
        }

        fun formatOff(off: Set<Int>): String = off.filter { it in 0 until PartnerCard.SLOT_COUNT }.sorted().joinToString(",")

        /**
         * A restore ADDS: each sentence the backup holds that this phone does not already have goes into an empty slot of this phone, in order. A slot that already holds a sentence is never
         * overwritten (the person may have written it since), a sentence this phone already has is not added twice, and one that finds no empty slot is not added. The on/off choices are this
         * phone's own and are not touched.
         */
        fun mergeOwn(device: PartnerCardSettings, backupOwn: List<String>): PartnerCardSettings {
            val incoming = backupOwn.map { PartnerCard.cleanOwn(it) }.filter { it.isNotEmpty() }.distinct().filter { it !in device.own }
            if (incoming.isEmpty()) return device
            val next = device.own.toMutableList()
            val queue = incoming.iterator()
            for (n in next.indices) if (next[n].isEmpty() && queue.hasNext()) next[n] = queue.next()
            return PartnerCardSettings(next, device.off)
        }
    }

    override fun equals(other: Any?): Boolean = other is PartnerCardSettings && other.own == own && other.off == off
    override fun hashCode(): Int = 31 * own.hashCode() + off.hashCode()
}

/**
 * The part of EXPORT .JSON that holds the partner card: the person's own sentences, and nothing else (the on/off choices are this phone's own and the built-in sentences are in the app). It holds
 * words the person wrote, so EXPORT .JSON names it in its warning (core/ExportContents.kt). Restore only adds (see [PartnerCardSettings.mergeOwn]).
 */
@Serializable
data class PartnerCardBackup(val ownSentences: List<String> = emptyList()) {
    /**
     * Why this cannot be restored, or null. Every reason holds sizes only, never a sentence: what the person wrote does not go into a log. A sentence is checked against the same rule the
     * screen uses ([PartnerCard.cleanOwn]), so a file the app itself wrote always passes.
     */
    fun validate(): String? {
        if (ownSentences.size > PartnerCard.OWN_SLOTS) return "partnerCard ownSentences has ${ownSentences.size} entries (at most ${PartnerCard.OWN_SLOTS})"
        for ((i, sentence) in ownSentences.withIndex()) {
            if (sentence.length > PartnerCard.MAX_OWN_LENGTH) return "partnerCard ownSentences[$i] is ${sentence.length} characters (at most ${PartnerCard.MAX_OWN_LENGTH})"
            if (PartnerCard.cleanOwn(sentence) != sentence) return "partnerCard ownSentences[$i] is not one line of plain text (${sentence.length} characters)"
        }
        return null
    }
}
