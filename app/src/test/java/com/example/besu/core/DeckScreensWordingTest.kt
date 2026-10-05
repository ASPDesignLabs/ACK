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
 * Part 1: the CREATE DECK dialog. Part 2: the QUICK ACTIONS deck and its two editors (QuickActionLabelsTest holds the decisions).
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
    private val qaNames = listOf(
        "qa_hint_tap", "qa_hint_hold", "qa_group_short", "qa_pose_short_identity", "qa_pose_short_defend", "qa_pose_short_connect", "qa_pose_part", "qa_root_part",
        "qa_hold_configure", "qa_slot_default", "qa_group_default",
        "qa_edit_title", "qa_phrase_template", "qa_edit_group", "qa_group_label", "qa_group_pose_desc", "qa_group_root_title", "qa_group_root_desc",
    )
    private val allNames get() = createNames + qaNames
    private val quick get() = file("decks/QuickActionsDeck.kt")

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringTheDeckScreensNameExists_inEveryLanguage_andNoneIsLeftUnused() {
        val sources = create + "\n" + quick
        val screenRefs = Regex("""R\.string\.((?:deck|qa)_[a-z_]+)""").findAll(sources).map { it.groupValues[1] }.toSet()
        // The words core/QuickActionLabels.kt names itself (a screen asks it for them), plus every other string either screen reads.
        val named = Regex(""""(qa_[a-z_]+)"""").findAll(file("core/QuickActionLabels.kt")).map { it.groupValues[1] }.toSet()
        val referenced = screenRefs + named
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = (referenced + Regex("""R\.string\.([a-z_]+)""").findAll(sources).map { it.groupValues[1] }).filter { it !in map }
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

    // ---- part 2: the QUICK ACTIONS deck ----------------------------------------------------------------------------------------------------

    @Test
    fun theOldQuickActionsLiteralsAreGone() {
        for (literal in listOf(
            "\"TAP: EXECUTE  //  HOLD: EDIT\"", "text = \"G${'$'}{group.groupIndex + 1}\"", "boundPose.take(3)", "category.take(3)", "\"POSE: ${'$'}{group.boundPose}", "text = \"EDIT\"", "\"[HOLD TO CONFIGURE]\"",
            "title = \"EDIT QUICK ACTION\"", "Text(\"BUTTON LABEL\")", "Text(\"PHRASE TEMPLATE\")", "TightSectionLabel(\"LOCAL VARIABLES\"", "\"VAR:${'$'}it\"", "TightSectionLabel(\"TARGET TAG FALLBACKS\"",
            "resolves to whichever entry is", "Text(\"TARGET TAG ${'$'}{index + 1} //", "text = \"SAVE\"", "text = \"CANCEL\"", "title = \"EDIT GROUP\"", "Text(\"GROUP LABEL\")",
            "WHICH GESTURE ON THE WATCH FIRES THIS GROUP", "TightSectionLabel(\"ROOT OVERRIDE SOURCE\"", "WHICH A/B/C VARIABLE BANK FILLS", "\"+ ${'$'}{computerCategory.label}\"",
        )) assertFalse("QuickActionsDeck.kt still holds $literal", quick.contains(literal))
        assertTrue(quick.contains("import com.example.besu.core.QuickActionLabels"))
        assertTrue(quick.contains("import androidx.compose.ui.res.stringResource"))
    }

    @Test
    fun theDecksOwnWordsComeFromTheDecisionsInCore() {
        assertTrue(quick.contains("text = QuickActionLabels.hint(words),"))
        assertTrue(quick.contains("text = QuickActionLabels.groupTab(words, group.groupIndex),"))
        assertTrue(quick.contains("text = QuickActionLabels.poseShort(words, group.boundPose),"))
        assertTrue(quick.contains("text = QuickActionLabels.poseShort(words, category),"))
        assertTrue("the header names the group like the editor does", quick.contains("text = QuickActionLabels.shownGroupLabel(words, group.label, group.groupIndex),"))
        assertTrue("the button names the slot", quick.contains("text = QuickActionLabels.shownSlotLabel(words, slot.label, slot.slotIndex),"))
        assertTrue(
            "POSE and ROOT are named the way the Matrix screen names them, and the POSE word follows PLAIN WORDS",
            quick.contains("text = QuickActionLabels.poseRootLine(words, labelFor(LabelKey.POSE), poseLabel(group.boundPose), poseLabel(group.rootCategory)),"),
        )
    }

    @Test
    fun theEditorsStartFromTheShownNameButSaveTheStoredOneWhenTheFieldWasNotTouched() {
        assertTrue(quick.contains("QuickActionLabels.shownSlotLabel(words, slot.label, slot.slotIndex)\n    }\n\n    var label by remember(slot.slotIndex) {\n        mutableStateOf(shownLabelAtStart)"))
        assertTrue(quick.contains("QuickActionLabels.shownGroupLabel(words, group.label, group.groupIndex)\n    }\n\n    var label by remember(group.groupIndex) {\n        mutableStateOf(shownLabelAtStart)"))
        assertTrue("the slot editor saves through labelToSave", Regex("""onSave\(\s*QuickActionLabels\.labelToSave\(label, shownLabelAtStart, slot\.label\),\s*template,""").containsMatchIn(quick))
        assertTrue("the group editor saves through labelToSave", quick.contains("onSave(QuickActionLabels.labelToSave(label, shownLabelAtStart, group.label), rootCategory, boundPose)"))
        // The pose and the root are saved as the stored constants, never as a word on a button.
        assertTrue(quick.contains(".clickable { onSelect(category) }"))
        assertTrue(quick.contains("onSelect = { boundPose = it }") && quick.contains("onSelect = { rootCategory = it }"))
    }

    @Test
    fun eachQuickActionsWordSitsOnTheControlThatDoesWhatItSays() {
        assertTrue("EDIT opens the group editor", Regex("""text = stringResource\(R\.string\.common_edit\),[\s\S]{0,300}?mainColor = primaryColor\s*\) \{\s*onEdit\(\)""").containsMatchIn(quick))
        assertTrue("[HOLD TO CONFIGURE] is only what an empty slot says", Regex("""if \(isConfigured\) \{\s*slot\.template\s*\} else \{\s*stringResource\(R\.string\.qa_hold_configure\)""").containsMatchIn(quick))
        assertTrue("the slot editor's title", Regex("""title = stringResource\(R\.string\.qa_edit_title\)[\s\S]{0,300}?stringResource\(R\.string\.emergency_button_label\)""").containsMatchIn(quick))
        assertTrue("the button label and the template have their own fields", Regex("""emergency_button_label[\s\S]{0,900}?qa_phrase_template""").containsMatchIn(quick))
        assertTrue("SAVE saves and CANCEL leaves, in the slot editor", Regex("""text = stringResource\(R\.string\.common_save\),[\s\S]{0,300}?QUICK_ACTION_SAVE[\s\S]{0,2500}?text = stringResource\(R\.string\.common_cancel\),[\s\S]{0,200}?onClick = onDismiss""").containsMatchIn(quick))
        assertTrue("SAVE saves and CANCEL leaves, in the group editor", Regex("""text = stringResource\(R\.string\.common_save\),\s*modifier = Modifier\.weight\(1f\),[\s\S]{0,300}?text = stringResource\(R\.string\.common_cancel\),[\s\S]{0,200}?onClick = onDismiss""").containsMatchIn(quick))
        // The group editor reads top to bottom: its title, the watch pose with its sentence over the pose buttons, then the root source with its sentence over the root buttons.
        val order = listOf(
            "R.string.qa_edit_group", "labelFor(LabelKey.WATCH_POSE)", "R.string.qa_group_pose_desc", "selected = boundPose", "R.string.qa_group_root_title", "R.string.qa_group_root_desc", "selected = rootCategory",
        )
        val at = order.map { quick.indexOf(it) }
        assertTrue("every part of the group editor is there: $at", at.all { it >= 0 })
        assertEquals("in this order", at.sorted(), at)
        assertTrue("the group label field", Regex("""label = \{\s*Text\(stringResource\(R\.string\.qa_group_label\)\)""").containsMatchIn(quick))
    }

    @Test
    fun theFallbackAndVariableLinesUseTheWordsTheMatrixEditorUses_withTheCategoryNamedLikeThePeopleScreens() {
        assertTrue(quick.contains("TightSectionLabel(stringResource(R.string.emergency_local_variables), color = primaryColor)"))
        assertTrue("the variable's field label is VAR:A or VAR n, as the autocomplete tree words it", quick.contains("AutocompleteLabels.quickActionField(words, index, tag)"))
        assertTrue(quick.contains("TightSectionLabel(stringResource(R.string.matrix_edit_fallbacks_title), color = primaryColor)"))
        assertTrue(quick.contains("text = stringResource(R.string.matrix_edit_fallbacks_hint),"))
        assertTrue(quick.contains("Text(stringResource(R.string.matrix_edit_target_tag, index + 1, categoryLabel))"))
        assertTrue("a category is named the way the People screens name it (a default in the language, a typed one as typed)", quick.contains("?.let { categoryName(it) }") && quick.contains("""text = "+ ${'$'}{categoryName(computerCategory)}","""))
    }

    @Test
    fun theWordsTheDeckSharesWithOtherScreensAreExactlyTheOldEnglish() {
        assertEquals("BUTTON LABEL", english.getValue("emergency_button_label"))
        assertEquals("LOCAL VARIABLES", english.getValue("emergency_local_variables"))
        assertEquals("TARGET TAG FALLBACKS", english.getValue("matrix_edit_fallbacks_title"))
        assertEquals(
            "[COMPUTER:X] resolves to whichever entry is currently active for that category in the Target Computer. If nothing is active, the fallback below is used instead.",
            english.getValue("matrix_edit_fallbacks_hint"),
        )
        assertEquals("TARGET TAG 2 // PEOPLE", EnglishText.get("matrix_edit_target_tag", 2, "PEOPLE"))
        assertEquals("EDIT", english.getValue("common_edit"))
        assertEquals("SAVE", english.getValue("common_save"))
        assertEquals("CANCEL", english.getValue("common_cancel"))
    }

    @Test
    fun theQuickActionsEnglishIsHeldExactly() {
        val expected = mapOf(
            "qa_hint_tap" to "TAP: EXECUTE", "qa_hint_hold" to "HOLD: EDIT", "qa_group_short" to "G%1\$d", "qa_pose_short_identity" to "IDE", "qa_pose_short_defend" to "DEF", "qa_pose_short_connect" to "CON",
            "qa_hold_configure" to "[HOLD TO CONFIGURE]", "qa_slot_default" to "ACTION %1\$d", "qa_group_default" to "GROUP %1\$d", "qa_edit_title" to "EDIT QUICK ACTION",
            "qa_phrase_template" to "PHRASE TEMPLATE", "qa_edit_group" to "EDIT GROUP", "qa_group_label" to "GROUP LABEL", "qa_group_pose_desc" to "WHICH GESTURE ON THE WATCH FIRES THIS GROUP.",
            "qa_group_root_title" to "ROOT OVERRIDE SOURCE", "qa_group_root_desc" to "WHICH A/B/C VARIABLE BANK FILLS THIS GROUP'S {{TAGS}}.",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
        assertEquals("POSE: IDENTITY", EnglishText.get("qa_pose_part", "POSE", "IDENTITY"))
        assertEquals("ROOT: DEFEND", EnglishText.get("qa_root_part", "DEFEND"))
    }

    @Test
    fun theQuickActionsArgumentsAreWhereTheCodePutsThem() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in listOf("qa_group_short", "qa_slot_default", "qa_group_default")) assertTrue("$tag/$name takes a number", map.getValue(name).contains("%1\$d"))
            assertTrue("$tag: the pose part takes the POSE word then a name", map.getValue("qa_pose_part").let { it.contains("%1\$s") && it.contains("%2\$s") && it.indexOf("%1\$s") < it.indexOf("%2\$s") })
            assertTrue("$tag: the root part takes a name", map.getValue("qa_root_part").contains("%1\$s"))
            for (name in qaNames - setOf("qa_group_short", "qa_slot_default", "qa_group_default", "qa_pose_part", "qa_root_part")) {
                assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
            }
        }
    }

    @Test
    fun theRootSentenceKeepsItsExampleTextAsWritten_andTheBracketedHintKeepsItsBrackets_inEveryLanguage() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertTrue("$tag: the {{TAGS}} example text is kept as written", map.getValue("qa_group_root_desc").contains("{{TAGS}}"))
            assertTrue("$tag: A/B/C is kept", map.getValue("qa_group_root_desc").contains("A/B/C"))
            val hold = map.getValue("qa_hold_configure")
            assertTrue("$tag: $hold", hold.startsWith("[") && hold.endsWith("]"))
        }
    }

    @Test
    fun theQuickActionsWordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "qa_hint_tap" to "qa_hint_hold", "qa_edit_title" to "qa_edit_group", "qa_group_label" to "qa_phrase_template", "qa_group_pose_desc" to "qa_group_root_desc",
            "qa_slot_default" to "qa_group_default", "qa_group_root_title" to "qa_group_label", "qa_pose_short_identity" to "qa_pose_short_defend", "qa_pose_short_defend" to "qa_pose_short_connect",
            "qa_pose_short_identity" to "qa_pose_short_connect", "qa_hold_configure" to "qa_hint_hold",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
    }

    @Test
    fun theHintsWordsMatchTheEmergencyDecksHint_soTheTwoDecksSayTheSameThing() {
        // The Emergency deck's hint says "TAP: EXECUTE  //  HOLD: CONFIGURE"; this deck's first half is the same words in every language.
        for ((tag, map) in listOf("en" to english) + translations.toList()) assertEquals("$tag", map.getValue("emergency_hint_tap"), map.getValue("qa_hint_tap"))
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
