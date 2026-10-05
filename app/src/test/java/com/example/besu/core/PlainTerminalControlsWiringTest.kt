// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * PLAIN WORDS adds buttons and switches to the Terminal screen for what used to need a typed command (docs/PLAIN_LANGUAGE.md, section B). The screen
 * code cannot be built here, so this reads it and holds it to what was agreed: the switches stay on until turned off but never act while they are
 * hidden, EMERGENCY still never asks, CLEAR HISTORY is a two-step with CANCEL prominent, nothing vibrates or moves, text is 12 sp or more, and the
 * typed commands are untouched. The decisions themselves (which flags a send uses) are tested in SendFlagsTest.
 */
class PlainTerminalControlsWiringTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")

    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line.substringBefore(" // ")
    }

    private val controls get() = noComments(source("ui/TerminalPlainControls.kt"))
    private val design get() = noComments(source("ui/DesignSystem.kt"))
    private val strings get() = StringsXml.map(StringsXml.default)

    // ---- the words ---------------------------------------------------------------------------------------------------------------------

    @Test
    fun everyControlStringTheScreenUsesExists_andNoneIsLeftOver() {
        // The Terminal controls, the Type tab's button and SETTINGS' FIX PROBLEMS all draw these.
        val used = listOf("ui/TerminalPlainControls.kt", "settings/SettingsView.kt", "composer/StatementComposerView.kt")
            .flatMap { Regex("""R\.string\.(plain_ctl_[a-z_]+)""").findAll(noComments(source(it))).map { m -> m.groupValues[1] }.toList() }.toSet()
        val defined = strings.keys.filter { it.startsWith("plain_ctl_") }.toSet()
        assertEquals("used but not defined, or defined but never used", used, defined)
    }

    @Test
    fun theControlWordsAreInCapitals_theAppsHouseStyle_andOnlyOneTakesAnArgument() {
        for ((name, text) in strings.filterKeys { it.startsWith("plain_ctl_") }) {
            val words = text.replace(Regex("""%(?:\d+\$)?[sdf]"""), "") // a format placeholder keeps its lower-case letter
            assertEquals(name, words.uppercase(), words)
        }
        val withPlaceholder = strings.filterKeys { it.startsWith("plain_ctl_") }.filterValues { StringsXml.placeholders(it).isNotEmpty() }.keys
        assertEquals(setOf("plain_ctl_send_options_on"), withPlaceholder)
    }

    @Test
    fun theFourSwitchesAreNamedAsTheDocumentProposes() {
        assertEquals("SEND QUIETLY", strings["plain_ctl_send_quietly"])
        assertEquals("DO NOT SAVE IN HISTORY", strings["plain_ctl_send_no_history"])
        assertEquals("KEEP ON SCREEN UNTIL I CLEAR IT", strings["plain_ctl_send_keep"])
        assertEquals("EMERGENCY", strings["plain_ctl_send_emergency"])
        assertEquals("WHAT'S NEW", strings["plain_ctl_whats_new"])
        assertEquals("CLEAR HISTORY", strings["plain_ctl_clear_history"])
    }

    // ---- quiet, steady and readable ---------------------------------------------------------------------------------------------------

    @Test
    fun theControlsNeverVibrateOrAnimate_andTheTextIs12spOrLarger_andEveryTapTargetIs48dpTall() {
        assertFalse("a vibration is audible to an open microphone", controls.contains("Haptic") || controls.contains("NeonButtonHaptic"))
        assertFalse("nothing here may move", Regex("""animate\w*|Animated\w*|Transition""").containsMatchIn(controls))
        val sizes = Regex("""fontSize = (\d+)\.sp""").findAll(controls).map { it.groupValues[1].toInt() }.toList()
        assertTrue(sizes.isNotEmpty())
        assertTrue("text under 12 sp: $sizes", sizes.all { it >= 12 })
        // Every clickable or toggleable row/box carries a 48 dp minimum.
        val taps = Regex("""\.(clickable|toggleable)\(""").findAll(controls).count()
        val minimums = Regex("""heightIn\(min = 48\.dp\)""").findAll(controls).count()
        assertTrue("$taps tap targets but only $minimums 48 dp minimums", minimums >= taps)
    }

    @Test
    fun anOnSwitchIsShownWithWordsNotOnlyColour_andIsASwitchToAScreenReader() {
        assertTrue(controls.contains("R.string.plain_ctl_on"))
        assertTrue(controls.contains("R.string.plain_ctl_off"))
        assertTrue(controls.contains("role = Role.Switch"))
    }

    @Test
    fun aSwitchThatIsOnIsNeverHidden_theClosedRowNamesWhatIsOn() {
        val panel = controls.substring(controls.indexOf("fun SendOptionsPanel("))
        assertTrue(panel.contains("R.string.plain_ctl_send_options_on"))
        assertTrue(panel.contains("flags.onFlags().map { sendFlagName(it) }"))
    }

    // ---- the switches ---------------------------------------------------------------------------------------------------------------

    @Test
    fun theSwitchesAreKeptInMemoryOnly_soThereIsNothingToWipeOrBackUp() {
        assertFalse(controls.contains("SharedPreferences") || controls.contains("AssistPrefs") || controls.contains("getSharedPreferences"))
        assertTrue(controls.contains("object TerminalSendSwitches"))
        assertTrue(controls.contains("by mutableStateOf(SendFlags())"))
    }

    @Test
    fun nothingResetsTheSwitchesAfterASend_theyStayOnUntilTurnedOff() {
        assertEquals("only the PLAIN WORDS switch and the owner of the state may reset them", 1,
            Regex("""TerminalSendSwitches\.reset\(\)""").findAll(noComments(source("ui/PlainWords.kt"))).count())
        for (file in RepoFiles.file(base).walkTopDown().filter { it.isFile && it.extension == "kt" }) {
            val name = file.name
            if (name == "PlainWords.kt" || name == "TerminalPlainControls.kt") continue
            assertFalse("$name resets the send switches", noComments(file.readText(Charsets.UTF_8)).contains("TerminalSendSwitches.reset()"))
        }
    }

    @Test
    fun turningPlainWordsOffTurnsTheSwitchesOff() {
        val plain = noComments(source("ui/PlainWords.kt"))
        val set = RepoFiles.declarationOf(plain, "set")
        assertTrue(set.contains("if (!value) TerminalSendSwitches.reset()"))
    }

    @Test
    fun aSendUsesTheTestedPolicy_andIsTheOnlyPlaceTheSwitchesAreRead() {
        assertTrue(design.contains("SendSwitchPolicy.effective(result.flags, TerminalSendSwitches.flags, plainWordsOn)"))
        // One definition and one call of the dispatch, so no send can skip the policy.
        assertEquals(2, Regex("""dispatchTerminalPhrase\(""").findAll(design).count())
        assertEquals("only the Terminal reads the switches", 1,
            RepoFiles.file(base).walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "TerminalPlainControls.kt" && it.name != "PlainWords.kt" }
                .count { noComments(it.readText(Charsets.UTF_8)).contains("TerminalSendSwitches.flags") })
    }

    @Test
    fun emergencyStillNeverAsksForConfirmation_typedOrSwitched() {
        val row = controls.substring(controls.indexOf("private fun SendSwitchRow("), controls.indexOf("internal fun PlainActionButton("))
        assertTrue(row.contains("onValueChange = { TerminalSendSwitches.set(flag, it) }"))
        assertFalse("a switch must flip in one tap", Regex("""Dialog|confirm|Confirm""").containsMatchIn(row))
        // The typed command is untouched.
        assertTrue(design.contains("\"/e\", \"/emergency\" -> flags = flags.copy(emergency = true)"))
    }

    @Test
    fun theTypedCommandsStillParseExactlyAsBefore() {
        assertTrue(design.contains("\"/q\", \"/quiet\" -> flags = flags.copy(quiet = true)"))
        assertTrue(design.contains("\"/n\", \"/nosave\" -> flags = flags.copy(skipLog = true)"))
        assertTrue(design.contains("\"/s\", \"/sticky\" -> flags = flags.copy(sticky = true)"))
        assertTrue(design.contains("first == \"/info\""))
        assertTrue(design.contains("first == \"/m\""))
        assertTrue(design.contains("first == \"/repair\""))
        assertTrue("/cls must still need CONFIRM when typed", design.contains("if (rest == \"confirm\") {\n            return TerminalPromptResult.ClearLog"))
    }

    // ---- what is shown, and only in plain mode ---------------------------------------------------------------------------------------

    @Test
    fun theTerminalControlsAreShownOnlyWhilePlainWordsIsOn() {
        val terminal = design.substring(design.indexOf("fun TerminalView("))
        assertTrue(terminal.contains("val plainWordsOn = LocalPlainWords.current"))
        for (call in listOf("TerminalToolsRow(", "SendOptionsPanel(")) {
            val at = terminal.indexOf(call)
            assertTrue("$call not found", at >= 0)
            val before = terminal.substring(maxOf(0, at - 60), at)
            assertTrue("$call is not inside an if (plainWordsOn) block: $before", before.contains("if (plainWordsOn) {"))
        }
    }

    // ---- CLEAR HISTORY ----------------------------------------------------------------------------------------------------------------

    @Test
    fun clearHistoryNeedsASecondTap_andCancelIsTheProminentButton() {
        val terminal = design.substring(design.indexOf("fun TerminalView("))
        // The button only opens the dialog.
        assertTrue(terminal.contains("onClearHistory = { showClearHistoryDialog = true }"))
        // The log is cleared in one function, called from the typed /cls CONFIRM and from the dialog's confirm button, and nowhere else.
        assertEquals(1, Regex("""TerminalLogStore\.clearAll\(""").findAll(terminal).count())
        assertEquals(3, Regex("""clearHistoryNow\(\)""").findAll(terminal).count())
        val dialog = controls.substring(controls.indexOf("fun ClearHistoryDialog("))
        val cancelAt = dialog.indexOf("NeonButton(cancel,")
        val deleteAt = dialog.indexOf("NeonButton(stringResource(R.string.plain_ctl_clear_history)")
        assertTrue("CANCEL must come first", cancelAt in 0 until deleteAt)
        assertTrue("the deleting button is red", dialog.substring(deleteAt).contains("mainColor = RadicalRed"))
        assertTrue("CANCEL uses the person's colour, not red", dialog.substring(cancelAt, deleteAt).contains("mainColor = primaryColor"))
    }

    // ---- /v and /t buttons ------------------------------------------------------------------------------------------------------------

    @Test
    fun theInsertButtonsUseTheSharedInsertionRule_andAddNothingTwice() {
        val terminal = design.substring(design.indexOf("fun TerminalView("))
        val fn = terminal.substring(terminal.indexOf("fun insertTriggerWord("), terminal.indexOf("fun submitPrompt()"))
        assertTrue(fn.contains("TextInsertion.insert(promptValue.text, selection.min, selection.max, word, InsertMode.WORD)"))
        assertTrue(fn.contains("if (!alreadyThere)"))
        assertTrue(terminal.contains("insertTriggerWord(\"/v\", variableTriggerRange != null)"))
        assertTrue(terminal.contains("insertTriggerWord(\"/t\", targetTriggerRange != null)"))
    }

    // ---- FIX PROBLEMS (/repair) --------------------------------------------------------------------------------------------------------

    @Test
    fun fixProblemsIsOneTapWithNoConfirmation_andRunsTheSameCodeAsTheTypedRepair() {
        // One function does the restart and writes the history line; the typed /repair and the button both call it.
        val repair = RepoFiles.declarationOf(design.replace("\ninternal fun", "\n    internal fun"), "repairBackgroundServices")
        assertTrue(repair.contains("restartBackgroundServices(context)"))
        assertTrue(repair.contains("logTerminalLocal(context, context.getString(R.string.term_services_restarted))"))
        assertEquals("the restart itself is called from one place", 1, Regex("""\brestartBackgroundServices\(context\)""").findAll(design).count())
        assertEquals("the definition plus the typed command", 2, Regex("""repairBackgroundServices\(""").findAll(design).count() - 0)
        val settings = noComments(source("settings/SettingsView.kt"))
        val at = settings.indexOf("AckTags.SETTINGS_FIX_PROBLEMS")
        assertTrue(at >= 0)
        val item = settings.substring(settings.lastIndexOf("item {", at), settings.indexOf("item {", at))
        assertTrue("shown only while PLAIN WORDS is on", item.contains("if (PlainWordsState.on) {"))
        assertTrue(item.contains("repairBackgroundServices(context)"))
        assertFalse("no confirmation, as the typed command", Regex("""Dialog|confirm|Confirm""").containsMatchIn(item))
        val sizes = Regex("""fontSize = (\d+)\.sp""").findAll(item).map { it.groupValues[1].toInt() }.toList()
        assertTrue("text under 12 sp: $sizes", sizes.all { it >= 12 })
    }

    // ---- the Type tab's button (/m) -----------------------------------------------------------------------------------------------------

    @Test
    fun theTypeTabButtonOpensTheSameClassicManualOverrideAsTheTypedCommand() {
        val main = noComments(source("MainActivity.kt"))
        // Both entrances set the same overlay and report the same HELP event.
        assertEquals(2, Regex("""showLegacyManualOverride = true""").findAll(main).count())
        assertEquals(2, Regex("""HelpEvent\.WatchInput\("MANUAL_OVERRIDE_OPENED"\)""").findAll(main).count())
        assertTrue("classic Manual Override needs the app's own header, so full screen is left first", main.contains("composerFullscreen = false\n                                    showLegacyManualOverride = true"))
        val composer = noComments(source("composer/StatementComposerView.kt"))
        assertTrue(composer.contains("if (LocalPlainWords.current && onShowManualOverride != null) {"))
        assertTrue(composer.contains("labelFor(LabelKey.MANUAL_OVERRIDE)"))
        assertTrue(composer.contains("AckTags.TYPE_CLASSIC_BUTTON"))
        // The plain wording the document proposes.
        assertEquals("TYPE AND SPEAK (CLASSIC)", strings["label_manual_override_plain"])
    }
}
