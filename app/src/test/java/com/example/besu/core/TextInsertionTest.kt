// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The shared rule for dropping a word or token into text (B1). Every expected string below shows the cursor as `|` and a
 * selection as `⟨...⟩`, so a test reads like what the person sees on screen.
 */
class TextInsertionTest {

    private fun run(
        marked: String,
        insertion: String,
        mode: InsertMode = InsertMode.WORD,
        replace: CharSpan? = null
    ): String {
        val cursor = marked.indexOf('|')
        val text: String
        val start: Int
        val end: Int
        if (cursor >= 0) {
            text = marked.removeRange(cursor, cursor + 1)
            start = cursor
            end = cursor
        } else {
            val open = marked.indexOf('⟨')
            val close = marked.indexOf('⟩')
            require(open >= 0 && close > open) { "no cursor or selection marker in: $marked" }
            text = marked.removeRange(close, close + 1).removeRange(open, open + 1)
            start = open
            end = close - 1
        }
        val result = TextInsertion.insert(text, start, end, insertion, mode, replace)
        return result.text.substring(0, result.cursor) + "|" + result.text.substring(result.cursor)
    }

    // ---- where the cursor is -------------------------------------------------------------------------------------

    @Test
    fun emptyText_getsTheWordAndAFreeSpaceToKeepTypingIn() {
        assertEquals("X |", run("|", "X"))
    }

    @Test
    fun cursorAtTheStart_hasNoLeadingSpaceButSeparatesFromTheWordAfter() {
        assertEquals("X |Hello", run("|Hello", "X"))
    }

    @Test
    fun cursorInTheMiddleOfAWord_isSeparatedOnBothSides() {
        assertEquals("Hel X |lo", run("Hel|lo", "X"))
    }

    @Test
    fun cursorBetweenWords_addsNoDoubleSpace() {
        assertEquals("Hello X |world", run("Hello |world", "X"))
    }

    @Test
    fun cursorRightAfterAWordWithASpaceAfterIt_stepsOverThatSpace() {
        assertEquals("Hello X |world", run("Hello| world", "X"))
    }

    @Test
    fun cursorAtTheEnd_leavesASpaceToContinueTyping() {
        assertEquals("Hello X |", run("Hello|", "X"))
        assertEquals("Hello X |", run("Hello |", "X"))
        assertEquals("Hello\nX |", run("Hello\n|", "X"))
    }

    // ---- what is next to the cursor ------------------------------------------------------------------------------

    @Test
    fun beforeClosingPunctuation_noSpaceIsPutBeforeIt() {
        for (c in listOf('.', ',', '!', '?', ';', ':', ')', ']', '}', '”', '’', '»', '›')) {
            assertEquals("closing $c", "Hello X|$c", run("Hello|$c", "X"))
        }
    }

    @Test
    fun beforeALineBreak_noTrailingSpaceAndTheCursorStaysBeforeTheBreak() {
        assertEquals("Hello X|\nWorld", run("Hello|\nWorld", "X"))
        assertEquals("Hello\nX |World", run("Hello\n|World", "X"))
    }

    @Test
    fun afterAnOpeningBracketOrQuote_noLeadingSpace() {
        for (c in listOf('(', '[', '{', '“', '‘', '„', '«', '‹')) {
            assertEquals("opening $c", "${c}X |b", run("$c|b", "X"))
        }
    }

    @Test
    fun straightQuotes_areOpeningOrClosingByWhatPrecedesThem() {
        assertEquals("\"X |hi\"", run("\"|hi\"", "X"))
        assertEquals("say \"X |hi\"", run("say \"|hi\"", "X"))
        assertEquals("\"hi\" X |", run("\"hi\"|", "X"))
        assertEquals("say \"hi X|\"", run("say \"hi|\"", "X"))
        assertEquals("X |\"hi\"", run("|\"hi\"", "X"))
        assertEquals("Hi X |\"hi\"", run("Hi |\"hi\"", "X"))
        assertEquals("it X|'s", run("it|'s", "X"))
    }

    @Test
    fun anyKindOfWhiteSpaceCountsAsASpace_includingNoBreakSpaceAndNextLine() {
        assertEquals("Hello X |world", run("Hello |world", "X"))
        // a no-break space after the cursor is white space (no trailing space) but is not an ordinary space to step over
        assertEquals("Hello X| world", run("Hello| world", "X"))
        assertEquals("Hello\u0085X |World", run("Hello\u0085|World", "X"))
        assertEquals("Hello X|\u0085World", run("Hello|\u0085World", "X"))
    }

