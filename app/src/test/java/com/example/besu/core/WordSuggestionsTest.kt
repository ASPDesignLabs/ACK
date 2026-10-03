// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Locale
import java.util.Random

/**
 * The suggestion rules for the history chips (B3): with nothing typed, today's behaviour; with text typed, only values that start
 * with it; case variants are one word; nothing is suggested that is already typed; the order never depends on how the input was
 * ordered. Nothing here changes a stored value except through [WordSuggestions.recordUsage], which only ever touches one entry.
 */
class WordSuggestionsTest {

    private fun c(value: String, count: Int = 1, at: Long = 0L) = SuggestionCandidate(value, count, at)

    private fun suggest(candidates: List<SuggestionCandidate>, typed: String = "") = WordSuggestions.suggest(candidates, typed)

    // ---- nothing typed: today's behaviour ---------------------------------------------------------------------------------

    @Test
    fun withNothingTyped_itIsTheTopFiveByCountThenMostRecent() {
        val list = listOf(
            c("a", 1, 10), c("b", 5, 1), c("c", 5, 2), c("d", 3, 3), c("e", 2, 4), c("f", 2, 9), c("g", 1, 99),
        )
        // counts: b5 c5 d3 e2 f2 g1 a1 ; ties by recency: c before b, f before e, g before a
        assertEquals(listOf("c", "b", "d", "f", "e"), suggest(list))
    }

    @Test
    fun withNothingTyped_itMatchesTheOldRuleOverRandomHistories() {
        // The old rule: sort by count descending, then lastUsedAt descending, take five. Times are distinct here, so no tie is left
        // to stored order (which the new rule resolves by value instead).
        val random = Random(12345)
        repeat(200) {
            val n = random.nextInt(30)
            val list = (0 until n).map { i -> c("value$i", 1 + random.nextInt(6), i * 1000L + random.nextInt(900)) }
            val old = list.sortedWith(compareByDescending<SuggestionCandidate> { it.count }.thenByDescending { it.lastUsedAt })
                .take(5).map { it.value }
            assertEquals(old, suggest(list))
        }
    }

    @Test
    fun whitespaceOnlyTypedText_countsAsNothingTyped() {
        val list = listOf(c("Mum", 3), c("Dad", 2))
        assertEquals(listOf("Mum", "Dad"), suggest(list, "   "))
        assertEquals(listOf("Mum", "Dad"), suggest(list, "\t\n"))
    }

    @Test
    fun anEmptyHistory_suggestsNothing() {
        assertTrue(suggest(emptyList(), "").isEmpty())
        assertTrue(suggest(emptyList(), "x").isEmpty())
    }

    // ---- text typed: only what starts with it -----------------------------------------------------------------------------

    @Test
    fun onlyValuesThatStartWithWhatWasTypedAreKept() {
        val list = listOf(c("Mum", 3), c("Mum and Dad", 2), c("Dad", 5), c("Grandmum", 9))
        assertEquals(listOf("Mum", "Mum and Dad"), suggest(list, "mu"))
    }

    @Test
    fun exactlyOneMatch() {
        assertEquals(listOf("Dad"), suggest(listOf(c("Mum"), c("Dad")), "d"))
    }

    @Test
    fun noMatchGivesNothing() {
        assertTrue(suggest(listOf(c("Mum"), c("Dad")), "z").isEmpty())
    }

    @Test
    fun spacesAtTheEndsOfWhatWasTypedAreIgnored() {
        assertEquals(listOf("Mum"), suggest(listOf(c("Mum")), "  mu  "))
    }

    @Test
    fun aSpaceInTheMiddleOfWhatWasTypedIsPartOfTheMatch() {
        val list = listOf(c("New York"), c("Newark"))
        assertEquals(listOf("New York"), suggest(list, "new y"))
    }

    @Test
    fun matchingIgnoresCase() {
        assertEquals(listOf("mum"), suggest(listOf(c("mum")), "MU"))
        assertEquals(listOf("Mum"), suggest(listOf(c("Mum")), "mU"))
    }

    @Test
    fun moreThanFiveMatches_showsOnlyFive() {
        val list = (1..9).map { c("name$it", count = it) }
        assertEquals(5, suggest(list, "name").size)
        assertEquals(listOf("name9", "name8", "name7", "name6", "name5"), suggest(list, "name"))
    }

    // ---- not what is already typed -------------------------------------------------------------------------------------------

