// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The words the deck screens show read from string resources, in the chosen language. The screens cannot be compiled here (some are type-checked, none are run), so this reads them: the old
 * English literals are gone, every string they name exists and none is unused, each word sits on the control that does what it says, and the values that are SAVED (a new deck's default name,
 * the stored pose names, ids) were not translated. The words that name a deck type come from the label table (`label_deck_type_*`).
 *
 * Part 1: the CREATE DECK dialog.
 */
class DeckScreensWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val create get() = file("decks/CreateDeckDialog.kt")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val createNames = listOf(
        "deck_create_type", "deck_create_color", "deck_create_desc_matrix", "deck_create_desc_quick", "deck_create_desc_emergency", "deck_create_desc_emoji", "deck_create_desc_gif",
    )
    private val allNames get() = createNames

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringTheDeckScreensNameExists_inEveryLanguage_andNoneIsLeftUnused() {
        val sources = create
        val referenced = Regex("""R\.string\.(deck_[a-z_]+)""").findAll(sources).map { it.groupValues[1] }.toSet()
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = referenced.filter { it !in map }
            assertEquals("$tag: named but not defined: $missing", emptyList<String>(), missing)
        }
        val unused = allNames.filter { it !in referenced }
        assertTrue("defined but never used: $unused", unused.isEmpty())
    }

    @Test
    fun theOldCreateDeckLiteralsAreGone() {
        for (literal in listOf(
            "A full 3-pose Matrix", "Three action groups with four configurable slots", "Four immediate prompt slots", "Visual-only emoji pages", "Local GIF library with categories",
            "text = \"DECK TYPE\"", "text = \"DECK COLOR\"", "text = \"CANCEL\"", "text = \"CREATE\"",
        )) assertFalse("CreateDeckDialog.kt still holds $literal", create.contains(literal))
        assertTrue(create.contains("import com.example.besu.R\n"))
        assertTrue(create.contains("import androidx.compose.ui.res.stringResource"))
    }

    // ---- each word sits on the control that does what it says -----------------------------------------------------------------------------

    @Test
    fun eachDeckTypeIsDescribedByItsOwnSentence() {
        val block = create.substring(create.indexOf("val description = stringResource("), create.indexOf("Dialog(onDismissRequest"))
        for ((type, name) in listOf("MATRIX" to "matrix", "QUICK_ACTIONS" to "quick", "EMERGENCY" to "emergency", "EMOJI" to "emoji", "GIF" to "gif")) {
            assertTrue("$type is described by deck_create_desc_$name", block.contains("DeckType.$type -> R.string.deck_create_desc_$name"))
        }
    }

    @Test
    fun theSectionLabelsNameDeckByTheLabelTheScreenAlreadyUses_soTheyFollowPlainWords() {
        assertTrue(create.contains("text = stringResource(R.string.deck_create_type, labelFor(LabelKey.DECK)),"))
        assertTrue(create.contains("text = stringResource(R.string.deck_create_color, labelFor(LabelKey.DECK)),"))
        // The five type buttons are the label table's own names, as before.
        for (key in listOf("DECK_TYPE_MATRIX", "DECK_TYPE_QUICK", "DECK_TYPE_EMERGENCY", "DECK_TYPE_EMOJI", "DECK_TYPE_GIF")) assertTrue(create.contains("text = labelFor(LabelKey.$key),"))
        // The type label sits above the five buttons and the colour label above the swatches.
        assertTrue(Regex("""deck_create_type[\s\S]{0,900}?DeckTypeOption\(""").containsMatchIn(create))
        assertTrue(Regex("""deck_create_color[\s\S]{0,300}?DeckColorPicker\(""").containsMatchIn(create))
    }

    @Test
    fun cancelClosesAndCreateCreates_withTheSharedWords() {
        assertTrue(Regex("""text = stringResource\(R\.string\.common_cancel\),[\s\S]{0,200}?onDismiss\(\)""").containsMatchIn(create))
        assertTrue(Regex("""text = stringResource\(R\.string\.common_create\),[\s\S]{0,500}?AckTags\.DECK_CREATE_COMMIT[\s\S]{0,400}?onCreate\(""").containsMatchIn(create))
    }

    @Test
    fun aNewDecksDefaultNameIsWhatGetsSaved_soItStaysTheEnglishNameAndNeverFollowsTheLanguage() {
        // The prefilled name (and the name used when the field is left empty) is SAVED as the deck's name, so it is a name like CYBER or MY VOICE: the English text, in every language.
        for ((type, name) in listOf("MATRIX" to "MATRIX", "QUICK_ACTIONS" to "QUICK ACTIONS", "EMERGENCY" to "EMERGENCY", "EMOJI" to "EMOJI", "GIF" to "GIF")) {
            assertTrue("the fallback name for $type", create.contains("DeckType.$type -> \"$name\""))
            assertTrue("the prefilled name for $type", Regex("""deckType = DeckType\.$type\s*if \(deckName\.isDefaultDeckName\(\)\) \{\s*deckName = "$name"""").containsMatchIn(create))
        }
        assertTrue(create.contains("mutableStateOf(\"QUICK ACTIONS\")"))
        assertTrue(Regex("""isBlank\(\) \|\|\s*this == "MATRIX" \|\|\s*this == "QUICK ACTIONS" \|\|\s*this == "EMERGENCY" \|\|\s*this == "EMOJI" \|\|\s*this == "GIF"""").containsMatchIn(create))
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------------

    @Test
    fun theEnglishIsHeldExactly() {
        assertEquals("A full 3-pose Matrix with its own phrases, context layers, and profiles.", english.getValue("deck_create_desc_matrix"))
        assertEquals("Three action groups with four configurable slots per group.", english.getValue("deck_create_desc_quick"))
        assertEquals("Four immediate prompt slots with optional emergency overrides.", english.getValue("deck_create_desc_emergency"))
        assertEquals("Visual-only emoji pages with configurable grids and optional text.", english.getValue("deck_create_desc_emoji"))
        assertEquals("Local GIF library with categories, previews, and fullscreen playback.", english.getValue("deck_create_desc_gif"))
        assertEquals("DECK TYPE", EnglishText.get("deck_create_type", english.getValue("label_deck")))
        assertEquals("DECK COLOR", EnglishText.get("deck_create_color", english.getValue("label_deck")))
        assertEquals("CANCEL", english.getValue("common_cancel"))
        assertEquals("CREATE", english.getValue("common_create"))
    }

    @Test
    fun theTwoSectionLabelsTakeTheDeckLabelAsTheirOnlyArgument_inEveryLanguage() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in listOf("deck_create_type", "deck_create_color")) {
                assertTrue("$tag/$name takes the deck label", map.getValue(name).contains("%1\$s"))
                assertFalse("$tag/$name takes only one argument", map.getValue(name).contains("%2"))
            }
            for (name in createNames - setOf("deck_create_type", "deck_create_color")) assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
        }
    }

    @Test
    fun theFiveDescriptionsAndTheTwoLabelsDifferInEveryLanguage() {
        val pairs = createNames.flatMap { a -> createNames.filter { it > a }.map { b -> a to b } }
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
    }

    @Test
    fun theSectionLabelsNameTheDeckInTheLanguage_withTheLabelItWasGiven() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            assertTrue("$tag: type", f.get("deck_create_type", map.getValue("label_deck")).contains(map.getValue("label_deck")))
            assertTrue("$tag: colour", f.get("deck_create_color", map.getValue("label_deck")).contains(map.getValue("label_deck")))
        }
    }
}
