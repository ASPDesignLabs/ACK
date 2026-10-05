// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * HELP's own screens (the header's HELP button, the menu, the two chooser dialogs and the coach panel) read their words from string resources, in the chosen language. They cannot be
 * compiled here, so this reads them: the old English literals are gone, every string they name exists and none is unused, each word sits on the control that does what it says, and
 * every language has the words. HelpMenuTextTest holds the decisions (the family names, the cards' step line). The walkthroughs' own text is still English and is not tested here.
 */
class HelpWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val menu get() = file("help/HelpMenuDialog.kt")
    private val coach get() = file("help/HelpCoachDialog.kt")
    private val pose get() = file("help/PoseSelectorDialog.kt")
    private val voice get() = file("help/VoiceRecordingsHelpSelectorDialog.kt")
    private val banner get() = file("help/HelpOfferBanner.kt")
    private val main get() = file("MainActivity.kt")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val helpNames get() = english.keys.filter { it.startsWith("help_") } + StringsXml.plurals(StringsXml.default).keys.filter { it.startsWith("help_") }

    @Test
    fun everyStringTheScreensNameExists_andNoneIsLeftUnused() {
        val screens = listOf(menu, coach, pose, voice, banner, main, file("settings/ManageRecordingsDialog.kt"), file("output/VoiceRecordingPanel.kt"), file("voicecapture/TrainingCaptureHome.kt"))
        val referenced = screens.flatMap { Regex("""R\.string\.(help_[a-z_]+)""").findAll(it).map { m -> m.groupValues[1] }.toList() }.toSet()
        val missing = referenced.filter { it !in helpNames }
        assertEquals("named but not defined: $missing", emptyList<String>(), missing)
        // The family names, the view names and the step line are named by the decisions in core/HelpMenuText.kt, not by R.string.
        val named = Regex(""""(help_[a-z_]+)"""").findAll(file("core/HelpMenuText.kt")).map { it.groupValues[1] }.toSet()
        val byFamily = Regex("""^help_cat_[a-z_]+_(title|chip|subtitle)$""")
        val unused = helpNames.toSet() - referenced - named - helpNames.filter { byFamily.matches(it) }.toSet() - HelpMenuText.viewNameResources.values.toSet()
        assertTrue("defined but never used: $unused", unused.isEmpty())
    }

    @Test
    fun theOldEnglishLiteralsAreGone() {
        val gone = mapOf(
            "help/HelpMenuDialog.kt" to listOf("\"ACK // HELP SYSTEM\"", "\"TRAINING MODULES AND REFERENCE PROTOCOLS\"", "\"[CLOSE]\"", "\"SELECT MODULE FAMILY\"", "\"[RUN]\"", "\"NO MODULES DEPLOYED\"",
                "\"THIS KNOWLEDGE FAMILY HAS NO ACTIVE HELP PROTOCOLS.\"", "STEPS // ", "CURRENT VIEW", "substringAfter(\"// \")", "selectedCategory.title", "selectedCategory.subtitle", "category.title"),
            "help/HelpCoachDialog.kt" to listOf("\"GUIDANCE // ", "\"[ABORT]\"", "\"ACKNOWLEDGE // CONTINUE\"", "\"AWAITING LIVE INPUT\"", "PROCEED.", "\"READ AND CONTINUE.\"", "WAITING FOR WATCH EVENT"),
            "help/PoseSelectorDialog.kt" to listOf("\"SELECT A POSE\"", "\"[CLOSE]\"", "WHICHEVER POSE YOU PICK"),
            "help/VoiceRecordingsHelpSelectorDialog.kt" to listOf("\"VOICE RECORDINGS\"", "\"[CLOSE]\"", "PICK A TOPIC TO WALK THROUGH"),
            "MainActivity.kt" to listOf("text = \"HELP\""),
            "voicecapture/TrainingCaptureHome.kt" to listOf("HAS A HELP WALKTHROUGH", "UNDER HELP ANYTIME"),
        )
        for ((path, literals) in gone) for (literal in literals) assertFalse("$path still holds $literal", file(path).contains(literal))
        for (path in listOf("help/HelpMenuDialog.kt", "help/HelpCoachDialog.kt", "help/PoseSelectorDialog.kt", "help/VoiceRecordingsHelpSelectorDialog.kt")) {
            assertTrue("$path needs the R import", RepoFiles.read("$base/$path").contains("import com.example.besu.R\n"))
        }
        // HelpCategory no longer carries English of its own: its words are resources, found by the constant's name.
        val core = RepoFiles.read("$base/help/HelpCore.kt")
        val enumBody = core.substringAfter("enum class HelpCategory {").substringBefore("}")
        assertFalse("a family still holds a title or a subtitle", enumBody.contains("title") || enumBody.contains("subtitle") || enumBody.contains("\""))
        assertTrue(core.contains("enum class HelpCategory {"))
    }

    @Test
    fun theTextSourceIsMadeOnceInEachComposableThatNeedsIt_andNoLambdaHidesIt() {
        assertEquals("the menu, a chip and a card each make it once", 3, Regex("""val text = rememberText\(\)""").findAll(menu).count())
        assertFalse("a lambda parameter named text would hide the text source", Regex("""\{ text ->""").containsMatchIn(menu))
    }

    @Test
    fun eachWordSitsOnTheControlThatDoesWhatItSays() {
        fun wordThenAction(source: String, word: String, action: String, within: Int) =
            Regex("""R\.string\.${Regex.escape(word)}\)?[\s\S]{0,$within}?${Regex.escape(action)}""").containsMatchIn(source)
        // The coach panel: ABORT ends the walkthrough, and ACKNOWLEDGE moves on from a reading step.
        assertTrue("[ABORT] aborts", wordThenAction(coach, "help_coach_abort", "manager.abort()", 400))
        assertTrue("ACKNOWLEDGE advances a reading step", wordThenAction(coach, "help_coach_acknowledge", "manager.advanceReadStep()", 200))
        assertTrue("the acknowledge button is only for a step that waits for nothing", coach.contains("if (step.action == HelpAction.Read) {"))
        // Each kind of wait says its own instruction, and no two kinds share one.
        val instructions = mapOf(
            "HelpAction.Interact" to "help_coach_use_control", "HelpAction.CommitText" to "help_coach_commit_text", "HelpAction.CommitFile" to "help_coach_commit_file",
            "HelpAction.OverlayCleared" to "help_coach_clear_overlay", "HelpAction.DeckSelected" to "help_coach_select_deck", "HelpAction.ProfileSelected" to "help_coach_select_profile",
            "HelpAction.KeyboardDismissed" to "help_coach_close_keyboard",
        )
        for ((action, resource) in instructions) assertTrue("$action says $resource", coach.contains("is $action -> stringResource(R.string.$resource)"))
        assertTrue("a watch event names the event", coach.contains("is HelpAction.WatchEvent -> stringResource(R.string.help_coach_watch_event, action.eventType)"))
        assertTrue("a reading step says read and continue", coach.contains("HelpAction.Read -> stringResource(R.string.help_coach_read)"))
        assertTrue("the position is passed as an argument", coach.contains("stringResource(R.string.help_coach_guidance, stepPosition(manager, module))"))
        assertTrue("an instruction still goes through helpText (it can hold a label placeholder)", coach.contains("text = helpText(helpActionInstruction(step.action))"))
        // The menu: CLOSE closes it, and the chooser dialogs' CLOSE closes them.
        assertTrue("the menu's close", Regex("""rightLabel = stringResource\(R\.string\.help_close\),\s*onRightClick = onDismiss""").containsMatchIn(menu))
        assertTrue("the pose chooser's close", wordThenAction(pose, "help_close", ".clickable(onClick = onDismiss)", 400))
        assertTrue("the voice chooser's close", wordThenAction(voice, "help_close", ".clickable(onClick = onDismiss)", 400))
        assertTrue("the pose chooser's title and hint", pose.contains("text = stringResource(R.string.help_pose_title),") && pose.contains("text = stringResource(R.string.help_pose_hint),"))
        assertTrue("the voice chooser's title and hint", voice.contains("text = stringResource(R.string.help_voice_selector_title),") && voice.contains("text = stringResource(R.string.help_voice_selector_hint),"))
        // The menu's header says its title, then its subtitle; the empty state says its heading, then its sentence; each chooser's title is the large line and its hint the small one.
        assertTrue("the menu's title, then its subtitle", Regex("""title = stringResource\(R\.string\.help_menu_title\),\s*subtitle = stringResource\(R\.string\.help_menu_subtitle\),""").containsMatchIn(menu))
        val empty = menu.substring(menu.indexOf("private fun HelpEmptyState("))
        assertTrue("the empty state's heading comes before its sentence", empty.indexOf("R.string.help_menu_empty_title") in 0 until empty.indexOf("R.string.help_menu_empty_body"))
        assertTrue("the empty state's heading is the bold line", Regex("""help_menu_empty_title\),[\s\S]{0,200}?fontWeight = FontWeight\.Bold""").containsMatchIn(empty))
        for ((source, title, hint) in listOf(Triple(pose, "help_pose_title", "help_pose_hint"), Triple(voice, "help_voice_selector_title", "help_voice_selector_hint"))) {
            assertTrue("$title is the 13 sp title", Regex("""R\.string\.$title\),[\s\S]{0,120}?fontSize = 13\.sp""").containsMatchIn(source))
            assertTrue("$hint is the 9 sp hint", Regex("""R\.string\.$hint\),[\s\S]{0,120}?fontSize = 9\.sp""").containsMatchIn(source))
        }
        // A card names the screen by its view mode (the logic string the mapping is keyed by), not by the enum constant.
        assertTrue("the card passes the view mode", menu.contains("module.destination?.viewMode)"))
        // The header's button is the one that opens the menu.
        assertTrue("the HELP button opens the menu", Regex("""showHelpMenu = true[\s\S]{0,300}?text = stringResource\(R\.string\.help_button\),""").containsMatchIn(main))
    }

    @Test
    fun theSentencesThatPointAtTheHelpButtonTakeItsNameFromTheSameString() {
        assertEquals(1, Regex("""stringResource\(R\.string\.voice_rec_help_offer, stringResource\(R\.string\.help_button\)\)""").findAll(file("settings/ManageRecordingsDialog.kt")).count())
        assertEquals(1, Regex("""stringResource\(R\.string\.voice_rec_help_offer, stringResource\(R\.string\.help_button\)\)""").findAll(file("output/VoiceRecordingPanel.kt")).count())
        val capture = file("voicecapture/TrainingCaptureHome.kt")
        assertTrue(capture.contains("val helpButton = stringResource(R.string.help_button)"))
        assertTrue(capture.contains("HAS A \$helpButton WALKTHROUGH. FIND IT UNDER \$helpButton ANYTIME."))
        // The language notice says what is still English now: the walkthroughs, no longer HELP as a whole.
        assertTrue(english.getValue("interface_language_explanation").contains("THE WALKTHROUGHS INSIDE HELP, THE TERMINAL AND MANY DIALOGS ARE STILL IN ENGLISH."))
        assertFalse("the old claim that all of HELP is English", english.getValue("interface_language_explanation").contains(". HELP, THE TERMINAL"))
    }

    // ---- English is exactly what the screens always said --------------------------------------------------------------------------------

    @Test
    fun theEnglishIsHeldExactly() {
        val expected = mapOf(
            "help_button" to "HELP", "help_close" to "[CLOSE]",
            "help_menu_title" to "ACK // HELP SYSTEM", "help_menu_subtitle" to "TRAINING MODULES AND REFERENCE PROTOCOLS", "help_menu_select_family" to "SELECT MODULE FAMILY",
            "help_menu_run" to "[RUN]", "help_menu_current_view" to "CURRENT VIEW",
            "help_menu_empty_title" to "NO MODULES DEPLOYED", "help_menu_empty_body" to "THIS KNOWLEDGE FAMILY HAS NO ACTIVE HELP PROTOCOLS.",
            "help_coach_abort" to "[ABORT]", "help_coach_acknowledge" to "ACKNOWLEDGE // CONTINUE", "help_coach_awaiting" to "AWAITING LIVE INPUT",
            "help_coach_use_control" to "USE THE HIGHLIGHTED CONTROL TO PROCEED.", "help_coach_commit_text" to "COMMIT TEXT INPUT TO PROCEED.",
            "help_coach_commit_file" to "COMMIT A FILE TO PROCEED.", "help_coach_clear_overlay" to "CLEAR THE ACTIVE OVERLAY TO PROCEED.",
            "help_coach_select_deck" to "SELECT A MATRIX {{DECK}} TO PROCEED.", "help_coach_select_profile" to "SELECT A PROFILE TO PROCEED.",
            "help_coach_close_keyboard" to "TYPE IF NEEDED, THEN CLOSE THE KEYBOARD TO PROCEED.", "help_coach_read" to "READ AND CONTINUE.",
            "help_pose_title" to "SELECT A POSE", "help_pose_hint" to "THE WALKTHROUGH WILL FOCUS ON WHICHEVER POSE YOU PICK.",
            "help_voice_selector_title" to "VOICE RECORDINGS", "help_voice_selector_hint" to "PICK A TOPIC TO WALK THROUGH.",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
        assertEquals("GUIDANCE // 2/7", EnglishText.get("help_coach_guidance", "2/7"))
        assertEquals("WAITING FOR WATCH EVENT: TWIST_UP", EnglishText.get("help_coach_watch_event", "TWIST_UP"))
        assertEquals("[GOT IT]", english.getValue("help_got_it"))
        // The step-position text is built as it always was: the step number from 1, a slash, the number of steps.
        assertTrue(coach.contains("""return "${'$'}{manager.currentStepIndex + 1}/${'$'}{module.steps.size}""""))
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------------------

    @Test
    fun theThreeTapTargetsKeepTheirBracketsInEveryLanguage() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) for (name in listOf("help_close", "help_menu_run", "help_coach_abort", "help_got_it")) {
            val text = map.getValue(name)
            assertTrue("$tag/$name keeps its brackets: $text", text.startsWith("[") && text.endsWith("]"))
        }
    }

    @Test
    fun wordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "help_coach_abort" to "help_coach_acknowledge", "help_close" to "help_menu_run", "help_coach_abort" to "help_close", "help_menu_title" to "help_coach_guidance",
            "help_pose_title" to "help_voice_selector_title", "help_pose_hint" to "help_voice_selector_hint", "help_menu_empty_title" to "help_menu_empty_body",
            "help_coach_acknowledge" to "help_coach_awaiting", "help_button" to "help_menu_title",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
            // Each kind of wait says something different, so a person can tell from the words what the walkthrough is waiting for.
            val waits = listOf("use_control", "commit_text", "commit_file", "clear_overlay", "watch_event", "select_deck", "select_profile", "close_keyboard", "read").map { map.getValue("help_coach_$it") }
            assertEquals("$tag: two waits read the same", waits.size, waits.toSet().size)
        }
    }

    @Test
    fun theArgumentsAreWhereTheCodePutsThem() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertTrue("$tag: guidance takes the position", map.getValue("help_coach_guidance").contains("%1\$s"))
            assertTrue("$tag: watch event takes the event", map.getValue("help_coach_watch_event").contains("%1\$s"))
            val line = map.getValue("help_menu_steps_line")
            assertTrue("$tag: the steps line takes the count, then the view", line.contains("%1\$s") && line.contains("%2\$s"))
            // Everything else takes none: an argument the code never passes would show as a raw "%1$s".
            for (name in map.keys.filter { it.startsWith("help_") } - setOf("help_coach_guidance", "help_coach_watch_event", "help_menu_steps_line")) {
                assertFalse("$tag/$name takes an argument nothing passes", map.getValue(name).contains("%1\$s"))
            }
        }
    }

    @Test
    fun theDeckSelectionInstructionNamesTheMatrixDeckInTheLanguage_andKeepsTheDeckPlaceholder() {
        for ((tag, map) in translations) {
            val text = map.getValue("help_coach_select_deck")
            assertTrue("$tag: the deck placeholder", text.contains("{{DECK}}"))
            assertTrue("$tag: the word for a MATRIX deck, as the create-deck dialog says it ($text)", text.contains(map.getValue("label_deck_type_matrix")))
        }
    }

    @Test
    fun theHelpButtonIsShortEnoughToStayInTheHeader() {
        // The button sits in a row with the other header items and is not given a fixed width; a word much longer than the English would push them. A draft word is judged by length only.
        for ((tag, map) in translations) assertTrue("$tag: help_button is ${map.getValue("help_button").length} letters", map.getValue("help_button").length <= 8)
    }
}
