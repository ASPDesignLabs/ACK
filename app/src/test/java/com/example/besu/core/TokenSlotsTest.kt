// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * A phrase's local {VAR} values and its [COMPUTER:..] fallbacks are stored BY POSITION: the first {VAR} in the text uses the
 * first value, the second uses the second, and so on. So a token inserted in the MIDDLE of the text (the editors' insert buttons now
 * insert at the cursor) must put a blank value at the same position, or every value after it would silently attach to the wrong
 * token. These tests pin that.
 */
class TokenSlotsTest {

    private fun insertVar(text: String, start: Int, end: Int, token: String, values: List<String>): List<String> {
        val r = TextInsertion.insert(text, start, end, token)
        return TokenSlots.realign(values, text, r.replaced, token, SlotFamily.VARIABLE)
    }

    private fun insertComputer(text: String, start: Int, end: Int, token: String, values: List<String>): List<String> {
        val r = TextInsertion.insert(text, start, end, token)
        return TokenSlots.realign(values, text, r.replaced, token, SlotFamily.COMPUTER)
    }

    // ---- one token goes in ---------------------------------------------------------------------------------------------

    @Test
    fun atTheEnd_theBlankValueGoesLast() {
        assertEquals(listOf("bob", ""), insertVar("Hi {VAR}", 8, 8, "{VAR}", listOf("bob")))
    }

    @Test
    fun atTheStart_everyExistingValueMovesDownOne() {
        assertEquals(listOf("", "bob"), insertVar("Hi {VAR}", 0, 0, "{VAR:A}", listOf("bob")))
    }

    @Test
    fun betweenTwoTokens_theBlankValueGoesBetweenTheirValues() {
        val text = "{VAR} and {VAR}"
        assertEquals(listOf("x", "", "y"), insertVar(text, 8, 8, "{VAR:B}", listOf("x", "y")))
    }

    @Test
    fun withNoTokensYet_theFirstValueIsBlank() {
        assertEquals(listOf(""), insertVar("Hello", 5, 5, "{VAR}", emptyList()))
    }

    @Test
    fun aCursorInsideAToken_countsThatTokenAsBeforeTheInsertion() {
        // "{VAR} and {VAR}" with the cursor inside the first token: the new token goes after it
        assertEquals(listOf("x", "", "y"), insertVar("{VAR} and {VAR}", 2, 2, "{VAR:C}", listOf("x", "y")))
    }

    @Test
    fun theLetterOfAVariableDoesNotMatter_everyVariableTokenIsOneFamily() {
        assertEquals(listOf("a", "", "c"), insertVar("{VAR:A} {VAR:C}", 8, 8, "{VAR}", listOf("a", "c")))
    }

    // ---- the two families are separate -------------------------------------------------------------------------------------

    @Test
    fun aComputerTagInsertedBetweenVariables_leavesTheVariableValuesAlone() {
        val text = "{VAR} and {VAR}"
        val r = TextInsertion.insert(text, 8, 8, "[COMPUTER:HOME]")
        assertEquals(listOf("x", "y"), TokenSlots.realign(listOf("x", "y"), text, r.replaced, "[COMPUTER:HOME]", SlotFamily.VARIABLE))
    }

    @Test
    fun aVariableInsertedBetweenComputerTags_leavesTheFallbacksAlone() {
        val text = "[COMPUTER:HOME] and [COMPUTER:WORK]"
        val r = TextInsertion.insert(text, 16, 16, "{VAR}")
        assertEquals(listOf("mum", "office"), TokenSlots.realign(listOf("mum", "office"), text, r.replaced, "{VAR}", SlotFamily.COMPUTER))
    }

    @Test
    fun aComputerTagBetweenTwoComputerTags_getsABlankFallbackBetweenTheirs() {
        val text = "[COMPUTER:HOME] and [COMPUTER:WORK]"
        assertEquals(listOf("mum", "", "office"), insertComputer(text, 16, 16, "[COMPUTER:SCHOOL]", listOf("mum", "office")))
    }

    // ---- a selection that is replaced -----------------------------------------------------------------------------------------

    @Test
    fun replacingATokenWithAnother_dropsTheOldValueAndAddsABlank() {
        val text = "A {VAR} B"
        assertEquals(listOf(""), insertVar(text, 2, 7, "{VAR:B}", listOf("v")))
    }

    @Test
    fun replacingTwoTokens_dropsBothValues() {
        val text = "{VAR} {VAR} {VAR}"
        // select the first two tokens and what is between them
        assertEquals(listOf("", "z"), insertVar(text, 0, 11, "{VAR}", listOf("x", "y", "z")))
    }

    @Test
    fun aSelectionThatCoversPartOfAToken_dropsTheWholeTokensValue() {
        val text = "Go {VAR} now"
        // selection starts inside the token: it is widened to the whole token, so the value goes with it
        assertEquals(listOf(""), insertVar(text, 5, 6, "{VAR:A}", listOf("v")))
    }

