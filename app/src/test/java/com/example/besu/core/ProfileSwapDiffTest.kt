// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * A person learns WHICH GESTURE SAYS WHAT by repetition. A profile can hold a different phrase for the same slot, so changing
 * profile can change what a practised gesture says, with no sign that it has. These tests pin what counts as a change, so the
 * warning appears when it should and, just as important, never when nothing would change.
 */
class ProfileSwapDiffTest {

    private fun slot(path: String, current: String, target: String, name: String = path) = SlotPhrases(path, name, current, target)

    private val twelve: List<SlotPhrases> = StarterSets.matrixPhrases.map { slot(it.path, it.phrase, it.phrase) }

    // ---- what counts as a change ------------------------------------------------------------------------------------------

    @Test
    fun noDifferences_meansNoChanges_andNoWarning() {
        val changes = ProfileSwapDiff.changes(twelve)
        assertTrue(changes.isEmpty())
        assertFalse(ProfileSwapDiff.shouldWarn(warningOn = true, changes = changes))
    }

    @Test
    fun oneDifference() {
        val slots = twelve.toMutableList().also { it[3] = slot("/std/id/3", "Hello.", "Goodbye.") }
        val changes = ProfileSwapDiff.changes(slots)
        assertEquals(listOf(SlotChange("/std/id/3", "/std/id/3", "Hello.", "Goodbye.")), changes)
    }

    @Test
    fun allTwelveDiffer() {
        val slots = twelve.map { slot(it.path, "before ${it.path}", "after ${it.path}") }
        assertEquals(12, ProfileSwapDiff.changes(slots).size)
    }

    @Test
    fun aCustomContextSlot_isIncludedLikeTheBuiltInOnes() {
        val slots = twelve + slot("/custom/WORK/1", "Yes.", "Sure.", "WORK / TWIST 0")
        val changes = ProfileSwapDiff.changes(slots)
        assertEquals(listOf("/custom/WORK/1"), changes.map { it.path })
        assertEquals("WORK / TWIST 0", changes.single().name)
    }

    @Test
    fun differingOnlyByLeadingOrTrailingWhiteSpace_isTheSame_becauseItIsSpokenTheSame() {
        assertTrue(ProfileSwapDiff.changes(listOf(slot("a", "Hello.", "  Hello. "))).isEmpty())
        assertTrue(ProfileSwapDiff.changes(listOf(slot("a", "Hello.\n", "Hello."))).isEmpty())
        assertTrue(ProfileSwapDiff.changes(listOf(slot("a", " Hello.", "Hello."))).isEmpty())
    }

    @Test
    fun anyOtherDifference_counts_includingCapitalisationAndPunctuation() {
        assertEquals(1, ProfileSwapDiff.changes(listOf(slot("a", "Hello.", "hello."))).size)
        assertEquals(1, ProfileSwapDiff.changes(listOf(slot("a", "Hello.", "Hello"))).size)
        assertEquals(1, ProfileSwapDiff.changes(listOf(slot("a", "Hello there.", "Hello  there."))).size)
        assertEquals(1, ProfileSwapDiff.changes(listOf(slot("a", "", "Hello."))).size)
    }

    @Test
    fun theChangesKeepTheOrderOfTheSlots_andTheOldAndNewPhrasesAsTheyAre() {
        val slots = listOf(slot("c", "1", "2"), slot("a", "x", "x"), slot("b", " old", "new "))
        val changes = ProfileSwapDiff.changes(slots)
        assertEquals(listOf("c", "b"), changes.map { it.path })
        // the phrases shown are the real ones, not trimmed copies
        assertEquals(" old", changes[1].oldPhrase)
        assertEquals("new ", changes[1].newPhrase)
    }

    @Test
    fun noSlotsAtAll_isNoChange() {
        assertTrue(ProfileSwapDiff.changes(emptyList()).isEmpty())
    }

    // ---- when the warning shows ---------------------------------------------------------------------------------------------

    @Test
    fun theWarningShowsOnlyWhenItIsOn_andSomethingWouldChange() {
        val some = listOf(SlotChange("a", "A", "x", "y"))
        assertTrue(ProfileSwapDiff.shouldWarn(warningOn = true, changes = some))
        assertFalse(ProfileSwapDiff.shouldWarn(warningOn = false, changes = some))
        assertFalse(ProfileSwapDiff.shouldWarn(warningOn = true, changes = emptyList()))
        assertFalse(ProfileSwapDiff.shouldWarn(warningOn = false, changes = emptyList()))
    }

    @Test
    fun reselectingTheProfileYouAreOn_isNeverAChangeToWarnAbout() {
        // The caller does not even ask: the same profile on both sides gives identical phrases for every slot.
        val slots = twelve.map { slot(it.path, "same ${it.path}", "same ${it.path}") }
        assertTrue(ProfileSwapDiff.changes(slots).isEmpty())
    }

    // ---- the words the dialog shows -------------------------------------------------------------------------------------------

    private fun change(i: Int, old: String = "old $i", new: String = "new $i") = SlotChange("p$i", "SLOT $i", old, new)

    @Test
    fun theHeading_countsTheGestures_andAgreesWithTheNumber() {
        assertEquals("1 GESTURE WILL SAY SOMETHING DIFFERENT IF YOU CHANGE TO WORK:", ProfileSwapText.heading(1, "WORK"))
        assertEquals("2 GESTURES WILL SAY SOMETHING DIFFERENT IF YOU CHANGE TO WORK:", ProfileSwapText.heading(2, "WORK"))
        assertEquals("12 GESTURES WILL SAY SOMETHING DIFFERENT IF YOU CHANGE TO HIGH_STRESS:", ProfileSwapText.heading(12, "HIGH_STRESS"))
    }

    @Test
    fun aFewChangesAreListed_theRestAreCounted() {
        val lines = ProfileSwapText.lines((1..9).map { change(it) })
        assertEquals(ProfileSwapText.MAX_LISTED + 1, lines.size)
        assertEquals("SLOT 1: old 1", lines[0].substringBefore(", becomes:"))
        assertTrue(lines[0].contains(", becomes: new 1"))
        assertEquals("AND ${9 - ProfileSwapText.MAX_LISTED} MORE", lines.last())
    }

    @Test
    fun exactlyAsManyAsFit_havingNoAndMoreLine() {
        val lines = ProfileSwapText.lines((1..ProfileSwapText.MAX_LISTED).map { change(it) })
        assertEquals(ProfileSwapText.MAX_LISTED, lines.size)
        assertTrue(lines.none { it.startsWith("AND ") })
    }

    @Test
    fun aVeryLongPhraseIsShortenedInTheMiddle_soTheDialogStaysReadable() {
        val long = "A".repeat(40) + "-the-important-end"
        val line = ProfileSwapText.lines(listOf(change(1, old = long, new = "short"))).single()
        assertTrue(line.length < long.length + 40)
        assertTrue("the end of the phrase is kept", line.contains("important-end"))
        assertTrue(line.contains("…"))
    }

    @Test
    fun aBlankPhrase_isShownAsBlank_notAsNothing() {
        val line = ProfileSwapText.lines(listOf(change(1, old = "", new = "Hello."))).single()
        assertTrue(line.contains("(BLANK)"))
        val line2 = ProfileSwapText.lines(listOf(change(1, old = "Hello.", new = "  "))).single()
        assertTrue(line2.contains("(BLANK)"))
    }

    @Test
    fun noChanges_giveNoLines() {
        assertTrue(ProfileSwapText.lines(emptyList()).isEmpty())
    }
}
