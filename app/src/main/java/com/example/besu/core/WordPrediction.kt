// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/** What the suggestion strip is offering: the rest of the word being typed, or the word that usually comes next. */
enum class PredictionKind { COMPLETE, NEXT }

/**
 * [replace] is the half-typed word a COMPLETE suggestion replaces (null for NEXT, which is inserted at the cursor). Both go through
 * [TextInsertion], which decides the spacing.
 */
data class Prediction(val kind: PredictionKind?, val replace: CharSpan?, val suggestions: List<String>) {
    companion object {
        val NONE = Prediction(null, null, emptyList())
    }
}

/**
 * Decides what word suggestions to offer for the text before the cursor. Plain Kotlin (no `android.*`).
 *
 *  - **COMPLETE:** the cursor is at the END of a word being typed: the model's words that start with it (and any [extraWords], names the
 *    person already keeps), best first, capitalised if the typed letters are. Never the word already typed.
 *  - **NEXT:** the cursor is after a space that follows a word: the words that most often followed it, in the same sentence.
 *  - **Nothing** (quiet is the rule): in the middle of a word, inside a tag, after punctuation or a full stop or a line break, at the start,
 *    for anything with a digit, or when there is nothing worth offering.
 *
 * Nothing here inserts anything; a suggestion is only ever a button the person taps.
 */
object WordPrediction {
    /** How a name from elsewhere ranks against learned words: ahead of one used once, behind one used often. */
    const val EXTRA_COUNT = 2

    private const val DEFAULT_LIMIT = 3

    fun predict(model: WordModel, extraWords: List<String>, text: String, cursor: Int, limit: Int = DEFAULT_LIMIT): Prediction {
        val at = cursor.coerceIn(0, text.length)
        if (TextInsertion.tokenSpans(text).any { at > it.start && at < it.end }) return Prediction.NONE
        val masked = WordTokens.maskTokens(text)
        if (continuesAWord(masked, at)) return Prediction.NONE

        val start = wordStartBefore(masked, at)
        return if (start < at) complete(model, extraWords, masked, start, at, limit) else next(model, masked, at, limit)
    }

    private fun complete(model: WordModel, extraWords: List<String>, masked: String, start: Int, at: Int, limit: Int): Prediction {
        val partial = masked.substring(start, at)
        if (partial.length > WordTokens.MAX_WORD_LENGTH || partial.any { Character.isDigit(it) } || partial.none { Character.isLetter(it) }) {
            return Prediction.NONE
        }
        val prefix = WordTokens.normalize(partial)
        val prefixKey = WordSuggestions.key(prefix)

        val candidates = model.completions(prefix).toMutableList()
        val seen = candidates.map { it.key }.toMutableSet()
        for (name in extraWords) {
            val key = WordSuggestions.key(name)
            if (key.isNotEmpty() && key.startsWith(prefixKey) && seen.add(key)) candidates.add(ScoredWord(name, key, EXTRA_COUNT, 0L))
        }

        val capitalise = prefix.first().isUpperCase()
        val forms = candidates
            .filter { WordTokens.normalize(it.form) != prefix }
            .sortedWith(compareByDescending<ScoredWord> { it.count }.thenByDescending { it.lastUsedAt }.thenBy { it.key })
            .map { if (capitalise) it.form.replaceFirstChar { c -> c.titlecase() } else it.form }
            .distinct()
            .take(limit)
        return if (forms.isEmpty()) Prediction.NONE else Prediction(PredictionKind.COMPLETE, CharSpan(start, at), forms)
    }

    private fun next(model: WordModel, masked: String, at: Int, limit: Int): Prediction {
        if (at == 0) return Prediction.NONE
        // Only straight after a space (or other white space) that follows a word, with no line break in between.
        var gap = at
        var lineBreak = false
        while (gap > 0 && masked[gap - 1].let { it.isWhitespace() || it == '\u0085' }) {
            val c = masked[gap - 1]
            if (c == '\n' || c == '\r' || c == '\u0085' || c == ' ' || c == ' ') lineBreak = true
            gap--
        }
        if (gap == at || gap == 0 || lineBreak) return Prediction.NONE
        val previousStart = wordStartBefore(masked, gap)
        if (previousStart == gap) return Prediction.NONE
        val previous = masked.substring(previousStart, gap)
        if (previous.any { Character.isDigit(it) } || previous.none { Character.isLetter(it) }) return Prediction.NONE
        val forms = model.nextWords(WordTokens.normalize(previous), limit).map { it.form }
        return if (forms.isEmpty()) Prediction.NONE else Prediction(PredictionKind.NEXT, null, forms)
    }

    // True if the character after the cursor carries on a word, so the cursor is in the middle of one.
    private fun continuesAWord(masked: String, at: Int): Boolean {
        if (at >= masked.length) return false
        val cp = masked.codePointAt(at)
        if (WordTokens.isWordChar(cp)) return true
        val width = Character.charCount(cp)
        return WordTokens.isJoiner(cp) && at > 0 && at + width < masked.length &&
            WordTokens.isWordChar(masked.codePointBefore(at)) && WordTokens.isWordChar(masked.codePointAt(at + width))
    }

    // Where the word that ends at [end] begins (equal to [end] if there is none). An apostrophe or hyphen counts only between letters.
    private fun wordStartBefore(masked: String, end: Int): Int {
        var start = end
        while (start > 0) {
            val before = masked.codePointBefore(start)
            val width = Character.charCount(before)
            if (WordTokens.isWordChar(before)) {
                start -= width
            } else if (WordTokens.isJoiner(before) && start < end && start - width > 0 && WordTokens.isWordChar(masked.codePointBefore(start - width))) {
                start -= width
            } else {
                break
            }
        }
        return start
    }
}
