// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * B4: the history chips under a variable field must be readable, reachable, quiet and steady. The chip row is a Compose screen that
 * cannot be compiled or run without the Android SDK, so these tests read its source and hold it to the rules, and check that every
 * place that shows chips passes the text typed so far (so the chips narrow as the person types).
 */
class ChipRowGuardTest {

    private fun source(name: String) = RepoFiles.read("app/src/main/java/com/example/besu/$name")

    private fun bodyOf(text: String, name: String): String {
        val at = text.indexOf("fun $name(")
        assertTrue("fun $name( not found", at >= 0)
        val open = text.indexOf('{', text.indexOf(')', at))
        var depth = 0
        var i = open
        while (i < text.length) {
            if (text[i] == '{') depth++
            if (text[i] == '}') { depth--; if (depth == 0) return text.substring(open + 1, i) }
            i++
        }
        error("unbalanced braces in $name")
    }

    // The chip row's function body. Its parameter list holds a function type with its own parentheses, so find the body by
    // its opening brace after the parameter list's closing line.
    private fun chipRowBody(): String {
        val shared = source("ui/SharedComponents.kt")
        val at = shared.indexOf("fun AutocompleteChipRow(")
        assertTrue(at >= 0)
        val paramsEnd = shared.indexOf(") {", at)
        val open = shared.indexOf('{', paramsEnd)
        var depth = 0
        var i = open
        while (i < shared.length) {
            if (shared[i] == '{') depth++
            if (shared[i] == '}') { depth--; if (depth == 0) return shared.substring(open + 1, i) }
            i++
        }
        error("unbalanced braces in AutocompleteChipRow")
    }

    // ---- the chip row ------------------------------------------------------------------------------------------------

    @Test
    fun noTextInTheChipRowIsUnderTwelveSp() {
        val sizes = Regex("""fontSize\s*=\s*(\d+(?:\.\d+)?)\.sp""").findAll(chipRowBody()).map { it.groupValues[1].toDouble() }.toList()
        assertTrue("the chip row must set its text size", sizes.isNotEmpty())
        for (s in sizes) assertTrue("a chip's text is $s sp; the floor is 12", s >= 12.0)
    }

    @Test
    fun everyChipIsAtLeast48DpTall() {
        assertTrue(chipRowBody().contains("heightIn(min = 48.dp)"))
    }

    @Test
    fun theRowReservesItsHeight_soNothingMovesWhenTheChipsChange() {
        val body = chipRowBody()
        assertFalse("the row must not disappear when there are no chips", body.contains("suggestions.isEmpty()"))
        assertFalse(body.contains("return"))
        val reserved = Regex("""CHIP_ROW_MIN_HEIGHT\s*=\s*(\d+)\.dp""").find(source("ui/SharedComponents.kt"))?.groupValues?.get(1)?.toInt()
        assertTrue("CHIP_ROW_MIN_HEIGHT must be defined", reserved != null)
        assertTrue("the reserved height must hold a 48 dp chip", reserved!! >= 48)
        assertTrue("the row must use it", body.contains("heightIn(min = CHIP_ROW_MIN_HEIGHT)"))
    }

    @Test
    fun theChipRowIsQuiet_noAnimationAndNoHaptics() {
        val body = chipRowBody()
        for (banned in listOf(
            "animate", "AnimatedVisibility", "Crossfade", "AnimatedContent", "HapticFeedback", "performHapticFeedback",
            "NeonButton", "TightPanelButton",
        )) {
            assertFalse("the chip row must not use $banned", body.contains(banned))
        }
    }

    @Test
    fun aLongValueScrollsSidewaysAndKeepsBothEnds_notJustItsStart() {
        val body = chipRowBody()
        assertTrue(body.contains("horizontalScroll("))
        assertTrue(body.contains("MiddleEllipsis.shorten("))
        assertTrue(body.contains("maxLines = 2"))
    }

    @Test
    fun theFullValueIsAvailableToAssistiveTechnology_evenIfTheChipIsShortened() {
        assertTrue(chipRowBody().contains("contentDescription = suggestion"))
    }

    @Test
    fun tappingAChipStillReplacesTheWholeField() {
        // The row hands the chosen value to the caller, and each caller sets the whole field to it (unchanged).
        assertTrue(chipRowBody().contains("onSelect(suggestion)"))
    }

    // ---- everywhere that shows chips narrows them as the person types ------------------------------------------------------

    /** The number of top-level arguments in the call whose opening parenthesis is at [open]. */
    private fun argCount(text: String, open: Int): Int {
        var depth = 0
        var commas = 0
        var anyChar = false
        var inString = false
        var i = open
        while (i < text.length) {
            val ch = text[i]
            if (inString) {
                if (ch == '\\') i++ else if (ch == '"') inString = false
            } else when (ch) {
                '"' -> { inString = true; anyChar = true }
                '(', '[', '{' -> depth++
                ')', ']', '}' -> { depth--; if (depth == 0) return if (anyChar) commas + 1 else 0 }
                ',' -> if (depth == 1) commas++
                else -> if (depth >= 1 && !ch.isWhitespace()) anyChar = true
            }
            i++
        }
        error("unbalanced parentheses")
    }

    @Test
    fun theArgumentCounterCountsWhatItShould() {
        assertEquals(3, argCount("f(a, g(b, c), \"x,y\")", 1))
        assertEquals(1, argCount("f(a)", 1))
        assertEquals(0, argCount("f()", 1))
        assertEquals(2, argCount("f(a, { b, c })", 1))
    }

    @Test
    fun everyPlaceThatShowsChipsPassesTheTextTypedSoFar() {
        var calls = 0
        for (file in listOf("ui/DesignSystem.kt", "decks/QuickActionsDeck.kt")) {
            val text = source(file)
            val marker = "AutocompleteHistoryRepository.getSuggestions("
            var from = 0
            while (true) {
                val at = text.indexOf(marker, from)
                if (at < 0) break
                calls++
                val args = argCount(text, at + marker.length - 1)
                assertTrue("$file: getSuggestions at offset $at passes $args argument(s); it must pass the typed text as the third", args >= 3)
                from = at + marker.length
            }
        }
        assertEquals("the five places that show chips", 5, calls)
    }

    @Test
    fun theRepositoryAsksTheTestedEngine() {
        val repo = source("data/AutocompleteHistoryRepository.kt")
        assertTrue(repo.contains("fun getSuggestions(context: Context, scopeKey: String, typed: String = \"\")"))
        assertTrue(bodyOf(repo, "getSuggestions").contains("WordSuggestions.suggest("))
        assertTrue(bodyOf(repo, "recordUsage").contains("WordSuggestions.recordUsage("))
    }

    @Test
    fun theRepositoryNeverRewritesStoredHistoryWhenReading() {
        // Reading must not save anything: the merge of case variants happens in memory, on the way out.
        val body = bodyOf(source("data/AutocompleteHistoryRepository.kt"), "getSuggestions")
        assertFalse(body.contains("saveScope"))
        assertFalse(body.contains(".edit()"))
    }
}
