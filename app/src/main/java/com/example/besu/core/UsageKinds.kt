// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale

/**
 * Which channel and which kind a message counts under (docs/USAGE_SUMMARY_DESIGN.md, sections 2 and 4). Plain Kotlin so every mapping is tested without a phone.
 *
 * Rules that must stay true:
 *  - **A channel comes from the tag the message already carries** (`OutputService`'s `source`), by a closed table. A deck's or a button's own name (`MTX/<title>`) is
 *    never kept: the whole `MTX/` family is MATRIX. A tag not in the table is OTHER, so a new entry point is counted rather than lost, and a test makes it be added here.
 *  - **A kind comes from the words, matched in memory against ACK's own starter phrases and then thrown away** (except a partner card play, whose kind comes from its tag). The comparison ignores capital letters and spaces at either
 *    end and nothing else. No match is OTHER. Nothing is guessed about the person's own words, and the words are never kept.
 */
object UsageKinds {

    /** The channel a message sent with this `source` tag counts under. Tutorial narration (`HELP/...`) is never counted, so it is not here. */
    fun channelOf(source: String): UsageChannel = when {
        source.startsWith("MTX/") -> UsageChannel.MATRIX
        source == "QUICK_ACTION" -> UsageChannel.QUICK_ACTIONS
        source == "EMERGENCY" -> UsageChannel.EMERGENCY
        source == "TERM/PROMPT" -> UsageChannel.TERMINAL
        source == "TERM/INPUT" || source.startsWith("BANK/") -> UsageChannel.MANUAL_OVERRIDE // BANK/<tag>: a saved phrase played from Manual Override; the tag is the person's own and is never kept
        source.startsWith("COMPOSER/") -> UsageChannel.COMPOSER
        source == "LOG/REPLAY" || source == "CACHE/REPLAY" -> UsageChannel.REPLAY
        source == "HW/WATCH" -> UsageChannel.WATCH
        source == "M-KEY" -> UsageChannel.SHORTCUT
        source == "COMPUTER/CONTACT" -> UsageChannel.PEOPLE
        source == PartnerCard.SOURCE -> UsageChannel.PARTNER_CARD
        else -> UsageChannel.OTHER
    }

    /** The source tags the app sends today, that count as a message (every one of them maps to the channel named). A test reads the app's source and fails on a tag missing here. */
    val KNOWN_SOURCES: Map<String, UsageChannel> = mapOf(
        "MTX/*" to UsageChannel.MATRIX,
        "QUICK_ACTION" to UsageChannel.QUICK_ACTIONS,
        "EMERGENCY" to UsageChannel.EMERGENCY,
        "TERM/PROMPT" to UsageChannel.TERMINAL,
        "TERM/INPUT" to UsageChannel.MANUAL_OVERRIDE,
        "BANK/*" to UsageChannel.MANUAL_OVERRIDE,
        "COMPOSER/SPEAK" to UsageChannel.COMPOSER,
        "COMPOSER/BANK" to UsageChannel.COMPOSER,
        "LOG/REPLAY" to UsageChannel.REPLAY,
        "CACHE/REPLAY" to UsageChannel.REPLAY,
        "HW/WATCH" to UsageChannel.WATCH,
        "M-KEY" to UsageChannel.SHORTCUT,
        "COMPUTER/CONTACT" to UsageChannel.PEOPLE,
        "PARTNER/CARD" to UsageChannel.PARTNER_CARD,
    )

    /** The kind a starter function counts as. An exhaustive `when`: a new function fails the build until it is mapped here. */
    fun kindOf(function: StarterFunction): UsageKind = when (function) {
        StarterFunction.YES -> UsageKind.YES
        StarterFunction.NO -> UsageKind.NO
        StarterFunction.UNSURE -> UsageKind.UNSURE
        StarterFunction.HELP -> UsageKind.HELP
        StarterFunction.REPAIR -> UsageKind.REPAIR
        StarterFunction.TURN_HOLDING -> UsageKind.TURN_HOLDING
        StarterFunction.NAME_OR_ID -> UsageKind.NAME_OR_ID
        StarterFunction.BREAK -> UsageKind.BREAK
        StarterFunction.BOUNDARY -> UsageKind.BOUNDARY
        StarterFunction.SOCIAL -> UsageKind.SOCIAL
    }

    /** What a phrase is compared as: no capitals, no space at either end, nothing else changed. */
    fun normalised(text: String): String = text.trim().lowercase(Locale.ROOT)

    /** Every starter phrase, with its kind, from the two starter sets. */
    val starterPhrases: List<Pair<String, UsageKind>> =
        StarterSets.matrixPhrases.map { it.phrase to kindOf(it.function) } +
            StarterSets.quickActionsGroups.flatMap { group -> group.slots.map { it.phrase to kindOf(it.function) } }

    private val byPhrase: Map<String, UsageKind> = starterPhrases.associate { normalised(it.first) to it.second }

    /** The kind of a message with these words: a starter's kind where the words are exactly a starter phrase, otherwise OTHER. The words are not kept. */
    fun kindOf(text: String): UsageKind = byPhrase[normalised(text)] ?: UsageKind.OTHER

    /**
     * The kind of a message sent with this `source` tag and these words. A play of the partner card is PARTNER_CARD **whatever its words say** (the developer's decision, and it keeps the person's own
     * sentences out of the starter match: one that happens to read "Yes." is still the card). Every other message is decided by its words, as [kindOf] says.
     */
    fun kindOf(source: String, text: String): UsageKind = if (source == PartnerCard.SOURCE) UsageKind.PARTNER_CARD else kindOf(text)
}
