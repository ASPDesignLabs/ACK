// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Test
import java.util.Random

class DisplayTextTest {
    private fun legacy(raw: String) = resolveDisplayText(raw, targetName = null, matrixVisualOverride = null, fullText = false)
    private fun full(raw: String) = resolveDisplayText(raw, targetName = null, matrixVisualOverride = null, fullText = true)

    private fun words(n: Int) = (1..n).joinToString(" ") { "w$it" }

    // --- the legacy 5-word rule (fullText = false), exactly as it was ---

    @Test
    fun aFiveWordPhraseIsUnchangedButUppercased() {
        assertEquals("I NEED SOME WATER NOW", legacy("I need some water now"))
    }

    @Test
    fun aSixWordPhraseIsCutToAlertPlusThreeWords() {
        assertEquals("ALERT:\nA B C...", legacy("a b c d e f"))
    }

    @Test
    fun theLimitIsExactlyFiveWords_sixIsTheFirstCut() {
        assertEquals("W1 W2 W3 W4 W5", legacy(words(5)))
        assertEquals("ALERT:\nW1 W2 W3...", legacy(words(6)))
    }

    // --- full text (fullText = true) ---

    @Test
    fun theSameSixWordPhraseIsCompleteWhenFullTextIsOn() {
        assertEquals("A B C D E F", full("a b c d e f"))
    }

    @Test
    fun aTwelveWordAndAFourHundredWordPhraseAreCompleteWhenFullTextIsOn() {
        assertEquals(words(12).uppercase(), full(words(12)))
        assertEquals(words(400).uppercase(), full(words(400)))
    }

    @Test
    fun fullTextKeepsSpacingAndLineBreaksAsTyped() {
        assertEquals("ONE  TWO\nTHREE", full("one  two\nthree"))
    }

    // --- the order of the rules ---

    @Test
    fun aVisualOverrideBeatsATargetNameWhichBeatsThePhrase() {
        assertEquals("OVERRIDE", resolveDisplayText("the phrase", "target", "override", fullText = false))
        assertEquals("OVERRIDE", resolveDisplayText("the phrase", "target", "override", fullText = true))
        assertEquals("TARGET", resolveDisplayText("the phrase", "target", null, fullText = false))
        assertEquals("TARGET", resolveDisplayText("the phrase", "target", null, fullText = true))
        assertEquals("THE PHRASE", resolveDisplayText("the phrase", null, null, fullText = true))
    }

    @Test
    fun aBlankOverrideOrTargetNameIsIgnored() {
        assertEquals("TARGET", resolveDisplayText("p", "target", "   ", fullText = false))
        assertEquals("P", resolveDisplayText("p", "  ", "", fullText = false))
        assertEquals("P", resolveDisplayText("p", "", null, fullText = false))
    }

    // --- counting words ---

    @Test
    fun repeatedSpacesLeadingSpacesAndLineBreaksCountWordsSensibly() {
        // Five words with odd spacing: still five, so shown as typed (uppercased, spacing kept).
        assertEquals("  ONE   TWO\nTHREE  FOUR FIVE ", legacy("  one   two\nthree  four five "))
        // Six words with odd spacing: cut to the first three, joined by single spaces.
        assertEquals("ALERT:\nONE TWO THREE...", legacy("  one   two\nthree  four five\n\nsix"))
        assertEquals("ALERT:\nONE TWO THREE...", legacy("one\ttwo\r\nthree four five six"))
    }

    @Test
    fun accentedWordsCountAsWords() {
        assertEquals("ALERT:\nÉCLAIR CAFÉ NAÏVE...", legacy("éclair café naïve señor über zoë"))
        assertEquals("ÉCLAIR CAFÉ NAÏVE SEÑOR ÜBER", legacy("éclair café naïve señor über"))
    }

    @Test
    fun anEmptyPhraseReturnsAnEmptyString() {
        assertEquals("", legacy(""))
        assertEquals("", full(""))
    }

    // --- today's behaviour is kept exactly: compare against a verbatim copy of the old code ---

    /** The body of VisualLogicEngine.resolveDisplayPrompt as it was before this was moved, with preset.bypassTruncation as a Boolean. */
    private fun oldResolveDisplayPrompt(rawPhrase: String, targetName: String?, matrixVisualOverride: String?, bypassTruncation: Boolean): String {
        if (!matrixVisualOverride.isNullOrBlank()) {
            return matrixVisualOverride.uppercase()
        }
        if (!targetName.isNullOrBlank()) {
            return targetName.uppercase()
        }
        if (bypassTruncation) {
            return rawPhrase.uppercase()
        }
        val words = rawPhrase.trim().split("\\s+".toRegex())
        return if (words.size <= 5) {
            rawPhrase.uppercase()
        } else {
            "ALERT:\n${words.take(3).joinToString(" ").uppercase()}..."
        }
    }

    @Test
    fun theMovedRulesGiveTheSameAnswerAsTheOldCodeOnSeededRandomInput() {
        val random = Random(20261003L)
        val pieces = listOf("a", "bb", "Hello", "water", "é", "ß", "über", "I", "NEED", "x1", "...", "&", "<", "😀", "日本", " ", "  ", "\n", "\t", "\r\n", " ")
        fun phrase(): String = buildString { repeat(random.nextInt(16)) { append(pieces[random.nextInt(pieces.size)]); if (random.nextBoolean()) append(' ') } }
        fun maybe(): String? = when (random.nextInt(4)) { 0 -> null; 1 -> ""; 2 -> "  "; else -> phrase() }

        repeat(5000) {
            val raw = phrase(); val target = maybe(); val override = maybe(); val bypass = random.nextBoolean()
            assertEquals(
                "raw=[$raw] target=[$target] override=[$override] bypass=$bypass",
                oldResolveDisplayPrompt(raw, target, override, bypass),
                resolveDisplayText(raw, target, override, fullText = bypass),
            )
        }
    }
}