    @Test
    fun aRunOfSpacesAfterTheCursor_isNeverAddedToAndTheCursorStaysBeforeIt() {
        assertEquals("Hello X|  world", run("Hello |  world", "X"))
    }

    // ---- selections and clamping ---------------------------------------------------------------------------------

    @Test
    fun aSelection_isReplaced() {
        assertEquals("Hello X |", run("Hello ⟨world⟩", "X"))
        assertEquals("Say X |there", run("Say ⟨hi⟩ there", "X"))
        assertEquals("Say X |there", run("Say⟨ hi⟩ there", "X"))
    }

    @Test
    fun aReversedSelection_isTheSameAsTheRightWayRound() {
        val reversed = TextInsertion.insert("Say hi there", 6, 4, "X")
        val forwards = TextInsertion.insert("Say hi there", 4, 6, "X")
        assertEquals(forwards, reversed)
        assertEquals("Say X there", reversed.text)
        assertEquals(6, reversed.cursor)
    }

    @Test
    fun aSelectionOutsideTheText_isClamped() {
        val whole = TextInsertion.insert("abc", -5, 99, "X")
        assertEquals("X ", whole.text)
        assertEquals(2, whole.cursor)
        val past = TextInsertion.insert("abc", 10, 10, "X")
        assertEquals("abc X ", past.text)
        assertEquals(6, past.cursor)
    }

    @Test
    fun anEmojiIsNeverSplit() {
        val text = "a😀b" // a, one emoji (two chars), b
        // a cursor between the two halves moves to after the emoji
        assertEquals("a😀 X |b", render(TextInsertion.insert(text, 2, 2, "X")))
        // a selection that starts or ends in the middle of the emoji is widened to cover it all
        assertEquals("a X |b", render(TextInsertion.insert(text, 2, 3, "X")))
        assertEquals("X |b", render(TextInsertion.insert(text, 0, 2, "X")))
        assertEquals("a X |b", render(TextInsertion.insert(text, 1, 3, "X")))
    }

    // ---- tokens ----------------------------------------------------------------------------------------------------

    @Test
    fun aCursorInsideAToken_insertsAfterIt() {
        assertEquals("Go to [COMPUTER:HOME] X |now", run("Go to [COM|PUTER:HOME] now", "X"))
        assertEquals("I am {VAR} X |today", run("I am {V|AR} today", "X"))
        assertEquals("{VAR:B} X |is", run("{VAR:|B} is", "X"))
        assertEquals("{VAR:C} X |is", run("{VAR:|C} is", "X"))
    }

    @Test
    fun aCursorOnATokenEdge_isNotInsideIt() {
        assertEquals("Go to X |[COMPUTER:HOME]", run("Go to |[COMPUTER:HOME]", "X"))
        assertEquals("[COMPUTER:HOME] X |now", run("[COMPUTER:HOME]| now", "X"))
    }

    @Test
    fun aSelectionThatCoversPartOfAToken_isWidenedToTheWholeToken() {
        assertEquals("Go X |now", run("Go ⟨to [COM⟩PUTER:HOME] now", "X"))
        assertEquals("Go X |ow", run("Go [COM⟨PUTER:HOME] n⟩ow", "X"))
        assertEquals("X |", run("[COM⟨PUTER:HOME] and {V⟩AR}", "X"))
    }

    @Test
    fun somethingThatOnlyLooksLikeAToken_isNotOne() {
        assertEquals("{VAR X|:D}", run("{VAR|:D}", "X"))
        assertEquals("[computer:ho X |me]", run("[computer:ho|me]", "X"))
    }

    // ---- modes, empty insertions, trimming ------------------------------------------------------------------------

    @Test
    fun exactMode_addsNoSpacesAtAll() {
        assertEquals("Hello.|", run("Hello|", ".", InsertMode.EXACT))
        assertEquals("Hello X| now", run("Hello ⟨world⟩ now", "X", InsertMode.EXACT))
        assertEquals("a  |b", run("a|b", "  ", InsertMode.EXACT))
    }

    @Test
    fun exactMode_stillNeverSplitsATokenOrAnEmoji() {
        assertEquals("[COMPUTER:HOME],|", run("[COM|PUTER:HOME]", ",", InsertMode.EXACT))
        val text = "a😀b"
        assertEquals("a😀,|b", render(TextInsertion.insert(text, 2, 2, ",", InsertMode.EXACT)))
    }

    @Test
    fun anEmptyInsertion_changesNothing_eventhoughTextIsSelected() {
        assertEquals("Hello wor|ld", run("Hello ⟨wor⟩ld", ""))
        assertEquals("Hello wor|ld", run("Hello ⟨wor⟩ld", "", InsertMode.EXACT))
        assertEquals("Hello|", run("Hello|", "   "))
    }