    @Test
    fun replacingPlainTextWithAToken_keepsEveryExistingValue() {
        val text = "word {VAR}"
        assertEquals(listOf("", "v"), insertVar(text, 0, 4, "{VAR}", listOf("v")))
    }

    @Test
    fun replacingATokenWithPlainText_justDropsItsValue() {
        val text = "{VAR} and {VAR}"
        val r = TextInsertion.insert(text, 0, 5, "hello")
        assertEquals(listOf("y"), TokenSlots.realign(listOf("x", "y"), text, r.replaced, "hello", SlotFamily.VARIABLE))
    }

    @Test
    fun aTokenOfTheOtherFamilyBeingReplaced_leavesThisFamilysValuesAlone() {
        val text = "[COMPUTER:HOME] {VAR}"
        val r = TextInsertion.insert(text, 0, 15, "hello")
        assertEquals(listOf("v"), TokenSlots.realign(listOf("v"), text, r.replaced, "hello", SlotFamily.VARIABLE))
    }

    // ---- bad or odd stored lists --------------------------------------------------------------------------------------------

    @Test
    fun aListShorterThanTheTokens_isPaddedSoNothingIsRemovedFromTheWrongPlace() {
        // two tokens, one stored value: inserting between them must not throw and must keep the first value first
        val result = insertVar("{VAR} and {VAR}", 8, 8, "{VAR}", listOf("x"))
        assertEquals("x", result.first())
        assertEquals(3, result.size)
        assertEquals("", result[1])
    }

    @Test
    fun anEmptyInsertion_changesNothing() {
        val text = "Hi {VAR}"
        val r = TextInsertion.insert(text, 3, 3, "")
        assertEquals(listOf("bob"), TokenSlots.realign(listOf("bob"), text, r.replaced, "", SlotFamily.VARIABLE))
    }

    // ---- the property, over every cursor and selection ------------------------------------------------------------------------

    @Test
    fun overEveryCursorAndSelection_everyTokenThatSurvivesKeepsItsOwnValue_andTheListMatchesTheText() {
        // Every computer tag is different, so each tag's own text says which old value it must still carry.
        val text = "Call [COMPUTER:A1] at [COMPUTER:B2], then [COMPUTER:C3] or [COMPUTER:D4]."
        val oldTokens = TextInsertion.tokenSpans(text).map { text.substring(it.start, it.end) }
        val values = oldTokens.map { "value-of-$it" }
        for (token in listOf("[COMPUTER:E5]", "{VAR}", "word")) for (s in 0..text.length) for (e in 0..text.length) {
            val r = TextInsertion.insert(text, s, e, token)
            val label = "token=$token sel=$s..$e"
            val realigned = TokenSlots.realign(values, text, r.replaced, token, SlotFamily.COMPUTER)
            val newComputerTokens = TextInsertion.tokenSpans(r.text)
                .map { r.text.substring(it.start, it.end) }
                .filter { it.startsWith("[COMPUTER:") }
            assertEquals("list length matches the tags: $label", newComputerTokens.size, realigned.size)
            newComputerTokens.forEachIndexed { i, t ->
                val expected = if (t in oldTokens) "value-of-$t" else ""
                assertEquals("tag $t at $i: $label", expected, realigned[i])
            }
        }
    }

    @Test
    fun theSameHoldsForVariables_withTheirValuesFollowingTheirOrder() {
        val text = "{VAR} one {VAR:A} two {VAR:B} three {VAR:C}"
        val spans = TextInsertion.tokenSpans(text)
        val values = spans.indices.map { "v$it" }
        for (s in 0..text.length) for (e in 0..text.length) {
            val r = TextInsertion.insert(text, s, e, "{VAR}")
            val realigned = TokenSlots.realign(values, text, r.replaced, "{VAR}", SlotFamily.VARIABLE)
            val newCount = TextInsertion.tokenSpans(r.text).count { r.text.substring(it.start, it.end).startsWith("{VAR") }
            assertEquals("length: sel=$s..$e", newCount, realigned.size)
            assertTrue("the inserted token has a blank value: sel=$s..$e", "" in realigned)
        }
    }

    // ---- the edit tells the caller exactly what it replaced ---------------------------------------------------------------------

    @Test
    fun theResultSaysWhichSpanOfTheOldTextWasReplaced() {
        assertEquals(CharSpan(2, 7), TextInsertion.insert("A {VAR} B", 2, 7, "X").replaced)
        // a selection that starts inside a token is widened, and the result says so
        assertEquals(CharSpan(3, 8), TextInsertion.insert("Go {VAR} now", 5, 6, "X").replaced)
        // a bare cursor replaces nothing, and one inside a token moves to after it
        assertEquals(CharSpan(3, 3), TextInsertion.insert("Hello", 3, 3, "X").replaced)
        assertEquals(CharSpan(8, 8), TextInsertion.insert("Go {VAR} now", 5, 5, "X").replaced)
        // an empty insertion replaces nothing
        assertEquals(CharSpan(5, 5), TextInsertion.insert("Hello world", 2, 5, "").replaced)
    }
}
