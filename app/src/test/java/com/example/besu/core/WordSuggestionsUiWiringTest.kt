// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The word-suggestion screens (the Statement Composer strip and offer, SETTINGS and FORGET WORDS) cannot be compiled or run without the Android
 * SDK. This reads them and holds them to the promises that matter: learning happens in exactly three places and nowhere else, nothing is
 * inserted without a tap, the strip is quiet, names are read and never copied, and a person can always see, remove and be asked.
 */
class WordSuggestionsUiWiringTest {

    private fun source(name: String) = RepoFiles.read("app/src/main/java/com/example/besu/$name")
    private val composer get() = source("composer/StatementComposerView.kt")
    private val section get() = source("settings/WordSuggestionsSection.kt")

    /** Every Kotlin file of the app with its text, so a rule can be checked everywhere at once. */
    private fun allSources(): List<Pair<String, String>> =
        RepoFiles.appSource.walkTopDown().filter { it.isFile && it.extension == "kt" }
            .map { it.relativeTo(RepoFiles.appSource).path.replace('\\', '/') to it.readText(Charsets.UTF_8) }.toList()

    /** [text] without comments (block and line), so a rule is checked against what runs, not what is said about it. */
    private fun code(text: String): String =
        text.replace(Regex("/\\*.*?\\*/", RegexOption.DOT_MATCHES_ALL), "").lines().joinToString("\n") { it.substringBefore("//") }

    /** The text of the first `{ ... }` that follows [marker], found by counting braces. */
    private fun blockAfter(text: String, marker: String): String {
        val at = text.indexOf(marker)
        assertTrue("$marker not found", at >= 0)
        val open = text.indexOf('{', at)
        var depth = 0
        var i = open
        while (i < text.length) {
            if (text[i] == '{') depth++
            if (text[i] == '}') { depth--; if (depth == 0) return text.substring(open + 1, i) }
            i++
        }
        error("unbalanced braces after $marker")
    }

    // ---- learning happens in exactly one place, from three buttons ------------------------------------------------------------

    @Test
    fun onlyTheComposerEverLearns_notTheTerminalManualOverrideTheEmergencyDeckOrAnyEditor() {
        val callers = allSources()
            .filter { (name, text) -> Regex("""LearnedWordsRepository\.learn\(""").containsMatchIn(code(text)) && !name.endsWith("data/LearnedWordsRepository.kt") }
            .map { it.first.removePrefix("com/example/besu/") }
        assertEquals(listOf("composer/StatementComposerView.kt"), callers)
        assertEquals("one call, inside learnFromCommittedText", 1, Regex("""LearnedWordsRepository\.learn\(""").findAll(code(composer)).count())
    }

    @Test
    fun learningIsCalledFromSaveCopyAndSpeakOfTheComposersOwnText_andNowhereElseInTheComposer() {
        val text = code(composer)
        val calls = Regex("""(?<!fun )learnFromCommittedText\(([\w.]+)\)""").findAll(text).map { it.groupValues[1] }.toList()
        assertEquals("exactly three calls (the definition is not one)", 3, calls.size)
        assertTrue("SAVE learns from the node it saved", calls.any { it == "node.template" })
        assertEquals("COPY and SPEAK learn from the field's own text", 2, calls.count { it == "textFieldValue.text" })
        // MY STATEMENTS' own COPY and SPEAK (a saved statement used again) do not learn.
        val copyAt = text.indexOf("onCopy = {")
        assertTrue("MY STATEMENTS' buttons not found", copyAt >= 0)
        val bank = text.substring(copyAt, text.indexOf("onDeleteRequest =", copyAt))
        assertFalse(bank.contains("learnFromCommittedText"))
    }

    @Test
    fun learningNeverBlocksATap_itRunsInTheBackground_andACommitWithNothingToSayLearnsNothing() {
        val body = blockAfter(code(composer), "fun learnFromCommittedText(")
        assertTrue(body.contains("Dispatchers.IO"))
        assertTrue("an unchanged text is counted once", body.contains("text == lastLearnedText"))
        assertTrue("with the switch off nothing is learned", body.contains("!wordSuggestionsOn"))
        val text = code(composer)
        assertEquals(2, Regex("""if \(resolvedPreview\.isNotBlank\(\)\) learnFromCommittedText""").findAll(text).count())
    }

    // ---- the strip -------------------------------------------------------------------------------------------------------------

