// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/** One starter phrase to save: under [storageKey] in `ack_matrix_config`, noted under [recordKey] in the seed's own record. */
data class PhraseWrite(val storageKey: String, val phrase: String, val recordKey: String)

/**
 * Decides what the starter seed writes, before any file is touched, so the rules are tested without a phone and the Android
 * edge (data/StarterSeed.kt) only has to carry them out.
 *
 * The seed's one rule: write nothing that is already there. A key that exists, whatever it holds, belongs to the person (or
 * to an earlier, interrupted seed) and is left alone.
 */
object StarterSeedPlan {

    /** The Matrix phrases to save for [deckId] under [profile], skipping every key in [existingKeys]. */
    fun phraseWrites(deckId: String, profile: String, existingKeys: Set<String>): List<PhraseWrite> =
        StarterSets.matrixPhrases
            .map { PhraseWrite(PhraseKeys.storageKey(deckId, profile, it.path), it.phrase, StarterSets.recordKey(it.path)) }
            .filter { it.storageKey !in existingKeys }

    /**
     * The STARTERS Quick Actions deck is made once: not if a deck with its id already exists. A saved layout with no deck is what an
     * interrupted seed leaves, so that case is finished, not skipped.
     */
    fun shouldCreateQuickActionsDeck(existingDeckIds: Set<String>): Boolean =
        StarterSets.QUICK_ACTIONS_DECK_ID !in existingDeckIds
}
