// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Names the person already keeps (Target Computer entries, Shared Root Variables) become suggestion candidates: split into words, no numbers, no repeats, capped. */
class ExtraWordsTest {

    @Test
    fun aNameIsSplitIntoItsWords_inOrder() {
        assertEquals(listOf("Dr", "Jane", "Smith"), ExtraWords.fromTexts(listOf("Dr. Jane Smith")))
    }

    @Test
    fun manyTextsAreJoined_keepingTheOrderTheyCameIn() {
        assertEquals(listOf("Sarah", "Mum", "Clinic"), ExtraWords.fromTexts(listOf("Sarah", "Mum", "Clinic")))
    }

    @Test
    fun aRepeatIsDropped_whateverItsCase_andTheFirstFormIsKept() {
        assertEquals(listOf("Sarah", "Mum"), ExtraWords.fromTexts(listOf("Sarah", "sarah", "SARAH", "Mum", "mum")))
    }

    @Test
    fun aSingleLetterIsDropped_butTwoLettersStay() {
        assertEquals(listOf("Al"), ExtraWords.fromTexts(listOf("A", "I", "Al")))
    }

    @Test
    fun numbersAndAnythingWithADigitAreNeverCandidates() {
        assertEquals(listOf("Room"), ExtraWords.fromTexts(listOf("Room 12 07700900123 abc123")))
    }

    @Test
    fun anApostropheOrHyphenInsideANameIsKept() {
        assertEquals(listOf("O'Brien", "Anne-Marie"), ExtraWords.fromTexts(listOf("O'Brien Anne-Marie")))
    }

    @Test
    fun aTagIsNeverACandidate() {
        assertEquals(listOf("Call", "now"), ExtraWords.fromTexts(listOf("Call [COMPUTER:HOME] now {VAR:A}")))
    }

    @Test
    fun blankTextsAndNoTextsGiveNothing() {
        assertTrue(ExtraWords.fromTexts(emptyList()).isEmpty())
        assertTrue(ExtraWords.fromTexts(listOf("", "   ", "\n")).isEmpty())
    }

    @Test
    fun theListStopsAtTheCap_exactlyAtTheBoundary() {
        fun word(i: Int) = "w" + ('a' + i % 26) + ('a' + (i / 26) % 26) + ('a' + (i / 676) % 26)
        val texts = (0 until ExtraWords.MAX_WORDS + 5).map { word(it) }
        val out = ExtraWords.fromTexts(texts)
        assertEquals(ExtraWords.MAX_WORDS, out.size)
        assertEquals(texts.first(), out.first())
        assertEquals(texts[ExtraWords.MAX_WORDS - 1], out.last())
        // one under the cap is not cut
        assertEquals(ExtraWords.MAX_WORDS - 1, ExtraWords.fromTexts(texts.take(ExtraWords.MAX_WORDS - 1)).size)
        assertEquals(ExtraWords.MAX_WORDS, ExtraWords.fromTexts(texts.take(ExtraWords.MAX_WORDS)).size)
    }

    @Test
    fun anAccentedNameKeepsItsAccent_andComposedAndDecomposedAreOne() {
        val composed = "Jos\u00e9"
        val decomposed = "Jose\u0301"
        assertEquals(listOf(composed), ExtraWords.fromTexts(listOf(decomposed, composed)))
    }
}
