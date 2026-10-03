// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Restoring a backup onto a phone that was given the starter phrases.
 *
 * A backup never records a phrase that was left at the built-in text, so a restore from a phone that had no starters would
 * leave the starters showing where that phone showed the built-in wording. A restore is additive (it never deletes what the
 * file does not mention), with one narrow exception decided here: a starter phrase the person has NEVER edited is not their
 * data, so it can be taken back. Anything edited, anything the file mentions, and anything in another deck is never touched.
 */
class StarterRestoreTest {

    private val allSeeded: List<SeededPhrase> = StarterRestore.seededPhrases(
        StarterSets.matrixPhrases.associate { StarterSets.recordKey(it.path) to it.phrase }
    )

    /** What the twelve DEFAULT-deck keys hold when nothing has been edited. */
    private val untouched: Map<String, String> = allSeeded.associate { it.storageKey to it.text }

    private fun takeBack(
        current: Map<String, String> = untouched,
        backupKeys: Set<String> = emptySet(),
        marker: Boolean? = null,
        seeded: List<SeededPhrase> = allSeeded
    ) = StarterRestore.toTakeBack(seeded, current, backupKeys, marker).map { it.storageKey }

    // ---- the note the seed keeps -------------------------------------------------------------------------------------

    @Test
    fun theNote_becomesOneSeededPhrasePerPhrase_keyedByTheDefaultDecksStorageKey() {
        assertEquals(12, allSeeded.size)
        assertEquals(StarterSets.matrixPhrases.map { it.path }, allSeeded.map { it.storageKey })
        assertEquals(StarterSets.matrixPhrases.map { StarterSets.recordKey(it.path) }, allSeeded.map { it.recordKey })
        assertEquals(StarterSets.matrixPhrases.map { it.phrase }, allSeeded.map { it.text })
    }

    @Test
    fun anEntryThatIsNotOursOrNotTextInTheNote_isIgnored() {
        val note: Map<String, Any> = mapOf(
            "seeded:/std/id/0" to "Yes.",
            "seeded:/std/id/99" to "Not a slot.",   // not one of the twelve
            "seeded:/std/id/1" to 5,                 // not text
            "unrelated" to "x",
        )
        val seeded = StarterRestore.seededPhrases(note)
        assertEquals(listOf("/std/id/0"), seeded.map { it.storageKey })
    }

    @Test
    fun anEmptyNote_meansNothingWasSeeded() {
        assertTrue(StarterRestore.seededPhrases(emptyMap<String, String>()).isEmpty())
    }

    // ---- which starters are taken back -------------------------------------------------------------------------------

    @Test
    fun anOlderBackup_takesBackEveryStarterTheFileDoesNotMentionAndThePersonNeverEdited() {
        assertEquals(untouched.keys.toList(), takeBack(marker = null))
    }

    @Test
    fun aBackupFromAPhoneThatHadNoStarters_isTreatedTheSameAsAnOlderOne() {
        assertEquals(untouched.keys.toList(), takeBack(marker = false))
    }

    @Test
    fun aBackupFromAPhoneThatHadTheStarters_takesNothingBack() {
        assertTrue(takeBack(marker = true).isEmpty())
    }

    @Test
    fun aStarterThePersonEdited_isKept() {
        val edited = untouched + ("/std/id/0" to "Yes, please.")
        val taken = takeBack(current = edited)
        assertEquals(11, taken.size)
        assertTrue("/std/id/0" !in taken)
    }

    @Test
    fun aStarterTheFileMentions_isKept_becauseTheFileWinsAnyway() {
        val taken = takeBack(backupKeys = setOf("/std/def/1"))
        assertEquals(11, taken.size)
        assertTrue("/std/def/1" !in taken)
    }

    @Test
    fun aKeyForAnotherDeck_isNeverTouched_evenIfItHoldsTheSameText() {
        val current = untouched + ("DECK_1_/std/id/0" to "Yes.") + ("WORK_/std/id/0" to "Yes.")
        val taken = takeBack(current = current)
        assertEquals(12, taken.size)
        assertTrue(taken.none { it.startsWith("DECK_") || it.startsWith("WORK_") })
    }

    @Test
    fun aStarterTheSeedWroteButIsNoLongerStored_hasNothingToTakeBack() {
        val taken = takeBack(current = untouched - "/std/con/2")
        assertEquals(11, taken.size)
        assertTrue("/std/con/2" !in taken)
    }

    @Test
    fun aDifferenceOfASingleSpace_countsAsAnEdit() {
        val taken = takeBack(current = untouched + ("/std/id/0" to "Yes. "))
        assertTrue("/std/id/0" !in taken)
    }

    @Test
    fun aDifferenceOfCapitalisation_countsAsAnEdit() {
        val taken = takeBack(current = untouched + ("/std/id/0" to "yes."))
        assertTrue("/std/id/0" !in taken)
    }

    @Test
    fun aMixOfEditedMentionedAndUntouched_takesBackOnlyTheUntouched() {
        val current = untouched + ("/std/id/1" to "Hi.") + ("/std/id/2" to "Again, please.")
        val taken = takeBack(current = current, backupKeys = setOf("/std/id/2", "/std/def/0"))
        // id/1 edited, id/2 edited AND mentioned, def/0 mentioned: three kept, nine taken back
        assertEquals(9, taken.size)
        assertTrue(listOf("/std/id/1", "/std/id/2", "/std/def/0").none { it in taken })
    }

    @Test
    fun withNothingSeeded_nothingIsTakenBack() {
        assertTrue(takeBack(seeded = emptyList()).isEmpty())
    }

    @Test
    fun theKeyOfAnotherDecksPhraseInTheFile_doesNotSaveADefaultDeckStarter() {
        // The file mentions DECK_1's phrase, not the DEFAULT deck's: the DEFAULT starter is still untouched.
        val taken = takeBack(backupKeys = setOf("DECK_1_/std/id/0"))
        assertEquals(12, taken.size)
    }

    @Test
    fun whatIsTakenBack_carriesTheRecordKeyToForgetToo() {
        val taken = StarterRestore.toTakeBack(allSeeded, untouched, emptySet(), null)
        assertEquals(StarterSets.recordKeys, taken.map { it.recordKey }.toSet())
    }
}
