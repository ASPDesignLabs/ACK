// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The words around WORD SUGGESTIONS say what it learns from, where that stays, and what it never learns from, as plainly as the switch itself. */
class WordSuggestionTextTest {

    @Test
    fun theSwitchSaysOnOrOffInWords_notOnlyByColour() {
        assertEquals("WORD SUGGESTIONS: ON", WordSuggestionText.switchLabel(true))
        assertEquals("WORD SUGGESTIONS: OFF", WordSuggestionText.switchLabel(false))
    }

    @Test
    fun theExplanation_saysItStartsEmpty_whatItLearnsFrom_andNothingIsInsertedWithoutATap() {
        val text = WordSuggestionText.SWITCH_EXPLANATION
        assertTrue(text.contains("STARTS EMPTY"))
        assertTrue(text.contains("SAVE, SPEAK OR COPY"))
        assertTrue(text.contains("UNTIL YOU TAP"))
        assertTrue(text.contains("TARGET COMPUTER"))
        assertTrue(text.contains("SHARED VARIABLES"))
    }

    @Test
    fun theExplanation_namesWhereItNeverLearns_andWhereTheWordsAreKept() {
        val text = WordSuggestionText.SWITCH_EXPLANATION
        for (never in listOf("EMERGENCY", "TERMINAL", "MANUAL OVERRIDE", "TAGS", "NUMBERS")) assertTrue(never, text.contains(never))
        assertTrue(text.contains("THIS PHONE"))
        assertTrue(text.contains("EXPORT .JSON"))
        assertTrue(text.contains("FORGET WORDS"))
    }

    @Test
    fun theOffer_saysNothingIsLearnedUnlessTheyTurnItOn_andHasTwoDistinctButtons() {
        val text = WordSuggestionText.OFFER_TEXT
        assertTrue(text.contains("NOTHING IS LEARNED"))
        assertTrue(text.contains("UNLESS YOU TURN IT ON"))
        assertNotEquals(WordSuggestionText.OFFER_TURN_ON, WordSuggestionText.OFFER_NOT_NOW)
    }

    @Test
    fun noWordingIsInLowerCase_theAppsHouseStyle() {
        val all = listOf(
            WordSuggestionText.switchLabel(true), WordSuggestionText.switchLabel(false), WordSuggestionText.SWITCH_EXPLANATION,
            WordSuggestionText.OFFER_TEXT, WordSuggestionText.OFFER_TURN_ON, WordSuggestionText.OFFER_NOT_NOW,
        )
        for (t in all) assertEquals(t.uppercase(), t)
    }

    // ---- FORGET WORDS --------------------------------------------------------------------------------------------------------

    @Test
    fun theCountLineSaysHowManyInWords_andNoneYetWhenEmpty() {
        assertEquals("WORDS LEARNED: NONE YET", WordSuggestionText.countLine(0))
        assertEquals("WORDS LEARNED: 1", WordSuggestionText.countLine(1))
        assertEquals("WORDS LEARNED: 1234", WordSuggestionText.countLine(1234))
    }

    @Test
    fun howOftenAWordWasUsed_isSingularOnlyForOne() {
        assertEquals("USED 1 TIME", WordSuggestionText.usedLine(1))
        assertEquals("USED 2 TIMES", WordSuggestionText.usedLine(2))
        assertEquals("USED 1000000 TIMES", WordSuggestionText.usedLine(1_000_000))
    }

    @Test
    fun forgettingOneWordSaysItCanBeLearnedAgain_andOffersTwoDistinctButtons() {
        assertTrue(WordSuggestionText.REMOVE_QUESTION.contains("LEARNED AGAIN"))
        assertNotEquals(WordSuggestionText.REMOVE, WordSuggestionText.REMOVE_CANCEL)
    }

    @Test
    fun forgettingAllAsksTwice_namesTheCount_theBackup_andWhatIsNotAffected() {
        val first = WordSuggestionText.forgetAllFirstConfirmation(3)
        val text = first.joinToString("\n")
        assertTrue(text.contains("ALL 3 LEARNED WORDS"))
        assertTrue(text.contains("EXPORT .JSON"))
        assertTrue(text.contains("TARGET COMPUTER"))
        assertTrue(text.contains("STAYS ON OR OFF"))
        assertTrue("files saved elsewhere are not touched, and it says so", StorageCatalogue.NOT_ELSEWHERE in first)
        assertTrue(WordSuggestionText.forgetAllFirstConfirmation(1).joinToString("\n").contains("THE 1 LEARNED WORD "))
        assertEquals("THIS CANNOT BE UNDONE.", WordSuggestionText.FORGET_ALL_SECOND)
    }

    @Test
    fun theForgetWordsWording_isInCapitals() {
        val all = listOf(
            WordSuggestionText.FORGET_BUTTON, WordSuggestionText.FORGET_TITLE, WordSuggestionText.FORGET_EMPTY,
            WordSuggestionText.REMOVE_QUESTION, WordSuggestionText.REMOVE, WordSuggestionText.REMOVE_CANCEL,
            WordSuggestionText.FORGET_ALL, WordSuggestionText.BACK_UP_FIRST, WordSuggestionText.CONTINUE, WordSuggestionText.CANCEL,
            WordSuggestionText.FORGET_ALL_SECOND, WordSuggestionText.countLine(0), WordSuggestionText.countLine(5),
            WordSuggestionText.usedLine(1), WordSuggestionText.usedLine(9),
        ) + WordSuggestionText.forgetAllFirstConfirmation(2)
        for (t in all) assertEquals(t.uppercase(), t)
    }
}