    @Test
    fun theStripIsShownOnlyWithTheSwitchOn_andIsTheQuietHistoryChipRow() {
        val strip = blockAfter(code(composer), "if (wordSuggestionsOn) {\n            Spacer")
        assertTrue(strip.contains("AutocompleteChipRow("))
        assertTrue(strip.contains("AckTags.COMPOSER_WORD_STRIP"))
        for (banned in listOf("NeonButton", "TightPanelButton", "HeroButton")) assertFalse("$banned vibrates; a chip must not", strip.contains(banned))
    }

    @Test
    fun theComposerAndTheNewScreensAddNoAnimationSoundOrVibration() {
        for ((name, text) in listOf("composer" to composer, "settings section" to section, "name sources" to source("composer/WordSources.kt"))) {
            val c = code(text)
            for (banned in listOf("AnimatedVisibility", "animateContentSize", "Crossfade", "AnimatedContent", "animateFloatAsState", "performHapticFeedback", "Vibrator", "ToneGenerator", "MediaPlayer")) {
                assertFalse("$name uses $banned", c.contains(banned))
            }
        }
    }

    @Test
    fun aSuggestionIsOnlyEverInsertedByATap_throughTheOneInsertionRule_replacingTheHalfTypedWord() {
        val c = code(composer)
        val insert = blockAfter(c, "fun insertWordSuggestion(")
        assertTrue(insert.contains("TextInsertion.insert("))
        assertTrue(insert.contains("replace = prediction.replace"))
        // The only caller is the chip's own tap.
        assertEquals("the definition and one call", 2, Regex("""insertWordSuggestion\(""").findAll(c).count())
        assertTrue(c.contains("onSelect = { word -> insertWordSuggestion(word) }"))
    }

    @Test
    fun suggestionsAreQuietWhileTextIsSelected_andNeverWithTheSwitchOff() {
        val c = code(composer)
        assertTrue(c.contains("!wordSuggestionsOn || !textFieldValue.selection.collapsed"))
        assertTrue(c.contains("Prediction.NONE"))
    }

    // ---- names from elsewhere --------------------------------------------------------------------------------------------------

    @Test
    fun namesFromElsewhereAreOnlyReadAndNeverIncludeContactCardDetails() {
        val c = code(source("composer/WordSources.kt"))
        assertFalse("must never write", Regex("""\.edit\(|\.save\w*\(|\.put\w*\(|\.upsert\w*\(|LearnedWordsRepository""").containsMatchIn(c))
        for (card in listOf("contactCard", "phone", "email", "address", "ContactCard")) assertFalse("must not read $card", c.contains(card, ignoreCase = card[0].isLowerCase()))
        assertTrue("only entry names, not category headings", c.contains("ComputerNodeType.ENTRY") && c.contains("node.label"))
        assertTrue("only a slot that is switched on and filled in", c.contains("slot.enabled") && c.contains("slot.value.isNotBlank()"))
    }

    @Test
    fun namesAreReadLive_notStoredInTheComposer() {
        val c = code(composer)
        assertTrue(c.contains("WordSources.collect(context)"))
        assertTrue("re-read when a chip retargets a category", c.contains("remember(wordSuggestionsOn, targetRefreshKey)"))
    }

    // ---- the offer -------------------------------------------------------------------------------------------------------------

    @Test
    fun theOfferIsShownOnlyUnderTheCoreRule_turnsOnOnlyWhenTapped_andNotNowChangesNothing() {
        val c = code(composer)
        assertTrue(c.contains("AssistSettings.shouldOfferWordSuggestions("))
        val turnOn = blockAfter(c, "onTurnOn = {")
        assertTrue(turnOn.contains("AssistPrefs.setWordSuggestions(context, true)"))
        val notNow = blockAfter(c, "onNotNow = {")
        assertTrue(notNow.contains("AssistPrefs.dismissWordSuggestionsOffer(context)"))
        assertFalse("NOT NOW changes no setting", notNow.contains("setWordSuggestions"))
        // It never starts HELP or navigates (see the HELP navigation pitfall in CLAUDE.md).
        val offer = blockAfter(c, "private fun WordSuggestionsOffer(")
        assertFalse(offer.contains("helpManager") || offer.contains("HelpEvent") || offer.contains("viewMode"))
    }

    @Test
    fun theOfferTextIs12spOrLarger() {
        val offer = blockAfter(code(composer), "private fun WordSuggestionsOffer(")
        val sizes = Regex("""fontSize = (\d+)\.sp""").findAll(offer).map { it.groupValues[1].toInt() }.toList()
        assertTrue(sizes.isNotEmpty())
        assertTrue("the offer has text under 12 sp: $sizes", sizes.all { it >= 12 })
    }

    // ---- SETTINGS and FORGET WORDS ---------------------------------------------------------------------------------------------

