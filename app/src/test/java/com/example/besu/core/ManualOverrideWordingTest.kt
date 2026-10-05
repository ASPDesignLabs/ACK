// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The legacy Manual Override screen (TYPE behind Terminal's `/m`), its memory-banks popup, the BUILDER deck's tactical guide and the Matrix editor's category buttons read their words from string
 * resources. The screen cannot be compiled here (`ui/DesignSystem.kt` uses the SDK; it is syntax-checked), so this reads it: the old English literals are gone, every string it names exists in every
 * language and none is unused, each word sits on the control that does what it says, and the values that are logic or saved (speech source tags, the variable letters, ids, the stored pose names) were not translated.
 * ManualOverrideTextTest holds the decisions. The Terminal's own save dialog, which shares four words with this screen, is the Terminal's group and is left alone.
 */
class ManualOverrideWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val design get() = noComments(RepoFiles.read("$base/ui/DesignSystem.kt"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    private val names = listOf(
        "manual_placeholder", "manual_encode", "manual_transmit", "manual_hide_browser", "manual_cache_recent", "manual_banks_empty",
        "manual_encode_to_bank", "manual_assign_tag", "manual_new_tag",
        "manual_confirm_delete", "manual_delete_question", "manual_delete_warning", "manual_delete_permanently", "manual_replay",
        "manual_guide_header", "manual_guide_identity_title", "manual_guide_identity_body", "manual_guide_defend_title", "manual_guide_defend_body",
        "manual_guide_connect_title", "manual_guide_connect_body", "manual_guide_unknown_title", "manual_guide_unknown_body",
    )

    /** TypeView, QuickAccessAccordion and RecentHistoryItem: the legacy screen and its helpers, not the Terminal above them or the Matrix editor below. */
    private val legacy: String get() {
        val d = design
        return d.substring(d.indexOf("fun TypeView("), d.indexOf("fun MatrixEditor("))
    }

    private val terminal: String get() {
        val d = design
        return d.substring(d.indexOf("fun TerminalView("), d.indexOf("fun TypeView("))
    }

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringTheScreenNamesExists_inEveryLanguage_andNoneIsLeftUnused() {
        val referenced = Regex("""R\.string\.(manual_[a-z_]+)""").findAll(design).map { it.groupValues[1] }.toSet() +
            Regex(""""(manual_[a-z_]+)"""").findAll(noComments(RepoFiles.read("$base/core/ManualOverrideText.kt"))).map { it.groupValues[1] }.toSet()
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = referenced.filter { it !in map }
            assertEquals("$tag: named but not defined: $missing", emptyList<String>(), missing)
        }
        assertEquals("defined but never used", emptyList<String>(), names.filter { it !in referenced })
        assertEquals("used but not in the list this test holds", emptyList<String>(), referenced.filter { it !in names })
    }

    @Test
    fun theOldLiteralsAreGone_fromTheLegacyScreenItsHelpersAndTheGuide() {
        val scope = legacy + "\n" + design.substring(design.indexOf("fun BuilderGuideCard("))
        for (literal in listOf(
            "\"ENTER SEQUENCE...\"", "NeonButton(\"ENCODE\"", "HeroButton(\"TRANSMIT\"", "\"[HIDE TARGET BROWSER]\"", "\"CACHE [RECENT]\"", "\"NO SAVED PHRASES YET", "dismissLabel = \"CLOSE\"",
            "title = \"ENCODE TO BANK\"", "TightSectionLabel(\"ASSIGN A TAG\")", "Text(\"NEW TAG\")", "TightPanelButton(\"SAVE\"", "TightPanelButton(\"CANCEL\"", "title = \"CONFIRM DELETE\"",
            "dismissLabel = \"ABORT\"", "\"Permanently remove the saved phrase", "text = \"DELETE PERMANENTLY\"", "text = \"CANCEL\"", "Text(\"REPLAY\"", "TACTICAL GUIDE", "ARM RAISED UP", "ARM FLAT / PALM DOWN",
            "HANDSHAKE / SIDEWAYS", "\"No data available.\"", "Use for: ",
        )) assertFalse("the legacy screen still holds $literal", scope.contains(literal))
        val matrix = design.substring(design.indexOf("fun MatrixEditor("))
        assertFalse(matrix.contains("\"+ \${computerCategory.label}\""))
        assertFalse(matrix.contains("?.label ?: categoryId"))
    }

    @Test
    fun theTerminalsOwnSaveDialogIsTheTerminalsGroup_soItsSharedWordsAreStillLiteral() {
        // Four words (ASSIGN A TAG, NEW TAG, SAVE, CANCEL) are spelled the same in the Terminal's save dialog. That dialog moves with the Terminal; pinned here so the boundary is a decision, not an oversight.
        assertTrue(terminal.contains("TightSectionLabel(\"ASSIGN A TAG\")"))
        assertTrue(terminal.contains("placeholder = { Text(\"NEW TAG\") },"))
        assertTrue(terminal.contains("TightPanelButton(\"SAVE\", modifier = Modifier.weight(1f), mainColor = FluxCyan)"))
        assertTrue(terminal.contains("TightPanelButton(\"CANCEL\", modifier = Modifier.weight(1f), isActive = false, mainColor = FluxCyan)"))
    }

    // ---- each word sits on the control that does what it says -----------------------------------------------------------------------

    @Test
    fun encodeOpensTheSaveDialog_andTransmitSpeaks_andTheirWordsAreTheStringsOfThoseNames() {
        assertTrue(Regex("""NeonButton\(stringResource\(R\.string\.manual_encode\),[\s\S]{0,200}?showSaveDialog = true""").containsMatchIn(legacy))
        assertTrue(Regex("""HeroButton\(stringResource\(R\.string\.manual_transmit\),[\s\S]{0,200}?speak\(textFieldValue\.text, "TERM/INPUT"\)""").containsMatchIn(legacy))
        assertTrue("the field's hint", Regex("""manual_placeholder\)[\s\S]{0,200}?maxLines = 3""").containsMatchIn(legacy))
    }

    @Test
    fun theTargetBrowserToggleSaysHideWhenItIsOpenAndTheLabelWhenItIsNot_andRecentsHaveTheirOwnHeading() {
        assertTrue(legacy.contains("""text = if (showBrowsePanel) stringResource(R.string.manual_hide_browser) else "[${'$'}{labelFor(LabelKey.BROWSE_TARGETS)}]","""))
        assertTrue(Regex("""if \(recentPhrases\.isNotEmpty\(\)\) \{\s*Text\(stringResource\(R\.string\.manual_cache_recent\)""").containsMatchIn(legacy))
        assertTrue("REPLAY is on each recent row", Regex("""fun RecentHistoryItem[\s\S]{0,700}?R\.string\.manual_replay""").containsMatchIn(legacy))
    }

    @Test
    fun theMemoryBanksPopupUsesTheFramesOwnClose_andItsEmptyMessageNamesTheEncodeButtonByItsWord() {
        // No dismissLabel of its own any more: it reads the frame's default (common_close), which is how about fifty dialogs already do it.
        assertTrue(Regex("""title = labelFor\(LabelKey\.MEMORY_BANKS\)\s*\) \{""").containsMatchIn(legacy))
        assertTrue(legacy.contains("text = ManualOverrideText.emptyBanks(words, stringResource(R.string.manual_encode)),"))
        assertTrue("the empty message is under the check for no saved phrases", Regex("""if \(savedPhrases\.isEmpty\(\)\) \{\s*Text\(\s*text = ManualOverrideText\.emptyBanks""").containsMatchIn(legacy))
    }

    @Test
    fun theSaveDialogTitlesItselfAndSavesWhatWasTyped_andCancelOnlyCloses() {
        assertTrue(Regex("""title = stringResource\(R\.string\.manual_encode_to_bank\)[\s\S]{0,300}?R\.string\.manual_assign_tag""").containsMatchIn(legacy))
        assertTrue(Regex("""R\.string\.manual_assign_tag[\s\S]{0,1400}?R\.string\.manual_new_tag""").containsMatchIn(legacy))
        assertTrue("SAVE saves the field's text under the tag", Regex("""stringResource\(R\.string\.common_save\), modifier = Modifier\.weight\(1f\), mainColor = primaryColor\) \{[\s\S]{0,300}?saveQuickPhrase\(context, textFieldValue\.text, newTagInput\)""").containsMatchIn(legacy))
        assertTrue("CANCEL only closes", legacy.contains("TightPanelButton(stringResource(R.string.common_cancel), modifier = Modifier.weight(1f), isActive = false, mainColor = primaryColor) { showSaveDialog = false }"))
    }

    @Test
    fun theDeleteConfirmationAsksWithThePhraseThenOffersTheDestructiveButtonFirstAndCancelAfter() {
        assertTrue(Regex("""title = stringResource\(R\.string\.manual_confirm_delete\),\s*dismissLabel = stringResource\(R\.string\.common_abort\)""").containsMatchIn(legacy))
        assertTrue(legacy.contains("text = ManualOverrideText.deleteQuestion(rememberText(), deleting.text),"))
        assertTrue("DELETE PERMANENTLY deletes", Regex("""text = stringResource\(R\.string\.manual_delete_permanently\),[\s\S]{0,200}?onDelete\(deleting\)""").containsMatchIn(legacy))
        assertTrue("CANCEL (after it) only closes", Regex("""onDelete\(deleting\)[\s\S]{0,300}?text = stringResource\(R\.string\.common_cancel\),[\s\S]{0,200}?deletingPhrase = null""").containsMatchIn(legacy))
        // The dialog still opens from the X on a row, and X is a symbol, not a word.
        assertTrue(legacy.contains("""Text("X", color = Color.Red"""))
    }

    // ---- what is logic or saved stayed as it was --------------------------------------------------------------------------------------

    @Test
    fun theSpeechSourceTagsAreLogicAndStayEnglish() {
        assertTrue(legacy.contains("\"TERM/INPUT\""))
        assertTrue(legacy.contains("\"CACHE/REPLAY\""))
        assertTrue(legacy.contains("\"BANK/\${p.tag}\""))
    }

    @Test
    fun theMatrixEditorsVariableLettersAreTokenNamesAndStayAsTheyAre_whileCategoryButtonsUseTheNameInTheLanguage() {
        for (letter in listOf("A", "B", "C")) {
            assertTrue("+ $letter inserts {VAR:$letter}", Regex("""text = "\+ $letter",[\s\S]{0,200}?insertTokenAtCursor\("\{VAR:$letter\}"\)""").containsMatchIn(design))
        }
        // The button is named by the category's name in the language, but it inserts by id: the token never changes.
        assertTrue(Regex("""text = "\+ \$\{categoryName\(computerCategory\)\}",[\s\S]{0,200}?insertTokenAtCursor\("\[COMPUTER:\$\{computerCategory\.id\}\]"\)""").containsMatchIn(design))
        assertTrue(design.contains("val categoryLabel = computerCategories.find { it.id == categoryId }?.let { categoryName(it) } ?: categoryId"))
        assertTrue("the chip's value is still resolved by id", design.contains("ComputerRepository.resolveTag(context, categoryId)"))
    }

    @Test
    fun theTacticalGuideTakesThePoseLabelAndStaysOnTheBuilderDeckOnly() {
        val guide = design.substring(design.indexOf("fun BuilderGuideCard("))
        assertTrue(guide.contains("ManualOverrideText.guide(words, labelFor(LabelKey.POSE), category)"))
        assertTrue(guide.contains("Text(ManualOverrideText.guideHeader(words, title), color = primaryColor"))
        assertTrue(design.contains("""if (deckName == "BUILDER") { BuilderGuideCard(category, primaryColor)"""))
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------

    @Test
    fun theArgumentsAreWhereTheCodePutsThem() {
        val oneArgument = setOf("manual_banks_empty", "manual_delete_question", "manual_guide_header", "manual_guide_identity_title", "manual_guide_defend_title", "manual_guide_connect_title")
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in oneArgument) {
                assertTrue("$tag/$name takes its argument", map.getValue(name).contains("%1\$s"))
                assertFalse("$tag/$name takes only one", map.getValue(name).contains("%2"))
            }
            for (name in names - oneArgument) assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
            // The phrase sits in straight quotes in every language: the test of "exactly as saved" relies on it.
            assertTrue("$tag: quotes round the phrase", map.getValue("manual_delete_question").contains("\"%1\$s\""))
        }
    }

    @Test
    fun theWordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "manual_encode" to "manual_transmit", "manual_encode" to "manual_encode_to_bank", "manual_confirm_delete" to "manual_delete_permanently", "manual_delete_question" to "manual_delete_warning",
            "manual_assign_tag" to "manual_new_tag", "manual_cache_recent" to "manual_replay", "manual_guide_identity_title" to "manual_guide_defend_title", "manual_guide_defend_title" to "manual_guide_connect_title",
            "manual_guide_identity_title" to "manual_guide_connect_title", "manual_guide_identity_body" to "manual_guide_defend_body", "manual_guide_defend_body" to "manual_guide_connect_body",
            "manual_guide_identity_body" to "manual_guide_connect_body", "manual_guide_unknown_title" to "manual_guide_unknown_body", "manual_hide_browser" to "manual_cache_recent",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
    }

    @Test
    fun theHeadingsAndButtonsAreCapitalsInTheLatinLanguages_theTwoSentenceFamiliesStayMixedCase() {
        val capitals = names - setOf("manual_delete_question", "manual_delete_warning", "manual_guide_identity_body", "manual_guide_defend_body", "manual_guide_connect_body", "manual_guide_unknown_body")
        for (tag in listOf("es", "pt", "af")) {
            val map = translations.getValue(tag)
            for (name in capitals) {
                val words = map.getValue(name).replace(Regex("""%\d+\$[sd]"""), "")
                assertEquals("$tag/$name is in capitals like the English", words.uppercase(), words)
            }
        }
        // The English description lines and the delete sentences are mixed case, and so are their translations, as the English always was.
        for (name in listOf("manual_delete_question", "manual_delete_warning", "manual_guide_identity_body", "manual_guide_defend_body", "manual_guide_connect_body", "manual_guide_unknown_body")) {
            assertNotEquals("the English $name is a sentence, not capitals", english.getValue(name).uppercase(), english.getValue(name))
        }
    }

    @Test
    fun theHindiAndArabicWordsAreInTheirOwnScript() {
        for (name in names) {
            val hi = translations.getValue("hi").getValue(name)
            val ar = translations.getValue("ar").getValue(name)
            assertTrue("hi/$name has Devanagari: $hi", hi.any { it in 'ऀ'..'ॿ' })
            assertTrue("ar/$name has Arabic letters: $ar", ar.any { it in '؀'..'ۿ' })
        }
    }
}
