// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import com.example.besu.capture.Vectors.d
import com.example.besu.capture.Vectors.s
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CardSplitterTest {
    private fun summary(text: String, words: Int, est: Double, warnings: List<String>) = "[$words words, $est s, $warnings] $text"

    private fun expectedCards(arr: JsonArray) = arr.map { c ->
        val o = c.jsonObject
        summary(o.s("text"), o["words"]!!.jsonPrimitive.int, o.d("est_s"), o["warnings"]!!.jsonArray.map { it.jsonPrimitive.content })
    }

    private fun check(diffs: Differences, name: String, input: kotlinx.serialization.json.JsonObject, expected: JsonArray) {
        val got = CardSplitter.splitCards(input.s("text"), input.d("pace_wps"), input.s("lines"))
        diffs.expect(name, expectedCards(expected), got.map { summary(it.text, it.words, it.estS, it.warnings) })
    }

    @Test
    fun splitMatchesTheSharedCases() {
        val diffs = Differences()
        for (case in Vectors.load("cards.json").jsonObject["split"]!!.jsonArray) {
            val o = case.jsonObject
            check(diffs, o.s("name"), o["input"]!!.jsonObject, o["expected"]!!.jsonArray)
        }
        diffs.assertNone()
    }

    @Test
    fun describeMatchesTheSharedCases() {
        val diffs = Differences()
        for (case in Vectors.load("cards.json").jsonObject["describe"]!!.jsonArray) {
            val o = case.jsonObject
            val input = o["input"]!!.jsonObject
            val e = o["expected"]!!.jsonObject
            val got = CardSplitter.describeCard(input.s("text"), input.d("pace_wps"))
            diffs.expect(o.s("name"), summary("", e["words"]!!.jsonPrimitive.int, e.d("est_s"), e["warnings"]!!.jsonArray.map { it.jsonPrimitive.content }),
                summary("", got.words, got.estS, got.warnings))
        }
        diffs.assertNone()
    }

    @Test
    fun splitMatchesTheGeneratedCases() {
        // 70 generated texts with Unicode letters, non-breaking spaces, abbreviations, quotes, tabs, stray control characters.
        val diffs = Differences()
        val cases = Vectors.load("fuzz.json").jsonObject["cards"]!!.jsonArray
        assertTrue(cases.size >= 50)
        cases.forEachIndexed { i, case ->
            check(diffs, "generated card case $i", case.jsonObject["input"]!!.jsonObject, case.jsonObject["expected"]!!.jsonArray)
        }
        diffs.assertNone()
    }

    @Test
    fun noCardIsEverLongerThanTheReaderCanSayInOneBreath() {
        val cases = Vectors.load("fuzz.json").jsonObject["cards"]!!.jsonArray
        for (case in cases) {
            val input = case.jsonObject["input"]!!.jsonObject
            val cards = CardSplitter.splitCards(input.s("text"), input.d("pace_wps"), input.s("lines"))
            for (c in cards) {
                assertTrue("card over the character limit: ${c.text.length}", c.text.length <= CaptureConstants.MAX_CARD_CHARS)
                assertTrue("empty card", c.text.isNotBlank())
                assertTrue("line break inside a card", c.text.none { it == '\n' || it == '\r' })
            }
        }
    }

    @Test
    fun nothingTheReaderShouldSayIsLost() {
        val text = "First paragraph here, with a few words to read aloud.\n\nSecond paragraph, which is a little different. It has two sentences."
        val joined = CardSplitter.splitCards(text).joinToString(" ") { it.text }
        assertEquals(text.split(Regex("\\s+")).filter { it.isNotEmpty() }, joined.split(" ").filter { it.isNotEmpty() })
    }

    @Test
    fun aSlowerReaderGetsSmallerCards() {
        val text = (1..60).joinToString(" ") { "word$it" } + "."
        val fast = CardSplitter.splitCards(text, 4.0)
        val slow = CardSplitter.splitCards(text, 1.5)
        assertTrue(slow.size > fast.size)
        for (c in slow) assertTrue(c.estS <= CaptureConstants.MAX_EST_S + 1.0)
    }

    @Test
    fun anOutOfRangePaceIsKeptWithinTheAllowedRange() {
        assertEquals(CardSplitter.describeCard("one two three four five six", 1.5), CardSplitter.describeCard("one two three four five six", 0.1))
        assertEquals(CardSplitter.describeCard("one two three four five six", 4.0), CardSplitter.describeCard("one two three four five six", 99.0))
    }

    @Test
    fun paceIsMeasuredFromKeptClipsAndKeptWithinRange() {
        val clips = (1..5).map { "one two three four five six seven eight nine ten" to SpeechSpan(0.5, 4.5) }     // 10 words in 4 s = 2.5/s
        assertEquals(2.5, CardSplitter.measurePace(clips)!!, 1e-9)
        assertNull("four clips are too few to judge", CardSplitter.measurePace(clips.take(4)))
        val noSpeech = clips.take(4) + ("one two three" to null)
        assertNull("a clip with no speech does not count", CardSplitter.measurePace(noSpeech))
        val fast = (1..5).map { "a b c d e f g h i j k l" to SpeechSpan(0.0, 1.0) }                                   // 12/s
        assertEquals(CaptureConstants.PACE_MAX_WPS, CardSplitter.measurePace(fast)!!, 0.0)
        val slow = (1..5).map { "a b" to SpeechSpan(0.0, 10.0) }                                                       // 0.2/s
        assertEquals(CaptureConstants.PACE_MIN_WPS, CardSplitter.measurePace(slow)!!, 0.0)
        assertNotNull(CardSplitter.measurePace(clips))
    }

    @Test
    fun wordsAreLettersAndNumbersOfAnyScriptNotSymbols() {
        assertEquals(4, CardSplitter.describeCard("日本語 Привет café 42 — & ...", 2.6).words)
    }
}
