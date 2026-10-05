// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The HELP walkthroughs' own words move to string resources one family (one file in help/) at a time. This reads the families that have moved: each holds only resource names that
 * follow the naming rule, every name exists in English and in every language, English is word for word what the walkthrough always said, a translation uses the bare label placeholder and
 * names the same labels as English, and the three places that draw or speak a step read it through the walkthrough text. A family that has not moved is listed here with its reason, so a
 * new family file cannot be forgotten and a moved one cannot be left on the list. HelpWalkthroughTextTest holds the decisions.
 */
class HelpWalkthroughWordingTest {
    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val everyLanguage get() = listOf("en" to english) + translations.toList()

    /** The families that have moved to resources (a file in help/). */
    private val moved = listOf("GeoProtocolHelp.kt", "LogsHelp.kt", "GifDeckHelp.kt", "EmojiDeckHelp.kt", "EmergencyDeckHelp.kt", "DeckManagementHelp.kt", "BasicsNavigationHelp.kt", "QuickActionsDeckHelp.kt", "SettingsManagementHelp.kt", "TargetComputerHelp.kt", "PersonalizationHelp.kt", "StatementComposerHelp.kt", "RecordTrainingDataHelp.kt", "MatrixDeckHelp.kt")

    /** The families that still hold their own English, each to be moved in its own commit. */
    private val notYetMoved = listOf(
        "FieldOpsHelp.kt",
        "VoiceRecordingsHelp.kt",
        // The registry itself holds one inline module (MANUAL OVERRIDE), so it is a family too.
        "HelpRegistry.kt",
    )

    private class Step(val id: String, val title: String?, val body: String?)
    private class Mod(val id: String, val title: String?, val summary: String?, val steps: List<Step>)

