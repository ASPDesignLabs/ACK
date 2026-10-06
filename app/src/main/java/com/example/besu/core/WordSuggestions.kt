// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.text.Normalizer

/** One remembered value for a field: what it is, how often it has been used, and when it was last used (any consistent clock). */
data class SuggestionCandidate(val value: String, val count: Int, val lastUsedAt: Long)

/**
 * The rules for the history chips under a field (B3). Plain Kotlin (no `android.*`); data/AutocompleteHistoryRepository.kt only
 * stores and loads, and asks this what to show and what to store.
 *
 *  - **Nothing typed:** the top five by use count, then most recently used (what the chips have always shown).
 *  - **Text typed:** only values that START WITH it, ignoring case and treating composed and decomposed accents as the same
 *    (NFC, then lower case with a locale-independent rule, so a Turkish phone gets the same result). Spaces at the ends of what was
 *    typed are ignored.
 *  - **Case variants are one word.** "Mum" and "mum" count together; the most recently used form is the one shown.
 *  - **Nothing already typed is suggested back:** a value is left out if what is typed is exactly one of its forms.
 *  - **The order never depends on how the history was stored:** count, then recency, then the value itself.
 *  - **One field only.** This works on the values of ONE field; a value learned in one field is never offered in another because
 *    the repository only ever hands it that field's values.
 *
 * It never changes what is stored in place: [recordUsage] returns a new list and touches at most one entry.
 */
object WordSuggestions {
    /** Chips shown per field. A test keeps this equal to AutocompleteHistoryRepository.MAX_SUGGESTIONS. */
    const val MAX_SHOWN = 5

    /** Values remembered per field. A test keeps this equal to AutocompleteHistoryRepository's own limit. */
    const val MAX_STORED_PER_SCOPE = 20

    private fun nfc(text: String): String = Normalizer.normalize(text, Normalizer.Form.NFC)

    /**
     * What two values must share to count as the same word: NFC, lower case, NFC again (lower-casing can split a letter from its
     * accent). Kotlin's lowercase() is locale-independent, so "I" becomes "i" on every phone.
     */
    fun key(text: String): String = nfc(nfc(text).lowercase())

    // The values that are the same word, seen as one: summed use, latest use, and the form to show.
    private class Word(val members: List<SuggestionCandidate>) {
        val count: Int = members.sumOf { it.count }
        val lastUsedAt: Long = members.maxOf { it.lastUsedAt }
        val shown: String = members.sortedWith(RECENT_FIRST).first().value
    }

    // Most recently used first; then the more used; then the value itself, so two equal entries always sort the same way.
    private val RECENT_FIRST: Comparator<SuggestionCandidate> =
        compareByDescending<SuggestionCandidate> { it.lastUsedAt }.thenByDescending { it.count }.thenBy { it.value }

    private val BEST_FIRST: Comparator<Word> =
        compareByDescending<Word> { it.count }.thenByDescending { it.lastUsedAt }.thenBy { it.shown }

    fun suggest(candidates: List<SuggestionCandidate>, typed: String, limit: Int = MAX_SHOWN): List<String> {
        val typedText = typed.trim()
        val typedKey = key(typedText)
        val typedExact = nfc(typedText)
        val words = candidates
            .filter { it.value.isNotBlank() }
            .groupBy { key(it.value.trim()) }
        val kept = words.filter { (wordKey, members) ->
            typedKey.isEmpty() || (wordKey.startsWith(typedKey) && members.none { nfc(it.value.trim()) == typedExact })
        }
        return kept.values.map { Word(it) }.sortedWith(BEST_FIRST).take(limit).map { it.shown }
    }

    /**
     * The history after [value] was typed and committed. Blank is never recorded. A value that is the same word as one already
     * remembered counts up THAT entry (the most recently used of them if an older history already holds two forms) and takes the
     * form just typed; every other entry is left exactly as it was. A new value is added. Over [cap] entries, the least used (then
     * oldest) go, as they always have.
     */
    fun recordUsage(
        entries: List<SuggestionCandidate>,
        value: String,
        now: Long,
        cap: Int = MAX_STORED_PER_SCOPE
    ): List<SuggestionCandidate> {
        val trimmed = value.trim()
        if (trimmed.isEmpty()) return entries
        val wanted = key(trimmed)
        val target = entries.withIndex()
            .filter { key(it.value.value.trim()) == wanted }
            .minWithOrNull(Comparator { a, b -> RECENT_FIRST.compare(a.value, b.value) })
        val updated = entries.toMutableList()
        if (target != null) {
            updated[target.index] = SuggestionCandidate(trimmed, target.value.count + 1, now)
        } else {
            updated.add(SuggestionCandidate(trimmed, 1, now))
        }
        if (updated.size <= cap) return updated
        return updated
            .sortedWith(compareByDescending<SuggestionCandidate> { it.count }.thenByDescending { it.lastUsedAt }.thenBy { it.value })
            .take(cap)
    }
}
