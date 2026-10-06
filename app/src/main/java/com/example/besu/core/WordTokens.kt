// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.text.Normalizer

/**
 * What counts as a word for the word model (and for word suggestions), and where a sentence ends. Plain Kotlin (no `android.*`).
 *
 * A word is a run of letters of ANY script (with their combining accents) in which an apostrophe or hyphen may sit BETWEEN letters:
 * "don't", "well-known". A curly apostrophe is made straight and the word is put in composed (NFC) form. **Anything with a digit in it
 * is not a word** (a phone number, a code, "3rd"), an emoji or any other symbol is a separator, and a [COMPUTER:..] or {VAR..} tag is
 * never a word and ends the sentence around it. A run longer than [MAX_WORD_LENGTH] characters is not a word.
 */
object WordTokens {
    /** Longer runs (a pasted code, a URL) are not words. A backup field is held to the same ceiling. */
    const val MAX_WORD_LENGTH = 60

    // Stands in for every character of a tag, so positions stay the same and the gap between two words shows a tag was there.
    private const val TAG = '￼'

    /** A word, where it sits in the ORIGINAL text ([start, end)), and its normal form. */
    data class WordSpan(val start: Int, val end: Int, val word: String)

    fun isMark(cp: Int): Boolean {
        val type = Character.getType(cp)
        return type == Character.NON_SPACING_MARK.toInt() || type == Character.COMBINING_SPACING_MARK.toInt() ||
            type == Character.ENCLOSING_MARK.toInt()
    }

    fun isWordChar(cp: Int): Boolean = Character.isLetterOrDigit(cp) || isMark(cp)

    fun isJoiner(cp: Int): Boolean = cp == '\''.code || cp == 0x2019 || cp == '-'.code

    /** [text] with every tag blanked out character for character, so nothing inside a tag can be read as a word. */
    fun maskTokens(text: String): String {
        val tags = TextInsertion.tokenSpans(text)
        if (tags.isEmpty()) return text
        val masked = StringBuilder(text)
        for (tag in tags) for (i in tag.start until tag.end) masked.setCharAt(i, TAG)
        return masked.toString()
    }

    fun normalize(raw: String): String = Normalizer.normalize(raw.replace('’', '\''), Normalizer.Form.NFC)

    fun words(text: String): List<WordSpan> {
        val masked = maskTokens(text)
        val found = ArrayList<WordSpan>()
        var i = 0
        while (i < masked.length) {
            val first = masked.codePointAt(i)
            if (!isWordChar(first)) {
                i += Character.charCount(first)
                continue
            }
            val start = i
            var j = i
            var hasLetter = false
            var hasDigit = false
            while (j < masked.length) {
                val cp = masked.codePointAt(j)
                val width = Character.charCount(cp)
                if (isWordChar(cp)) {
                    if (Character.isDigit(cp)) hasDigit = true else if (Character.isLetter(cp)) hasLetter = true
                    j += width
                } else if (isJoiner(cp) && j + width < masked.length && isWordChar(masked.codePointAt(j + width))) {
                    j += width
                } else {
                    break
                }
            }
            if (hasLetter && !hasDigit && j - start <= MAX_WORD_LENGTH) found.add(WordSpan(start, j, normalize(masked.substring(start, j))))
            i = j
        }
        return found
    }

    /**
     * The words grouped into sentences. A sentence ends at a full stop, question mark, exclamation mark or ellipsis, a line break, a tag,
     * or a number: words are only ever linked to the one next to them in the SAME sentence.
     */
    fun sentences(text: String): List<List<WordSpan>> {
        val masked = maskTokens(text)
        val sentences = ArrayList<MutableList<WordSpan>>()
        var current: MutableList<WordSpan>? = null
        var previousEnd = 0
        for (span in words(text)) {
            if (current == null || endsSentence(masked, previousEnd, span.start)) {
                current = ArrayList()
                sentences.add(current)
            }
            current.add(span)
            previousEnd = span.end
        }
        return sentences
    }

    private fun endsSentence(masked: String, from: Int, to: Int): Boolean {
        for (k in from until to) {
            val c = masked[k]
            if (c == '.' || c == '!' || c == '?' || c == '…' || c == '\n' || c == '\r' || c == '\u0085' ||
                c == ' ' || c == ' ' || c == TAG || Character.isDigit(c)
            ) return true
        }
        return false
    }
}
