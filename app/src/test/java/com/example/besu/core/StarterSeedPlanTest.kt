// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the starter seed writes, decided before any file is touched: all twelve phrases on an empty deck, never anything that
 * is already there, always through the repository's own key function.
 */
class StarterSeedPlanTest {

    @Test
    fun anEmptyDeck_getsAllTwelvePhrases() {
        val writes = StarterSeedPlan.phraseWrites("DEFAULT", "DEFAULT", emptySet())
        assertEquals(12, writes.size)
        assertEquals(StarterSets.matrixPhrases.map { it.phrase }, writes.map { it.phrase })
    }

    @Test
    fun theDefaultDeck_isWrittenUnderTheBarePaths() {
        val writes = StarterSeedPlan.phraseWrites("DEFAULT", "DEFAULT", emptySet())
        assertEquals(StarterSets.matrixPhrases.map { it.path }, writes.map { it.storageKey })
    }

    @Test
    fun aKeyThatIsAlreadyThere_isNeverWrittenOver() {
        val writes = StarterSeedPlan.phraseWrites("DEFAULT", "DEFAULT", setOf("/std/id/0", "/std/def/2"))
        assertEquals(10, writes.size)
        assertFalse(writes.any { it.storageKey == "/std/id/0" || it.storageKey == "/std/def/2" })
    }

    @Test
    fun whenEverythingIsAlreadyThere_nothingIsWritten() {
        val all = StarterSets.matrixPhrases.map { it.path }.toSet()
        assertTrue(StarterSeedPlan.phraseWrites("DEFAULT", "DEFAULT", all).isEmpty())
    }

    @Test
    fun aNewDeck_isWrittenUnderItsOwnPrefix_withTheDefaultProfile() {
        val writes = StarterSeedPlan.phraseWrites("DECK_77", "DEFAULT", emptySet())
        assertEquals("DECK_77_/std/id/0", writes.first().storageKey)
        assertEquals(12, writes.size)
    }

    @Test
    fun aKeyForAnotherDeck_doesNotCountAsAlreadyThere() {
        val writes = StarterSeedPlan.phraseWrites("DECK_77", "DEFAULT", setOf("/std/id/0", "DECK_78_/std/id/0"))
        assertEquals(12, writes.size)
    }

    @Test
    fun eachWrite_carriesTheRecordKeyTheRestoreRuleLooksUp() {
        val writes = StarterSeedPlan.phraseWrites("DEFAULT", "DEFAULT", emptySet())
        assertEquals(StarterSets.matrixPhrases.map { StarterSets.recordKey(it.path) }, writes.map { it.recordKey })
    }

    @Test
    fun theQuickActionsDeckIsOnlyMadeOnce() {
        assertTrue(StarterSeedPlan.shouldCreateQuickActionsDeck(existingDeckIds = emptySet()))
        assertFalse(StarterSeedPlan.shouldCreateQuickActionsDeck(setOf(StarterSets.QUICK_ACTIONS_DECK_ID)))
        assertTrue(StarterSeedPlan.shouldCreateQuickActionsDeck(setOf("DECK_1", "DEFAULT")))
    }

    @Test
    fun aDeckThatIsMissingIsMadeEvenIfItsLayoutWasSavedBeforeAnInterruption() {
        // The seed saves the layout, then the deck. If it stopped in between, only the deck is missing: the next run finishes it.
        // So the decision depends on the deck list alone, never on whether the layout key exists.
        assertTrue(StarterSeedPlan.shouldCreateQuickActionsDeck(setOf("DEFAULT")))
    }
}
