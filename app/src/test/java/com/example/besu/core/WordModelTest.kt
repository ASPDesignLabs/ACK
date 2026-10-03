// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Random

/**
 * The on-device word model behind word suggestions: how often each word was used and how often one word followed another, learned only
 * from text the person committed, capped so it stays small. Nothing here touches a file; the repository saves and loads it.
 */
class WordModelTest {

    private fun model(maxWords: Int = WordModel.MAX_WORDS, maxPairs: Int = WordModel.MAX_PAIRS) = WordModel(maxWords, maxPairs)

    private fun WordModel.words(prefix: String = "") = completions(prefix).map { it.form }

    // ---- learning ------------------------------------------------------------------------------------------------------------

    @Test
    fun everyOccurrenceCounts() {
        val m = model()
        m.learn("the cat the dog", 1)
        assertEquals(2, m.countOf("the"))
        assertEquals(1, m.countOf("cat"))
        assertEquals(1, m.countOf("dog"))
        assertEquals(3, m.wordCount)
    }

    @Test
    fun aTagIsNeverLearned_nor_whatIsInsideIt() {
        val m = model()
        m.learn("Call [COMPUTER:HOME] and {VAR:A} now", 1)
        assertEquals(setOf("call", "and", "now"), m.listWords().map { it.key }.toSet())
        for (leaked in listOf("computer", "home", "var", "a")) assertFalse(leaked, m.contains(leaked))
    }

    @Test
    fun numbersAndCodesAreNeverLearned() {
        val m = model()
        m.learn("ring 07700 900123 about abc123", 1)
        assertEquals(setOf("ring", "about"), m.listWords().map { it.key }.toSet())
    }

    @Test
    fun nothingIsLearnedFromBlankText() {
        val m = model()
        m.learn("", 1)
        m.learn("   \n", 1)
        m.learn("[COMPUTER:A] {VAR}", 1)
        assertEquals(0, m.wordCount)
        assertEquals(0, m.pairCount)
    }

    // ---- the form a word is shown in --------------------------------------------------------------------------------------------

    @Test
    fun aNameTypedMidSentenceKeepsItsCapital() {
        val m = model()
        m.learn("I see Sarah", 1)
        assertEquals("Sarah", m.formOf("sarah"))
        assertEquals("I", m.formOf("i"))
    }

    @Test
    fun aWordOnlyCapitalisedBecauseItStartedASentence_isKeptLowerCase() {
        val m = model()
        m.learn("Hello there", 1)
        assertEquals("hello", m.formOf("Hello"))
        assertEquals("there", m.formOf("there"))
    }

    @Test
    fun theMostRecentMidSentenceFormWins() {
        val m = model()
        m.learn("see Sarah", 1)
        m.learn("see sarah", 2)
        assertEquals("sarah", m.formOf("sarah"))
        m.learn("see SARAH", 3)
        assertEquals("SARAH", m.formOf("sarah"))
    }

    @Test
    fun aSentenceInitialCapitalNeverOverridesAnEarlierForm() {
        val m = model()
        m.learn("I like Sarah.", 1)
        m.learn("Sarah is here.", 2)
        assertEquals("Sarah", m.formOf("sarah"))
    }

    @Test
    fun anAcronymAtTheStartOfASentence_keepsItsCapitals() {
        val m = model()
        m.learn("OK then", 1)
        assertEquals("OK", m.formOf("ok"))
    }

    // ---- which word follows which ---------------------------------------------------------------------------------------------------

    @Test
    fun wordsAreLinkedWithTheOneThatFollowedThem() {
        val m = model()
        m.learn("I like tea", 1)
        assertEquals(listOf("like"), m.nextWords("I", 5).map { it.form })
        assertEquals(listOf("tea"), m.nextWords("like", 5).map { it.form })
        assertTrue(m.nextWords("tea", 5).isEmpty())
    }

    @Test
    fun wordsAreNeverLinkedAcrossASentenceOrATag() {
        val m = model()
        m.learn("Hi. There", 1)
        m.learn("Call [COMPUTER:HOME] now", 2)
        m.learn("one\ntwo", 3)
        assertTrue(m.nextWords("hi", 5).isEmpty())
        assertTrue(m.nextWords("call", 5).isEmpty())
        assertTrue(m.nextWords("one", 5).isEmpty())
    }

