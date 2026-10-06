// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The words around WORD SUGGESTIONS say what it learns from, where that stays, and what it never learns from, as plainly as the switch itself. */
class WordSuggestionTextTest {

    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val t = EnglishText

    @Test
    fun theSwitchSaysOnOrOffInWords_notOnlyByColour() {
        assertEquals("WORD SUGGESTIONS: ON", WordSuggestionText.switchLabel(t, true))
        assertEquals("WORD SUGGESTIONS: OFF", WordSuggestionText.switchLabel(t, false))
    }

    @Test
    fun theExplanation_saysItStartsEmpty_whatItLearnsFrom_andNothingIsInsertedWithoutATap() {
        val text = WordSuggestionText.explanation(t)
        assertTrue(text.contains("STARTS EMPTY"))
        assertTrue(text.contains("SAVE, SPEAK OR COPY"))
        assertTrue(text.contains("UNTIL YOU TAP"))
        assertTrue(text.contains("TARGET COMPUTER"))
        assertTrue(text.contains("SHARED VARIABLES"))
    }

    @Test
    fun theExplanation_namesWhereItNeverLearns_andWhereTheWordsAreKept() {
        val text = WordSuggestionText.explanation(t)
        for (never in listOf("EMERGENCY", "TERMINAL", "MANUAL OVERRIDE", "TAGS", "NUMBERS")) assertTrue(never, text.contains(never))
        assertTrue(text.contains("THIS PHONE"))
        assertTrue(text.contains("EXPORT .JSON"))
        assertTrue(text.contains("FORGET WORDS"))
    }

    @Test
    fun theExplanationIsFiveSentencesJoinedWithOneSpace_exactlyAsItAlwaysWas() {
        assertEquals(
            "WHEN ON, THE STATEMENT COMPOSER OFFERS WORDS UNDER THE TEXT BOX: THE REST OF THE WORD YOU ARE TYPING, OR THE WORD THAT USUALLY COMES NEXT. " +
                "NOTHING IS ADDED UNTIL YOU TAP IT. " +
                "IT STARTS EMPTY AND LEARNS ONLY FROM STATEMENTS YOU SAVE, SPEAK OR COPY, AND FROM NAMES YOU ALREADY KEEP IN TARGET COMPUTER AND SHARED VARIABLES. " +
                "IT NEVER LEARNS FROM THE EMERGENCY DECK, THE TERMINAL, MANUAL OVERRIDE, TAGS OR NUMBERS. " +
                "THE WORDS ARE KEPT ON THIS PHONE ONLY AND ARE INCLUDED IF YOU SAVE EXPORT .JSON. FORGET WORDS REMOVES THEM.",
            WordSuggestionText.explanation(t)
        )
    }

    @Test
    fun theOffer_saysNothingIsLearnedUnlessTheyTurnItOn_andHasTwoDistinctButtons() {
        val text = english.getValue("words_offer_text")
        assertEquals("NEW: WORD SUGGESTIONS IN THE STATEMENT COMPOSER. IT IS OFF AND NOTHING IS LEARNED UNLESS YOU TURN IT ON.", text)
        assertTrue(text.contains("NOTHING IS LEARNED"))
        assertTrue(text.contains("UNLESS YOU TURN IT ON"))
        assertNotEquals(english.getValue("words_offer_turn_on"), english.getValue("words_offer_not_now"))
    }

    @Test
    fun noEnglishWordingIsInLowerCase_theAppsHouseStyle() {
        val all = listOf(WordSuggestionText.switchLabel(t, true), WordSuggestionText.switchLabel(t, false), WordSuggestionText.explanation(t)) +
            english.filterKeys { it.startsWith("words_") }.values
        // A placeholder such as %1$s is not a word, so it is taken out before the check.
        for (text in all) {
            val words = text.replace(Regex("""%\d\$[sd]"""), "")
            assertEquals(words.uppercase(), words)
        }
    }

    // ---- FORGET WORDS --------------------------------------------------------------------------------------------------------

    @Test
    fun theCountLineSaysHowManyInWords_andNoneYetWhenEmpty() {
        assertEquals("WORDS LEARNED: NONE YET", WordSuggestionText.countLine(t, 0))
        assertEquals("WORDS LEARNED: NONE YET", WordSuggestionText.countLine(t, -3))
        assertEquals("WORDS LEARNED: 1", WordSuggestionText.countLine(t, 1))
        assertEquals("WORDS LEARNED: 1234", WordSuggestionText.countLine(t, 1234))
    }

    @Test
    fun howOftenAWordWasUsed_isSingularOnlyForOne() {
        assertEquals("USED 1 TIME", WordSuggestionText.usedLine(t, 1))
        assertEquals("USED 2 TIMES", WordSuggestionText.usedLine(t, 2))
        assertEquals("USED 1000000 TIMES", WordSuggestionText.usedLine(t, 1_000_000))
    }