    /** Modules and steps of a family file: each `HelpModule(` / `HelpStep(` with its `id`, and the `title`, `summary` and `body` that follow it before the next one. */
    private fun parse(text: String): List<Mod> {
        val marks = Regex("""Help(Module|Step)\(""").findAll(text).toList()
        val mods = mutableListOf<Mod>()
        var steps = mutableListOf<Step>()
        var current: Triple<String, String?, String?>? = null
        fun flush() { current?.let { mods.add(Mod(it.first, it.second, it.third, steps)) }; steps = mutableListOf() }
        for ((i, m) in marks.withIndex()) {
            val region = text.substring(m.range.last, if (i + 1 < marks.size) marks[i + 1].range.first else text.length)
            val id = Regex("""\bid = "([^"]+)"""").find(region)?.groupValues?.get(1) ?: continue
            val title = Regex("""\btitle = "([^"]*)"""").find(region)?.groupValues?.get(1)
            if (m.groupValues[1] == "Module") {
                flush()
                current = Triple(id, title, Regex("""\bsummary = "([^"]*)"""").find(region)?.groupValues?.get(1))
            } else {
                steps.add(Step(id, title, Regex("""\bbody = "([^"]*)"""").find(region)?.groupValues?.get(1)))
            }
        }
        flush()
        return mods
    }

    private fun namesIn(path: String): List<String> = parse(file(path)).flatMap { m ->
        listOfNotNull(m.title, m.summary) + m.steps.flatMap { listOfNotNull(it.title, it.body) }
    }

    // ---- the files ------------------------------------------------------------------------------------------------------------------------------

    @Test
    fun everyFamilyFileIsEitherMovedOrListedAsNotYetMoved_neverBoth_neverNeither() {
        val onDisk = RepoFiles.file("$base/help").listFiles()!!.map { it.name }.filter { it.endsWith("Help.kt") || it == "HelpRegistry.kt" }.toSet()
        assertEquals("a family file that is on neither list (or listed but gone)", onDisk, (moved + notYetMoved).toSet())
        assertEquals("a file on both lists", emptyList<String>(), moved.filter { it in notYetMoved })
        for (f in notYetMoved) assertFalse("$f holds a resource name but is listed as not yet moved", file("help/$f").contains("\"helpmod_"))
        for (f in moved) assertTrue("$f is listed as moved but holds no resource name", file("help/$f").contains("\"helpmod_"))
    }

    @Test
    fun aFamilyThatMovedHoldsOnlyResourceNames_followingTheNamingRule() {
        for (f in moved) {
            val mods = parse(file("help/$f"))
            assertTrue("$f: no module found", mods.isNotEmpty())
            for (m in mods) {
                assertEquals("$f/${m.id}: module title", HelpWalkthroughText.moduleTitle(m.id), m.title)
                assertEquals("$f/${m.id}: module summary", HelpWalkthroughText.moduleSummary(m.id), m.summary)
                assertTrue("$f/${m.id}: no steps", m.steps.isNotEmpty())
                for (s in m.steps) {
                    assertEquals("$f/${m.id}/${s.id}: step title", HelpWalkthroughText.stepTitle(m.id, s.id), s.title)
                    assertEquals("$f/${m.id}/${s.id}: step body", HelpWalkthroughText.stepBody(m.id, s.id), s.body)
                }
            }
            // Nothing else in the file is a string with words in it that the person would see: the old title/body/summary parameters are the only text a step holds.
            assertFalse("$f: a title, body or summary is still written out", Regex("""\b(title|body|summary) = "(?!helpmod_)""").containsMatchIn(file("help/$f")))
        }
    }

    @Test
    fun noWalkthroughNameIsDefinedTwiceInAnyLanguage() {
        for (path in listOf("values") + StringsXml.translations().keys.map { "values-$it" }) {
            val names = Regex("""<string name="(helpmod_[a-z0-9_]+)"""").findAll(RepoFiles.read("app/src/main/res/$path/strings.xml")).map { it.groupValues[1] }.toList()
            assertEquals("$path: a walkthrough name is defined twice", emptyList<String>(), names.groupingBy { it }.eachCount().filter { it.value > 1 }.keys.toList())
        }
    }

    @Test
    fun everyNameUsedExistsInEnglishAndInEveryLanguage_andNoWalkthroughStringIsLeftUnused() {
        val used = moved.flatMap { namesIn("help/$it") }.toSet()
        val defined = english.keys.filter { it.startsWith(HelpWalkthroughText.PREFIX) }.toSet()
        assertEquals("a name used that English does not define, or defined and never used", used, defined)
        for ((tag, map) in translations) for (name in used) assertTrue("$tag is missing $name", map[name]?.isNotBlank() == true)
        for ((tag, map) in translations) {
            val extra = map.keys.filter { it.startsWith(HelpWalkthroughText.PREFIX) }.toSet() - defined
            assertEquals("$tag defines a walkthrough string English does not", emptySet<String>(), extra)
        }
    }

    // ---- English is exactly what it always said -----------------------------------------------------------------------------------------------

    /** The English of every moved family, as the walkthrough said it before it moved (help_walkthrough_english.tsv: name, a tab, the text with \\n, \\t and \\\\ escaped). */
    private val pins: Map<String, String> get() = RepoFiles.read("app/src/test/resources/help_walkthrough_english.tsv").split("\n").filter { it.isNotEmpty() }.associate { line ->
        val (name, text) = line.split("\t", limit = 2)
        name to Regex("""\\(.)""").replace(text) { m -> when (m.groupValues[1]) { "n" -> "\n"; "t" -> "\t"; else -> m.groupValues[1] } }
    }

    @Test
    fun theEnglishOfEveryMovedFamilyIsWordForWordWhatItAlwaysSaid() {
        val pinned = pins
        val defined = english.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }
        assertEquals("a string with no pin, or a pin with no string", pinned.keys, defined.keys)
        for ((name, text) in pinned) assertEquals(name, text, english.getValue(name))
    }

    // ---- the labels a step names ------------------------------------------------------------------------------------------------------------------

    /** A lowercase brace token such as {{tags}} is shown as it is (it is not a label placeholder), so it is not a leftover. */
    private fun withoutLiteralTokens(text: String): String = text.replace(Regex("""\{\{[a-z][a-z_]*\}\}"""), "")

    private fun filled(map: Map<String, String>, text: String, plain: Boolean): String =
        HelpPlaceholders.substitute(text, plain) { key, usePlain -> map[key.resourceName(usePlain)] }

    @Test
    fun theEnglishOriginalsReadLikeTheStandardLabel_andATranslationUsesTheBarePlaceholderNamingTheSameLabels() {
        var checked = 0
        for ((name, text) in english.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) {
            val keys = HelpPlaceholders.keysIn(text)
            for (m in Regex("""\{\{([A-Z0-9_]+)(?::([^{}]*))?\}\}""").findAll(text)) {
                val key = LabelKey.fromName(m.groupValues[1])
                assertTrue("$name: {{${m.groupValues[1]}}} is not a LabelKey", key != null)
                val original = m.groups[2]?.value
                if (original != null) assertTrue("$name: the original \"$original\" does not read like the standard label", original.equals(english.getValue(key!!.resourceName(false)), ignoreCase = true))
                checked++
            }
            for ((tag, map) in translations) {
                val t = map.getValue(name)
                assertFalse("$tag/$name: a translation carries no English original", Regex("""\{\{[A-Z0-9_]+:""").containsMatchIn(t))
                assertEquals("$tag/$name: the same labels as English (a translation may restructure and name one a different number of times)", keys.toSet(), HelpPlaceholders.keysIn(t).toSet())
                for (plain in listOf(false, true)) assertFalse("$tag/$name: braces left after the labels are filled in (plain=$plain)", withoutLiteralTokens(filled(map, t, plain)).contains("{{"))
            }
            for (plain in listOf(false, true)) assertFalse("en/$name: braces left (plain=$plain)", withoutLiteralTokens(filled(english, text, plain)).contains("{{"))
        }
        assertTrue("expected to check some placeholders, checked $checked", checked > 0)
    }

    @Test
    fun aLatinScriptDraftHasNoArticleBeforeAPlaceholder_soAnEverydayWordOfAnotherGenderStillReads() {
        val articles = mapOf(
            "es" to listOf("EL", "LA", "LOS", "LAS", "UN", "UNA", "DEL", "AL"),
            "pt" to listOf("O", "A", "OS", "AS", "UM", "UMA", "DO", "DA", "NO", "NA", "AO"),
        )
        for ((tag, list) in articles) for ((name, text) in translations.getValue(tag).filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) {
            for (article in list) assertFalse("$tag/$name: article $article before a placeholder: $text", Regex("""(?<![\p{L}])$article \{\{""").containsMatchIn(text))
        }
    }

    /** A title that is exactly a label's or a control's own word in every language, so the walkthrough and the screen agree. */
    private val isExactly = mapOf(
        "helpmod_geo_protocol_title" to "label_geo_protocol",
        "helpmod_geo_protocol_intro_title" to "label_geo_protocol",
        "helpmod_geo_protocol_map_data_title" to "geo_map_data",
        "helpmod_deck_emergency_overrides_title" to "emergency_overrides_title",
        "helpmod_deck_management_intro_title" to "label_decks",
        "helpmod_settings_management_audio_output_routing_title" to "settings_audio_routing_heading",
        "helpmod_settings_management_watch_audio_title" to "settings_watch_audio_heading",
        "helpmod_target_computer_guide_me_title" to "people_wizard_title",
        "helpmod_personalization_manage_profiles_title" to "audio_manage_profiles",
        "helpmod_statement_composer_save_title" to "common_save",
        "helpmod_statement_composer_copy_title" to "common_copy",
        "helpmod_statement_composer_speak_title" to "common_speak",
        "helpmod_ack_command_bar_header_protocol_title" to "label_settings_entry",
        "helpmod_matrix_prompt_creation_macro_template_title" to "matrix_edit_subtitle",
    )

    /** A text that names a label in plain words (English has no placeholder there), so every language holds that label's own standard word, and it does not follow PLAIN WORDS (a known gap). */
    private val namesLabelLiterally = mapOf(
        "helpmod_logs_intro_title" to listOf("label_terminal"),
        "helpmod_logs_intro_body" to listOf("label_terminal"),
        // "Choose IMPORT": the word on the screen's import button (and its confirm button) in each language.
        "helpmod_deck_gif_import_body" to listOf("gif_import_confirm"),
        // The switch the Emergency screen names, and the EDIT button (as the Emergency card words it).
        "helpmod_deck_emergency_overrides_body" to listOf("emergency_confirm_before_sending"),
        "helpmod_deck_emergency_info_save_body" to listOf("common_edit"),
        // MANAGE in the deck menu, and the four kinds of deck the create dialog offers.
        "helpmod_deck_management_manage_body" to listOf("deckmenu_manage"),
        "helpmod_deck_management_type_body" to listOf("label_deck_type_quick", "label_deck_type_emergency", "label_deck_type_emoji", "label_deck_type_gif"),
        // The PROFILE button in the header, the three poses a Quick Actions group can be bound to, EDIT and the ROOT OVERRIDE SOURCE setting.
        "helpmod_basics_navigation_profile_selector_body" to listOf("header_profile"),
        "helpmod_deck_quick_actions_groups_intro_body" to listOf("label_pose_identity", "label_pose_defend", "label_pose_connect"),
        "helpmod_deck_quick_actions_edit_group_body" to listOf("common_edit", "qa_group_root_title"),
        // The nav button that opens the settings screen, the switches and sliders in AUDIO OUTPUT ROUTING and the watch configuration, and the DATA PORT buttons.
        "helpmod_settings_management_intro_title" to listOf("label_settings_entry"),
        "helpmod_settings_management_intro_body" to listOf("label_settings_entry"),
        "helpmod_settings_management_completion_body" to listOf("label_settings_entry"),
        "helpmod_settings_management_audio_output_routing_body" to listOf("label_vox", "label_silent_mode"),
        "helpmod_settings_management_hardware_config_body" to listOf("label_cryo", "label_twist_sens"),
        "helpmod_settings_management_data_port_body" to listOf("label_export_json", "label_full_restore", "label_import_matrix"),
        // The Target Computer screen's own buttons and the header's COMPUTER status.
        "helpmod_target_computer_tree_navigation_body" to listOf("people_add_category_button", "people_add_entry_button"),
        "helpmod_target_computer_display_modes_title" to listOf("people_mode_tree", "people_mode_dropdown"),
        "helpmod_target_computer_display_modes_body" to listOf("people_mode_tree", "people_mode_dropdown"),
        "helpmod_target_computer_guide_me_body" to listOf("people_guide_me"),
        "helpmod_target_computer_status_indicator_body" to listOf("header_computer"),
        // AUDIO ARCHITECT: GUIDE VOX and the PROTOCOL entry where the global switches now live, the MANAGE PROFILES button, COMMIT, and the DSP chain.
        "helpmod_personalization_global_output_body" to listOf("label_vox", "label_settings_entry"),
        "helpmod_personalization_manage_profiles_body" to listOf("audio_manage_profiles"),
        "helpmod_personalization_save_profile_body" to listOf("common_commit", "label_dsp_chain"),
        "helpmod_personalization_completion_body" to listOf("label_dsp_chain"),
        // The Composer's buttons: FULL SCREEN (without its brackets), SAVE, COPY, SPEAK; and the Shared Root Variables label.
        "helpmod_statement_composer_fullscreen_body" to listOf("composer_full_screen"),
        "helpmod_statement_composer_save_body" to listOf("common_save"),
        "helpmod_statement_composer_copy_body" to listOf("common_copy"),
        "helpmod_statement_composer_speak_body" to listOf("common_speak"),
        "helpmod_statement_composer_insert_variable_body" to listOf("label_shared_variables"),
        "helpmod_statement_composer_word_suggestions_title" to listOf("words_title"),
        // RECORD TRAINING DATA: the capture screens' own buttons and marks, and the free-speech notice (the same sentence the home screen shows).
        "helpmod_record_training_data_new_script_body" to listOf("capture_new_script"),
        "helpmod_record_training_data_save_body" to listOf("common_save", "common_back"),
        "helpmod_record_training_data_record_body" to listOf("capture_record"),
        "helpmod_record_training_data_redo_body" to listOf("capture_redo_last", "capture_pause", "capture_resume", "capture_mark_noise", "capture_mark_unclear", "capture_mark_laugh", "capture_mark_cough", "capture_mark_stumble"),
        "helpmod_record_training_data_end_body" to listOf("capture_end_session"),
        "helpmod_record_training_data_free_body" to listOf("capture_record_free", "capture_free_notice_home"),
        "helpmod_record_training_data_save_file_body" to listOf("capture_save_all"),
        // The command bar's buttons, the profile-change confirmation, and the Matrix editor's own headings and controls.
        "helpmod_ack_command_bar_header_profile_body" to listOf("header_profile"),
        "helpmod_ack_command_bar_header_protocol_body" to listOf("label_settings_entry"),
        "helpmod_ack_command_bar_header_help_title" to listOf("help_button"),
        "helpmod_ack_command_bar_header_help_body" to listOf("help_button"),
        "helpmod_deck_profile_selection_select_profile_body" to listOf("profile_warn_change"),
        "helpmod_matrix_prompt_creation_macro_template_body" to listOf("matrix_edit_subtitle", "matrix_edit_template"),
        "helpmod_matrix_prompt_creation_commit_prompt_body" to listOf("matrix_edit_destructive", "common_commit"),
    )

    @Test
    fun aTitleThatNamesALabelOrAControlIsThatLabelsOrControlsOwnWordInEveryLanguage() {
        // English writes this step's title "LIVE SAVE EDITOR" (a space) where the screen says "LIVE-SAVE EDITOR"; English stays as it always was, so only the translations are held to the screen.
        val englishWritesItDifferently = setOf("helpmod_matrix_prompt_creation_macro_template_title")
        for ((tag, map) in everyLanguage) for ((name, source) in isExactly) {
            if (tag == "en" && name in englishWritesItDifferently) continue
            assertEquals("$tag/$name", map.getValue(source), map.getValue(name))
        }
        assertTrue("every entry names a walkthrough string that exists", (isExactly.keys + namesLabelLiterally.keys).all { it in english })
    }

    @Test
    fun theRootIdentityHeadingIsTheScreensHeadingWithTheLanguagesOwnPoseWord_andTheWatchStatesStayAsTheWatchShowsThem() {
        for ((tag, map) in everyLanguage) {
            val heading = map.getValue("matrix_root_heading").replace("%1\$s", map.getValue("label_pose_identity"))
            assertEquals("$tag: the step's title is the heading the Matrix shows", heading, map.getValue("helpmod_matrix_prompt_creation_identity_root_title"))
            assertTrue("$tag: the body names it too", map.getValue("helpmod_matrix_prompt_creation_identity_root_body").contains(heading))
            val link = map.getValue("helpmod_ack_command_bar_header_watch_link_body")
            for (state in listOf("OFFLINE", "ARMED", "LOCKED")) assertTrue("$tag: the watch's own state word $state: $link", link.contains(state, ignoreCase = tag == "en"))
        }
    }

    @Test
    fun aTextThatNamesALabelInPlainWordsHoldsThatLabelsOwnWordInEveryTranslation() {
        // English may name a button loosely ("Export", "Full Restore"); a translation names it by the word the screen shows, so the step and the button always agree.
        for ((tag, map) in translations) for ((name, sources) in namesLabelLiterally) for (source in sources) {
            val word = map.getValue(source).trim('[', ']')
            assertTrue("$tag/$name does not hold \"$word\" ($source): ${map.getValue(name)}", map.getValue(name).contains(word, ignoreCase = true))
        }
    }

    @Test
    fun theMapStepStillNamesTheFileKindAndTheFormat_andTakesNoArgumentInEveryLanguage() {
        for ((tag, map) in everyLanguage) {
            val body = map.getValue("helpmod_geo_protocol_map_data_body")
            assertTrue("$tag: Mapsforge is a name: $body", body.contains("Mapsforge", ignoreCase = true))
            assertTrue("$tag: the .map file kind is named: $body", body.contains(".map", ignoreCase = true))
            for ((name, text) in map.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) assertFalse("$tag/$name takes an argument nothing passes: $text", Regex("""%(\d+\$)?[sdf]""").containsMatchIn(text))
        }
    }

    @Test
    fun aParagraphBreakInEnglishIsAParagraphBreakInEveryLanguage_andNoFileHoldsARawNewline() {
        for ((name, text) in english.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) && it.value.contains("\n") }) {
            for ((tag, map) in translations) assertEquals("$tag/$name: the same number of line breaks as English", text.count { it == '\n' }, map.getValue(name).count { it == '\n' })
        }
        // Android collapses a raw newline inside a string resource to a space, so a break must be written as the \n escape; the XML parser used by the tests would not notice.
        for (path in listOf("values") + StringsXml.translations().keys.map { "values-$it" }) {
            val raw = RepoFiles.read("app/src/main/res/$path/strings.xml")
            for (m in Regex("""<string name="(helpmod_[a-z0-9_]+)"[^>]*>([^<]*)</string>""").findAll(raw)) assertFalse("$path/${m.groupValues[1]} holds a raw newline", m.groupValues[2].contains("\n"))
        }
    }

    @Test
    fun aLiteralLowercaseBraceTokenInEnglishIsKeptAsItIsInEveryLanguage_neverUppercasedIntoAPlaceholder() {
        val literal = Regex("""\{\{[a-z][a-z_]*\}\}""")
        var checked = 0
        for ((name, text) in english.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) {
            val tokens = literal.findAll(text).map { it.value }.sorted().toList()
            if (tokens.isEmpty()) continue
            checked++
            for ((tag, map) in translations) assertEquals("$tag/$name: the same literal tokens as English", tokens, literal.findAll(map.getValue(name)).map { it.value }.sorted().toList())
        }
        assertTrue("expected at least the Quick Actions {{tags}} step", checked >= 1)
    }

    @Test
    fun aStoredTagInEnglishIsKeptExactlyInEveryLanguage() {
        // [COMPUTER:PEOPLE] is the token the phrase editor really inserts; it is never translated.
        val tag = Regex("""\[[A-Z]+:[A-Z_]+\]""")
        var checked = 0
        for ((name, text) in english.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) {
            for (token in tag.findAll(text).map { it.value }) {
                checked++
                for ((lang, map) in translations) assertTrue("$lang/$name lost the token $token: ${map.getValue(name)}", map.getValue(name).contains(token))
            }
        }
        assertTrue("expected the Target Computer tag step", checked >= 1)
    }

    @Test
    fun noWalkthroughStringStartsOrEndsWithASpace_whichAndroidWouldTrim() {
        for ((tag, map) in everyLanguage) for ((name, text) in map.filter { it.key.startsWith(HelpWalkthroughText.PREFIX) }) assertEquals("$tag/$name", text.trim(), text)
    }

    // ---- where a step is drawn and spoken -------------------------------------------------------------------------------------------------------

    @Test
    fun theCoachAndTheMenuDrawAWalkthroughsWordsThroughHelpWords() {
        val coach = file("help/HelpCoachDialog.kt")
        val menu = file("help/HelpMenuDialog.kt")
        assertTrue(coach.contains("text = helpWords(step.title)") && coach.contains("text = helpWords(step.body)"))
        assertTrue(menu.contains("text = helpWords(module.title)") && menu.contains("text = helpWords(module.summary)"))
        assertTrue(coach.contains("import com.example.besu.ui.helpWords") && menu.contains("import com.example.besu.ui.helpWords"))
        val words = RepoFiles.read("$base/ui/PlainWords.kt")
        val helpWords = words.substring(words.indexOf("fun helpWords("))
        assertTrue("helpWords reads the name through the walkthrough text and then fills the placeholders", helpWords.contains("helpText(remember(nameOrText, words) { HelpWalkthroughText.read(words, nameOrText) })"))
        assertTrue("helpWords makes the text source once", helpWords.contains("val words = rememberText()"))
    }

    @Test
    fun theSpokenGuideSpeaksTheTranslatedStepOnlyWhenTheRuleSaysSo_andOtherwiseTheEnglishStep() {
        val main = RepoFiles.read("$base/MainActivity.kt").lines().joinToString("\n") { it.substringBefore("//") }
        val from = main.indexOf("val speakTranslated")
        assertTrue("the speaking rule was not found", from >= 0)
        val block = main.substring(from, main.indexOf("val spokenText = buildString", from))
        assertTrue(block.contains("HelpWalkthroughText.speaksInterfaceLanguage(AssistPrefs.speechLanguage(context), ActiveScript.tag, Locale.getDefault().language)"))
        assertTrue("the English step is read from an English context", block.contains("val spokenContext = if (speakTranslated) context else EnglishResources.context(context)"))
        assertTrue(block.contains("val spokenWords = ResourceText(spokenContext)"))
        assertTrue("the words are read through the walkthrough text, from the spoken text source", block.contains("HelpWalkthroughText.read(spokenWords, nameOrText)"))
        assertTrue("the labels placeholders fill in from the same context, so an English step never gets a Spanish label", block.contains("LabelText.resolveOrNull(spokenContext, key, plain)"))
        assertTrue(block.contains("PlainWordsState.on"))
        assertFalse("nothing else reads the step's words", Regex("""append\(step\.(title|body)\)""").containsMatchIn(main))
        val edge = RepoFiles.read("$base/data/ResourceText.kt")
        assertTrue(edge.contains("object EnglishResources") && edge.contains("setLocale(Locale.ENGLISH)"))
        assertTrue("it never throws", edge.substring(edge.indexOf("object EnglishResources")).contains("catch (e: Exception)"))
    }

    @Test
    fun theOtherSpokenPlacesAreNotChanged_thePhraseGoesToTheServiceAsBefore() {
        val main = RepoFiles.read("$base/MainActivity.kt").lines().joinToString("\n") { it.substringBefore("//") }
        val at = main.indexOf("val spokenText = buildString")
        val tail = main.substring(at, at + 700)
        assertTrue(tail.contains("""putExtra("phrase", spokenText)""") && tail.contains("""putExtra("robotic", true)""") && tail.contains("""putExtra("source", "HELP/${'$'}{module.id}")"""))
    }
}