    @Test
    fun theMostCommonFollowerComesFirst() {
        val m = model()
        m.learn("like tea. like coffee. like tea.", 1)
        assertEquals(listOf("tea", "coffee"), m.nextWords("like", 5).map { it.form })
    }

    @Test
    fun theFollowersAreLimited() {
        val m = model()
        m.learn("go a. go b. go c. go d.", 1)
        assertEquals(2, m.nextWords("go", 2).size)
    }

    // ---- prefixes --------------------------------------------------------------------------------------------------------------

    @Test
    fun completionsAreRankedByUseThenRecencyThenAlphabet() {
        val m = model()
        m.learn("the the the", 1)
        m.learn("that", 5)
        m.learn("then", 9)
        m.learn("thin thin", 3)
        // the:3, thin:2, then:1 (newer), that:1 (older)
        assertEquals(listOf("the", "thin", "then", "that"), m.words("th"))
        assertEquals(listOf("the", "thin", "then"), m.completions("th", 3).map { it.form })
    }

    @Test
    fun aPrefixIsMatchedIgnoringCase_andComposedOrDecomposedAccents() {
        val m = model()
        m.learn("see café", 1)
        assertEquals(listOf("café"), m.words("CAF"))
        assertEquals(listOf("café"), m.words("café"))
        assertTrue(m.words("cafe").isEmpty())
    }

    @Test
    fun anEmptyPrefixListsEverythingRankedTheSameWay() {
        val m = model()
        m.learn("b a b", 1)
        assertEquals(listOf("b", "a"), m.words(""))
    }

    // ---- caps ------------------------------------------------------------------------------------------------------------------

    @Test
    fun theLeastUsedWordIsEvictedFirst_thenTheOldest_thenTheAlphabeticallyFirst() {
        val m = model(maxWords = 3)
        m.learn("alpha alpha alpha beta beta gamma delta", 1)
        // alpha 3, beta 2, gamma 1, delta 1 -> over by one: gamma and delta tie on count and time, "delta" goes
        assertEquals(3, m.wordCount)
        assertEquals(setOf("alpha", "beta", "gamma"), m.listWords().map { it.key }.toSet())
    }

    @Test
    fun anOlderWordGoesBeforeANewerOneAtTheSameUse() {
        val m = model(maxWords = 1)
        m.learn("old", 1)
        m.learn("new", 2)
        assertEquals(listOf("new"), m.listWords().map { it.key })
    }

    @Test
    fun exactlyAtTheCap_nothingIsEvicted_oneOverEvictsExactlyOne() {
        val m = model(maxWords = 3)
        m.learn("a1 b1 c1".replace("1", "x"), 1)
        assertEquals(3, m.wordCount)
        m.learn("dd", 2)
        assertEquals(3, m.wordCount)
    }

    @Test
    fun aWordThatIsEvicted_takesItsPairsWithIt() {
        val m = model(maxWords = 2)
        m.learn("keep keep keep also also gone", 1)
        assertFalse(m.contains("gone"))
        assertTrue(m.nextWords("also", 9).none { it.key == "gone" })
        assertTrue(m.nextWords("keep", 9).all { m.contains(it.key) })
    }

    @Test
    fun theLeastUsedPairIsEvictedWhenThereAreTooMany() {
        val m = model(maxWords = 100, maxPairs = 2)
        m.learn("a b c d", 1)
        assertEquals(2, m.pairCount)
    }

    @Test
    fun theCapsHoldAndEveryPairKeepsItsWords_overRandomLearning() {
        val random = Random(2024)
        repeat(30) {
            val m = model(maxWords = 12, maxPairs = 20)
            repeat(40) { step ->
                val text = (0 until 1 + random.nextInt(8)).joinToString(" ") { "w${random.nextInt(30)}x".replace(Regex("\\d"), { d -> ('a' + d.value.toInt()).toString() }) } +
                    (if (random.nextBoolean()) "." else "")
                m.learn(text, step.toLong())
                assertTrue(m.wordCount <= 12)
                assertTrue(m.pairCount <= 20)
                for (w in m.listWords()) for (n in m.nextWords(w.key, 99)) assertTrue("pair to a missing word", m.contains(n.key))
            }
        }
    }

