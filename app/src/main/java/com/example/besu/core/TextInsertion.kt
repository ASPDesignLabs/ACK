// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/** A half-open range of characters in a string: [start, end). Plain Kotlin, so it is not tied to Compose's own TextRange. */
data class CharSpan(val start: Int, val end: Int)

/**
 * The new text and where the cursor goes. [replaced] is the span of the OLD text that was replaced (after any widening for a
 * token or an emoji): empty for a bare cursor or an empty insertion. A caller that keeps position-based data alongside the text
 * (TokenSlots) needs it to know which tokens went.
 */
data class InsertionResult(val text: String, val cursor: Int, val replaced: CharSpan = CharSpan(cursor, cursor))

enum class InsertMode {
    /** A word or token: spaces are added or left out so it neither glues onto a neighbour nor leaves a double space. */
    WORD,

    /** Exactly what was given, with no spacing at all (punctuation, a deliberate paste). */
    EXACT
}

/**
 * The one rule for dropping a word or token into text, used by every surface that has an insert button (B1), so the same
 * button behaves the same way everywhere. Plain Kotlin (no `android.*`); the rules are pinned by TextInsertionTest.
 *
 * What it does, in order:
 *  1. The selection (or the replace range, which wins) is put in order, kept inside the text, and never left between the two
 *     halves of an emoji. A bare cursor between the halves moves to after the emoji; a selection is widened to cover it.
 *  2. It never splits a token. A bare cursor inside a token moves to after it; a selection that covers part of a token is
 *     widened to cover all of it. A token is whatever TemplateEngine would resolve (a drift test keeps the two the same).
 *  3. WORD mode trims the insertion, then adds one leading space only if there is text before the insertion point and the
 *     character there is not white space or an opening bracket or quote; and one trailing space only if the insertion is at
 *     the very end (so typing can continue) or the next character is not white space or closing punctuation.
 *  4. The cursor lands after the insertion and any space this added. If the next character is exactly one ordinary space and
 *     none was added, the cursor steps over it, so typing continues after that space.
 *
 * An empty insertion changes nothing (it never deletes a selection).
 */
object TextInsertion {
    // Copied from data/TemplateEngine.kt (which is not plain Kotlin, so it cannot be shared directly). TextInsertionTest reads
    // that file and fails if these two stop matching.
    const val VARIABLE_TOKEN_PATTERN = """\{VAR(?::([A-C]))?\}"""
    const val COMPUTER_TOKEN_PATTERN = """\[COMPUTER:([A-Z0-9_]+)\]"""

    private val tokenRegex = Regex("$VARIABLE_TOKEN_PATTERN|$COMPUTER_TOKEN_PATTERN")

    private const val OPENING_BRACKETS_AND_QUOTES = "([{“‘„‚«‹"
    private const val CLOSING_PUNCTUATION_AND_QUOTES = ".,!?;:)]}”’»›"

    /** Where each token in [text] sits, in order. */
    fun tokenSpans(text: String): List<CharSpan> =
        tokenRegex.findAll(text).map { CharSpan(it.range.first, it.range.last + 1) }.toList()

    fun insert(
        text: String,
        selectionStart: Int,
        selectionEnd: Int,
        insertion: String,
        mode: InsertMode = InsertMode.WORD,
        replace: CharSpan? = null
    ): InsertionResult {
        val span = snap(text, replace ?: CharSpan(selectionStart, selectionEnd))
        val piece = if (mode == InsertMode.WORD) insertion.trim { isSpaceLike(it) } else insertion
        if (piece.isEmpty()) return InsertionResult(text, span.end, CharSpan(span.end, span.end))

        val before = text.substring(0, span.start)
        val after = text.substring(span.end)
        if (mode == InsertMode.EXACT) return InsertionResult(before + piece + after, before.length + piece.length, span)

        val leading = needsLeadingSpace(text, span.start)
        val trailing = needsTrailingSpace(text, span.end)
        val inserted = (if (leading) " " else "") + piece + (if (trailing) " " else "")
        var cursor = before.length + inserted.length
        if (!trailing && nextIsExactlyOneOrdinarySpace(text, span.end)) cursor += 1
        return InsertionResult(before + inserted + after, cursor, span)
    }

    private fun snap(text: String, raw: CharSpan): CharSpan {
        var start = raw.start.coerceIn(0, text.length)
        var end = raw.end.coerceIn(0, text.length)
        if (start > end) {
            val t = start
            start = end
            end = t
        }
        val tokens = tokenSpans(text)
        if (start == end) {
            var p = start
            if (splitsSurrogatePair(text, p)) p += 1
            tokens.firstOrNull { p > it.start && p < it.end }?.let { p = it.end }
            return CharSpan(p, p)
        }
        if (splitsSurrogatePair(text, start)) start -= 1
        if (splitsSurrogatePair(text, end)) end += 1
        val widenedStart = tokens.firstOrNull { start > it.start && start < it.end }?.start ?: start
        val widenedEnd = tokens.firstOrNull { end > it.start && end < it.end }?.end ?: end
        return CharSpan(widenedStart, widenedEnd)
    }

    private fun splitsSurrogatePair(text: String, index: Int): Boolean =
        index in 1 until text.length && text[index - 1].isHighSurrogate() && text[index].isLowSurrogate()

    // Kotlin's isWhitespace covers every Unicode space, including the no-break space, but not U+0085 (next line).
    private fun isSpaceLike(c: Char): Boolean = c.isWhitespace() || c == '\u0085'

    private fun needsLeadingSpace(text: String, start: Int): Boolean {
        if (start <= 0) return false
        val previous = text[start - 1]
        return !isSpaceLike(previous) && !isOpening(text, start - 1)
    }

    private fun needsTrailingSpace(text: String, end: Int): Boolean {
        if (end >= text.length) return true
        val next = text[end]
        return !isSpaceLike(next) && !isClosing(text, end)
    }

    private fun nextIsExactlyOneOrdinarySpace(text: String, end: Int): Boolean =
        end < text.length && text[end] == ' ' && !(end + 1 < text.length && text[end + 1] == ' ')

    // A straight quote can open or close, so it is judged by what comes before it: at the start, after white space, or after an
    // opening bracket or quote, it opens; anywhere else it closes (and an apostrophe inside a word is not an opening quote).
    private fun isOpening(text: String, index: Int): Boolean {
        val c = text[index]
        if (c in OPENING_BRACKETS_AND_QUOTES) return true
        if (c != '"' && c != '\'') return false
        if (index == 0) return true
        val before = text[index - 1]
        return isSpaceLike(before) || before in OPENING_BRACKETS_AND_QUOTES
    }

    private fun isClosing(text: String, index: Int): Boolean {
        val c = text[index]
        if (c in CLOSING_PUNCTUATION_AND_QUOTES) return true
        return (c == '"' || c == '\'') && !isOpening(text, index)
    }
}