    @Test
    fun forgettingOneWordSaysItCanBeLearnedAgain_andOffersTwoDistinctButtons() {
        assertTrue(english.getValue("words_remove_question").contains("LEARNED AGAIN"))
        assertNotEquals(english.getValue("words_remove"), english.getValue("words_keep"))
    }

    @Test
    fun forgettingAllAsksTwice_namesTheCount_theBackup_andWhatIsNotAffected() {
        val first = WordSuggestionText.forgetAllFirstConfirmation(t, 3)
        val text = first.joinToString("\n")
        assertTrue(text.contains("ALL 3 LEARNED WORDS"))
        assertTrue(text.contains("EXPORT .JSON"))
        assertTrue(text.contains("TARGET COMPUTER"))
        assertTrue(text.contains("STAYS ON OR OFF"))
        assertEquals("five sentences", 5, first.size)
        assertTrue("files saved elsewhere are not touched, and it says so", WordSuggestionText.notElsewhere(t) in first)
        assertTrue(WordSuggestionText.forgetAllFirstConfirmation(t, 1).joinToString("\n").contains("THE 1 LEARNED WORD "))
        assertEquals("THIS CANNOT BE UNDONE.", WordSuggestionText.forgetAllSecond(t))
    }

    @Test
    fun theTwoSentencesSharedWithDeleteDataAreTheSameResources_soTheyCannotDiffer() {
        assertEquals(EnglishText.get(StorageCatalogue.CANNOT_UNDO), WordSuggestionText.forgetAllSecond(EnglishText))
        assertEquals(EnglishText.get(StorageCatalogue.NOT_ELSEWHERE), WordSuggestionText.notElsewhere(EnglishText))
        for ((tag, _) in translations) {
            val f = FileText(tag)
            assertEquals("$tag: second confirmation", f.get(StorageCatalogue.CANNOT_UNDO), WordSuggestionText.forgetAllSecond(f))
            assertEquals("$tag: not elsewhere", f.get(StorageCatalogue.NOT_ELSEWHERE), WordSuggestionText.notElsewhere(f))
        }
    }

    // ---- in every language ------------------------------------------------------------------------------------------------------

    @Test
    fun theWordsAreRealInEveryLanguage_andTheyNameTheButtonsAsTheyReadThere() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val explanation = WordSuggestionText.explanation(f)
            val first = WordSuggestionText.forgetAllFirstConfirmation(f, 4)
            for (said in listOf(explanation, WordSuggestionText.switchLabel(f, true), WordSuggestionText.switchLabel(f, false), WordSuggestionText.countLine(f, 0),
                WordSuggestionText.countLine(f, 7), WordSuggestionText.usedLine(f, 1), WordSuggestionText.usedLine(f, 3)) + first) {
                assertFalse("$tag: a resource name was shown instead of words: $said", said.contains("words_") || said.contains("label_") || said.contains("storage_"))
            }
            // The sentences name the screen and the buttons in this language's own words, so a person can find them.
            assertTrue("$tag: TARGET COMPUTER as the label reads", explanation.contains(map.getValue("label_target_computer")))
            assertTrue("$tag: EXPORT .JSON as the button reads", explanation.contains(map.getValue("label_export_json")))
            assertTrue("$tag: FORGET WORDS as the button reads", explanation.contains(map.getValue("words_forget_button")))
            assertTrue("$tag: the backup sentence names EXPORT .JSON", first[1].contains(map.getValue("label_export_json")))
            assertTrue("$tag: the names sentence names TARGET COMPUTER", first[2].contains(map.getValue("label_target_computer")))
            // And SHARED VARIABLES is the screen's own name in this language, as the English sentence says SHARED VARIABLES.
            assertTrue("$tag: shared variables as the label reads", explanation.contains(map.getValue("label_shared_variables")))
            assertTrue("$tag: shared variables in the names sentence", first[2].contains(map.getValue("label_shared_variables")))
            assertNotEquals("$tag: still English", WordSuggestionText.explanation(EnglishText), explanation)
            assertNotEquals("$tag: ON and OFF read the same", WordSuggestionText.switchLabel(f, true), WordSuggestionText.switchLabel(f, false))
            assertNotEquals("$tag: REMOVE and KEEP read the same", map.getValue("words_remove"), map.getValue("words_keep"))
            assertNotEquals("$tag: TURN ON and NOT NOW read the same", map.getValue("words_offer_turn_on"), map.getValue("words_offer_not_now"))
        }
    }

    @Test
    fun theCountsAreFilledIn_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            assertTrue("$tag: the count", WordSuggestionText.countLine(f, 1234).contains("1234"))
            assertTrue("$tag: the times", WordSuggestionText.usedLine(f, 12).contains("12"))
            assertTrue("$tag: the number removed", WordSuggestionText.forgetAllFirstConfirmation(f, 12)[0].contains("12"))
            assertNotEquals("$tag: none and some read the same", WordSuggestionText.countLine(f, 0), WordSuggestionText.countLine(f, 5))
        }
    }
}
