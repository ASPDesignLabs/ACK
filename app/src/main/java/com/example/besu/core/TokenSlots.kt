// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/** The two kinds of token whose values are stored by position: every {VAR...} is one list, every [COMPUTER:..] another. */
enum class SlotFamily { VARIABLE, COMPUTER }

/**
 * A phrase keeps its local {VAR} values, and its [COMPUTER:..] fallbacks, as lists BY POSITION: the first {VAR} in the text uses
 * the first value, the second {VAR} the second, and so on (TemplateEngine.resolve counts them in text order). So a token put into
 * the MIDDLE of the text has to put a blank value at the same position in its list, and a token removed from the middle has to take
 * its value with it; otherwise every value after it attaches to the wrong token.
 *
 * Plain Kotlin (no `android.*`). The Matrix and Quick Actions editors' insert buttons use this when they insert at the cursor.
 */
object TokenSlots {
    private val variableToken = Regex(TextInsertion.VARIABLE_TOKEN_PATTERN)
    private val computerToken = Regex(TextInsertion.COMPUTER_TOKEN_PATTERN)

    private fun regexFor(family: SlotFamily): Regex = when (family) {
        SlotFamily.VARIABLE -> variableToken
        SlotFamily.COMPUTER -> computerToken
    }

    /** Where each token of [family] sits in [text], in order. */
    fun spansOf(text: String, family: SlotFamily): List<CharSpan> =
        regexFor(family).findAll(text).map { CharSpan(it.range.first, it.range.last + 1) }.toList()

    /** True if [candidate] (ignoring spaces at its ends) is exactly one token of [family]. */
    fun isToken(candidate: String, family: SlotFamily): Boolean = regexFor(family).matchEntire(candidate.trim()) != null

    /**
     * The value list for [family] after [inserted] replaced the span [replaced] of [oldText] (TextInsertion.insert's
     * `InsertionResult.replaced`): the values of tokens inside the span are dropped, and, if [inserted] is a token of this family,
     * a blank value is put where the new token now sits. Every other token keeps its own value. A list shorter than the tokens
     * (stored data can be) is padded with blanks first, so nothing is removed from the wrong place.
     */
    fun realign(values: List<String>, oldText: String, replaced: CharSpan, inserted: String, family: SlotFamily): List<String> {
        val spans = spansOf(oldText, family)
        val before = spans.count { it.end <= replaced.start }
        val inside = spans.count { it.start >= replaced.start && it.end <= replaced.end }
        val out = values.toMutableList()
        while (out.size < spans.size) out.add("")
        repeat(inside) { out.removeAt(before) }
        if (isToken(inserted, family)) out.add(before, "")
        return out
    }
}