    @Test
    fun wordMode_trimsTheInsertionButKeepsItsInnerSpaces() {
        assertEquals("Hello X |", run("Hello|", "  X  "))
        assertEquals("Hello New York |", run("Hello|", "New York"))
    }

    // ---- replace range (the Terminal's /v and /t triggers, a half-typed word) ----------------------------------------

    @Test
    fun aReplaceRange_swapsTheTriggerForTheValue() {
        val r = TextInsertion.insert("say /v now", 0, 0, "Sarah", InsertMode.WORD, CharSpan(4, 6))
        assertEquals("say Sarah now", r.text)
        assertEquals(10, r.cursor)
        val atEnd = TextInsertion.insert("say /v", 6, 6, "Sarah", InsertMode.WORD, CharSpan(4, 6))
        assertEquals("say Sarah ", atEnd.text)
        assertEquals(10, atEnd.cursor)
    }

    @Test
    fun aReplaceRange_winsOverTheSelection() {
        val withSelection = TextInsertion.insert("say /v now", 0, 3, "Sarah", InsertMode.WORD, CharSpan(4, 6))
        val without = TextInsertion.insert("say /v now", 0, 0, "Sarah", InsertMode.WORD, CharSpan(4, 6))
        assertEquals(without, withSelection)
    }

    // ---- the properties, over every cursor and selection ----------------------------------------------------------

    private val texts = listOf(
        "", "Hello", "Hello world", "Go to [COMPUTER:HOME] and {VAR:A}, now.", "a😀b", " leading", "trailing ",
        "(quote) “hi” 'x'", "multi\nline  text"
    )
    private val insertions = listOf("X", "New York", "[COMPUTER:SELF]", "😀", "")

    @Test
    fun overEveryCursorAndSelection_theResultIsAlwaysSound() {
        for (text in texts) for (ins in insertions) for (s in 0..text.length) for (e in 0..text.length) {
            val label = "text='$text' ins='$ins' sel=$s..$e"
            val r = TextInsertion.insert(text, s, e, ins)
            assertTrue("cursor in range: $label", r.cursor in 0..r.text.length)
            assertFalse("no lone surrogate: $label", hasLoneSurrogate(r.text))
            val lo = minOf(s, e)
            val hi = maxOf(s, e)
            // every token that was not touched by the selection is still whole
            val untouched = TextInsertion.tokenSpans(text).filter { it.end <= lo || it.start >= hi }.map { text.substring(it.start, it.end) }
            val after = TextInsertion.tokenSpans(r.text).map { r.text.substring(it.start, it.end) }.toMutableList()
            for (t in untouched) assertTrue("token $t kept: $label", after.remove(t))
            if (!text.contains("  ") && !ins.contains("  ")) assertFalse("no double space made: $label", r.text.contains("  "))
            if (s == e) {
                // a cursor with nothing selected never deletes anything
                assertEquals("nothing lost: $label", nonBlank(text).length + nonBlank(ins).length, nonBlank(r.text).length)
            }
        }
    }

    // ---- the token patterns must be the ones TemplateEngine really resolves ---------------------------------------------

    @Test
    fun theTokenPatterns_areTheOnesTemplateEngineUses() {
        val source = RepoFiles.read("app/src/main/java/com/example/besu/data/TemplateEngine.kt")
        fun patternOf(name: String): String {
            val m = Regex("val $name = Regex\\(\"\"\"(.+?)\"\"\"\\)").find(source)
            return m?.groupValues?.get(1) ?: error("TemplateEngine.kt no longer defines `$name` the way this test reads it")
        }
        assertEquals(patternOf("variableRegex"), TextInsertion.VARIABLE_TOKEN_PATTERN)
        assertEquals(patternOf("computerRegex"), TextInsertion.COMPUTER_TOKEN_PATTERN)
    }

    private fun render(r: InsertionResult) = r.text.substring(0, r.cursor) + "|" + r.text.substring(r.cursor)

    private fun nonBlank(s: String) = s.filter { !it.isWhitespace() }

    private fun hasLoneSurrogate(s: String): Boolean {
        var i = 0
        while (i < s.length) {
            val c = s[i]
            if (c.isHighSurrogate()) {
                if (i + 1 >= s.length || !s[i + 1].isLowSurrogate()) return true
                i += 2
                continue
            }
            if (c.isLowSurrogate()) return true
            i++
        }
        return false
    }
}
