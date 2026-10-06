// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** What counts as a word, for the word model: letters of any script, an apostrophe or hyphen INSIDE a word, no digits, never a tag. */
class WordTokensTest {

    private fun words(text: String) = WordTokens.words(text).map { it.word }

    @Test
    fun plainWordsAreSplitOnSpaces_andKeepTheirPositions() {
        val spans = WordTokens.words("Hello world")
        assertEquals(listOf("Hello", "world"), spans.map { it.word })
        assertEquals(listOf(0 to 5, 6 to 11), spans.map { it.start to it.end })
    }

    @Test
    fun punctuationSeparatesWords() {
        assertEquals(listOf("Hi", "there"), words("Hi, there!"))
        assertEquals(listOf("a", "b", "c"), words("a;b:c"))
        assertEquals(listOf("one", "two"), words("(one) \"two\""))
    }

    @Test
    fun anApostropheInsideAWordIsPartOfIt_straightOrCurly() {
        assertEquals(listOf("don't"), words("don't"))
        assertEquals(listOf("don't"), words("don’t"))
        assertEquals(listOf("o'clock"), words("o'clock"))
    }

    @Test
    fun theSpanCoversTheOriginalCharacters_evenWhenACurlyApostropheWasMadeStraight() {
        val span = WordTokens.words("say don’t now").first { it.word == "don't" }
        assertEquals(4 to 9, span.start to span.end)
    }

    @Test
    fun anApostropheOrHyphenAtTheEdgeIsNotPartOfTheWord() {
        assertEquals(listOf("quoted"), words("'quoted'"))
        assertEquals(listOf("dash"), words("-dash"))
        assertEquals(listOf("trail"), words("trail-"))
        assertEquals(listOf("a", "b"), words("a - b"))
    }

    @Test
    fun aHyphenInsideAWordIsPartOfIt() {
        assertEquals(listOf("well-known"), words("well-known"))
        assertEquals(listOf("mother-in-law"), words("mother-in-law"))
    }

    @Test
    fun anythingWithADigitIsNotAWord_soNumbersAndCodesAreNeverLearned() {
        assertEquals(listOf("version"), words("version 2"))
        assertTrue(words("abc123").isEmpty())
        assertTrue(words("3rd").isEmpty())
        assertTrue(words("2024").isEmpty())
        assertEquals(listOf("call", "me"), words("call 07700 900123 me"))
    }

    @Test
    fun anEmojiSeparatesWords_andIsNeverAWord() {
        assertEquals(listOf("hi", "there"), words("hi😀there"))
        assertTrue(words("😀😀").isEmpty())
    }

    @Test
    fun lettersOfAnyScriptAreWords() {
        assertEquals(listOf("Μαμά", "καλημέρα"), words("Μαμά καλημέρα")) // Greek
        assertEquals(listOf("привет"), words("привет")) // Cyrillic
        assertEquals(listOf("你好吗"), words("你好吗")) // Chinese: no spaces, so one run
        assertEquals(listOf("مرحبا"), words("مرحبا")) // Arabic
    }

    @Test
    fun aLetterKeepsItsAccent_composedOrDecomposed() {
        assertEquals(listOf("café"), words("café")) // normalised to the composed form
        assertEquals(listOf("café"), words("café"))
    }

    @Test
    fun aTagIsNeverAWord_andItSeparatesTheWordsAroundIt() {
        assertEquals(listOf("Call", "now"), words("Call [COMPUTER:HOME] now"))
        assertEquals(listOf("Hi", "today"), words("Hi {VAR:A} today"))
        assertEquals(listOf("Hi"), words("Hi {VAR}"))
        assertTrue(words("[COMPUTER:SELF]").isEmpty())
    }

    @Test
    fun whiteSpaceOfEveryKindSeparates() {
        assertEquals(listOf("a", "b", "c", "d"), words("a\tb\nc d"))
    }

    @Test
    fun aVeryLongRun_isNotAWord() {
        assertTrue(words("x".repeat(WordTokens.MAX_WORD_LENGTH + 1)).isEmpty())
        assertEquals(1, words("x".repeat(WordTokens.MAX_WORD_LENGTH)).size)
    }

    @Test
    fun anEmptyOrBlankText_hasNoWords() {
        assertTrue(WordTokens.words("").isEmpty())
        assertTrue(WordTokens.words("  \n\t ").isEmpty())
    }

    // ---- sentences: words are only linked inside one sentence ------------------------------------------------------------

    private fun sentences(text: String) = WordTokens.sentences(text).map { s -> s.map { it.word } }

    @Test
    fun aFullStopQuestionMarkOrExclamationEndsASentence() {
        assertEquals(listOf(listOf("Hi", "there"), listOf("How", "are", "you")), sentences("Hi there. How are you?"))
        assertEquals(listOf(listOf("Stop"), listOf("now")), sentences("Stop! now"))
    }

    @Test
    fun aLineBreakEndsASentence() {
        assertEquals(listOf(listOf("Fine"), listOf("thanks")), sentences("Fine\nthanks"))
    }

    @Test
    fun aTagEndsASentence_soWordsAreNeverLinkedAcrossIt() {
        assertEquals(listOf(listOf("Call"), listOf("now")), sentences("Call [COMPUTER:HOME] now"))
    }

    @Test
    fun aCommaDoesNotEndASentence() {
        assertEquals(listOf(listOf("yes", "please", "thanks")), sentences("yes, please, thanks"))
    }

    @Test
    fun noWords_noSentences() {
        assertTrue(sentences("...").isEmpty())
        assertFalse(sentences("a").isEmpty())
    }
}
