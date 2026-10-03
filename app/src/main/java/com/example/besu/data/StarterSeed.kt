// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.util.Log
import com.example.besu.core.StarterSeedPlan
import com.example.besu.core.StarterSets
import com.example.besu.decks.QuickActionGroup
import com.example.besu.decks.QuickActionSlot
import com.example.besu.decks.QuickActionsDeckConfig

/**
 * Writes the neutral starter phrases (core/StarterSets.kt) for a NEW install, so it opens with wording that suits anyone
 * instead of the developer's own. The thin Android edge: WHAT to write is decided in core/StarterSeedPlan.kt (tested); this
 * only carries it out. Never throws: a failure is logged and the app carries on with its old built-in wording.
 *
 * The rules that keep this safe (see CLAUDE.md, STARTER PHRASES):
 *  - It SAVES values. It never edits CommandRepository.BASE_TEMPLATE, because a button with no saved value falls back to that
 *    text and editing it would silently change what an existing person's untouched buttons say.
 *  - It writes nothing that is already there.
 *  - It runs for a fresh install (InstallState.ensureRecorded), after DELETE DATA > MESSAGES AND DECKS, and for a new Matrix deck
 *    on a phone that was seeded. It never runs for an install that already existed, and never after a SETTINGS wipe.
 *  - For the DEFAULT deck it notes, in its own small file, each phrase it wrote and the text it wrote. That note is what lets a
 *    restore of an older backup take back only the starters the person never edited (core/StarterRestore.kt).
 *    A new Matrix deck's starters are not noted: such a deck did not exist when an older backup was made.
 */
object StarterSeed {
    private const val TAG = "ACK_STARTER_SEED"

    // Literal on purpose: the storage scan (StorageCatalogueTest) finds preference files by their literal names, and
    // StarterSeedWiringTest checks these two equal StarterSets.RECORD_FILE and StarterSets.MATRIX_FILE.
    private const val PREFS_NAME = "ack_starter_seed"
    private const val MATRIX_PREFS = "ack_matrix_config"

    /** A fresh install: the twelve Matrix phrases for the DEFAULT deck, noted, and the STARTERS Quick Actions deck. */
    fun seedFreshInstall(context: Context) {
        try {
            writePhrases(context, deckId = "DEFAULT", noteThem = true)
        } catch (e: Exception) {
            Log.e(TAG, "could not seed the starter phrases", e)
        }
        try {
            seedStartersDeck(context)
        } catch (e: Exception) {
            Log.e(TAG, "could not seed the STARTERS deck", e)
        }
    }

    /**
     * DELETE DATA > MESSAGES AND DECKS (also part of DELETE EVERYTHING): the Matrix phrases are saved again so a wiped phone does
     * not fall back to the developer's own built-in wording. The STARTERS deck is only made on a brand-new install.
     */
    fun seedAfterWipe(context: Context) {
        try {
            writePhrases(context, deckId = "DEFAULT", noteThem = true)
        } catch (e: Exception) {
            Log.e(TAG, "could not seed the starter phrases after a wipe", e)
        }
    }

    /** A Matrix deck the person just made, on a phone that began with the starters: it begins with them too. */
    fun seedNewMatrixDeck(context: Context, deckId: String) {
        if (!wasSeeded(context)) return
        try {
            writePhrases(context, deckId = deckId, noteThem = false)
        } catch (e: Exception) {
            Log.e(TAG, "could not seed the starter phrases for a new deck", e)
        }
    }

    /**
     * True if this phone was given the starter phrases (its note exists). A phone that already had ACK when this was added has no
     * note, and never will. Read only: it creates nothing.
     */
    fun wasSeeded(context: Context): Boolean =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).all.keys.any { it in StarterSets.recordKeys }

    private fun writePhrases(context: Context, deckId: String, noteThem: Boolean) {
        val matrix = context.getSharedPreferences(MATRIX_PREFS, Context.MODE_PRIVATE)
        val writes = StarterSeedPlan.phraseWrites(deckId, "DEFAULT", matrix.all.keys)
        if (writes.isEmpty()) return

        if (noteThem) {
            // The note goes first, so an interruption can leave a note with no phrase (harmless) but never a phrase with no note.
            val note = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit()
            writes.forEach { note.putString(it.recordKey, it.phrase) }
            if (!note.commit()) Log.e(TAG, "the note of what was seeded could not be saved")
        }
        val edit = matrix.edit()
        writes.forEach { edit.putString(it.storageKey, it.phrase) }
        if (!edit.commit()) Log.e(TAG, "the starter phrases could not be saved")
    }

    private fun seedStartersDeck(context: Context) {
        val existingIds = CommandRepository.getDecks(context).map { it.id }.toSet()
        if (!StarterSeedPlan.shouldCreateQuickActionsDeck(existingIds)) return

        val config = QuickActionsDeckConfig(
            deckId = StarterSets.QUICK_ACTIONS_DECK_ID,
            groups = StarterSets.quickActionsGroups.mapIndexed { groupIndex, group ->
                QuickActionGroup(
                    groupIndex = groupIndex,
                    label = group.label,
                    slots = group.slots.mapIndexed { slotIndex, slot ->
                        QuickActionSlot(slotIndex = slotIndex, label = slot.label, template = slot.phrase)
                    }
                )
            }
        )
        // The layout first, then the deck that points at it: an interruption between them leaves a layout nobody can see, and the
        // next run finishes the job (it only asks whether the deck exists).
        CommandRepository.saveQuickActionsConfig(context, config)
        CommandRepository.upsertDeck(
            context,
            DeckMeta(
                id = StarterSets.QUICK_ACTIONS_DECK_ID,
                name = StarterSets.QUICK_ACTIONS_DECK_NAME,
                colorIndex = 0,
                type = DeckType.QUICK_ACTIONS
            )
        )
        // Both repository calls save in the background (apply). An empty commit() on the same file waits for those writes, so the
        // deck is on disk before InstallState writes its "recorded" flag. Read from the SharedPreferences contract; not observed
        // on a device.
        context.getSharedPreferences(MATRIX_PREFS, Context.MODE_PRIVATE).edit().commit()
    }
}
