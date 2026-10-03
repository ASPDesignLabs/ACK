// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/** One card of a script: what to read in one go, how long that should take, and anything to be careful about. */
data class Card(val text: String, val words: Int, val estS: Double, val warnings: List<String>)

/** A card's numbers worked out again, for when the person's pace changes after the cards were made. */
data class CardInfo(val words: Int, val estS: Double, val warnings: List<String>)

// Cutting a script into cards (format document, section 6). The phone sizes the cards so that no audio ever has to be cut in
// script mode: one card, one clip. A line-for-line port of ack_capture_reference.split_cards; CardSplitterTest holds it to the
// shared test cases.
object CardSplitter {
    private val ABBREVIATIONS = setOf("mr.", "mrs.", "ms.", "dr.", "st.", "vs.", "etc.", "e.g.", "i.e.", "no.", "jr.", "sr.", "prof.", "gen.", "col.")
    private const val CLOSERS = "\"'”’)]"
    private const val TERMINALS = ".!?…"
    private const val OPENERS = "\"'“‘(["
    private const val STRONG_BREAKS = ";:—–"
    private const val SYMBOLS = "&@#%*_=+<>{}\\/|"

    // White space the way Python's str.split() sees it (Java's isWhitespace leaves out U+0085 and the separator controls).
    private fun isSpace(c: Char) = c.isWhitespace() || c == '\u0085' || c in '\u001c'..'\u001f'

    private fun words(s: String): List<String> {
        val out = mutableListOf<String>()
        var start = -1
        for (i in s.indices) {
            if (isSpace(s[i])) {
                if (start >= 0) { out.add(s.substring(start, i)); start = -1 }
            } else if (start < 0) {
                start = i
            }
        }
        if (start >= 0) out.add(s.substring(start))
        return out
    }

    /** A letter or a number of any script (Unicode general category starting with L or N). */
    private fun isWord(token: String): Boolean = token.any { val c = it.category.code; c.startsWith("L") || c.startsWith("N") }

    private fun wordCount(tokens: List<String>) = tokens.count { isWord(it) }

    private fun endsWithAfterClosers(token: String, set: String): Boolean {
        val stripped = token.trimEnd { it in CLOSERS }
        return stripped.isNotEmpty() && stripped.last() in set
    }

    private fun startsLikeSentence(token: String): Boolean {
        val rest = token.trimStart { it in OPENERS }
        return rest.isNotEmpty() && (rest[0] in 'A'..'Z' || rest[0] in '0'..'9')
    }

    private fun paragraphs(textIn: String, lines: String): List<String> {
        val cleaned = StringBuilder()
        for (ch in textIn.replace("\r\n", "\n").replace('\r', '\n').replace('\t', ' ')) {
            if (ch == '\n' || (ch >= ' ' && ch != '\u007f')) cleaned.append(ch)
        }
        val rows = cleaned.toString().split('\n')
        if (lines == "keep") return rows.map { it.trim { c -> isSpace(c) } }.filter { it.isNotEmpty() }
        val out = mutableListOf<String>()
        val current = mutableListOf<String>()
        fun flush() {
            if (current.isNotEmpty()) { out.add(words(current.joinToString(" ")).joinToString(" ")); current.clear() }
        }
        for (row in rows) {
            if (row.all { isSpace(it) }) flush() else current.add(row)
        }
        flush()
        return out.filter { it.isNotEmpty() }
    }

    private fun sentences(tokens: List<String>): List<List<String>> {
        val out = mutableListOf<List<String>>()
        var cur = mutableListOf<String>()
        for (i in tokens.indices) {
            val t = tokens[i]
            cur.add(t)
            val next = tokens.getOrNull(i + 1)
            val ends = endsWithAfterClosers(t, TERMINALS) && t.lowercase().trimEnd { it in CLOSERS } !in ABBREVIATIONS
            if (ends && (next == null || startsLikeSentence(next))) { out.add(cur); cur = mutableListOf() }
        }
        if (cur.isNotEmpty()) out.add(cur)
        return out
    }

    private fun splitLong(tokens: List<String>, maxWords: Int): List<List<String>> {
        val n = wordCount(tokens)
        if (n <= maxWords) return listOf(tokens)
        var bestClass = 0
        var bestCloseness = 0.0
        var bestIndex = -1
        var left = 0
        for (i in 0 until tokens.size - 1) {                      // cut after token i
            if (isWord(tokens[i])) left++
            val right = n - left
            if (left < CaptureConstants.MIN_SPLIT_WORDS || right < CaptureConstants.MIN_SPLIT_WORDS) continue
            val cls = when {
                endsWithAfterClosers(tokens[i], STRONG_BREAKS) -> 3
                endsWithAfterClosers(tokens[i], ",") -> 2
                else -> 1
            }
            val closeness = -abs(left - n / 2.0)
            // the best cut: highest class, then closest to the middle, then the earliest
            val better = bestIndex < 0 || cls > bestClass || (cls == bestClass && closeness > bestCloseness)
            if (better) { bestClass = cls; bestCloseness = closeness; bestIndex = i }
        }
        if (bestIndex < 0) return listOf(tokens)
        return splitLong(tokens.subList(0, bestIndex + 1), maxWords) + splitLong(tokens.subList(bestIndex + 1, tokens.size), maxWords)
    }

