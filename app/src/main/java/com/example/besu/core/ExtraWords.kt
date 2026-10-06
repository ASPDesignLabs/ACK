// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Turns the names the person already keeps elsewhere (Target Computer entry names, Shared Root Variable values) into extra suggestion
 * candidates for [WordPrediction]. Plain Kotlin (no `android.*`).
 *
 * These are read live every time and **never copied into the learned words**: renaming a contact changes what is offered, and deleting it
 * stops it being offered, with nothing left behind. Only the words are used (split like any typed text), so a phone number, a street number or a
 * code is never a candidate, and neither is a tag.
 */
object ExtraWords {
    /** A ceiling so a very large address book cannot slow every keystroke. */
    const val MAX_WORDS = 500

    /** A single letter is never worth a button. */
    const val MIN_LETTERS = 2

    fun fromTexts(texts: List<String>): List<String> {
        val seen = HashSet<String>()
        val out = ArrayList<String>()
        for (text in texts) {
            for (span in WordTokens.words(text)) {
                if (span.word.count { Character.isLetter(it) } < MIN_LETTERS) continue
                if (!seen.add(WordSuggestions.key(span.word))) continue
                out.add(span.word)
                if (out.size >= MAX_WORDS) return out
            }
        }
        return out
    }
}
