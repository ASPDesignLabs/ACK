// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The RECORD TRAINING DATA library, the script editor and the session detail dialog (`voicecapture/TrainingCaptureHome.kt`, `ScriptEditor.kt`, `SessionDetailDialog.kt`) read their words from string
 * resources in the chosen language. They use the SDK and cannot be compiled here (they are syntax-checked), so this reads them: the old English literals are gone, every string they name exists in every language
 * and none is left unused, each word sits on the control that does what it says, a delete still takes two steps with the delete only in the last, a stored value (a mark's id, a line setting) is still what is saved,
 * and none of these screens gained a standard button (those buzz, and a buzz is audible to a microphone that may be open). CaptureTextTest holds the decisions.
 */
class CaptureWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val home get() = noComments(RepoFiles.read("$base/voicecapture/TrainingCaptureHome.kt"))
    private val editor get() = noComments(RepoFiles.read("$base/voicecapture/ScriptEditor.kt"))
    private val detail get() = noComments(RepoFiles.read("$base/voicecapture/SessionDetailDialog.kt"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    private fun bodyOf(text: String, start: String, end: String): String {
        val a = text.indexOf(start)
        check(a >= 0) { "$start not found" }
        val b = text.indexOf(end, a + start.length)
        check(b >= 0) { "$end not found after $start" }
        return text.substring(a, b)
    }

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringTheCaptureScreensNameExists_inEveryLanguage_andNoneIsLeftUnused() {
        val screens = listOf("TrainingCaptureHome.kt", "ScriptEditor.kt", "SessionDetailDialog.kt", "CaptureSessionScreen.kt").map { noComments(RepoFiles.read("$base/voicecapture/$it")) }
        val referenced = screens.flatMap { Regex("""R\.string\.(capture_[a-z0-9_]+)""").findAll(it).map { m -> m.groupValues[1] }.toList() }.toSet() +
            screens.flatMap { Regex("""words\.get\("(capture_[a-z0-9_]+)"""").findAll(it).map { m -> m.groupValues[1] }.toList() }.toSet() +
            Regex(""""(capture_[a-z0-9_]+)"""").findAll(noComments(RepoFiles.read("$base/core/CaptureText.kt"))).map { it.groupValues[1] }.toSet() +
            // The DELETE DATA note points at SAVE ALL TO A FILE by this name.
            Regex(""""(capture_[a-z0-9_]+)"""").findAll(noComments(RepoFiles.read("$base/core/StorageCatalogue.kt"))).map { it.groupValues[1] }.toSet()
        val defined = english.keys.filter { it.startsWith("capture_") }.toSet()
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = referenced.filter { it !in map }
            assertEquals("$tag: named but not defined: $missing", emptyList<String>(), missing)
        }
        assertEquals("defined but never used: ${defined - referenced}", emptySet<String>(), defined - referenced)
        // The shared strings these screens borrow exist too.
        for ((tag, map) in listOf("en" to english) + translations.toList()) for (name in listOf("common_edit", "common_save", "common_cancel", "common_continue", "common_delete", "manual_close", "help_button")) {
            assertTrue("$tag/$name", map.containsKey(name))
        }
    }

    @Test
    fun theOldEnglishLiteralsAreGoneFromTheLibrary() {
        val h = home
        for (literal in listOf(
            "READ TEXT ALOUD", "WALKTHROUGH. FIND IT", "ON THIS PHONE", "SESSION(S) WERE ENDED", "COULD NOT READ", "NO SCRIPTS YET", "\"RECORD\"", "+ NEW SCRIPT", "TALK ABOUT ANYTHING",
            "\"RECORD FREE SPEECH\"", "NOTHING RECORDED YET", "\"SAVE ALL TO A FILE\"", "A SAVED PACKAGE ON YOUR COMPUTER", "SAVING FILE", "OF AUDIO", "DELETE THIS SESSION?", "REALLY DELETE?", "LAST CHANCE",
            "DELETE FOREVER", "\"KEEP IT\"", "\"[OK]\"", "\"[CLOSE]\"", "SAVE CANCELLED", "SAVED AND CHECKED", "THERE IS NOTHING TO SAVE", "TOO BIG FOR ONE FILE", "COULD NOT BE OPENED FOR WRITING",
            "COULD NOT BE READ BACK", "FAILED ITS CHECK", "THE PACKAGE COULD NOT BE MADE", "SAVING FAILED", "\"RECORDED SESSIONS\"", "\"SCRIPTS\"", "\"FREE SPEECH\"", "\"EDIT\"", "\"CONTINUE\"",
            "NOT ENDED", "NO RECORDING", "WAITING FOR YOU TO LISTEN", "\"SCRIPT\"",
        )) assertFalse("TrainingCaptureHome still holds $literal", h.contains(literal))
        assertFalse("a size is made by the shared decision", h.contains("String.format"))
    }

    @Test
    fun theOldEnglishLiteralsAreGoneFromTheScriptEditor() {
        val e = editor
        for (literal in listOf(
            "\"NEW SCRIPT\"", "\"EDIT SCRIPT\"", "\"[BACK]\"", "\"TITLE\"", "TEXT TO READ", "TYPE OR PASTE ANYTHING", "CHARACTERS\"", "\"LINE BREAKS\"", "\"JOIN LINES\"", "\"ONE CARD PER LINE\"",
            "A LINE BREAK IS JUST", "EVERY LINE IS ITS OWN", "\"LANGUAGE CODE\"", "THE LANGUAGE CODE SHOULD", "\"CARDS\"", "NOTHING TO READ YET", "WORDS A SECOND", "HAVE DIGITS OR SYMBOLS", "...AND ", "\"SAVE\"",
            "\"CANCEL\"", "DELETE THIS SCRIPT", "DELETING A SCRIPT REMOVES", "SAVE THESE CHANGES?", "KEEP EDITING", "LEAVE WITHOUT SAVING?", "WHAT YOU TYPED HERE", "\"LEAVE\"", "ITS TEXT WILL BE REMOVED",
            "REALLY DELETE?", "LAST CHANCE", "DELETE FOREVER", "\"KEEP IT\"", "\"CONTINUE\"", "THE SCRIPT COULD NOT BE SAVED", "WILL BE REPLACED BY WHAT IS ON THIS SCREEN", "String.format",
        )) assertFalse("ScriptEditor still holds $literal", e.contains(literal))
    }

    @Test
    fun theOldEnglishLiteralsAreGoneFromTheSessionDetail() {
        val d = detail
        for (literal in listOf(
            "\"SESSION\"", "\"[CLOSE]\"", "LOADING...", "\"SCRIPT\"", "\"FREE SPEECH\"", " KHZ", "NOT ENDED", "NOTHING WAS RECORDED", "SUGGESTED PIECE", "REPAIRED, WAITING", "THE APP CLOSED WHILE",
            "KEEP THIS RECORDING", "SET ASIDE OR WAITING", "SAVE TO A FILE", "DELETE SESSION", "DELETE THIS RECORDING?", "IT WAS SET ASIDE", "\"DELETE\"", "\"KEEP IT\"", "CARD \${", "REPAIRED: LISTEN",
            "\"NOTES: \"", "\"PLAY\"", "\"KEEP\"", "\"SET ASIDE\"", "MARK THIS CLIP", "flag.uppercase()", "CAN'T BE READ", "THAT DID NOT WORK", "String.format", "\"KEPT\"", "\"UNFINISHED\"",
        )) assertFalse("SessionDetailDialog still holds $literal", d.contains(literal))
    }

    // ---- English is exactly what the screens always said ---------------------------------------------------------------------------------

    @Test
    fun theSimpleWordsAreHeldExactly() {
        val expected = mapOf(
            "capture_close" to "[CLOSE]", "capture_scripts" to "SCRIPTS", "capture_record" to "RECORD", "capture_new_script" to "+ NEW SCRIPT", "capture_free_speech" to "FREE SPEECH",
            "capture_record_free" to "RECORD FREE SPEECH", "capture_sessions" to "RECORDED SESSIONS", "capture_no_sessions" to "NOTHING RECORDED YET.", "capture_save_all" to "SAVE ALL TO A FILE",
            "capture_delete_session_title" to "DELETE THIS SESSION?", "capture_keep_it" to "KEEP IT", "capture_really_delete" to "REALLY DELETE?", "capture_last_chance" to "LAST CHANCE. THIS CANNOT BE UNDONE.",
            "capture_delete_forever" to "DELETE FOREVER", "capture_ok" to "[OK]", "capture_editor_new" to "NEW SCRIPT", "capture_editor_edit" to "EDIT SCRIPT", "capture_back" to "[BACK]",
            "capture_title" to "TITLE", "capture_text_to_read" to "TEXT TO READ", "capture_line_breaks" to "LINE BREAKS", "capture_join_lines" to "JOIN LINES", "capture_one_per_line" to "ONE CARD PER LINE",
            "capture_language_code" to "LANGUAGE CODE", "capture_cards" to "CARDS", "capture_nothing_to_read" to "NOTHING TO READ YET.", "capture_delete_script" to "DELETE THIS SCRIPT",
            "capture_save_changes_title" to "SAVE THESE CHANGES?", "capture_keep_editing" to "KEEP EDITING", "capture_leave_title" to "LEAVE WITHOUT SAVING?", "capture_leave" to "LEAVE",
            "capture_delete_script_title" to "DELETE THIS SCRIPT?", "capture_script_save_failed" to "THE SCRIPT COULD NOT BE SAVED.", "capture_session" to "SESSION", "capture_loading" to "LOADING...",
            "capture_nothing_recorded" to "NOTHING WAS RECORDED.", "capture_keep_recording" to "KEEP THIS RECORDING", "capture_save_file" to "SAVE TO A FILE", "capture_delete_session" to "DELETE SESSION",
            "capture_delete_clip_title" to "DELETE THIS RECORDING?", "capture_play" to "PLAY", "capture_keep" to "KEEP", "capture_set_aside" to "SET ASIDE", "capture_save_cancelled" to "SAVE CANCELLED. NOTHING WAS WRITTEN.",
            "capture_saved_checked" to "SAVED AND CHECKED. MOVE THE FILE TO YOUR COMPUTER.", "capture_session_unreadable" to "THIS SESSION CAN'T BE READ.", "capture_action_failed" to "THAT DID NOT WORK.",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
    }

    @Test
    fun theSentencesKeepTheirSafetyWordsInEveryLanguage() {
        // A delete confirmation says it cannot be undone and what is lost; a save notice says nothing was lost from the phone. Checked by shape, in every language: each sentence is present and keeps its placeholders.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in listOf("capture_last_chance", "capture_delete_session_body", "capture_delete_session_body_unknown", "capture_delete_script_body", "capture_delete_clip_body", "capture_pkg_readback", "capture_pkg_check", "capture_pkg_failed")) {
                assertTrue("$tag/$name", map.getValue(name).isNotBlank())
            }
            assertEquals("$tag: the size in the delete sentence", listOf("%1\$s"), StringsXml.placeholders(map.getValue("capture_delete_session_body")))
            assertEquals("$tag: the unknown-size sentence has no placeholder", emptyList<String>(), StringsXml.placeholders(map.getValue("capture_delete_session_body_unknown")))
            assertEquals("$tag: saving a package that failed its check names the problem", listOf("%1\$s"), StringsXml.placeholders(map.getValue("capture_pkg_check")))
            assertEquals("$tag: a failed save names the reason", listOf("%1\$s"), StringsXml.placeholders(map.getValue("capture_pkg_failed")))
            assertEquals("$tag: the script's title in the save-changes sentence", listOf("%1\$s"), StringsXml.placeholders(map.getValue("capture_save_changes_body")))
            assertEquals("$tag: the example in the language-code sentence", listOf("%1\$s"), StringsXml.placeholders(map.getValue("capture_language_code_bad")))
        }
    }

    @Test
    fun aBracketedButtonKeepsItsBracketsInEveryLanguage() {
        // [CLOSE], [BACK] and [OK] keep their brackets inside the resource (the house style of these screens); a translation does not have to keep a separator.
        for ((tag, map) in listOf("en" to english) + translations.toList()) for (name in listOf("capture_close", "capture_back", "capture_ok")) {
            val text = map.getValue(name)
            assertTrue("$tag/$name: '$text'", text.startsWith("[") && text.endsWith("]") && text.length > 2)
        }
    }

    // ---- each word sits on the control that does what it says --------------------------------------------------------------------------------

    @Test
    fun theLibraryButtonsOpenWhatTheirWordsSay() {
        val h = home
        assertTrue(Regex("""R\.string\.capture_record\)[\s\S]{0,700}?CaptureScreen\.ScriptSetup""").containsMatchIn(h))
        assertTrue(Regex("""R\.string\.common_edit\)[\s\S]{0,300}?CaptureScreen\.Editor\(summary""").containsMatchIn(h))
        assertTrue(Regex("""R\.string\.capture_new_script\)[\s\S]{0,700}?CaptureScreen\.Editor\(null\)""").containsMatchIn(h))
        assertTrue(Regex("""R\.string\.capture_record_free\)[\s\S]{0,700}?CaptureScreen\.FreeSetup""").containsMatchIn(h))
        assertTrue(Regex("""R\.string\.capture_save_all\)[\s\S]{0,700}?startSaving\(sessions""").containsMatchIn(h))
        assertTrue(Regex("""R\.string\.capture_close\)[\s\S]{0,500}?onClose\(\)""").containsMatchIn(h))
        // The three buttons the walkthrough points at still carry their tags next to the translated words.
        for (tag in listOf("TRAIN_SCRIPT_RECORD_BTN", "TRAIN_NEW_SCRIPT_BTN", "TRAIN_FREE_BTN", "TRAIN_SAVE_ALL_BTN")) assertTrue(tag, h.contains("helpTarget(AckTags.$tag"))
    }

    @Test
    fun deletingASessionStillTakesTwoStepsAndOnlyTheSecondDeletes() {
        val h = home
        assertEquals("one delete call in the library", 1, Regex("""store\.deleteSession\(""").findAll(h).count())
        assertTrue(Regex("""R\.string\.capture_delete_session_title\)[\s\S]{0,700}?onConfirm = \{ deleteStep = 2 \}""").containsMatchIn(h))
        assertTrue("the delete is in the last dialog", Regex("""R\.string\.capture_delete_forever\)[\s\S]{0,900}?store\.deleteSession\(id\)""").containsMatchIn(h))
        val first = bodyOf(h, "if (deleteStep == 1) {", "} else if (deleteStep == 2) {")
        assertFalse("the first dialog cannot delete", first.contains("store.deleteSession("))
        assertTrue("CANCEL is KEEP IT in both", first.contains("cancelLabel = stringResource(R.string.capture_keep_it)") && h.substringAfter("} else if (deleteStep == 2) {").contains("cancelLabel = stringResource(R.string.capture_keep_it)"))
    }

    @Test
    fun deletingAScriptStillTakesTwoStepsAndOnlyTheSecondDeletes() {
        val e = editor
        assertEquals("one delete call in the editor", 1, Regex("""store\.deleteScript\(""").findAll(e).count())
        assertTrue(Regex("""R\.string\.capture_delete_script\),[\s\S]{0,200}?deleteStep = 1""").containsMatchIn(e))
        assertTrue(Regex("""R\.string\.capture_delete_script_title\)[\s\S]{0,700}?onConfirm = \{ deleteStep = 2 \}""").containsMatchIn(e))
        assertTrue(Regex("""R\.string\.capture_delete_forever\)[\s\S]{0,700}?store\.deleteScript\(existing\.id\)""").containsMatchIn(e))
        assertFalse("the first dialog cannot delete", bodyOf(e, "if (deleteStep == 1) {", "if (deleteStep == 2").contains("store.deleteScript("))
    }

    @Test
    fun theEditorsButtonsDoWhatTheirWordsSay_andAChoiceStoresTheOldWord() {
        val e = editor
        assertTrue(Regex("""R\.string\.capture_join_lines\)[\s\S]{0,300}?lines = "join" \}""").containsMatchIn(e))
        assertTrue(Regex("""R\.string\.capture_one_per_line\)[\s\S]{0,300}?lines = "keep" \}""").containsMatchIn(e))
        assertTrue(Regex("""R\.string\.common_save\)[\s\S]{0,700}?save\(\) else confirmSave = true""").containsMatchIn(e))
        assertTrue(Regex("""R\.string\.common_cancel\)[\s\S]{0,300}?confirmLeave = true else onDone\(false\)""").containsMatchIn(e))
        assertTrue(Regex("""R\.string\.capture_back\)[\s\S]{0,500}?confirmLeave = true else onDone\(false\)""").containsMatchIn(e))
        assertTrue(Regex("""R\.string\.capture_leave\)[\s\S]{0,700}?onConfirm = \{ confirmLeave = false; onDone\(false\) \}""").containsMatchIn(e))
        assertTrue(Regex("""R\.string\.capture_save_changes_title\)[\s\S]{0,700}?onConfirm = \{ confirmSave = false; save\(\) \}""").containsMatchIn(e))
        // What the file stores for the setting is the old word, never the drawn one.
        assertTrue(e.contains("lines = lines, language = language"))
        for (tag in listOf("TRAIN_SCRIPT_SAVE_BTN", "TRAIN_SCRIPT_TEXT")) assertTrue(tag, e.contains("helpTarget(AckTags.$tag"))
        assertTrue("the language example is the stored form of a code", e.contains("""CaptureText.languageCodeBad(words, "EN-US")"""))
    }

    @Test
    fun theDetailButtonsDoWhatTheirWordsSay_andAMarkToggledIsStoredAsItsId() {
        val d = detail
        assertTrue(Regex("""R\.string\.capture_keep_recording\)[\s\S]{0,300}?keepRecoveredRecording""").containsMatchIn(d))
        assertTrue(Regex("""R\.string\.capture_save_file\)[\s\S]{0,300}?onSave\(s\)""").containsMatchIn(d))
        assertTrue(Regex("""R\.string\.capture_delete_session\)[\s\S]{0,300}?onDelete\(\)""").containsMatchIn(d))
        assertTrue(Regex("""R\.string\.capture_play\)[\s\S]{0,200}?onClick = onPlay""").containsMatchIn(d))
        assertTrue(Regex("""R\.string\.capture_keep\)[\s\S]{0,200}?onClick = onKeep""").containsMatchIn(d))
        assertTrue(Regex("""R\.string\.capture_set_aside\)[\s\S]{0,300}?onClick = onAside""").containsMatchIn(d))
        assertTrue(Regex("""R\.string\.common_delete\)[\s\S]{0,200}?onClick = onDelete""").containsMatchIn(d))
        assertTrue("a mark is drawn through its word and toggled by its id", Regex("""CaptureText\.markWord\(words, flag\)[\s\S]{0,200}?onToggle\(flag\)""").containsMatchIn(d))
        assertFalse("a drawn word is never what is stored", d.contains("onToggle(CaptureText"))
        assertTrue("the marks a person can set are still the stored ones", d.contains("ClipFlags.PERSON.chunked(3)"))
        assertEquals("one clip delete, in the dialog", 1, Regex("""store\.deleteClip\(""").findAll(d).count())
        assertTrue(Regex("""R\.string\.capture_delete_clip_title\)[\s\S]{0,900}?store\.deleteClip\(sessionId, index\)""").containsMatchIn(d))
        assertTrue("the delete button is only on a clip that was set aside", Regex("""ClipState\.REDONE -> TightPanelButton\(stringResource\(R\.string\.common_delete\)""").containsMatchIn(d))
    }

    // ---- what is decided stays in the decisions -----------------------------------------------------------------------------------------

    @Test
    fun aStateOrAModeIsReadFromItsStoredValueInTheDecision_andNeverFromAWordOnScreen() {
        val text = noComments(RepoFiles.read("$base/core/CaptureText.kt"))
        assertTrue(text.contains("""mode == "script""""))
        assertTrue(text.contains("ClipState.DONE -> \"capture_state_kept\""))
        for (screen in listOf(home, editor, detail)) {
            assertFalse("a screen compares a drawn word", Regex("""==\s*(stringResource|words\.get)\(""").containsMatchIn(screen))
            assertFalse("a screen reads logic back from text", Regex("""\.(label|text)\s*==\s*"[A-Z]""").containsMatchIn(screen))
        }
        assertTrue("the session's stored mode is what the library hands the decision", home.contains("CaptureText.sessionTitle(words, s.mode, s.scriptTitle, s.label)"))
        assertTrue(detail.contains("CaptureText.sessionTitle(words, s.mode, s.scriptTitle, s.label)"))
    }

    @Test
    fun aSaveResultIsCarriedByAType_notByASentence() {
        val h = home
        val write = bodyOf(h, "private fun writePackage(", "\n}\n")
        assertFalse("writePackage builds no words", write.contains("stringResource") || write.contains("words.") || write.contains("R.string") || write.contains("getString("))
        assertTrue(write.contains("CaptureText.SaveNotice.CouldNotOpen") && write.contains("CaptureText.SaveNotice.CouldNotReadBack") && write.contains("CaptureText.SaveNotice.FailedCheck(") &&
            write.contains("CaptureText.SaveNotice.CouldNotMake(") && write.contains("CaptureText.SaveNotice.Failed("))
        assertTrue("the notice is written where it is drawn", h.contains("CaptureText.saveNotice(words, notice)"))
        assertTrue("a technical detail is passed as it came", write.contains("e.problems.firstOrNull() ?: e.message") && write.contains("verified.problems.first()"))
    }

    @Test
    fun aToastAndANonComposableMessageReadTheirTextThroughTheContext() {
        val h = home
        for (line in h.lines().filter { it.contains("Toast.makeText") }) assertTrue("a toast reads through the context: $line", line.contains("context.getString(R.string.capture_"))
        assertEquals("both toasts", 2, h.lines().count { it.contains("Toast.makeText") })
        // save() in the editor is not a composable lambda, so it reads the words it was given.
        val save = bodyOf(editor, "fun save() {", "\n    }\n")
        assertFalse("save() cannot call stringResource", save.contains("stringResource("))
        assertTrue(save.contains("words.get(\"capture_script_save_failed\")"))
        // The detail dialog's LaunchedEffect and change() are not composable lambdas either.
        val effect = bodyOf(detail, "LaunchedEffect(reload) {", "fun change(")
        assertFalse("the load effect cannot call stringResource", effect.contains("stringResource("))
        assertTrue(effect.contains("words.get(\"capture_session_unreadable\")"))
        assertTrue(bodyOf(detail, "fun change(", "fun play(").contains("words.get(\"capture_action_failed\")"))
    }

    // ---- quiet: no standard button, no vibration, on the screens that are not the recording screen -----------------------------------------------

    @Test
    fun noStandardButtonOrVibrationWasAddedToTheLibraryTheEditorOrTheDetail() {
        for ((name, screen) in listOf("library" to home, "editor" to editor, "detail" to detail)) {
            assertFalse("$name has a NeonButton", screen.contains("NeonButton("))
            assertFalse("$name has a NeonToggle", screen.contains("NeonToggle("))
            assertFalse("$name vibrates", Regex("""[Vv]ibrat|HapticFeedback|performHapticFeedback""").containsMatchIn(screen))
            assertFalse("$name animates", Regex("""animate[A-Za-z]*AsState|AnimatedVisibility|Crossfade|infiniteRepeatable""").containsMatchIn(screen))
        }
    }

    @Test
    fun theNewWordsKeepTheTextSizeOfTheOldOnes() {
        // The words moved; their sizes did not (a smaller text for a longer translated word would be a hidden change). A font size is never written as a fixed width either.
        val sizes = Regex("""fontSize = (\d+)\.sp""")
        assertTrue(sizes.findAll(home).map { it.groupValues[1].toInt() }.toSet().all { it >= 9 })
        assertTrue("the notice's dismiss button is 48 dp high", home.contains("heightIn(min = 48.dp)"))
        for (screen in listOf(home, editor, detail)) assertFalse("a fixed width would clip a longer word", Regex("""\.width\(\d+\.dp\)""").containsMatchIn(screen))
    }
}