    // ---- saving and loading ---------------------------------------------------------------------------------------------------

    private fun roundTrip(m: WordModel): WordModel {
        val json = Json.encodeToString(m.toData())
        return WordModel.fromData(Json.decodeFromString<WordModelData>(json))
    }

    @Test
    fun aModelSurvivesBeingSavedAndLoaded() {
        val m = model()
        m.learn("I like tea. I like Sarah. like tea", 5)
        val loaded = roundTrip(m)
        assertEquals(m.listWords(), loaded.listWords())
        assertEquals(m.nextWords("like", 9), loaded.nextWords("like", 9))
        assertEquals(m.wordCount, loaded.wordCount)
        assertEquals(m.pairCount, loaded.pairCount)
        assertEquals("Sarah", loaded.formOf("sarah"))
    }

    @Test
    fun anEmptyModelIsEmpty_andSurvivesBeingSavedAndLoaded() {
        val m = model()
        assertEquals(WordModelData(), m.toData())
        val loaded = roundTrip(m)
        assertEquals(0, loaded.wordCount)
        assertTrue(loaded.words().isEmpty())
        assertTrue(loaded.nextWords("x", 3).isEmpty())
    }

    @Test
    fun loadingDropsWhatIsBroken_insteadOfFailing() {
        val data = WordModelData(
            words = listOf(
                StoredWord("good", "good", 3, 1),
                StoredWord("", "blank", 1, 1),
                StoredWord("neg", "neg", -4, 1),
                StoredWord("zero", "zero", 0, 1),
                StoredWord("x".repeat(WordTokens.MAX_WORD_LENGTH + 1), "long", 1, 1),
            ),
            pairs = listOf(StoredPair("good", "good", 2), StoredPair("good", "ghost", 5), StoredPair("ghost", "good", 5), StoredPair("good", "good", -1)),
        )
        val m = WordModel.fromData(data)
        assertEquals(listOf("good"), m.listWords().map { it.key })
        assertEquals(1, m.pairCount)
    }

    @Test
    fun loadingTooMuch_keepsTheMostUsedWithinTheCaps() {
        val data = WordModelData(words = (1..10).map { StoredWord("w$it".replace(Regex("\\d"), { d -> ('a' + d.value.toInt()).toString() }), "w", it, it.toLong()) })
        val m = WordModel.fromData(data, maxWords = 4, maxPairs = 4)
        assertEquals(4, m.wordCount)
        assertEquals(listOf(10, 9, 8, 7), m.listWords().map { it.count })
    }

    // ---- forgetting ------------------------------------------------------------------------------------------------------------

    @Test
    fun forgettingAWord_removesItAndItsPairs_whateverTheCase() {
        val m = model()
        m.learn("I see Sarah today. I see Oliver", 1)
        assertTrue(m.forget("SARAH"))
        assertFalse(m.contains("sarah"))
        assertTrue(m.nextWords("see", 9).none { it.key == "sarah" })
        assertTrue(m.nextWords("sarah", 9).isEmpty())
        assertTrue(m.contains("oliver"))
    }

    @Test
    fun forgettingAnUnknownWord_changesNothing() {
        val m = model()
        m.learn("hello", 1)
        assertFalse(m.forget("nobody"))
        assertEquals(1, m.wordCount)
    }

    @Test
    fun forgettingEverything_leavesAnEmptyModel() {
        val m = model()
        m.learn("one two three", 1)
        m.forgetAll()
        assertEquals(0, m.wordCount)
        assertEquals(0, m.pairCount)
        assertEquals(WordModelData(), m.toData())
    }

    // ---- merging a restored backup ---------------------------------------------------------------------------------------------

    @Test
    fun aRestoreNeverLowersACount_orRemovesAWordTheFileDoesNotMention() {
        val m = model()
        m.learn("the the the the the keep", 10)
        val file = WordModelData(
            words = listOf(StoredWord("the", "the", 3, 99), StoredWord("cat", "cat", 2, 5)),
            pairs = listOf(StoredPair("the", "cat", 2)),
        )
        m.merge(file)
        assertEquals(5, m.countOf("the"))
        assertEquals(2, m.countOf("cat"))
        assertTrue(m.contains("keep"))
        assertTrue("cat" in m.nextWords("the", 5).map { it.form })
    }

