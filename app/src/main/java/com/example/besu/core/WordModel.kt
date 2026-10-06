// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import kotlinx.serialization.Serializable

/** One learned word as it is saved: its normal key, the form to show it in, how often it was used, and when it was last used. */
@Serializable
data class StoredWord(val key: String, val form: String, val count: Int, val lastUsedAt: Long)

/** How often [next] followed [prev] in the same sentence. */
@Serializable
data class StoredPair(val prev: String, val next: String, val count: Int)

/** The whole model as saved to a file and carried in EXPORT .JSON. */
@Serializable
data class WordModelData(val words: List<StoredWord> = emptyList(), val pairs: List<StoredPair> = emptyList()) {

    /**
     * Why this file must be refused, or null if it is sound. Every reason is specific (a count, a length) so a refused restore can be
     * diagnosed from a log, and **none of them contains a word**: what the person typed never goes into a log.
     */
    fun validate(maxWords: Int = WordModel.MAX_WORDS, maxPairs: Int = WordModel.MAX_PAIRS): String? {
        if (words.size > maxWords) return "learnedWords has ${words.size} words, more than the $maxWords allowed"
        if (pairs.size > maxPairs) return "learnedWords has ${pairs.size} word pairs, more than the $maxPairs allowed"
        val keys = HashSet<String>()
        for (w in words) {
            if (w.key.isBlank()) return "learnedWords has a word with a blank key"
            if (w.key.length > WordTokens.MAX_WORD_LENGTH) return "learnedWords has a key of ${w.key.length} characters, over ${WordTokens.MAX_WORD_LENGTH}"
            if (w.form.length > WordTokens.MAX_WORD_LENGTH) return "learnedWords has a form of ${w.form.length} characters, over ${WordTokens.MAX_WORD_LENGTH}"
            if (w.count < 1 || w.count > WordModel.MAX_COUNT) return "learnedWords has a word with count ${w.count} (must be 1 to ${WordModel.MAX_COUNT})"
            if (w.lastUsedAt < 0) return "learnedWords has a word with lastUsedAt ${w.lastUsedAt}"
            if (!keys.add(w.key)) return "learnedWords lists a word twice"
        }
        for (p in pairs) {
            if (p.prev !in keys || p.next !in keys) return "learnedWords has a pair that names a word the file does not list"
            if (p.count < 1 || p.count > WordModel.MAX_COUNT) return "learnedWords has a pair with count ${p.count} (must be 1 to ${WordModel.MAX_COUNT})"
        }
        return null
    }
}

/** A word with how it ranks. For a follower, [count] is how often it followed the word before. */
data class ScoredWord(val form: String, val key: String, val count: Int, val lastUsedAt: Long)

/**
 * The on-device word model behind word suggestions: how often each word was used and how often one word followed another, learned only
 * from text the person COMMITTED (a statement saved, spoken or copied), never from a tag or a number, and capped (5,000 words, 20,000
 * pairs, the least used evicted) so it stays small and fast. Plain Kotlin (no `android.*`); nothing here touches a file.
 *
 * Not thread-safe: the repository serialises access.
 */
class WordModel(val maxWords: Int = MAX_WORDS, val maxPairs: Int = MAX_PAIRS) {

    companion object {
        const val MAX_WORDS = 5000
        const val MAX_PAIRS = 20000

        /** A ceiling on a stored count, so a hostile file cannot overflow a sum. */
        const val MAX_COUNT = 1_000_000

        /** Loads saved data, DROPPING anything broken instead of failing, and keeping the most used within the caps. */
        fun fromData(data: WordModelData, maxWords: Int = MAX_WORDS, maxPairs: Int = MAX_PAIRS): WordModel =
            WordModel(maxWords, maxPairs).also { it.merge(data) }
    }

    private class Entry(var form: String, var count: Int, var lastUsedAt: Long)

    private val words = HashMap<String, Entry>()
    private val pairs = HashMap<String, HashMap<String, Int>>()
    private var pairTotal = 0

    val wordCount: Int get() = words.size
    val pairCount: Int get() = pairTotal

    // Most used first, then most recent, then the key, so two equal words always sort the same way.
    private val ranking: Comparator<ScoredWord> =
        compareByDescending<ScoredWord> { it.count }.thenByDescending { it.lastUsedAt }.thenBy { it.key }

    fun contains(word: String): Boolean = words.containsKey(WordSuggestions.key(word.trim()))
    fun countOf(word: String): Int = words[WordSuggestions.key(word.trim())]?.count ?: 0
    fun formOf(word: String): String? = words[WordSuggestions.key(word.trim())]?.form

    /**
     * Learns [text] (committed text, with any tags still in it; they are skipped). Each word is counted, and each word is linked to the one
     * before it in the same sentence. A word that only started a sentence ("Hello") is kept in lower case, a name in the middle ("Sarah")
     * keeps its capital, and the most recent mid-sentence form wins.
     */
    fun learn(text: String, now: Long) {
        for (sentence in WordTokens.sentences(text)) {
            var previous: String? = null
            sentence.forEachIndexed { index, span ->
                val key = WordSuggestions.key(span.word)
                val sentenceStartOnly = index == 0 && isTitleCase(span.word)
                val entry = words[key]
                if (entry == null) {
                    words[key] = Entry(if (sentenceStartOnly) key else span.word, 1, now)
                } else {
                    entry.count = (entry.count + 1).coerceAtMost(MAX_COUNT)
                    entry.lastUsedAt = maxOf(entry.lastUsedAt, now)
                    if (!sentenceStartOnly) entry.form = span.word
                }
                previous?.let { addPair(it, key, 1) }
                previous = key
            }
        }
        enforceCaps()
    }

