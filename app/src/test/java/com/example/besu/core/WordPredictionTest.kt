// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the suggestion strip offers under the composer field: the rest of the word being typed, or, after a space, the word that most
 * often followed the last one. Never inside a tag, never mid-word, never after a full stop, and never anything numeric.
 */
class WordPredictionTest {

    private fun learned(vararg texts: String): WordModel {
        val m = WordModel()
        texts.forEachIndexed { i, t -> m.learn(t, i.toLong() + 1) }
        return m
    }

    private fun predict(model: WordModel, text: String, cursor: Int = text.length, extras: List<String> = emptyList(), limit: Int = 3) =
        WordPrediction.predict(model, extras, text, cursor, limit)

    private val base = learned("the cat. the dog. that is fine. the end")

    // ---- finishing the word being typed ------------------------------------------------------------------------------------

    @Test
    fun theWordBeingTyped_isCompleted_andTheSuggestionReplacesIt() {
        val p = predict(base, "I like th")
        assertEquals(PredictionKind.COMPLETE, p.kind)
        assertEquals(CharSpan(7, 9), p.replace)
        assertEquals(listOf("the", "that"), p.suggestions)
    }

    @Test
    fun aWordThatIsAlreadyFullyTyped_isNotOfferedBack() {
        val p = predict(base, "the")
        assertTrue(p.suggestions.none { it == "the" })
    }

    @Test
    fun aCapitalLetterTyped_givesACapitalisedSuggestion() {
        assertEquals(listOf("The", "That"), predict(base, "Th").suggestions)
        assertEquals(listOf("the", "that"), predict(base, "th").suggestions)
    }

    @Test
    fun aNameKeepsItsOwnCapital_whateverWasTyped() {
        val m = learned("I see Sarah today")
        assertEquals(listOf("Sarah"), predict(m, "sa").suggestions)
    }

    @Test
    fun nothingIsOfferedInTheMiddleOfAWord() {
        val p = predict(base, "thexyz", cursor = 2)
        assertNull(p.kind)
        assertTrue(p.suggestions.isEmpty())
    }

    @Test
    fun nothingIsOfferedForAnythingWithADigit() {
        assertTrue(predict(base, "th3").suggestions.isEmpty())
        assertTrue(predict(base, "12th").suggestions.isEmpty())
    }

    @Test
    fun aWordWithAnApostropheIsCompleted() {
        val m = learned("please don't go")
        assertEquals(listOf("don't"), predict(m, "please don").suggestions)
    }

    @Test
    fun otherScriptsAreCompleted() {
        val m = learned("Δεν ξέρω") // Greek
        assertEquals(listOf("ξέρω"), predict(m, "ξέ").suggestions)
    }

    @Test
    fun moreThanTheLimitIsNeverOffered() {
        val m = learned("tea tee ten tex tez tea")
        assertEquals(3, predict(m, "te").suggestions.size)
        assertEquals(2, predict(m, "te", limit = 2).suggestions.size)
    }

    // ---- the next word after a space -----------------------------------------------------------------------------------------

    @Test
    fun afterASpace_theWordsThatFollowedTheLastOneAreOffered_toBeInsertedAtTheCursor() {
        val p = predict(base, "the ")
        assertEquals(PredictionKind.NEXT, p.kind)
        assertNull(p.replace)
        assertEquals(listOf("cat", "dog", "end"), p.suggestions)
    }

    @Test
    fun theNextWordFollowsTheLastWordTyped_notTheFirst() {
        val m = learned("go home now", "go away")
        assertEquals(listOf("now"), predict(m, "go home ").suggestions)
    }

    @Test
    fun nothingIsOfferedAfterTheEndOfASentence() {
        assertTrue(predict(base, "the end. ").suggestions.isEmpty())
        assertTrue(predict(base, "the end?\n").suggestions.isEmpty())
    }

    @Test
    fun nothingIsOfferedAfterALineBreak_evenStraightAfterAWord() {
        // a new line starts a new sentence, so "the" at the end of the last line is not a word to follow
        assertTrue(predict(base, "the\n").suggestions.isEmpty())
        assertTrue(predict(base, "the \n ").suggestions.isEmpty())
        assertTrue(predict(base, "the\r\n").suggestions.isEmpty())
        assertTrue("on the same line it still works", predict(base, "the ").suggestions.isNotEmpty())
    }

    @Test
    fun nothingIsOfferedAtTheStartOfAnEmptyOrBlankField() {
        assertTrue(predict(base, "").suggestions.isEmpty())
        assertTrue(predict(base, "   ").suggestions.isEmpty())
    }

    @Test
    fun nothingIsOfferedAfterPunctuationOrAnEmoji() {
        assertTrue(predict(base, "the, ").suggestions.isEmpty())
        assertTrue(predict(base, "the 😀 ").suggestions.isEmpty())
        assertTrue(predict(base, "the (").suggestions.isEmpty())
    }

    @Test
    fun anEmptyModel_offersNothing() {
        assertTrue(predict(WordModel(), "th").suggestions.isEmpty())
        assertTrue(predict(WordModel(), "the ").suggestions.isEmpty())
    }

    // ---- tags -----------------------------------------------------------------------------------------------------------------

    @Test
    fun nothingIsOfferedInsideATag() {
        val text = "Hi [COMPUTER:HOME] x"
        assertTrue(predict(base, text, cursor = 8).suggestions.isEmpty())
        assertTrue(predict(base, "Hi {VAR:A}", cursor = 6).suggestions.isEmpty())
    }

    @Test
    fun aWordAfterATagIsStillCompleted_butTheTagIsNotAPreviousWord() {
        assertEquals(listOf("the", "that"), predict(base, "Hi [COMPUTER:HOME] th").suggestions)
        assertTrue(predict(base, "[COMPUTER:HOME] ").suggestions.isEmpty())
    }

    // ---- names from elsewhere (Target Computer, Shared Variables) -------------------------------------------------------------------

    @Test
    fun namesPassedInAreOfferedEvenWithNothingLearned() {
        val m = WordModel()
        assertEquals(listOf("Sarah"), predict(m, "Hello Sa", extras = listOf("Sarah", "Oliver")).suggestions)
        assertEquals(listOf("Oliver"), predict(m, "Hello O", extras = listOf("Sarah", "Oliver")).suggestions)
    }

    @Test
    fun aNameRanksAheadOfAWordUsedOnce_andBehindOneUsedOften() {
        val m = learned("same", "same same same")
        // "same" used 4 times beats the name; with a single use a name comes first
        assertEquals(listOf("same", "Sarah"), predict(m, "sa", extras = listOf("Sarah")).suggestions)
        val once = learned("same")
        assertEquals(listOf("Sarah", "same"), predict(once, "sa", extras = listOf("Sarah")).suggestions)
    }

    @Test
    fun aNameTheModelAlreadyKnows_isOfferedOnce()  {
        val m = learned("I see Sarah")
        assertEquals(listOf("Sarah"), predict(m, "sa", extras = listOf("Sarah", "sarah")).suggestions)
    }

    @Test
    fun namesAreNeverOfferedAsTheNextWord() {
        // only words that really followed the last one are offered after a space
        assertTrue(predict(WordModel(), "Hello ", extras = listOf("Sarah")).suggestions.isEmpty())
    }

    // ---- odd cursors -----------------------------------------------------------------------------------------------------------

    @Test
    fun aCursorOutsideTheText_isClampedAndNeverCrashes() {
        assertEquals(predict(base, "th").suggestions, predict(base, "th", cursor = 99).suggestions)
        assertTrue(predict(base, "th", cursor = -5).suggestions.isEmpty())
    }
}
