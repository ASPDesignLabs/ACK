// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * MANAGE AUTOCOMPLETE (settings/ManageAutocompleteDialog.kt and its section in SETTINGS) reads its words from string resources, in the chosen language. The screens cannot
 * be compiled or run here, so this reads them: the old English literals are gone, every string named exists and none is unused, the tree is still grouped and identified by
 * the stored names (only its labels are words), a name the person gave is shown as typed, each word sits on the control that does what it says, and a field's history or
 * all of it is cleared only from the confirmation. AutocompleteLabelsTest holds the tree's own words.
 */
class ManageAutocompleteWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val dialog get() = file("settings/ManageAutocompleteDialog.kt")
    private val settings get() = file("settings/SettingsView.kt")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val acNames get() = english.keys.filter { it.startsWith("autocomplete_") } + StringsXml.plurals(StringsXml.default).keys.filter { it.startsWith("autocomplete_") }

    @Test
    fun everyStringTheScreensNameExists_andNoneIsLeftUnused() {
        val sources = dialog + "\n" + settings + "\n" + file("core/AutocompleteLabels.kt")
        val referenced = Regex("""R\.string\.(autocomplete_[a-z_]+)""").findAll(dialog + "\n" + settings).map { it.groupValues[1] }.toSet()
        val missing = referenced.filter { it !in acNames }
        assertEquals("named but not defined: $missing", emptyList<String>(), missing)
        val named = Regex(""""(autocomplete_[a-z_]+)"""").findAll(sources).map { it.groupValues[1] }.toSet()
        val unused = acNames.toSet() - referenced - named
        assertTrue("defined but never used: $unused", unused.isEmpty())
        assertTrue("CLEAR and CANCEL are the shared words", Regex("""R\.string\.common_clear\b""").containsMatchIn(dialog) && Regex("""R\.string\.common_cancel\b""").containsMatchIn(dialog))
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawn() {
        val gone = listOf(
            "\"MANAGE AUTOCOMPLETE\"", "FIELD\${if", "NOTHING REMEMBERED YET", "\"CLEAR ALL AUTOCOMPLETE HISTORY\"", "\"CLEAR FIELD HISTORY\"", "\"CANCEL\"", "\"CLEAR\"", "\"CLEAR ALL\"",
            "This removes every remembered value", "CLEAR THIS FIELD'S HISTORY", "\"MATRIX (", "\"QUICK ACTIONS (", "SHARED ROOT VARIABLES (", "\"VARIABLE \${", "\"UNKNOWN NODE\"", "\"UNKNOWN\"",
            "\"SLOT \${", "\"VAR \${", "\"TAG \$",
        )
        for (literal in gone) assertFalse("ManageAutocompleteDialog.kt still holds $literal", dialog.contains(literal))
        for (literal in listOf("\"AUTOCOMPLETE\"", "ACK remembers what you've typed", "\"MANAGE AUTOCOMPLETE\"")) assertFalse("SettingsView.kt still holds $literal", settings.contains(literal))
        assertTrue("an explicit R import outside the base package", dialog.contains("import com.example.besu.R"))
    }

    // ---- the tree is identified by stored names; only its labels are words ------------------------------------------------------------------

    @Test
    fun theTreeIsStillGroupedAndIdentifiedByTheStoredNames_andANameThePersonGaveIsShownAsTyped() {
        assertTrue(dialog.contains("private fun buildAutocompleteTree(\n    context: Context,\n    text: TextSource,"))
        assertTrue(dialog.contains("buildAutocompleteTree(context, text, scopes)"))
        // Grouping and the ids that remember what is expanded use the stored pose, profile, deck and category, never a label.
        assertTrue(dialog.contains("AcBranch(id = \"mtx_${'$'}{deckId}_${'$'}{profile}_${'$'}pose\", label = AutocompleteLabels.poseOrLayer(text, pose), children = nodeBranches)"))
        assertTrue(dialog.contains("AcBranch(id = \"root_${'$'}category\", label = AutocompleteLabels.poseOrLayer(text, category), children = tagLeaves)"))
        assertTrue(dialog.contains("AcBranch(id = \"mtx_deck_${'$'}deckId\", label = deckName, children = profileBranches)"))
        assertTrue(dialog.contains("AcBranch(id = \"mtx_${'$'}{deckId}_${'$'}profile\", label = profile, children = poseBranches)"))
        // A deck, a profile, a group, a slot and a node are the person's own names: shown as stored, with the default only when there is none.
        assertTrue(dialog.contains("val groupLabel = group?.label ?: \"G${'$'}{groupIndex + 1}\""))
        assertTrue(dialog.contains("val slotLabel = slot?.label ?: AutocompleteLabels.defaultSlot(text, slotIndex)"))
        assertTrue(dialog.contains("?.label ?: AutocompleteLabels.unknownNode(text)"))
        assertEquals("both missing-pose fallbacks use the key that cannot be a layer name", 2, Regex("""AutocompleteLabels\.UNKNOWN_KEY""").findAll(dialog).count())
        assertFalse("a label must not be what a branch is identified by", Regex("""id = "[^"]*\$\{?[a-zA-Z]*[lL]abel""").containsMatchIn(dialog))
        // The three kinds keep their ids and their counts.
        assertTrue(dialog.contains("AutocompleteLabels.kindHeading(text, AutocompleteLabels.Kind.MATRIX, matrixScopes.size)"))
        assertTrue(dialog.contains("AutocompleteLabels.kindHeading(text, AutocompleteLabels.Kind.QUICK_ACTIONS, qaScopes.size)"))
        assertTrue(dialog.contains("AutocompleteLabels.kindHeading(text, AutocompleteLabels.Kind.SHARED_ROOT, rootScopes.size)"))
        for (id in listOf("kind_mtx", "kind_qa", "kind_root")) assertTrue(id, dialog.contains("id = \"$id\""))
        // A remembered value is the person's own text.
        assertTrue(dialog.contains("text = entry.value,"))
    }

    @Test
    fun theSubtitleIsAPluralWithTheCount() {
        assertTrue(dialog.contains("subtitle = text.count(\"autocomplete_fields_remembered\", scopes.size)"))
        assertEquals("1 FIELD REMEMBERED", EnglishText.count("autocomplete_fields_remembered", 1))
        assertEquals("0 FIELDS REMEMBERED", EnglishText.count("autocomplete_fields_remembered", 0))
        assertEquals("5 FIELDS REMEMBERED", EnglishText.count("autocomplete_fields_remembered", 5))
        for ((tag, _) in translations) assertTrue("$tag: the count", FileText(tag).count("autocomplete_fields_remembered", 12).contains("12"))
    }

    // ---- each word sits on the control that does what it says; clearing only from the confirmation ----------------------------------------------

    private fun wordThenAction(word: String, action: String, within: Int = 300) =
        Regex("""R\.string\.${Regex.escape(word)}[\s\S]{0,$within}?${Regex.escape(action)}""").containsMatchIn(dialog)

    @Test
    fun everyButtonWordIsOnTheControlThatDoesWhatItSays() {
        assertTrue("CLEAR ALL AUTOCOMPLETE HISTORY only asks", wordThenAction("autocomplete_clear_all)", "onClick = { confirmingClearAll = true }", 200))
        assertTrue("CLEAR THIS FIELD'S HISTORY only asks", wordThenAction("autocomplete_clear_this_field)", "onClick = onClearRequested", 200))
        assertTrue("the row's request is the question", dialog.contains("onClearRequested = { confirmingClearKey = node.scopeKey }"))
        assertTrue("CLEAR clears the one field", wordThenAction("common_clear)", "AutocompleteHistoryRepository.clearScope(context, clearingKey)", 200))
        assertTrue("CLEAR ALL clears everything", wordThenAction("autocomplete_clear_all_button)", "AutocompleteHistoryRepository.clearAll(context)", 200))
        assertEquals("one call clears a field and one clears all, each from its own confirmation", 1, Regex("""clearScope\(context""").findAll(dialog).count())
        assertEquals(1, Regex("""\.clearAll\(context\)""").findAll(dialog).count())
        assertTrue("CANCEL in the field question", Regex("""R\.string\.common_cancel\)[\s\S]{0,200}?confirmingClearKey = null""").containsMatchIn(dialog))
        assertTrue("CANCEL in the all question", Regex("""R\.string\.common_cancel\)[\s\S]{0,200}?confirmingClearAll = false""").containsMatchIn(dialog))
        assertTrue("[X] removes one value", Regex("""text = "\[X\]",[\s\S]{0,400}?onValueRemoved\(entry\.value\)""").containsMatchIn(dialog))
        assertTrue("the field question's title", dialog.contains("title = stringResource(R.string.autocomplete_clear_field_title),"))
        assertTrue("the all question's title", dialog.contains("title = stringResource(R.string.autocomplete_clear_all),\n            dismissLabel = stringResource(R.string.common_cancel)"))
    }

    @Test
    fun theSettingsSectionNamesTheExportButtonAsItReadsNow_andOpensTheDialog() {
        assertTrue(settings.contains("stringResource(R.string.autocomplete_section_help, labelFor(LabelKey.EXPORT_JSON)),"))
        assertTrue(Regex("""R\.string\.autocomplete_manage\)[\s\S]{0,400}?showManageAutocomplete = true""").containsMatchIn(settings))
        assertTrue(settings.contains("Text(stringResource(R.string.autocomplete_section_title), color = primaryColor"))
        // The tag the HELP walkthrough points at is unchanged.
        assertTrue(settings.contains(".testTag(AckTags.AUTOCOMPLETE_MANAGE_BTN)"))
        assertTrue(dialog.contains("title = stringResource(R.string.autocomplete_manage),"))
    }

    // ---- every language ----------------------------------------------------------------------------------------------------------------------

    @Test
    fun theTwoClearQuestionsKeepTheirSafetySentences_inEveryLanguage() {
        // "Nothing else is affected" and "this cannot be undone" are two sentences: a translation that loses one of them is caught by the count of sentence ends.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val field = map.getValue("autocomplete_clear_field_body")
            val all = map.getValue("autocomplete_clear_all_body")
            val ends = Regex("""[.。।]""")
            assertEquals("$tag: the one-field question says three things", 3, ends.findAll(field).count())
            assertEquals("$tag: the clear-all question says two things", 2, ends.findAll(all).count())
        }
        for ((tag, map) in translations) {
            for (name in listOf("autocomplete_clear_field_body", "autocomplete_clear_all_body", "autocomplete_clear_all", "autocomplete_clear_field_title")) {
                assertNotEquals("$tag/$name is still English", english.getValue(name), map.getValue(name))
            }
            // CLEAR, CLEAR ALL and CANCEL are different words, so a person cannot tap the wrong one by reading.
            assertNotEquals("$tag: CLEAR and CLEAR ALL", map.getValue("common_clear"), map.getValue("autocomplete_clear_all_button"))
            assertNotEquals("$tag: CLEAR and CANCEL", map.getValue("common_clear"), map.getValue("common_cancel"))
            assertNotEquals("$tag: CLEAR ALL and CANCEL", map.getValue("autocomplete_clear_all_button"), map.getValue("common_cancel"))
            assertNotEquals("$tag: the two titles", map.getValue("autocomplete_clear_field_title"), map.getValue("autocomplete_clear_all"))
        }
    }

    @Test
    fun theSectionHelpNamesTheExportButtonByArgument_andUsesTheDeckTypeWordsInEveryLanguageButArabic() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val help = map.getValue("autocomplete_section_help")
            assertEquals("$tag: one placeholder", listOf("%1\$s"), StringsXml.placeholders(help))
            assertFalse("$tag: must not retype EXPORT .JSON", help.contains("EXPORT .JSON"))
        }
        // Arabic puts the definite article on these names ("الإجراءات السريعة"), so the label's exact text is not a substring there.
        for ((tag, map) in translations.filterKeys { it != "ar" }) {
            for (sentence in listOf("autocomplete_section_help", "autocomplete_empty")) {
                val text = map.getValue(sentence)
                assertTrue("$tag/$sentence says Matrix as the label does", text.contains(map.getValue("label_deck_type_matrix")))
                assertTrue("$tag/$sentence says Quick Actions as the label does", text.contains(map.getValue("label_deck_type_quick")))
            }
            assertTrue("$tag: shared variables as the label reads", map.getValue("autocomplete_section_help").contains(map.getValue("label_shared_variables")))
        }
    }

    @Test
    fun theEnglishIsHeldExactly() {
        assertEquals("MANAGE AUTOCOMPLETE", english.getValue("autocomplete_manage"))
        assertEquals("AUTOCOMPLETE", english.getValue("autocomplete_section_title"))
        assertEquals(
            "ACK remembers what you've typed into Matrix and Quick Actions variable fields and Shared Root Variables, offering your most-used past values back as tappable chips that narrow as you type. " +
                "Local to this device, and included in EXPORT .JSON backups.",
            EnglishText.get("autocomplete_section_help", EnglishText.get("label_export_json"))
        )
        assertEquals(
            "NOTHING REMEMBERED YET. START TYPING INTO A MATRIX NODE'S VARIABLE, A QUICK ACTIONS SLOT'S VARIABLE, OR A SHARED ROOT VARIABLE -- ACK REMEMBERS IT HERE.",
            english.getValue("autocomplete_empty")
        )
        assertEquals("This removes every remembered value for this one field. Nothing else is affected. This cannot be undone.", english.getValue("autocomplete_clear_field_body"))
        assertEquals("This removes every remembered value for every Matrix, Quick Actions, and Shared Root Variable field. This cannot be undone.", english.getValue("autocomplete_clear_all_body"))
        assertEquals("CLEAR THIS FIELD'S HISTORY", english.getValue("autocomplete_clear_this_field"))
    }
}