    private fun isTitleCase(word: String): Boolean = word.length >= 2 && word.first().isUpperCase() && word.drop(1).none { it.isUpperCase() }

    private fun addPair(prev: String, next: String, by: Int) {
        val followers = pairs.getOrPut(prev) { HashMap() }
        val had = followers[next]
        if (had == null) pairTotal++
        followers[next] = ((had ?: 0) + by).coerceAtMost(MAX_COUNT)
    }

    /** Words that start with [prefix] (any case, composed or decomposed accents), best first. */
    fun completions(prefix: String, limit: Int = Int.MAX_VALUE): List<ScoredWord> {
        val wanted = WordSuggestions.key(prefix.trim())
        return words.entries
            .filter { it.key.startsWith(wanted) }
            .map { ScoredWord(it.value.form, it.key, it.value.count, it.value.lastUsedAt) }
            .sortedWith(ranking)
            .take(limit)
    }

    /** The words that most often followed [previous], most common first; ties go to the more used word. */
    fun nextWords(previous: String, limit: Int): List<ScoredWord> {
        val followers = pairs[WordSuggestions.key(previous.trim())] ?: return emptyList()
        return followers.entries
            .mapNotNull { (nextKey, pairCount) -> words[nextKey]?.let { ScoredWord(it.form, nextKey, pairCount, it.lastUsedAt) } }
            .sortedWith(compareByDescending<ScoredWord> { it.count }.thenByDescending { words[it.key]?.count ?: 0 }.thenBy { it.key })
            .take(limit)
    }

    /** Every word, best first. */
    fun listWords(): List<ScoredWord> =
        words.entries.map { ScoredWord(it.value.form, it.key, it.value.count, it.value.lastUsedAt) }.sortedWith(ranking)

    /** Removes the word and every pair it is in. True if it was there. */
    fun forget(word: String): Boolean {
        val key = WordSuggestions.key(word.trim())
        if (!words.containsKey(key)) return false
        removeWord(key)
        return true
    }

    fun forgetAll() {
        words.clear()
        pairs.clear()
        pairTotal = 0
    }

    private fun removeWord(key: String) {
        words.remove(key)
        pairs.remove(key)?.let { pairTotal -= it.size }
        val iterator = pairs.entries.iterator()
        while (iterator.hasNext()) {
            val followers = iterator.next().value
            if (followers.remove(key) != null) pairTotal--
            if (followers.isEmpty()) iterator.remove()
        }
    }

    private fun enforceCaps() {
        if (words.size > maxWords) {
            words.entries
                .sortedWith(compareBy<Map.Entry<String, Entry>>({ it.value.count }, { it.value.lastUsedAt }, { it.key }))
                .take(words.size - maxWords)
                .map { it.key }
                .forEach { removeWord(it) }
        }
        if (pairTotal > maxPairs) {
            val all = pairs.flatMap { (prev, followers) -> followers.map { (next, count) -> Triple(prev, next, count) } }
            all.sortedWith(compareBy<Triple<String, String, Int>>({ it.third }, { it.first }, { it.second }))
                .take(pairTotal - maxPairs)
                .forEach { (prev, next, _) ->
                    val followers = pairs[prev] ?: return@forEach
                    if (followers.remove(next) != null) pairTotal--
                    if (followers.isEmpty()) pairs.remove(prev)
                }
        }
    }

    /** The model as saved: words by key, pairs by (prev, next), so the same model always saves the same way. */
    fun toData(): WordModelData = WordModelData(
        words = words.entries.sortedBy { it.key }.map { StoredWord(it.key, it.value.form, it.value.count, it.value.lastUsedAt) },
        pairs = pairs.entries.sortedBy { it.key }.flatMap { (prev, followers) -> followers.entries.sortedBy { it.key }.map { StoredPair(prev, it.key, it.value) } },
    )

    /**
     * Folds saved data into this model (a restored backup, or the load from disk). It NEVER lowers a count or removes a word the data does
     * not mention; the more recent form of a word wins; anything broken in the data is dropped; the caps are enforced afterwards.
     */
    fun merge(data: WordModelData) {
        for (w in data.words) {
            val key = WordSuggestions.key(w.key.trim())
            if (key.isBlank() || key.length > WordTokens.MAX_WORD_LENGTH || w.count < 1 || w.lastUsedAt < 0) continue
            val form = w.form.ifBlank { key }.take(WordTokens.MAX_WORD_LENGTH)
            val count = w.count.coerceAtMost(MAX_COUNT)
            val entry = words[key]
            if (entry == null) {
                words[key] = Entry(form, count, w.lastUsedAt)
            } else {
                if (w.lastUsedAt > entry.lastUsedAt) entry.form = form
                entry.count = maxOf(entry.count, count)
                entry.lastUsedAt = maxOf(entry.lastUsedAt, w.lastUsedAt)
            }
        }
        for (p in data.pairs) {
            val prev = WordSuggestions.key(p.prev.trim())
            val next = WordSuggestions.key(p.next.trim())
            if (p.count < 1 || !words.containsKey(prev) || !words.containsKey(next)) continue
            val followers = pairs.getOrPut(prev) { HashMap() }
            val had = followers[next]
            if (had == null) pairTotal++
            followers[next] = maxOf(had ?: 0, p.count.coerceAtMost(MAX_COUNT))
        }
        enforceCaps()
    }
}