    @Test
    fun aRestoreTakesTheMoreRecentForm() {
        val m = model()
        m.learn("see Sarah", 5)
        m.merge(WordModelData(words = listOf(StoredWord("sarah", "sarah", 1, 9))))
        assertEquals("sarah", m.formOf("sarah"))
        val n = model()
        n.learn("see Sarah", 9)
        n.merge(WordModelData(words = listOf(StoredWord("sarah", "sarah", 1, 5))))
        assertEquals("Sarah", n.formOf("sarah"))
    }

    @Test
    fun aRestoreStillRespectsTheCaps() {
        val m = model(maxWords = 3)
        m.learn("aa aa bb", 1)
        m.merge(WordModelData(words = (1..6).map { StoredWord("w$it".replace(Regex("\\d"), { d -> ('a' + d.value.toInt()).toString() }), "w", 10, 5) }))
        assertEquals(3, m.wordCount)
    }

    @Test
    fun aRestoreDropsWhatIsBroken_likeLoadingDoes() {
        val m = model()
        m.merge(WordModelData(words = listOf(StoredWord("ok", "ok", 1, 1), StoredWord("", "x", 1, 1), StoredWord("bad", "bad", -2, 1))))
        assertEquals(listOf("ok"), m.listWords().map { it.key })
    }

    // ---- checking a backup before it is applied --------------------------------------------------------------------------------------

    @Test
    fun aSoundFileIsAccepted() {
        val data = WordModelData(words = listOf(StoredWord("a", "a", 1, 0), StoredWord("b", "b", 2, 5)), pairs = listOf(StoredPair("a", "b", 1)))
        assertNull(data.validate())
        assertNull(WordModelData().validate())
    }

    @Test
    fun aFileThatIsTooBigIsRefused_withTheNumbersInTheMessage() {
        val tooManyWords = WordModelData(words = (0..5).map { StoredWord("w${'a' + it}", "w", 1, 0) })
        val reason = tooManyWords.validate(maxWords = 5, maxPairs = 5)
        assertNotNull(reason)
        assertTrue(reason!!.contains("6") && reason.contains("5"))
        val keys = listOf("a", "b")
        val tooManyPairs = WordModelData(words = keys.map { StoredWord(it, it, 1, 0) }, pairs = List(4) { StoredPair("a", "b", 1) })
        assertNotNull(tooManyPairs.validate(maxWords = 5, maxPairs = 3))
    }

    @Test
    fun eachKindOfBadEntry_isRefusedWithItsOwnReason() {
        val reasons = listOf(
            WordModelData(words = listOf(StoredWord("", "x", 1, 0))),
            WordModelData(words = listOf(StoredWord("a", "a", 0, 0))),
            WordModelData(words = listOf(StoredWord("a", "a", -1, 0))),
            WordModelData(words = listOf(StoredWord("a", "a", WordModel.MAX_COUNT + 1, 0))),
            WordModelData(words = listOf(StoredWord("a", "a", 1, -1))),
            WordModelData(words = listOf(StoredWord("x".repeat(WordTokens.MAX_WORD_LENGTH + 1), "x", 1, 0))),
            WordModelData(words = listOf(StoredWord("a", "x".repeat(WordTokens.MAX_WORD_LENGTH + 1), 1, 0))),
            WordModelData(words = listOf(StoredWord("a", "a", 1, 0), StoredWord("a", "a", 1, 0))),
            WordModelData(words = listOf(StoredWord("a", "a", 1, 0)), pairs = listOf(StoredPair("a", "ghost", 1))),
            WordModelData(words = listOf(StoredWord("a", "a", 1, 0)), pairs = listOf(StoredPair("a", "a", 0))),
        ).map { it.validate() }
        for (r in reasons) assertNotNull("a bad entry was accepted", r)
        assertEquals("every refusal says something different", reasons.size, reasons.toSet().size)
    }
}