    @Test
    fun aPrefixThatEqualsAValue_isNotSuggestedBack_butLongerValuesAre() {
        val list = listOf(c("Mum", 5), c("Mum and Dad", 1))
        assertEquals(listOf("Mum and Dad"), suggest(list, "Mum"))
    }

    @Test
    fun typedTextThatDiffersOnlyByCase_isStillOfferedInItsSavedForm() {
        // "mum" typed, "Mum" saved: tapping the chip is a correction, so it is offered
        assertEquals(listOf("Mum"), suggest(listOf(c("Mum")), "mum"))
    }

    @Test
    fun ifAnyCaseFormIsExactlyWhatWasTyped_itIsNotOfferedAgain() {
        val list = listOf(c("Mum", 2, 1), c("mum", 1, 5))
        assertTrue(suggest(list, "Mum").isEmpty())
        assertTrue(suggest(list, "mum").isEmpty())
    }

    // ---- case variants are one word ------------------------------------------------------------------------------------------

    @Test
    fun caseVariantsCountTogether() {
        val list = listOf(c("Mum", 2, 1), c("mum", 1, 2), c("Dad", 2, 3))
        // Mum + mum = 3 beats Dad = 2
        assertEquals(listOf("mum", "Dad"), suggest(list))
    }

    @Test
    fun theMostRecentlyTypedFormIsTheOneShown() {
        assertEquals(listOf("mum"), suggest(listOf(c("Mum", 1, 5), c("mum", 1, 9))))
        assertEquals(listOf("Mum"), suggest(listOf(c("mum", 1, 5), c("Mum", 1, 9))))
    }

    @Test
    fun equallyRecentCaseVariants_showTheMoreUsedForm_thenTheValue() {
        assertEquals(listOf("Mum"), suggest(listOf(c("Mum", 3, 5), c("mum", 1, 5))))
        assertEquals(listOf("MUM"), suggest(listOf(c("mum", 1, 5), c("MUM", 1, 5))))
    }

    // ---- accents and other scripts ------------------------------------------------------------------------------------------

    @Test
    fun composedAndDecomposedAccentsAreTheSameWord() {
        val composed = "café"
        val decomposed = "café"
        assertEquals(1, suggest(listOf(c(composed, 1, 1), c(decomposed, 1, 2))).size)
        assertEquals(listOf(decomposed), suggest(listOf(c(decomposed)), "caf"))
        assertEquals(listOf(decomposed), suggest(listOf(c(decomposed)), composed.dropLast(1)))
        assertEquals(listOf(composed), suggest(listOf(c(composed)), decomposed.substring(0, 3)))
    }

    @Test
    fun anAccentedLetterIsNotTheSameAsThePlainLetter() {
        // Only composed and decomposed forms are treated as equal; "cafe" does not match "café".
        assertTrue(suggest(listOf(c("café")), "cafe").isEmpty())
        assertEquals(listOf("café"), suggest(listOf(c("café")), "caf"))
    }

    @Test
    fun nonLatinScriptsMatchAndCaseFold() {
        assertEquals(listOf("Μαμά"), suggest(listOf(c("Μαμά")), "μα")) // Greek Μαμά / μα
        assertEquals(listOf("Мама"), suggest(listOf(c("Мама")), "ма")) // Cyrillic Мама / ма
        assertEquals(listOf("你好吗"), suggest(listOf(c("你好吗")), "你")) // Chinese, no case
        assertEquals(listOf("ماما"), suggest(listOf(c("ماما")), "م")) // Arabic
    }

    @Test
    fun anEmojiValueMatchesItsOwnPrefix() {
        assertEquals(listOf("😀 smile"), suggest(listOf(c("😀 smile")), "😀"))
    }

    @Test
    fun aTurkishPhone_doesNotChangeTheResult() {
        val saved = Locale.getDefault()
        try {
            Locale.setDefault(Locale("tr", "TR"))
            // With a Turkish default locale, "I".lowercase() would be a dotless i. The match must not depend on it.
            assertEquals(listOf("ilk"), suggest(listOf(c("ilk")), "I"))
            assertEquals(listOf("Ilk"), suggest(listOf(c("Ilk")), "i"))
        } finally {
            Locale.setDefault(saved)
        }
    }

    // ---- the order is deterministic -------------------------------------------------------------------------------------------

