// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The WORD SUGGESTIONS screens (SETTINGS, FORGET WORDS and the composer's one-time offer) read their words from string resources, in the chosen language. They
 * cannot be compiled here, so this reads them: the old English literals and the old constants are gone, every string they name exists and none is unused, each word
 * sits on the control that does what it says, a word is only forgotten after the question, and the counts are filled in by the strings (the plural forms are
 * TranslationsTest's). WordSuggestionTextTest holds the sentences; WordSuggestionsUiWiringTest holds the promises (what is learned, where, and when).
 */
class WordSuggestionsWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val section get() = file("settings/WordSuggestionsSection.kt")
    private val composer get() = file("composer/StatementComposerView.kt")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val wordsNames get() = english.keys.filter { it.startsWith("words_") } + StringsXml.plurals(StringsXml.default).keys.filter { it.startsWith("words_") }

    @Test
    fun everyStringTheScreensNameExists_andNoneIsLeftUnused() {
        val sources = section + "\n" + composer + "\n" + file("core/WordSuggestionText.kt")
        val referenced = Regex("""R\.string\.(words_[a-z_]+)""").findAll(section + "\n" + composer).map { it.groupValues[1] }.toSet()
        val missing = referenced.filter { it !in wordsNames }
        assertEquals("named but not defined: $missing", emptyList<String>(), missing)
        val named = Regex(""""(words_[a-z_]+)"""").findAll(sources).map { it.groupValues[1] }.toSet()
        val unused = wordsNames.toSet() - referenced - named
        assertTrue("defined but never used: $unused", unused.isEmpty())
        for (name in listOf("common_close", "common_cancel", "common_continue", "delete_data_back_up_first")) {
            assertTrue("$name is not used by the section", Regex("""R\.string\.$name\b""").containsMatchIn(section))
        }
    }

    @Test
    fun theOldEnglishLiteralsAndConstantsAreGone() {
        val goneFromSection = listOf(
            "\"WORD SUGGESTIONS\"", "\"CLOSE\"", "WordSuggestionText.SWITCH_EXPLANATION", "WordSuggestionText.FORGET_BUTTON", "WordSuggestionText.FORGET_TITLE", "WordSuggestionText.FORGET_EMPTY",
            "WordSuggestionText.REMOVE", "WordSuggestionText.REMOVE_QUESTION", "WordSuggestionText.REMOVE_CANCEL", "WordSuggestionText.FORGET_ALL", "WordSuggestionText.BACK_UP_FIRST",
            "WordSuggestionText.CONTINUE", "WordSuggestionText.CANCEL", "WordSuggestionText.FORGET_ALL_SECOND", "WordSuggestionText.countLine(count)", "WordSuggestionText.switchLabel(on)",
        )
        for (literal in goneFromSection) assertFalse("WordSuggestionsSection.kt still holds $literal", section.contains(literal))
        for (literal in listOf("WordSuggestionText.OFFER_TEXT", "WordSuggestionText.OFFER_TURN_ON", "WordSuggestionText.OFFER_NOT_NOW", "import com.example.besu.core.WordSuggestionText")) {
            assertFalse("StatementComposerView.kt still holds $literal", composer.contains(literal))
        }
        assertTrue(section.contains("import com.example.besu.R"))
        assertTrue(section.contains("import androidx.compose.ui.res.stringResource"))
        // The words of the core decisions are read through the screen's text source, and a lambda's own name does not hide it.
        assertEquals("the text source is made once in each composable that needs it", 2, Regex("""val text = rememberText\(\)""").findAll(section).count())
        assertFalse("a lambda parameter named text would hide the text source", Regex("""\{ index, text ->""").containsMatchIn(section))
    }

    @Test
    fun eachWordSitsOnTheControlThatDoesWhatItSays() {
        fun wordThenAction(word: String, action: String, within: Int = 350) =
            Regex("""R\.string\.${Regex.escape(word)}[\s\S]{0,$within}?${Regex.escape(action)}""").containsMatchIn(section)
        assertTrue("REMOVE on a row only opens the question", wordThenAction("words_remove", "confirmingKey = word.key", 200))
        assertTrue("the question's REMOVE forgets the word", wordThenAction("words_remove", "LearnedWordsRepository.forget(context, word.key)", 250))
        assertTrue("KEEP closes the question", wordThenAction("words_keep", "confirmingKey = null", 200))
        assertTrue("FORGET ALL WORDS opens the first confirmation", wordThenAction("words_forget_all", "firstForAll = true", 200))
        assertTrue("the second FORGET ALL WORDS forgets", wordThenAction("words_forget_all", "LearnedWordsRepository.forgetAll(context)", 200))
        assertTrue("BACK UP FIRST starts the save", wordThenAction("delete_data_back_up_first", "onBackUpFirst()", 200))
        assertTrue("CONTINUE opens the second confirmation", wordThenAction("common_continue", "secondForAll = true", 200))
        val offer = composer.substring(composer.indexOf("private fun WordSuggestionsOffer("))
        assertTrue("TURN ON asks to turn it on", Regex("""R\.string\.words_offer_turn_on[\s\S]{0,200}?onTurnOn\(\)""").containsMatchIn(offer))
        assertTrue("NOT NOW only says not now", Regex("""R\.string\.words_offer_not_now[\s\S]{0,200}?onNotNow\(\)""").containsMatchIn(offer))
        // The switch says ON or OFF in words, and the count comes from the strings, not from joining text on.
        assertTrue(section.contains("WordSuggestionText.switchLabel(text, on),"))
        assertTrue(section.contains("WordSuggestionText.countLine(text, count),"))
        assertTrue(section.contains("WordSuggestionText.usedLine(text, word.count)"))
        // The list dialog counts what it lists, and the first confirmation puts the backup sentence in bold (the second of five), as it always did.
        assertTrue(section.contains("subtitle = WordSuggestionText.countLine(text, words.size),"))
        assertTrue(section.contains("ConfirmBodyText(line, bold = index == 1)"))
    }

    @Test
    fun theTwoStateAndOppositeWordsDifferInEveryLanguage() {
        val pairs = listOf(
            "words_switch_on" to "words_switch_off", "words_offer_turn_on" to "words_offer_not_now", "words_remove" to "words_keep",
            "words_forget_button" to "words_forget_all", "words_count_none" to "words_count",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) {
            assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
        }
        // FORGET ALL WORDS is not CANCEL, and REMOVE is not KEEP, in any language: a person must not be able to tap the wrong one by reading.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertNotEquals("$tag: FORGET ALL WORDS reads like CANCEL", map.getValue("words_forget_all"), map.getValue("common_cancel"))
            assertNotEquals("$tag: REMOVE reads like CANCEL", map.getValue("words_remove"), map.getValue("common_cancel"))
        }
    }

    @Test
    fun theButtonNamesInTheSentencesArePassedInAndNeverRetyped() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in listOf("words_explain_learns", "words_forget_names")) assertTrue("$tag/$name takes TARGET COMPUTER as %1\$s", map.getValue(name).contains("%1\$s"))
            assertTrue("$tag: kept takes both names", map.getValue("words_explain_kept").contains("%1\$s") && map.getValue("words_explain_kept").contains("%2\$s"))
            assertTrue("$tag: saved takes EXPORT .JSON", map.getValue("words_forget_saved").contains("%1\$s"))
            for (name in listOf("words_explain_kept", "words_forget_saved")) assertFalse("$tag/$name must not retype EXPORT .JSON", map.getValue(name).contains("EXPORT .JSON"))
        }
    }
}
