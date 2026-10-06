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
 * Part 1: the CREATE DECK dialog. Part 2: the QUICK ACTIONS deck and its two editors (QuickActionLabelsTest holds the decisions). Part 3: the EMOJI deck, its editors, its library's headings
 * and its configuration dialog (EmojiLabelsTest holds the decisions). Part 4: the GIF deck, its backup menu, its import dialog and the messages after an import or an export (GifLabelsTest holds the decisions).
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
    private val emojiNames = listOf(
        "emoji_title", "emoji_hint_tap", "emoji_hint_hold", "emoji_config_button", "emoji_txt", "emoji_hold_to_set", "emoji_page_default",
        "emoji_configure_title", "emoji_related_edit_title", "emoji_custom", "emoji_hide_library", "emoji_pick_library", "emoji_label_optional", "emoji_overlay_text_optional",
        "emoji_open_related", "emoji_configure_related", "emoji_related_note", "emoji_related_title", "emoji_panel_default", "emoji_related_hold", "emoji_related_tap",
        "emoji_cat_responses", "emoji_cat_boundaries", "emoji_cat_needs", "emoji_cat_feelings", "emoji_cat_regulation", "emoji_cat_people_places",
        "emoji_config_title", "emoji_grid_size", "emoji_overlay_timeout", "emoji_timeout_standard", "emoji_timeout_extended", "emoji_timeout_none",
        "emoji_pages", "emoji_add_page", "emoji_save_config",
    )
    private val gifNames = listOf(
        "gif_title", "gif_backup", "gif_export_deck", "gif_import_deck", "gif_import_button", "gif_category_line", "gif_no_gifs", "gif_empty_title", "gif_empty_hint",
        "gif_overlay_landscape", "gif_prev", "gif_next", "gif_display_full", "gif_share", "gif_share_chooser",
        "gif_import_title", "gif_field_title", "gif_field_category", "gif_category_example", "gif_import_confirm",
        "gif_exported", "gif_export_failed", "gif_import_failed_check", "gif_import_failed",
        "gif_err_not_gif", "gif_err_too_big", "gif_err_unreadable", "gif_err_invalid", "gif_category_default",
    )
    private val gifPluralNames = listOf("gif_imported_toast", "gif_imported_skipped_toast")
    private val allNames get() = createNames + qaNames + emojiNames + gifNames
    private val emoji get() = file("decks/EmojiDeck.kt")
    private val gif get() = file("decks/GifDeck.kt")
    private val gifRepo get() = file("decks/GifRepository.kt")
    private val quick get() = file("decks/QuickActionsDeck.kt")

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringTheDeckScreensNameExists_inEveryLanguage_andNoneIsLeftUnused() {
        val sources = create + "\n" + quick + "\n" + emoji + "\n" + gif
        val screenRefs = Regex("""R\.string\.((?:deck|qa|emoji|gif)_[a-z_]+)""").findAll(sources).map { it.groupValues[1] }.toSet()
        // The words core/QuickActionLabels.kt, EmojiLabels.kt, GifLabels.kt and GifImportFailure.kt name themselves (a screen asks them for the words), plus every other string a screen reads.
        // (The two plurals are named there too but are not strings: part 4 checks them in every language.)
        val named = Regex(""""((?:qa|emoji|gif)_[a-z_]+)"""").findAll(
            file("core/QuickActionLabels.kt") + "\n" + file("core/EmojiLabels.kt") + "\n" + file("core/GifLabels.kt") + "\n" + file("core/GifImportFailure.kt")
        ).map { it.groupValues[1] }.toSet() - gifPluralNames.toSet()
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

    // ---- part 3: the EMOJI deck -------------------------------------------------------------------------------------------------------------

    @Test
    fun theOldEmojiLiteralsAreGone() {
        for (literal in listOf(
            "text = \"EMOJI // EXPRESS\"", "\"TAP: DISPLAY  //  HOLD: CONFIGURE\"", "text = \"CONFIG\"", "text = \"TXT\"", "\"HOLD\\nTO SET\"", "title = \"CONFIGURE EMOJI", "title = \"RELATED EMOJI", "label = \"CUSTOM EMOJI\"",
            "\"HIDE EMOJI LIBRARY\"", "\"PICK FROM LIBRARY\"", "\"LABEL // OPTIONAL\"", "\"OVERLAY TEXT // OPTIONAL\"", "\"OPEN RELATED EMOJI PANEL\"", "\"CONFIGURE RELATED PANEL\"",
            "THIS SLOT OPENS A SINGLE-PAGE EMOJI PANEL", "text = \"CLEAR\"", "text = \"SAVE\"", "text = \"DONE\"", "title = \"RELATED // ", "{ \"PANEL\" }", "HOLD A TILE TO CONFIGURE IT", "TAP AN EMOJI TO DISPLAY IT",
            "\"RESPONSES\" to", "\"BOUNDARIES\" to", "\"NEEDS\" to", "\"FEELINGS\" to", "\"REGULATION\" to", "\"PEOPLE / PLACES\" to", "title = \"EMOJI DECK CONFIG\"", "text = \"GRID SIZE\"",
            "text = \"OVERLAY TIMEOUT\"", "option.name.replace", "text = \"PAGES // ", "text = \"+ ADD PAGE\"", "text = \"SAVE CONFIG\"",
        )) assertFalse("EmojiDeck.kt still holds $literal", emoji.contains(literal))
        assertTrue(emoji.contains("import com.example.besu.R\n"))
        assertTrue(emoji.contains("import androidx.compose.ui.res.stringResource"))
    }

    @Test
    fun theDecksOwnWordsComeFromTheDecisionsInCore_andTheTitleNamesTheDeckTypeByItsLabel() {
        assertTrue(emoji.contains("text = stringResource(R.string.emoji_title, labelFor(LabelKey.DECK_TYPE_EMOJI)),"))
        assertTrue(emoji.contains("text = EmojiLabels.hint(words),"))
        assertTrue(emoji.contains("pageName = EmojiLabels.shownPageName(words, activePage.name, activePageIndex),"))
        assertEquals("both related dialogs title themselves the same way", 2, Regex("""title = EmojiLabels\.relatedTitle\(rememberText\(\), parentSlot\.label, parentSlot\.emoji\),""").findAll(emoji).count())
        assertTrue(emoji.contains("title = stringResource(R.string.emoji_config_title, labelFor(LabelKey.DECK_TYPE_EMOJI), labelFor(LabelKey.DECK)),"))
    }

    @Test
    fun theSavedPageNamesWereNotTranslated() {
        // A new page is SAVED as PAGE <n> (and the deck starts with PAGE 1), whatever the language: the screen shows them in the language, it never stores that.
        assertTrue(emoji.contains("""name = "PAGE 1""""))
        assertTrue(emoji.contains("""name = "PAGE ${'$'}nextNumber""""))
        assertTrue(emoji.contains("""pageId = "page_1","""))
        assertTrue(emoji.contains("""pageId = "page_${'$'}{UUID.randomUUID()}","""))
        // The emoji sent to the visual prompt and the tile's own text are the person's, passed along untouched.
        assertTrue(emoji.contains("""putExtra("emoji", slot.emoji)""") && emoji.contains("""putExtra("display_text", slot.displayText)"""))
    }

    @Test
    fun theLibraryHeadingsSitOverTheirOwnEmoji() {
        for ((name, first) in listOf("responses" to "✅", "boundaries" to "🛑", "needs" to "⏳", "feelings" to "😀", "regulation" to "🧠", "people_places" to "👤")) {
            assertTrue("emoji_cat_$name is over $first", emoji.contains("R.string.emoji_cat_$name to listOf(\"$first\""))
        }
        assertTrue(Regex("""stringResource\(titleRes\),[\s\S]{0,900}?emojiList\.forEach""").containsMatchIn(emoji))
    }

    @Test
    fun eachEmojiWordSitsOnTheControlThatDoesWhatItSays() {
        assertTrue("the library button flips the picker", Regex("""stringResource\(R\.string\.emoji_hide_library\)[\s\S]{0,300}?stringResource\(R\.string\.emoji_pick_library\)[\s\S]{0,700}?pickerOpen = !pickerOpen""").containsMatchIn(emoji))
        assertTrue("OPEN RELATED EMOJI PANEL is the switch for opensRelatedPanel", Regex("""label = stringResource\(R\.string\.emoji_open_related\),\s*enabled = opensRelatedPanel,[\s\S]{0,400}?opensRelatedPanel = !opensRelatedPanel""").containsMatchIn(emoji))
        assertTrue("CONFIGURE RELATED PANEL saves the parent and opens the child editor", Regex("""text = stringResource\(R\.string\.emoji_configure_related\),[\s\S]{0,900}?onSaveParentForRelated\([\s\S]{0,300}?showRelatedPanelEditor = true""").containsMatchIn(emoji))
        assertTrue("the note is under the related switch's button", Regex("""emoji_configure_related[\s\S]{0,1500}?text = stringResource\(R\.string\.emoji_related_note\)""").containsMatchIn(emoji))
        assertTrue("CLEAR empties the tile and SAVE saves it", Regex("""text = stringResource\(R\.string\.common_clear\),[\s\S]{0,400}?emoji = ""\s*label = ""\s*displayText = ""\s*opensRelatedPanel = false[\s\S]{0,300}?text = stringResource\(R\.string\.common_save\),[\s\S]{0,400}?onSave\(""").containsMatchIn(emoji))
        assertTrue("the three fields are the emoji, the label and the overlay text", Regex("""emoji_custom\),\s*value = emoji,[\s\S]{0,1500}?emoji_label_optional\),\s*value = label,[\s\S]{0,500}?emoji_overlay_text_optional\),\s*value = displayText,""").containsMatchIn(emoji))
        assertTrue("both viewers end with DONE closing them", Regex("""text = stringResource\(R\.string\.common_done\),[\s\S]{0,300}?onDismiss\(\)""").findAll(emoji).count() >= 2)
        assertTrue("the viewer's sentence is over tiles that only pass the chosen emoji on", Regex("""emoji_related_tap\)[\s\S]{0,1500}?onSelect\(childSlot\)""").containsMatchIn(emoji))
        assertTrue("the editor's sentence is over tiles that open the child editor", Regex("""emoji_related_hold\)[\s\S]{0,1500}?editingChildSlot = childSlot""").containsMatchIn(emoji))
    }

    @Test
    fun theConfigDialogsWordsSitOnTheirOwnControls() {
        val order = listOf(
            "R.string.emoji_config_title", "R.string.emoji_grid_size", "gridSize = option", "R.string.emoji_overlay_timeout", "R.string.emoji_timeout_standard", "timeout = option",
            "R.string.emoji_pages", "R.string.emoji_add_page", "R.string.emoji_save_config", "overlayTimeout = timeout",
        )
        val at = order.map { emoji.indexOf(it) }
        assertTrue("every part of the config dialog is there: $at", at.all { it >= 0 })
        assertEquals("in this order", at.sorted(), at)
        assertTrue(emoji.contains("EmojiOverlayTimeout.STANDARD -> R.string.emoji_timeout_standard"))
        assertTrue(emoji.contains("EmojiOverlayTimeout.EXTENDED -> R.string.emoji_timeout_extended"))
        assertTrue(emoji.contains("EmojiOverlayTimeout.NO_AUTO_CLEAR -> R.string.emoji_timeout_none"))
        assertTrue("the grid sizes are still numbers", emoji.contains("""text = "${'$'}{option.columns} X ${'$'}{option.rows}","""))
    }

    @Test
    fun theEmojiEnglishIsHeldExactly() {
        val expected = mapOf(
            "emoji_hint_tap" to "TAP: DISPLAY", "emoji_hint_hold" to "HOLD: CONFIGURE", "emoji_config_button" to "CONFIG", "emoji_txt" to "TXT", "emoji_hold_to_set" to "HOLD\nTO SET",
            "emoji_custom" to "CUSTOM EMOJI", "emoji_hide_library" to "HIDE EMOJI LIBRARY", "emoji_pick_library" to "PICK FROM LIBRARY", "emoji_label_optional" to "LABEL // OPTIONAL",
            "emoji_overlay_text_optional" to "OVERLAY TEXT // OPTIONAL", "emoji_open_related" to "OPEN RELATED EMOJI PANEL", "emoji_configure_related" to "CONFIGURE RELATED PANEL",
            "emoji_related_note" to "THIS SLOT OPENS A SINGLE-PAGE EMOJI PANEL.", "emoji_panel_default" to "PANEL", "emoji_related_hold" to "HOLD A TILE TO CONFIGURE IT.",
            "emoji_related_tap" to "TAP AN EMOJI TO DISPLAY IT.", "emoji_cat_responses" to "RESPONSES", "emoji_cat_boundaries" to "BOUNDARIES", "emoji_cat_needs" to "NEEDS",
            "emoji_cat_feelings" to "FEELINGS", "emoji_cat_regulation" to "REGULATION", "emoji_cat_people_places" to "PEOPLE / PLACES", "emoji_grid_size" to "GRID SIZE",
            "emoji_overlay_timeout" to "OVERLAY TIMEOUT", "emoji_timeout_standard" to "STANDARD", "emoji_timeout_extended" to "EXTENDED", "emoji_timeout_none" to "NO AUTO CLEAR",
            "emoji_add_page" to "+ ADD PAGE", "emoji_save_config" to "SAVE CONFIG",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
        assertEquals("EMOJI // EXPRESS", EnglishText.get("emoji_title", english.getValue("label_deck_type_emoji")))
        assertEquals("EMOJI DECK CONFIG", EnglishText.get("emoji_config_title", english.getValue("label_deck_type_emoji"), english.getValue("label_deck")))
        assertEquals("CONFIGURE EMOJI 3", EnglishText.get("emoji_configure_title", 3))
        assertEquals("RELATED EMOJI 3", EnglishText.get("emoji_related_edit_title", 3))
        assertEquals("PAGES // 2", EnglishText.get("emoji_pages", 2))
        assertEquals("PAGE 2", EnglishText.get("emoji_page_default", 2))
        assertEquals("RELATED // FOOD", EnglishText.get("emoji_related_title", "FOOD"))
        assertEquals("CLEAR", english.getValue("common_clear"))
        assertEquals("DONE", english.getValue("common_done"))
    }

    @Test
    fun theEmojiArgumentsAreWhereTheCodePutsThem() {
        val numbered = listOf("emoji_page_default", "emoji_configure_title", "emoji_related_edit_title", "emoji_pages")
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in numbered) assertTrue("$tag/$name takes a number", map.getValue(name).contains("%1\$d"))
            assertTrue("$tag: the title takes the EMOJI label", map.getValue("emoji_title").contains("%1\$s"))
            assertTrue("$tag: the related title takes the name", map.getValue("emoji_related_title").contains("%1\$s"))
            val config = map.getValue("emoji_config_title")
            assertTrue("$tag: the config title takes the EMOJI label then the DECK label (in either order on screen)", config.contains("%1\$s") && config.contains("%2\$s"))
            for (name in emojiNames - numbered.toSet() - setOf("emoji_title", "emoji_related_title", "emoji_config_title")) {
                assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
            }
        }
    }

    @Test
    fun theTileHintKeepsItsLineBreak_inEveryLanguage() {
        // The tile is narrow, so its words are on two lines: the resource holds a line-break escape in every language (read back here as a real break), and the screen draws it as one.
        for ((tag, map) in listOf("en" to english) + translations.toList()) assertTrue("$tag: ${map.getValue("emoji_hold_to_set")}", map.getValue("emoji_hold_to_set").contains("\n"))
    }

    @Test
    fun theEmojiWordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "emoji_hide_library" to "emoji_pick_library", "emoji_label_optional" to "emoji_overlay_text_optional", "emoji_open_related" to "emoji_configure_related",
            "emoji_related_hold" to "emoji_related_tap", "emoji_configure_title" to "emoji_related_edit_title", "emoji_timeout_standard" to "emoji_timeout_extended",
            "emoji_timeout_extended" to "emoji_timeout_none", "emoji_timeout_standard" to "emoji_timeout_none", "emoji_grid_size" to "emoji_overlay_timeout", "emoji_add_page" to "emoji_save_config",
            "emoji_hint_tap" to "emoji_hint_hold", "emoji_cat_responses" to "emoji_cat_boundaries", "emoji_cat_needs" to "emoji_cat_feelings", "emoji_cat_feelings" to "emoji_cat_regulation",
            "emoji_cat_regulation" to "emoji_cat_people_places", "emoji_cat_boundaries" to "emoji_cat_needs", "emoji_related_note" to "emoji_related_hold",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val cats = listOf("responses", "boundaries", "needs", "feelings", "regulation", "people_places").map { map.getValue("emoji_cat_$it") }
            assertEquals("$tag: six different headings", 6, cats.toSet().size)
        }
    }

    @Test
    fun theConfigTitleNamesEmojiAndDeckInTheLanguage_withTheLabelsItWasGiven() {
        for ((tag, map) in translations) {
            val said = FileText(tag).get("emoji_config_title", map.getValue("label_deck_type_emoji"), map.getValue("label_deck"))
            assertTrue("$tag: EMOJI in '$said'", said.contains(map.getValue("label_deck_type_emoji")))
            assertTrue("$tag: DECK in '$said'", said.contains(map.getValue("label_deck")))
            assertFalse("$tag: a placeholder leaked: $said", said.contains("%"))
            val title = FileText(tag).get("emoji_title", map.getValue("label_deck_type_emoji"))
            assertTrue("$tag: the title names EMOJI: $title", title.contains(map.getValue("label_deck_type_emoji")))
        }
    }

    // ---- part 4: the GIF deck ---------------------------------------------------------------------------------------------------------------

    @Test
    fun theOldGifLiteralsAreGone() {
        for (literal in listOf(
            "\"GIF DECK EXPORTED\"", "\"EXPORT FAILED\"", "\"IMPORTED \${", "\"IMPORT FAILED -- INTEGRITY CHECK\"", "\"GIF // LOCAL LIBRARY\"", "\"BACKUP ▲\"", "\"BACKUP ▼\"", "\"EXPORT DECK (.ZIP)\"",
            "\"IMPORT DECK (.ZIP)\"", "\"+ IMPORT\"", "append(\"CATEGORY: \")", "\"NO GIFS\"", "\"NO GIFS IN THIS CATEGORY\"", "\"IMPORT A LOCAL GIF TO BEGIN\"", "\"OVERLAY: LANDSCAPE [ON]\"",
            "\"OVERLAY: LANDSCAPE [OFF]\"", "\"◀ PREV\"", "\"NEXT ▶\"", "\"DISPLAY FULL SCREEN\"", "text = \"SHARE\"", "\"IMPORT GIF\"", "text = \"TITLE\"", "text = \"CATEGORY\"", "\"REACTIONS\"",
            "text = \"IMPORT\"", "text = \"CANCEL\"", "\"GIF IMPORT FAILED\"", "\"SHARE GIF\"", "text = category.name",
        )) assertFalse("GifDeck.kt still holds $literal", gif.contains(literal))
        assertTrue(gif.contains("import com.example.besu.R\n"))
        assertTrue(gif.contains("import androidx.compose.ui.res.stringResource"))
        // The repository no longer throws the four sentences itself: it throws the reason, and the screen says it.
        val importGif = gifRepo.substring(gifRepo.indexOf("fun importGif("), gifRepo.indexOf("fun upsertCategory("))
        assertFalse("importGif still throws a sentence", importGif.contains("error(\""))
        for (reason in listOf("NOT_A_GIF", "TOO_BIG", "UNREADABLE", "INVALID")) assertEquals("importGif throws $reason once", 1, Regex("""throw GifImportException\(GifImportFailure\.$reason\)""").findAll(importGif).count())
    }

    @Test
    fun theSavedGifNamesWereNotTranslated() {
        // A category left blank is SAVED as UNCATEGORIZED (one constant, shared with the screen's decision), and a GIF with no usable title is SAVED as UNTITLED GIF; both stay English whatever the language.
        assertTrue(gifRepo.contains(".ifBlank { GifLabels.STORED_DEFAULT_CATEGORY }"))
        assertFalse(gifRepo.contains(".ifBlank { \"UNCATEGORIZED\" }"))
        assertTrue(gifRepo.contains(".ifBlank { \"UNTITLED GIF\" }"))
        // The title the dialog starts with is what gets saved if the person imports without changing it, so it is the English text too.
        assertTrue(gif.contains("return \"UNTITLED GIF\""))
        // The category list shows the shown name but selects, and saves, by id; the dialog saves what was typed.
        assertTrue(Regex("""shownCategoryName\(words, category\.name\)[\s\S]{0,600}?selectedCategoryId = category\.id""").containsMatchIn(gif))
        assertTrue(gif.contains("name = categoryName"))
        // The zip's folder name for an uncategorised GIF is a path in a file meant for browsing without ACK, and is a stored name: it stays English.
        assertTrue(file("decks/GifBackupManager.kt").contains("categoryName ?: \"UNCATEGORIZED\", \"UNCATEGORIZED\""))
    }

    @Test
    fun theTitleAndTheExportToastTakeTheDeckTypeAndDeckLabels_soTheyFollowPlainWords() {
        assertTrue(gif.contains("val gifTypeLabel = labelFor(LabelKey.DECK_TYPE_GIF)"))
        assertTrue(gif.contains("val deckLabel = labelFor(LabelKey.DECK)"))
        assertTrue(gif.contains("text = stringResource(R.string.gif_title, gifTypeLabel),"))
        assertTrue(gif.contains("GifLabels.exportToast(words, success, gifTypeLabel, deckLabel)"))
        assertTrue(gif.contains("text = stringResource(R.string.gif_export_deck, deckLabel),"))
        assertTrue(gif.contains("text = stringResource(R.string.gif_import_deck, deckLabel),"))
    }

    @Test
    fun eachGifWordSitsOnTheControlThatDoesWhatItSays() {
        assertTrue("BACKUP opens the menu, the arrow follows the state", Regex("""stringResource\(R\.string\.gif_backup\) \+ if \(showBackupMenu\) " ▲" else " ▼",[\s\S]{0,300}?GIF_BACKUP_BTN[\s\S]{0,300}?showBackupMenu = !showBackupMenu""").containsMatchIn(gif))
        assertTrue("EXPORT writes a file", Regex("""gif_export_deck, deckLabel\),[\s\S]{0,700}?GIF_BACKUP_EXPORT_BTN[\s\S]{0,1200}?exportBackupLauncher\.launch""").containsMatchIn(gif))
        assertTrue("IMPORT reads a file", Regex("""gif_import_deck, deckLabel\),[\s\S]{0,700}?GIF_BACKUP_IMPORT_BTN[\s\S]{0,1200}?importBackupLauncher\.launch""").containsMatchIn(gif))
        assertTrue("+ IMPORT picks one GIF", Regex("""R\.string\.gif_import_button\),[\s\S]{0,300}?GIF_IMPORT\)[\s\S]{0,400}?importLauncher\.launch\(arrayOf\("image/gif"\)\)""").containsMatchIn(gif))
        assertTrue("the category button opens the category list, the arrow follows the state", Regex("""GifLabels\.categoryLine\(words, activeCategory\?\.name\) \+ if \(showCategoryMenu\) " ▲" else " ▼",[\s\S]{0,400}?GIF_CATEGORY[\s\S]{0,300}?showCategoryMenu = !showCategoryMenu""").containsMatchIn(gif))
        assertTrue("the empty state says there is nothing, then how to begin", Regex("""if \(selectedGif == null\) \{[\s\S]{0,400}?gif_empty_title[\s\S]{0,500}?gif_empty_hint""").containsMatchIn(gif))
        assertTrue("the overlay button flips and saves the setting", Regex("""GifLabels\.landscapeButton\(words, forceLandscapeOverlay\),[\s\S]{0,600}?GIF_LANDSCAPE_TOGGLE[\s\S]{0,400}?forceLandscapeOverlay = !forceLandscapeOverlay""").containsMatchIn(gif))
        assertTrue("PREV goes back", Regex("""R\.string\.gif_prev\),[\s\S]{0,200}?enabled = gifs\.size > 1[\s\S]{0,300}?pagerState\.currentPage - 1""").containsMatchIn(gif))
        assertTrue("NEXT goes forward", Regex("""R\.string\.gif_next\),[\s\S]{0,200}?enabled = gifs\.size > 1[\s\S]{0,300}?pagerState\.currentPage \+ 1""").containsMatchIn(gif))
        assertTrue("DISPLAY FULL SCREEN shows the overlay", Regex("""R\.string\.gif_display_full\),[\s\S]{0,300}?showGifOverlay\(""").containsMatchIn(gif))
        assertTrue("SHARE shares", Regex("""R\.string\.gif_share\),[\s\S]{0,400}?GIF_SHARE_BTN[\s\S]{0,300}?shareGif\(""").containsMatchIn(gif))
        assertTrue("the chooser's title is read from resources outside a composable", gif.contains("Intent.createChooser(shareIntent, context.getString(R.string.gif_share_chooser))"))
    }

    @Test
    fun theImportDialogsWordsSitOnTheirOwnFieldsAndButtons() {
        assertTrue("the title field", Regex("""value = title,[\s\S]{0,300}?R\.string\.gif_field_title""").containsMatchIn(gif))
        assertTrue("the category field with its example", Regex("""value = categoryName,[\s\S]{0,400}?R\.string\.gif_field_category[\s\S]{0,400}?R\.string\.gif_category_example""").containsMatchIn(gif))
        assertTrue("IMPORT imports", Regex("""R\.string\.gif_import_confirm\),[\s\S]{0,300}?GIF_IMPORT_COMMIT[\s\S]{0,700}?GifRepository\.importGif\(""").containsMatchIn(gif))
        assertTrue("the failure is shown in the language", Regex("""\.onFailure \{ error ->\s*errorMessage = GifLabels\.importError\(words, error\)""").containsMatchIn(gif))
        assertTrue("CANCEL closes", Regex("""R\.string\.common_cancel\),[\s\S]{0,200}?onDismiss\(\)""").containsMatchIn(gif))
        assertTrue("the dialog's title is the first word on it", Regex("""title = \{[\s\S]{0,200}?R\.string\.gif_import_title""").containsMatchIn(gif))
    }

    @Test
    fun theBackupToastsAreWrittenOutsideAComposable_andTheRestartPatternIsKept() {
        assertTrue(Regex("""GifBackupManager\.exportDeck\(context, deckId, uri\)[\s\S]{0,200}?GifLabels\.exportToast\(words, success, gifTypeLabel, deckLabel\)[\s\S]{0,100}?Toast\.LENGTH_SHORT""").containsMatchIn(gif))
        // The imported toast stays on screen long enough to read, then the delayed restart runs, exactly as before.
        assertTrue(Regex("""GifLabels\.importedToast\(words, result\.importedCount, result\.skippedCount\),[\s\S]{0,100}?Toast\.LENGTH_LONG[\s\S]{0,100}?\)\.show\(\)\s*pendingBackupRestart = true""").containsMatchIn(gif))
        assertTrue(Regex("""if \(pendingBackupRestart\) \{\s*delay\(1500\)\s*restartApp\(context\)""").containsMatchIn(gif))
        assertTrue(gif.contains("context.getString(R.string.gif_import_failed_check)"))
    }

    @Test
    fun theGifEnglishIsHeldExactly() {
        val expected = mapOf(
            "gif_backup" to "BACKUP", "gif_import_button" to "+ IMPORT", "gif_no_gifs" to "NO GIFS", "gif_empty_title" to "NO GIFS IN THIS CATEGORY", "gif_empty_hint" to "IMPORT A LOCAL GIF TO BEGIN",
            "gif_prev" to "◀ PREV", "gif_next" to "NEXT ▶", "gif_display_full" to "DISPLAY FULL SCREEN", "gif_share" to "SHARE", "gif_share_chooser" to "SHARE GIF", "gif_import_title" to "IMPORT GIF",
            "gif_field_title" to "TITLE", "gif_field_category" to "CATEGORY", "gif_category_example" to "REACTIONS", "gif_import_confirm" to "IMPORT", "gif_export_failed" to "EXPORT FAILED",
            "gif_import_failed_check" to "IMPORT FAILED -- INTEGRITY CHECK", "gif_import_failed" to "GIF IMPORT FAILED", "gif_category_default" to "UNCATEGORIZED",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
        assertEquals("GIF // LOCAL LIBRARY", EnglishText.get("gif_title", english.getValue("label_deck_type_gif")))
        assertEquals("EXPORT DECK (.ZIP)", EnglishText.get("gif_export_deck", english.getValue("label_deck")))
        assertEquals("IMPORT DECK (.ZIP)", EnglishText.get("gif_import_deck", english.getValue("label_deck")))
        assertEquals("CATEGORY: X", EnglishText.get("gif_category_line", "X"))
        assertEquals("OVERLAY: LANDSCAPE [ON]", EnglishText.get("gif_overlay_landscape", "ON"))
        assertEquals("GIF DECK EXPORTED", EnglishText.get("gif_exported", english.getValue("label_deck_type_gif"), english.getValue("label_deck")))
    }

    @Test
    fun theGifArgumentsAreWhereTheCodePutsThem() {
        val oneArgument = setOf("gif_title", "gif_export_deck", "gif_import_deck", "gif_category_line", "gif_overlay_landscape")
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in oneArgument) {
                assertTrue("$tag/$name takes its argument", map.getValue(name).contains("%1\$s"))
                assertFalse("$tag/$name takes only one", map.getValue(name).contains("%2"))
            }
            val exported = map.getValue("gif_exported")
            assertTrue("$tag: the export toast takes the GIF label then the DECK label (in either order on screen)", exported.contains("%1\$s") && exported.contains("%2\$s"))
            for (name in gifNames - oneArgument - "gif_exported") assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
        }
    }

    @Test
    fun theTwoImportedPluralsExistInEveryLanguage_andEachFormHoldsItsNumbers() {
        val files = listOf("en" to StringsXml.default) + StringsXml.translations().toList()
        for ((tag, file) in files) {
            val plurals = StringsXml.plurals(file)
            for (name in gifPluralNames) assertTrue("$tag: $name is defined", plurals.containsKey(name))
            val toast = plurals.getValue("gif_imported_toast")
            val skipped = plurals.getValue("gif_imported_skipped_toast")
            assertTrue("$tag: an 'other' form each", "other" in toast && "other" in skipped)
            assertEquals("$tag: both plurals have the same forms", toast.keys, skipped.keys)
            for ((q, text) in skipped) assertTrue("$tag/$q: the skipped count is in '$text'", text.contains("%2\$d"))
            // Every form for a quantity that is not spelled out in words holds the imported count (Arabic spells out one and two).
            for ((q, text) in toast) if (!(tag == "ar" && (q == "one" || q == "two"))) assertTrue("$tag/$q: the imported count is in '$text'", text.contains("%d"))
            for ((q, text) in skipped) if (!(tag == "ar" && (q == "one" || q == "two"))) assertTrue("$tag/$q: the imported count is in '$text'", text.contains("%1\$d"))
            for ((q, text) in toast + skipped) assertTrue("$tag/$q says ACK restarts", text.contains("--"))
        }
    }

    @Test
    fun theGifWordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "gif_export_deck" to "gif_import_deck", "gif_prev" to "gif_next", "gif_empty_title" to "gif_empty_hint", "gif_field_title" to "gif_field_category", "gif_share" to "gif_share_chooser",
            "gif_export_failed" to "gif_import_failed_check", "gif_import_failed" to "gif_import_failed_check", "gif_import_button" to "gif_import_confirm", "gif_import_title" to "gif_import_confirm",
            "gif_err_not_gif" to "gif_err_invalid", "gif_err_too_big" to "gif_err_unreadable", "gif_err_not_gif" to "gif_err_too_big", "gif_err_invalid" to "gif_err_unreadable",
            "gif_err_not_gif" to "gif_err_unreadable", "gif_err_invalid" to "gif_err_too_big", "gif_no_gifs" to "gif_empty_title", "gif_backup" to "gif_share",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
    }

    @Test
    fun theArrowsPointOutwardAtEachEdge_andArabicsAreMirroredWithItsLayout() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val prev = map.getValue("gif_prev")
            val next = map.getValue("gif_next")
            if (tag == "ar") {
                // The Arabic layout is mirrored: PREV is the first control, on the right, so its arrow points right and sits first; NEXT is on the left and points left.
                assertTrue("$tag: $prev", prev.startsWith("▶") && !prev.contains("◀"))
                assertTrue("$tag: $next", next.endsWith("◀") && !next.contains("▶"))
            } else {
                assertTrue("$tag: $prev", prev.startsWith("◀") && !prev.contains("▶"))
                assertTrue("$tag: $next", next.endsWith("▶") && !next.contains("◀"))
            }
        }
    }

    @Test
    fun theWordGifInASentenceNamesTheFileKind_soItIsLatinInTheLatinLanguagesAndTheLabelsOwnWordInHindiAndArabic() {
        val sentences = listOf("gif_empty_title", "gif_empty_hint", "gif_share_chooser", "gif_import_title", "gif_import_failed", "gif_err_not_gif", "gif_err_too_big", "gif_err_invalid")
        for ((tag, map) in translations) {
            val word = if (tag == "hi" || tag == "ar") map.getValue("label_deck_type_gif") else "GIF"
            // gif_empty_title in Spanish says "NO HAY GIF", in Portuguese and Afrikaans "GIFS": the word is inside it either way.
            for (name in sentences) assertTrue("$tag/$name names the file kind ($word)", map.getValue(name).contains(word) || map.getValue(name).contains(word + "S"))
        }
    }

    @Test
    fun theSizeLimitStaysAsASymbolInEveryLanguage_andTheFourSentencesAreMixedCaseWhereEnglishIs() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) assertTrue("$tag: 20 MB", map.getValue("gif_err_too_big").contains("20 MB"))
        for (name in listOf("gif_err_not_gif", "gif_err_too_big", "gif_err_unreadable", "gif_err_invalid")) assertNotEquals("the English $name is a sentence, not capitals", english.getValue(name).uppercase(), english.getValue(name))
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