    @Test
    fun equalCountsAndTimes_areOrderedByValue_whateverOrderTheyWereStoredIn() {
        val values = listOf("pear", "apple", "mango", "cherry")
        val forward = suggest(values.map { c(it, 2, 7) })
        val backward = suggest(values.reversed().map { c(it, 2, 7) })
        assertEquals(listOf("apple", "cherry", "mango", "pear"), forward)
        assertEquals(forward, backward)
    }

    @Test
    fun theSameHistoryInAnyOrder_givesTheSameSuggestions() {
        val random = Random(777)
        repeat(100) {
            val list = (0 until 12).map { i -> c("w${random.nextInt(8)}x$i", 1 + random.nextInt(3), random.nextInt(4).toLong()) }
            val shuffled = list.shuffled(random)
            for (typed in listOf("", "w", "w1", "w7x")) {
                assertEquals("typed='$typed'", suggest(list, typed), suggest(shuffled, typed))
            }
        }
    }

    // ---- recording a value ------------------------------------------------------------------------------------------------------

    private fun record(list: List<SuggestionCandidate>, value: String, now: Long = 100L) =
        WordSuggestions.recordUsage(list, value, now)

    @Test
    fun aBlankValueIsNeverRecorded() {
        val list = listOf(c("Mum"))
        assertEquals(list, record(list, ""))
        assertEquals(list, record(list, "   "))
    }

    @Test
    fun aNewValueIsAddedWithCountOne() {
        assertEquals(listOf(c("Mum"), c("Dad", 1, 100)), record(listOf(c("Mum")), "  Dad  "))
    }

    @Test
    fun anExistingValueCountsUp_andIsNowTheMostRecent() {
        assertEquals(listOf(c("Mum", 3, 100)), record(listOf(c("Mum", 2, 5)), "Mum"))
    }

    @Test
    fun aCaseVariantCountsUpTheMatchingEntry_andTakesTheNewForm() {
        assertEquals(listOf(c("mum", 3, 100)), record(listOf(c("Mum", 2, 5)), "mum"))
    }

    @Test
    fun composedAndDecomposedAccentsAreTheSameEntryWhenRecording() {
        val out = record(listOf(c("café", 2, 5)), "café")
        assertEquals(1, out.size)
        assertEquals(3, out.single().count)
    }

    @Test
    fun oldDuplicateVariantsAreNeverRewritten_onlyTheMostRecentOneIsTouched() {
        val old = listOf(c("Mum", 5, 1), c("mum", 1, 2))
        val out = record(old, "MUM")
        assertEquals(listOf(c("Mum", 5, 1), c("MUM", 2, 100)), out)
    }

    @Test
    fun theTwentyFirstValue_pushesOutTheOldestOfTheEquallyUsedOnes() {
        val twenty = (1..20).map { c("v$it", count = 1, at = it.toLong()) }
        val out = record(twenty, "brand new")
        assertEquals(20, out.size)
        assertTrue("the oldest of the equally used values goes", out.none { it.value == "v1" })
        assertTrue("the new value is kept", out.any { it.value == "brand new" })
    }

    @Test
    fun aMuchUsedValueSurvivesTheCap() {
        val twenty = (1..20).map { c("v$it", count = if (it == 1) 50 else 1, at = it.toLong()) }
        val out = record(twenty, "brand new")
        assertTrue("the much-used oldest value stays", out.any { it.value == "v1" })
        assertEquals(20, out.size)
        assertTrue("v2, used once and oldest of those, goes", out.none { it.value == "v2" })
    }

    @Test
    fun aNewValueCannotDisplaceTwentyThatAreUsedMoreThanOnce_theExistingRule() {
        // Pinned, not endorsed: the cap has always ranked by count first, so once a field holds twenty values each used twice or more,
        // a value typed for the first time is dropped as soon as it is recorded. It is in the report as something to decide.
        val twenty = (1..20).map { c("v$it", count = 5, at = it.toLong()) }
        val out = record(twenty, "brand new")
        assertEquals(twenty.toSet(), out.toSet())
    }

    @Test
    fun theLimitsAreTheRepositorysOwn() {
        val repo = RepoFiles.read("app/src/main/java/com/example/besu/data/AutocompleteHistoryRepository.kt")
        assertEquals(WordSuggestions.MAX_SHOWN, Regex("""const val MAX_SUGGESTIONS = (\d+)""").find(repo)!!.groupValues[1].toInt())
        assertEquals(WordSuggestions.MAX_STORED_PER_SCOPE, Regex("""const val MAX_ENTRIES_PER_SCOPE = (\d+)""").find(repo)!!.groupValues[1].toInt())
    }
}