    @Test
    fun settingsShowsTheSectionOnce() {
        assertEquals(1, Regex("""WordSuggestionsSection\(""").findAll(source("settings/SettingsView.kt")).count())
    }

    @Test
    fun theSwitchWritesThroughAssistPrefs_andSaysOnOrOffInWords() {
        val c = code(section)
        assertTrue(c.contains("AssistPrefs.setWordSuggestions(context, on)"))
        assertTrue(c.contains("WordSuggestionText.switchLabel(on)"))
    }

    @Test
    fun forgettingOneWordAsksOnceMore_andForgettingAllAsksTwice_withCancelProminentAndABackupNamedFirst() {
        val c = code(section)
        // one word: REMOVE only opens a question; the word goes only from the question's own REMOVE
        assertEquals(1, Regex("""LearnedWordsRepository\.forget\(""").findAll(c).count())
        val forgetAt = c.indexOf("LearnedWordsRepository.forget(")
        assertTrue("forget(word) must sit after the confirmation question", forgetAt > c.indexOf("WordSuggestionText.REMOVE_QUESTION"))
        // all: one call, only inside the second confirmation, and a first confirmation that offers BACK UP FIRST
        assertEquals(1, Regex("""LearnedWordsRepository\.forgetAll\(""").findAll(c).count())
        val second = blockAfter(c, "if (secondForAll) {")
        assertTrue(second.contains("LearnedWordsRepository.forgetAll(context)"))
        assertTrue(second.contains("WordSuggestionText.FORGET_ALL_SECOND"))
        val first = blockAfter(c, "if (firstForAll && !secondForAll) {")
        assertTrue(first.contains("WordSuggestionText.BACK_UP_FIRST"))
        assertTrue(first.contains("WordSuggestionText.forgetAllFirstConfirmation("))
        assertFalse("the first confirmation deletes nothing", first.contains("forgetAll("))
        // CANCEL comes before the destructive button on the second confirmation
        val cancelAt = second.indexOf("NeonButton(WordSuggestionText.CANCEL")
        val forgetAllAt = second.indexOf("NeonButton(WordSuggestionText.FORGET_ALL")
        assertTrue("both buttons must be there", cancelAt >= 0 && forgetAllAt >= 0)
        assertTrue("CANCEL must come first", cancelAt < forgetAllAt)
    }

    @Test
    fun forgetWordsWorksWithTheSwitchOff_andUsesNoSmallText() {
        val c = code(section)
        assertFalse("listing and forgetting must not depend on the switch", blockAfter(c, "private fun ForgetWordsDialog(").contains("isWordSuggestionsOn"))
        for (m in Regex("""fontSize = (\d+)\.sp[^\n]*""").findAll(c)) {
            val size = m.groupValues[1].toInt()
            // The section heading follows the other SETTINGS headings (10 sp, letter-spaced); everything else is 12 sp or more.
            assertTrue("text under 12 sp: ${m.value}", size >= 12 || m.value.contains("letterSpacing = 2.sp"))
        }
    }

    // ---- HELP and tags ---------------------------------------------------------------------------------------------------------

    @Test
    fun theComposerHelpSaysWhereToTurnItOn_thatItIsOff_andNothingIsAddedWithoutATap() {
        val help = source("help/StatementComposerHelp.kt")
        // The body is several string literals joined with +, so join them before looking for a phrase that spans two.
        val step = help.substring(help.indexOf("id = \"word_suggestions\""), help.indexOf("id = \"insert_target_chip\""))
            .replace(Regex("\"\\s*\\+\\s*\""), "")
        assertTrue(step.contains("off until you turn it on"))
        assertTrue(step.contains("SETTINGS > WORD SUGGESTIONS"))
        assertTrue(step.contains("until you tap"))
        assertTrue(step.contains("AckTags.COMPOSER_WORD_STRIP"))
        assertFalse("a Read step: nothing waits for the person to turn it on", step.contains("HelpAction."))
    }

    @Test
    fun theNewTagsAreNamedLikeTheirValues_andEveryOneIsUsed() {
        val tags = source("AckTags.kt")
        val used = allSources().filter { !it.first.endsWith("/AckTags.kt") }.joinToString("\n") { it.second }
        for (tag in listOf("COMPOSER_WORD_STRIP", "COMPOSER_WORD_OFFER", "WORD_SUGGESTIONS_SWITCH", "WORD_SUGGESTIONS_FORGET_BTN")) {
            assertTrue("$tag must be declared as const val $tag = \"$tag\"", tags.contains("const val $tag = \"$tag\""))
            assertTrue("$tag is declared but never used", used.contains("AckTags.$tag"))
        }
    }
}