    private fun mergeRunts(cardsIn: List<List<String>>, maxWords: Int): List<List<String>> {
        val cards = cardsIn.toMutableList()
        var changed = true
        while (changed && cards.size > 1) {
            changed = false
            for (idx in cards.indices) {
                val w = wordCount(cards[idx])
                if (w >= CaptureConstants.MIN_CARD_WORDS) continue
                if (idx > 0 && wordCount(cards[idx - 1]) + w <= maxWords) {
                    cards[idx - 1] = cards[idx - 1] + cards[idx]
                    cards.removeAt(idx)
                    changed = true
                    break
                }
                if (idx + 1 < cards.size && w + wordCount(cards[idx + 1]) <= maxWords) {
                    cards[idx + 1] = cards[idx] + cards[idx + 1]
                    cards.removeAt(idx)
                    changed = true
                    break
                }
            }
        }
        return cards
    }

    private fun capChars(textIn: String): List<String> {
        val out = mutableListOf<String>()
        var text = textIn
        val limit = CaptureConstants.MAX_CARD_CHARS
        while (text.length > limit) {
            var cut = text.lastIndexOf(' ', limit)
            if (cut <= 0) cut = limit
            out.add(text.substring(0, cut).trimEnd { isSpace(it) })
            text = text.substring(cut).trimStart { isSpace(it) }
        }
        out.add(text)
        return out
    }

    private fun clampPace(pace: Double) = min(max(pace, CaptureConstants.PACE_MIN_WPS), CaptureConstants.PACE_MAX_WPS)

    /** Words, estimated seconds and warnings for a card at a given pace. */
    fun describeCard(text: String, paceWps: Double): CardInfo {
        val pace = clampPace(paceWps)
        val w = wordCount(words(text))
        val est = LevelMath.rnd(w / pace, 1)
        val warnings = mutableListOf<String>()
        if (text.any { it.isDigit() }) warnings.add("digits")
        if (text.any { it in SYMBOLS }) warnings.add("symbols")
        if (est > CaptureConstants.MAX_EST_S) warnings.add("long")
        return CardInfo(w, est, warnings)
    }

    /** `lines` is "join" (a line break is a space; a blank line ends a paragraph) or "keep" (every non-empty line is its own paragraph). */
    fun splitCards(text: String, paceWps: Double = CaptureConstants.DEFAULT_PACE_WPS, lines: String = "join"): List<Card> {
        val pace = clampPace(paceWps)
        val budget = max(6, floor(pace * CaptureConstants.TARGET_S).toInt())
        val maxWords = max(budget, floor(pace * CaptureConstants.MAX_EST_S).toInt())
        val cards = mutableListOf<List<String>>()
        for (para in paragraphs(text, lines)) {
            val tokens = words(para)
            if (wordCount(tokens) == 0) continue
            val units = mutableListOf<List<String>>()
            for (s in sentences(tokens)) units.addAll(splitLong(s, maxWords))
            val paragraphCards = mutableListOf<List<String>>()
            var cur = mutableListOf<String>()
            var curWords = 0
            for (u in units) {
                val w = wordCount(u)
                if (cur.isNotEmpty() && curWords + w > budget) {
                    paragraphCards.add(cur)
                    cur = mutableListOf()
                    curWords = 0
                }
                cur.addAll(u)
                curWords += w
            }
            if (cur.isNotEmpty()) paragraphCards.add(cur)
            cards.addAll(mergeRunts(paragraphCards, maxWords))
        }
        val out = mutableListOf<Card>()
        for (toks in cards) {
            for (piece in capChars(toks.joinToString(" "))) {
                val info = describeCard(piece, pace)
                out.add(Card(piece, info.words, info.estS, info.warnings))
            }
        }
        return out
    }

    /**
     * The person's own reading pace, in words per second, from clips they have kept: all the words on the cards divided by all the
     * seconds of speech in them, limited to the allowed range. Null until PACE_MIN_CLIPS clips have a speech span.
     */
    fun measurePace(clips: List<Pair<String, SpeechSpan?>>): Double? {
        val usable = clips.filter { it.second != null && it.second!!.endS > it.second!!.startS }
        if (usable.size < CaptureConstants.PACE_MIN_CLIPS) return null
        val total = usable.sumOf { wordCount(words(it.first)) }
        val seconds = usable.sumOf { it.second!!.endS - it.second!!.startS }
        if (seconds <= 0.0 || total == 0) return null
        return clampPace(total / seconds)
    }
}
