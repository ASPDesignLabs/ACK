// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The words SETTINGS shows outside the sections that already had their own files (the backup, DELETE DATA, language, PLAIN WORDS, WORD SUGGESTIONS and AUTOCOMPLETE ones) read from string
 * resources, in the chosen language. SettingsView.kt cannot be compiled here, so this reads it: the old English literals are gone, every string it names exists and none is unused, each word
 * sits on the control that does what it says, and the logic strings that stay as they were (the stored route names, the view modes) were not touched. OutputRouteTextTest holds the decisions.
 *
 * Part A: AUDIO OUTPUT ROUTING, WATCH AUDIO FEEDBACK, VISUAL PROMPT DISPLAY and the display-permission warnings (the banner and the line under SILENT MODE).
 * Part B: the HARDWARE CONFIG sliders, the SHAKE KILL SWITCH and its test, the ENVIRONMENT SENSOR and the QUICK-ACCESS KEYS' field hints.
 * Part C: the TERMINAL LOG options, the VOICE RECORDINGS section and the PROFILES heading.
 */
class SettingsWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val settings get() = file("settings/SettingsView.kt")
    private val banner get() = file("ui/OverlayPermissionBanner.kt")
    private val shared get() = file("ui/SharedComponents.kt")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val partA = listOf(
        "settings_audio_routing_heading", "settings_force_speaker_desc", "settings_output_device", "settings_route_overridden", "settings_route_auto", "settings_route_auto_hint",
        "settings_route_watch", "settings_route_connected", "settings_route_not_connected", "settings_route_bt_device", "settings_route_bt_none",
        "settings_vox_desc", "settings_silent_desc", "settings_silent_no_display", "overlay_banner_text", "overlay_banner_allow",
        "settings_watch_audio_heading", "settings_tone_sharp", "settings_tone_clean", "settings_tone_soft", "settings_watch_volume",
        "settings_visual_heading", "settings_visual_desc", "settings_force_rotation", "settings_force_rotation_desc",
    )
    private val partB = listOf(
        "settings_hw_crown", "settings_label_value", "settings_hw_gravity_lock", "settings_hw_fire_grace", "settings_hw_fire_grace_desc", "settings_hw_wake_window", "settings_hw_wake_window_desc",
        "settings_hw_flyout", "settings_hw_flyout_desc", "settings_cryo_line",
        "settings_shake_desc", "settings_shake_sensitivity", "settings_btn_stop", "settings_btn_test", "settings_btn_scan", "settings_shake_detected", "settings_shake_armed", "settings_shake_test_note",
        "settings_env_authorize", "settings_open_settings", "settings_env_critical", "settings_env_warning", "settings_env_optimal", "settings_env_offline",
        "settings_qk_label_hint", "settings_qk_phrase_hint",
    )
    private val partC = listOf(
        "settings_term_hide_system", "settings_term_hide_system_desc", "settings_term_hide_path", "settings_term_hide_path_desc", "settings_term_mono", "settings_term_mono_desc",
        "settings_term_statusbox_color", "settings_term_statusbox_desc", "settings_term_retention_line", "settings_term_retention_desc",
        "settings_voice_heading", "settings_voice_manage_desc", "settings_voice_gain", "settings_voice_gain_desc", "settings_profiles_heading",
    )
    private val allNames get() = partA + partB + partC

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringTheScreenNamesExists_inEveryLanguage_andNoneIsLeftUnused() {
        val sources = settings + "\n" + banner + "\n" + file("core/OutputRouteText.kt")
        val referenced = Regex("""R\.string\.((?:settings|overlay_banner)_[a-z_]+)""").findAll(settings + "\n" + banner).map { it.groupValues[1] }.toSet()
        val named = Regex(""""((?:settings|overlay_banner)_[a-z_]+)"""").findAll(sources).map { it.groupValues[1] }.toSet()
        val used = referenced + named
        val plurals = mapOf("en" to StringsXml.plurals(StringsXml.default).keys) + StringsXml.translations().mapValues { StringsXml.plurals(it.value).keys }
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = used.filter { it !in map && it !in plurals.getValue(tag) }
            assertEquals("$tag: named but not defined: $missing", emptyList<String>(), missing)
        }
        val unused = allNames.filter { it !in used }
        assertTrue("defined but never used: $unused", unused.isEmpty())
    }

    @Test
    fun theOldEnglishLiteralsAreGone() {
        val goneFromSettings = listOf(
            "\"AUDIO OUTPUT ROUTING\"", "Routes speech to the device's built-in speaker", "\"OUTPUT DEVICE\"", "OVERRIDDEN BY FORCE SPEAKER ABOVE", "\"AUTO (SYSTEM DEFAULT)\"",
            "WHATEVER THE PHONE'S CURRENT AUDIO ROUTE IS", "\"ACK WATCH\"", "\"CONNECTED\"", "NOT CURRENTLY CONNECTED", "\"BLUETOOTH DEVICE\"", "NO BLUETOOTH DEVICES CURRENTLY CONNECTED",
            "Controls whether tutorial and guide narration", "Shows prompts as normal but never speaks them", "SILENT MODE IS ON AND DISPLAY PERMISSION IS OFF", "\"WATCH AUDIO FEEDBACK\"",
            "\"SHARP\"", "\"CLEAN\"", "\"SOFT\"", "\"WATCH VOLUME:", "\"VISUAL PROMPT DISPLAY\"", "Text/emoji/GIF prompts fill the screen", "\"FORCE DEVICE ROTATION\"", "OFF: rotate the prompt only",
        )
        val goneB = listOf(
            "\"CROWN RESISTANCE:", "\"GRAVITY LOCK:", "\"FIRE GRACE WINDOW:", "Extra time after a pose locks", "\"WAKE GESTURE WINDOW:", "How much time is allowed between each of the 3 wake twists",
            "\"TARGET FLYOUT TIMEOUT:", "How long the watch's Target Computer flyout", "} MIN\"", "Shake the phone to immediately stop", "\"SENSITIVITY:", "\"[STOP]\"", "\"[TEST]\"", "\"[SCAN]\"",
            "\"DETECTED ✓", "\"ARMED -- SHAKE THE PHONE\"", "This uses the real detector at the sensitivity above", "\"AUTHORIZE MIC SCAN\"", "\"OPEN SETTINGS\"", "\"CRITICAL: A.S.R.", "\"WARNING: MODERATE NOISE LEVEL\"",
            "\"OPTIMAL: ENVIRONMENT CLEAR\"", "\"MONITOR OFFLINE\"", "Text(\"LBL\")", "Text(\"TARGET PHRASE\")",
        )
        val goneC = listOf(
            "\"HIDE SYSTEM MESSAGES\"", "Filters boot, status, and error lines", "\"HIDE PATH RESOLUTION\"", "Filters out the verbose per-tag RESOLVE trace", "\"MONOSPACE TERMINAL\"", "Renders the Terminal screen",
            "} TEXT COLOR\"", "Color of the live TYPING / shared root variable strip", "\"LOG RETENTION:", "Entries older than this roll off", "Text(\"VOICE RECORDINGS\"", "Manage voice clips recorded for Quick Actions prompts",
            "\"MANAGE RECORDINGS\"", "\"RECORDING PLAYBACK GAIN:", "Trims volume for recorded voice prompts only", "Text(\"PROFILES\"", "DAY${'$'}{if",
        )
        for (literal in goneFromSettings + goneB + goneC) assertFalse("SettingsView.kt still holds $literal", settings.contains(literal))
        for (literal in listOf("DISPLAY PERMISSION IS OFF. MESSAGES ARE SPOKEN", "\"ALLOW\"")) assertFalse("OverlayPermissionBanner.kt still holds $literal", banner.contains(literal))
        assertTrue(settings.contains("import com.example.besu.core.OutputRouteText"))
        assertTrue(banner.contains("import com.example.besu.R"))
        assertTrue(banner.contains("import androidx.compose.ui.res.stringResource"))
    }

    // ---- each word sits on the control that does what it says -----------------------------------------------------------------------------

    private fun between(source: String, from: String, to: String): String {
        val a = source.indexOf(from)
        assertTrue("not found: $from", a >= 0)
        val b = source.indexOf(to, a)
        assertTrue("not found after it: $to", b > a)
        return source.substring(a, b)
    }

    @Test
    fun eachSwitchTitleAndDescriptionBelongToTheSwitchThatTheyDescribe() {
        fun toggle(label: String, desc: String, state: String) =
            Regex("""title = labelFor\(LabelKey\.$label\),\s*description = stringResource\(R\.string\.$desc\),\s*checked = $state,""").containsMatchIn(settings)
        assertTrue("FORCE SPEAKER", toggle("FORCE_SPEAKER", "settings_force_speaker_desc", "forceSpeaker"))
        assertTrue("GUIDE VOX", toggle("VOX", "settings_vox_desc", "guideVoxEnabled"))
        assertTrue("SILENT MODE", toggle("SILENT_MODE", "settings_silent_desc", "silentOutput"))
        // Each one saves what it shows.
        assertTrue(Regex("""forceSpeaker = enabled\s*syncPhoneAudio\(\)""").containsMatchIn(settings))
        assertTrue(Regex("""guideVoxEnabled = enabled\s*syncPhoneAudio\(\)""").containsMatchIn(settings))
        assertTrue(Regex("""silentOutput = enabled\s*syncPhoneAudio\(\)""").containsMatchIn(settings))
    }

    @Test
    fun eachRouteRowSetsTheRouteItIsNamed_andTheStoredRouteNamesWereNotTouched() {
        val picker = between(settings, "label = stringResource(R.string.settings_route_auto),", "if (connectedBtDevices.isEmpty()")
        assertTrue("the AUTO row", Regex("""label = stringResource\(R\.string\.settings_route_auto\),\s*hint = stringResource\(R\.string\.settings_route_auto_hint\),\s*isSelected = outputRouteMode == "AUTO",[\s\S]{0,200}?outputRouteMode = "AUTO"""").containsMatchIn(picker))
        assertTrue("the WATCH row", Regex("""label = stringResource\(R\.string\.settings_route_watch\),\s*hint = OutputRouteText\.watchHint\(words, isWatchConnected\),\s*isSelected = outputRouteMode == "WATCH",[\s\S]{0,200}?outputRouteMode = "WATCH"""").containsMatchIn(picker))
        assertTrue("a connected Bluetooth row", Regex("""hint = stringResource\(R\.string\.settings_route_connected\),\s*isSelected = outputRouteMode == "BLUETOOTH" &&[\s\S]{0,300}?outputRouteMode = "BLUETOOTH"""").containsMatchIn(picker))
        assertTrue("a saved pick that is not connected is shown but cannot be tapped", Regex("""label = OutputRouteText\.bluetoothName\(words, outputRouteBtLabel\),\s*hint = stringResource\(R\.string\.settings_route_not_connected\),\s*isSelected = true,[\s\S]{0,120}?enabled = false""").containsMatchIn(picker))
        assertTrue("nothing connected says so", Regex("""if \(connectedBtDevices\.isEmpty\(\) && !selectedBtMissing\) \{\s*Text\(\s*text = stringResource\(R\.string\.settings_route_bt_none\),""").containsMatchIn(settings))
        // The stored names the service reads are still the literals, in the same number of places as before.
        assertEquals(1, Regex("""outputRouteMode = "AUTO"""").findAll(settings).count())
        assertEquals(1, Regex("""outputRouteMode = "WATCH"""").findAll(settings).count())
        assertEquals(1, Regex("""outputRouteMode = "BLUETOOTH"""").findAll(settings).count())
        assertTrue(settings.contains("""prefs.getString("OUTPUT_ROUTE_MODE", "AUTO")"""))
    }

    @Test
    fun theOutputDeviceLineIsTheRouteSummary_namingTheSwitchByTheLabelItShows() {
        assertTrue(settings.contains("text = OutputRouteText.summary(words, forceSpeaker, outputRouteMode, outputRouteBtLabel, labelFor(LabelKey.FORCE_SPEAKER)),"))
        assertTrue("the picker heading", Regex("""text = stringResource\(R\.string\.settings_output_device\),\s*color = if \(forceSpeaker\) Color\.DarkGray""").containsMatchIn(settings))
    }

    @Test
    fun theOutputDevicePickerStaysShutAndUntappableWhileForceSpeakerIsOn() {
        // FORCE SPEAKER beats every route, so the picker is neither opened by a tap nor shown while it is on (the summary says why).
        assertTrue("the header is only tappable when FORCE SPEAKER is off", settings.contains(".clickable(enabled = !forceSpeaker) {"))
        assertTrue("the rows are only shown when it is off", settings.contains("if (outputDeviceExpanded && !forceSpeaker) {"))
        assertTrue("the arrow and the heading are dimmed while it is on", Regex("""color = if \(forceSpeaker\) Color\.DarkGray else primaryColor,\s*fontSize = 10\.sp""").containsMatchIn(settings))
    }

    @Test
    fun theThreeToneOptionsSetTheirOwnTone() {
        for ((id, name) in listOf(0 to "sharp", 1 to "clean", 2 to "soft")) {
            assertTrue("$name sets toneTheme = $id", Regex("""ThemeOption\($id, stringResource\(R\.string\.settings_tone_$name\), if\(toneTheme == $id\) $id else -1,[\s\S]{0,260}?\{ toneTheme = $id; syncAll\(\)""").containsMatchIn(settings))
        }
        assertTrue("the volume shows the slider's percentage", settings.contains("Text(stringResource(R.string.settings_watch_volume, (toneVolume * 100).toInt()),"))
        assertTrue(Regex("""settings_watch_volume[\s\S]{0,200}?Slider\(value = toneVolume""").containsMatchIn(settings))
    }

    @Test
    fun theForceRotationSwitchSaysOffThenOn_andSavesWhatItShows() {
        assertTrue(Regex("""stringResource\(R\.string\.settings_force_rotation\),\s*color = if \(forceDeviceRotation\) primaryColor""").containsMatchIn(settings))
        assertTrue("OFF is named first, then ON, as the English reads", settings.contains("stringResource(R.string.settings_force_rotation_desc, stringResource(R.string.common_off), stringResource(R.string.common_on)),"))
        assertTrue(Regex("""checked = forceDeviceRotation,\s*onCheckedChange = \{ enabled ->\s*forceDeviceRotation = enabled\s*OverlayDisplayPrefs\.setDeviceRotationEnabled\(context, enabled\)""").containsMatchIn(settings))
        assertTrue("the visual prompt sentence sits under its own heading", Regex("""settings_visual_heading\)[\s\S]{0,400}?settings_visual_desc""").containsMatchIn(settings))
    }

    @Test
    fun theSilentModeWarningOnlyShowsWhenBothAreTrue_andNamesSilentMode() {
        assertTrue(Regex("""if \(silentOutput && !canDrawOverlays\) \{[\s\S]{0,300}?stringResource\(R\.string\.settings_silent_no_display, labelFor\(LabelKey\.SILENT_MODE\)\),[\s\S]{0,100}?color = ErrorRed""").containsMatchIn(settings))
    }

    @Test
    fun theBannerSaysItsSentence_andAllowOpensTheSettingsPage() {
        assertTrue(Regex("""text = stringResource\(R\.string\.overlay_banner_text\),\s*color = ErrorRed""").containsMatchIn(banner))
        assertTrue(banner.contains("NeonButton(stringResource(R.string.overlay_banner_allow), mainColor = ErrorRed) { openOverlaySettings(context) }"))
        assertTrue("the banner is still not dismissible and still returns early when the permission is on", banner.contains("if (canDraw) return"))
    }

    @Test
    fun aToneOptionGrowsForALongerWord_insteadOfClipping() {
        val option = between(shared, "fun ThemeOption(id: Int, label: String, current: Int, activeColor: Color, modifier", "fun HeroButton(")
        assertTrue("a minimum width, not a fixed one", option.contains("modifier.widthIn(min = 60.dp)"))
        assertFalse("no fixed 60 dp width", option.contains(".width(60.dp)"))
    }

    @Test
    fun eachSliderLabelSitsOnItsOwnSlider_andTheNumbersAreFormattedAsBefore() {
        fun label(call: String, state: String, within: Int = 260) = Regex("""$call\)[\s\S]{0,$within}?Slider\(value = $state,""").containsMatchIn(settings)
        assertTrue("CROWN RESISTANCE", label("""settings_hw_crown, crownSens\.toInt\(\)""", "crownSens"))
        assertTrue("TWIST SENSITIVITY", label("""settings_label_value, labelFor\(LabelKey\.TWIST_SENS\), String\.format\("%\.1f", motTwist\)""", "motTwist"))
        assertTrue("GRAVITY LOCK", label("""settings_hw_gravity_lock, String\.format\("%\.1f", motPose\)""", "motPose"))
        assertTrue("FIRE GRACE WINDOW, its sentence in between", label("""settings_hw_fire_grace, fireGraceMs\.toInt\(\)\), color = Color\.Gray, fontSize = 10\.sp, fontFamily = FontFamily\.Monospace\)\s*Text\(\s*stringResource\(R\.string\.settings_hw_fire_grace_desc""", "fireGraceMs", 400))
        assertTrue("WAKE GESTURE WINDOW, its sentence in between", label("""settings_hw_wake_window, wakeWindowMs\.toInt\(\)\), color = Color\.Gray, fontSize = 10\.sp, fontFamily = FontFamily\.Monospace\)\s*Text\(\s*stringResource\(R\.string\.settings_hw_wake_window_desc""", "wakeWindowMs", 400))
        assertTrue("TARGET FLYOUT TIMEOUT, its sentence in between", label("""settings_hw_flyout, computerFlyoutTimeoutSec\.toInt\(\)\), color = Color\.Gray, fontSize = 10\.sp, fontFamily = FontFamily\.Monospace\)\s*Text\(\s*stringResource\(R\.string\.settings_hw_flyout_desc""", "computerFlyoutTimeoutSec", 400))
        assertTrue("AUTO-CRYO", label("""settings_cryo_line, labelFor\(LabelKey\.CRYO\), autoCryo\.toInt\(\)""", "autoCryo"))
        assertTrue("SENSITIVITY", label("""settings_shake_sensitivity, String\.format\("%\.1f", shakeThreshold\)""", "shakeThreshold"))
        // The decimals are formatted exactly as before (one place, the phone's own number format), not by the string.
        assertEquals(3, Regex("""String\.format\("%\.1f",""").findAll(settings).count())
        // The units stay in the strings as symbols, so the number is the only thing the code passes.
        assertFalse(Regex("""toInt\(\)\}ms|toInt\(\)\}s"|\} MIN""").containsMatchIn(settings))
    }

    @Test
    fun theShakeTestButtonsAndMessagesBelongToTheirState() {
        assertTrue("[STOP] or [TEST] flips the test", Regex("""stringResource\(if \(isShakeTestActive\) R\.string\.settings_btn_stop else R\.string\.settings_btn_test\),[\s\S]{0,700}?isShakeTestActive = !isShakeTestActive""").containsMatchIn(settings))
        assertTrue("DETECTED when the detector fired, ARMED while it waits", settings.contains("text = if (isShakeDetectedFlash) stringResource(R.string.settings_shake_detected, shakeDetectedCount) else stringResource(R.string.settings_shake_armed),"))
        assertTrue("the note is under the test box", Regex("""if \(isShakeTestActive\) \{[\s\S]{0,1800}?stringResource\(R\.string\.settings_shake_test_note\)""").containsMatchIn(settings))
        assertTrue("the description is under the heading", Regex("""labelFor\(LabelKey\.SHAKE_KILL\)[\s\S]{0,300}?stringResource\(R\.string\.settings_shake_desc\)""").containsMatchIn(settings))
    }

    @Test
    fun theEnvironmentSensorsButtonsAndStatusLinesBelongToTheirState() {
        assertTrue("[STOP] or [SCAN] flips the scan", Regex("""stringResource\(if \(isMonitoringActive\) R\.string\.settings_btn_stop else R\.string\.settings_btn_scan\),[\s\S]{0,500}?isMonitoringActive = !isMonitoringActive""").containsMatchIn(settings))
        assertTrue("AUTHORIZE asks for the microphone", Regex("""stringResource\(R\.string\.settings_env_authorize\),[\s\S]{0,700}?micPermissionLauncher\.launch\(Manifest\.permission\.RECORD_AUDIO\)""").containsMatchIn(settings))
        assertTrue("OPEN SETTINGS opens the app's settings page", Regex("""stringResource\(R\.string\.settings_open_settings\), Modifier\.weight\(1f\), mainColor = Color\.DarkGray\) \{\s*val intent = Intent\(android\.provider\.Settings\.ACTION_APPLICATION_DETAILS_SETTINGS\)""").containsMatchIn(settings))
        assertTrue("the three status lines keep their thresholds (80 and 65 dB)", Regex("""currentDb > 80f -> R\.string\.settings_env_critical\s*currentDb > 65f -> R\.string\.settings_env_warning\s*else -> R\.string\.settings_env_optimal""").containsMatchIn(settings))
        assertTrue("offline is what shows when the monitor is off", Regex("""\} else \{\s*Text\(stringResource\(R\.string\.settings_env_offline\)""").containsMatchIn(settings))
        // The colours chosen by the same thresholds were not touched.
        assertTrue(settings.contains("currentDb > 80f -> Color(0xFFFF0055)") && settings.contains("currentDb > 65f -> Color(0xFFFF9900)"))
    }

    @Test
    fun theQuickAccessKeyFieldHintsAreOnTheirOwnFields_andRecStaysTheEnglishAbbreviation() {
        assertTrue("the label field", Regex("""value = shortcut\.label,[\s\S]{0,1800}?placeholder = \{ Text\(stringResource\(R\.string\.settings_qk_label_hint\)\) \}""").containsMatchIn(settings))
        assertTrue("the phrase field", Regex("""value = shortcut\.phrase,[\s\S]{0,1500}?placeholder = \{ Text\(stringResource\(R\.string\.settings_qk_phrase_hint\)\) \}""").containsMatchIn(settings))
        assertTrue("REC and +REC are the button's text in every language (a narrow button, and manage_rec_empty names it REC)", settings.contains("""text = if (hasRecording) "REC" else "+REC","""))
    }

    @Test
    fun eachTerminalLogSwitchSaysItsOwnWords_andSavesWhatItShows() {
        fun toggle(title: String, desc: String, state: String, setter: String) =
            Regex("""title = stringResource\(R\.string\.$title\),\s*description = stringResource\(R\.string\.$desc\),\s*checked = $state,[\s\S]{0,400}?$state = enabled\s*TerminalLogStore\.$setter\(context, enabled\)""").containsMatchIn(settings)
        assertTrue("HIDE SYSTEM MESSAGES", toggle("settings_term_hide_system", "settings_term_hide_system_desc", "hideSystemMessages", "setHideSystemMessages"))
        assertTrue("HIDE PATH RESOLUTION", toggle("settings_term_hide_path", "settings_term_hide_path_desc", "hidePathTrace", "setHidePathTrace"))
        assertTrue("MONOSPACE TERMINAL", toggle("settings_term_mono", "settings_term_mono_desc", "monospaceTerminal", "setMonospaceEnabled"))
    }

    @Test
    fun theStatusboxColourLineAndTheRetentionLineSitOnTheirOwnControls() {
        assertTrue("the colour line names STATUSBOX by its label and sits above the swatches", Regex("""settings_term_statusbox_color, labelFor\(LabelKey\.STATUSBOX\)\),[\s\S]{0,300}?settings_term_statusbox_desc[\s\S]{0,700}?NeonPalette\.SWATCHES\.forEachIndexed""").containsMatchIn(settings))
        assertTrue("the retention line counts days in the language's plural form, then its sentence, then the slider", Regex("""settings_term_retention_line, words\.count\("settings_term_days", retentionDays\.toInt\(\)\)\),[\s\S]{0,300}?settings_term_retention_desc, TerminalLogStore\.MAX_ENTRIES\),[\s\S]{0,300}?Slider\(\s*value = retentionDays""").containsMatchIn(settings))
    }

    @Test
    fun theVoiceRecordingsSectionsWordsSitOnTheirControls() {
        assertTrue("heading, then the sentence, then the button that opens MANAGE RECORDINGS", Regex("""settings_voice_heading\)[\s\S]{0,400}?settings_voice_manage_desc[\s\S]{0,300}?stringResource\(R\.string\.manage_rec_title\),[\s\S]{0,300}?showManageRecordings = true""").containsMatchIn(settings))
        assertTrue("the gain line, its sentence, then the slider that saves it", Regex("""settings_voice_gain, recordingGainPercent\.toInt\(\)\),[\s\S]{0,300}?settings_voice_gain_desc[\s\S]{0,300}?Slider\(\s*value = recordingGainPercent[\s\S]{0,400}?VoiceRecordingRepository\.setPlaybackGainPercent""").containsMatchIn(settings))
        // The button is the dialog's own title, from the same string, so the two can never be called different things.
        assertTrue(file("settings/ManageRecordingsDialog.kt").contains("R.string.manage_rec_title"))
        assertEquals("MANAGE RECORDINGS", english.getValue("manage_rec_title"))
    }

    @Test
    fun theProfilesHeadingIsAboveTheProfileWarningSwitch() {
        assertTrue(Regex("""settings_profiles_heading\)[\s\S]{0,600}?profileWarningOffered""").containsMatchIn(settings))
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------------------

    @Test
    fun theEnglishIsHeldExactly() {
        val expected = mapOf(
            "settings_audio_routing_heading" to "AUDIO OUTPUT ROUTING",
            "settings_force_speaker_desc" to "Routes speech to the device's built-in speaker instead of the current audio route.",
            "settings_output_device" to "OUTPUT DEVICE", "settings_route_auto" to "AUTO (SYSTEM DEFAULT)", "settings_route_auto_hint" to "WHATEVER THE PHONE'S CURRENT AUDIO ROUTE IS",
            "settings_route_watch" to "ACK WATCH", "settings_route_connected" to "CONNECTED", "settings_route_bt_device" to "BLUETOOTH DEVICE",
            "settings_route_bt_none" to "NO BLUETOOTH DEVICES CURRENTLY CONNECTED", "settings_vox_desc" to "Controls whether tutorial and guide narration is spoken aloud.",
            "settings_silent_desc" to "Shows prompts as normal but never speaks them out loud -- for places where sound itself is the problem. Emergency messages and tutorial narration are never silenced.",
            "overlay_banner_text" to "DISPLAY PERMISSION IS OFF. MESSAGES ARE SPOKEN BUT NOT SHOWN ON SCREEN.", "overlay_banner_allow" to "ALLOW",
            "settings_watch_audio_heading" to "WATCH AUDIO FEEDBACK", "settings_tone_sharp" to "SHARP", "settings_tone_clean" to "CLEAN", "settings_tone_soft" to "SOFT",
            "settings_visual_heading" to "VISUAL PROMPT DISPLAY",
            "settings_visual_desc" to "Text/emoji/GIF prompts fill the screen and rotate their content in place so words display large without wrapping.",
            "settings_force_rotation" to "FORCE DEVICE ROTATION",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
        assertEquals("OVERRIDDEN BY FORCE SPEAKER ABOVE", EnglishText.get("settings_route_overridden", "FORCE SPEAKER"))
        assertEquals("SILENT MODE IS ON AND DISPLAY PERMISSION IS OFF: A MESSAGE WOULD BE NEITHER SPOKEN NOR SHOWN.", EnglishText.get("settings_silent_no_display", "SILENT MODE"))
        assertEquals("WATCH VOLUME: 80%", EnglishText.get("settings_watch_volume", 80))
        assertEquals("OFF: rotate the prompt only. ON: rotate the whole screen (old behavior).", EnglishText.get("settings_force_rotation_desc", "OFF", "ON"))
        assertTrue("the safety sentence and the banner agree on the name of the permission", english.getValue("overlay_banner_text").startsWith("DISPLAY PERMISSION IS OFF.") && english.getValue("settings_silent_no_display").contains("DISPLAY PERMISSION IS OFF"))
    }

    @Test
    fun theArgumentsAreWhereTheCodePutsThem() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertTrue("$tag: overridden names the switch", map.getValue("settings_route_overridden").contains("%1\$s"))
            assertTrue("$tag: the silent warning names SILENT MODE", map.getValue("settings_silent_no_display").contains("%1\$s"))
            assertTrue("$tag: the volume takes the percentage as a number and a literal percent sign", map.getValue("settings_watch_volume").contains("%1\$d%%"))
            val rotation = map.getValue("settings_force_rotation_desc")
            assertTrue("$tag: OFF then ON arguments", rotation.contains("%1\$s") && rotation.contains("%2\$s") && rotation.indexOf("%1\$s") < rotation.indexOf("%2\$s"))
            for (name in partA - setOf("settings_route_overridden", "settings_silent_no_display", "settings_watch_volume", "settings_force_rotation_desc")) {
                assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
            }
        }
    }

    @Test
    fun wordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "settings_route_connected" to "settings_route_not_connected", "settings_route_auto" to "settings_route_watch", "settings_route_watch" to "settings_route_bt_device",
            "settings_tone_sharp" to "settings_tone_clean", "settings_tone_clean" to "settings_tone_soft", "settings_tone_sharp" to "settings_tone_soft",
            "settings_force_speaker_desc" to "settings_vox_desc", "settings_vox_desc" to "settings_silent_desc", "settings_visual_heading" to "settings_watch_audio_heading",
            "settings_audio_routing_heading" to "settings_output_device", "overlay_banner_allow" to "common_cancel", "overlay_banner_allow" to "common_close",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
    }

    @Test
    fun theRotationSentenceTakesOffAndOnFromTheSharedWords() {
        // The rotation sentence takes OFF and ON from the shared words the toggles themselves show, so a sentence and a switch can never disagree.
        for ((tag, map) in translations) {
            val said = FileText(tag).get("settings_force_rotation_desc", map.getValue("common_off"), map.getValue("common_on"))
            assertTrue("$tag: OFF ($said)", said.contains(map.getValue("common_off")))
            assertTrue("$tag: ON ($said)", said.contains(map.getValue("common_on")))
        }
    }

    @Test
    fun theEnglishOfPartBIsHeldExactly() {
        val expected = mapOf(
            "settings_hw_fire_grace_desc" to "Extra time after a pose locks and goes quiet before it fires. Tap the watch face anytime before then to cancel instead.",
            "settings_hw_wake_window_desc" to "How much time is allowed between each of the 3 wake twists. Higher gives more room if your hand isn't perfectly steady.",
            "settings_hw_flyout_desc" to "How long the watch's Target Computer flyout (tap-tap-hold on a Quick Actions deck) waits with no interaction before closing itself.",
            "settings_shake_desc" to "Shake the phone to immediately stop whatever it's currently saying or showing -- a backstop for a mistaken watch fire or a wrong tap.",
            "settings_btn_stop" to "[STOP]", "settings_btn_test" to "[TEST]", "settings_btn_scan" to "[SCAN]", "settings_shake_armed" to "ARMED -- SHAKE THE PHONE",
            "settings_shake_test_note" to "This uses the real detector at the sensitivity above -- shake exactly as hard as you would to actually cut off output, and adjust the slider until that feels right.",
            "settings_env_authorize" to "AUTHORIZE MIC SCAN", "settings_open_settings" to "OPEN SETTINGS", "settings_env_critical" to "CRITICAL: A.S.R. INTERFERENCE HIGH",
            "settings_env_warning" to "WARNING: MODERATE NOISE LEVEL", "settings_env_optimal" to "OPTIMAL: ENVIRONMENT CLEAR", "settings_env_offline" to "MONITOR OFFLINE",
            "settings_qk_label_hint" to "LBL", "settings_qk_phrase_hint" to "TARGET PHRASE",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
        assertEquals("CROWN RESISTANCE: LEVEL 3", EnglishText.get("settings_hw_crown", 3))
        assertEquals("TWIST SENSITIVITY: 7.0", EnglishText.get("settings_label_value", "TWIST SENSITIVITY", "7.0"))
        assertEquals("GRAVITY LOCK: 6.0", EnglishText.get("settings_hw_gravity_lock", "6.0"))
        assertEquals("FIRE GRACE WINDOW: 500ms", EnglishText.get("settings_hw_fire_grace", 500))
        assertEquals("WAKE GESTURE WINDOW: 1800ms", EnglishText.get("settings_hw_wake_window", 1800))
        assertEquals("TARGET FLYOUT TIMEOUT: 10s", EnglishText.get("settings_hw_flyout", 10))
        assertEquals("AUTO-CRYO: 10 MIN", EnglishText.get("settings_cryo_line", "AUTO-CRYO", 10))
        assertEquals("SENSITIVITY: 15.0 (lower = easier to trigger)", EnglishText.get("settings_shake_sensitivity", "15.0"))
        assertEquals("DETECTED ✓  (4)", EnglishText.get("settings_shake_detected", 4))
    }

    @Test
    fun partBArgumentsAreWhereTheCodePutsThem() {
        val numbers = listOf("settings_hw_crown", "settings_hw_fire_grace", "settings_hw_wake_window", "settings_hw_flyout", "settings_shake_detected")
        val strings = listOf("settings_hw_gravity_lock", "settings_shake_sensitivity")
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in numbers) assertTrue("$tag/$name takes a whole number", map.getValue(name).contains("%1\$d"))
            for (name in strings) assertTrue("$tag/$name takes a formatted number", map.getValue(name).contains("%1\$s"))
            assertTrue("$tag: label then value", map.getValue("settings_label_value").let { it.contains("%1\$s") && it.contains("%2\$s") && it.indexOf("%1\$s") < it.indexOf("%2\$s") })
            assertTrue("$tag: the cryo line takes a label then minutes", map.getValue("settings_cryo_line").let { it.contains("%1\$s") && it.contains("%2\$d") })
            // The units are symbols that stay as they are in every language, so a number is never read with a translated unit stuck on it.
            assertTrue("$tag: ms", map.getValue("settings_hw_fire_grace").contains("%1\$dms") && map.getValue("settings_hw_wake_window").contains("%1\$dms"))
            assertTrue("$tag: s", map.getValue("settings_hw_flyout").contains("%1\$ds"))
            for (name in partB - numbers - strings - setOf("settings_label_value", "settings_cryo_line")) {
                assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
            }
        }
    }

    @Test
    fun theThreeBracketedButtonsKeepTheirBrackets_andDifferInEveryLanguage() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val words = listOf("settings_btn_stop", "settings_btn_test", "settings_btn_scan").map { map.getValue(it) }
            for (w in words) assertTrue("$tag: $w keeps its brackets", w.startsWith("[") && w.endsWith("]"))
            assertEquals("$tag: three buttons, three words: $words", 3, words.toSet().size)
        }
    }

    @Test
    fun partBWordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "settings_shake_detected" to "settings_shake_armed", "settings_env_authorize" to "settings_open_settings", "settings_qk_label_hint" to "settings_qk_phrase_hint",
            "settings_env_critical" to "settings_env_warning", "settings_env_warning" to "settings_env_optimal", "settings_env_critical" to "settings_env_optimal",
            "settings_env_offline" to "settings_env_optimal", "settings_hw_fire_grace_desc" to "settings_hw_wake_window_desc", "settings_hw_wake_window_desc" to "settings_hw_flyout_desc",
            "settings_hw_fire_grace" to "settings_hw_wake_window", "settings_hw_wake_window" to "settings_hw_flyout", "settings_shake_desc" to "settings_shake_test_note",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
    }

    @Test
    fun theFlyoutSentenceNamesTargetComputerAndQuickActionsTheWayTheLanguagesOwnLabelsDo() {
        for ((tag, map) in translations) {
            val said = map.getValue("settings_hw_flyout_desc")
            assertTrue("$tag: ${map.getValue("label_target_computer")} is in '$said'", said.contains(map.getValue("label_target_computer")))
            assertTrue("$tag: ${map.getValue("label_deck_type_quick")} is in '$said'", said.contains(map.getValue("label_deck_type_quick")))
        }
    }

    @Test
    fun theThreeStatusLinesNameTheirLevelFirst_asTheEnglishDoes() {
        // CRITICAL, WARNING and OPTIMAL come first, followed by a colon, in every language: the level is read before the explanation.
        for ((tag, map) in listOf("en" to english) + translations.toList()) for (name in listOf("settings_env_critical", "settings_env_warning", "settings_env_optimal")) {
            assertTrue("$tag/$name: a level, then a colon: ${map.getValue(name)}", Regex("""^[^:]{2,20}:""").containsMatchIn(map.getValue(name)))
        }
    }

    @Test
    fun theEnglishOfPartCIsHeldExactly() {
        val expected = mapOf(
            "settings_term_hide_system" to "HIDE SYSTEM MESSAGES",
            "settings_term_hide_system_desc" to "Filters boot, status, and error lines out of the Terminal view. The underlying log is untouched -- switch off to see them again.",
            "settings_term_hide_path" to "HIDE PATH RESOLUTION",
            "settings_term_hide_path_desc" to "Filters out the verbose per-tag RESOLVE trace logged every time a Matrix phrase plays, independent of the toggle above.",
            "settings_term_mono" to "MONOSPACE TERMINAL",
            "settings_term_mono_desc" to "Renders the Terminal screen -- log rows, the prompt line, command output -- in a true monospace font so columns line up like a real terminal. Off by default to keep the existing look.",
                        "settings_voice_heading" to "VOICE RECORDINGS", "settings_voice_manage_desc" to "Manage voice clips recorded for Quick Actions prompts.",
            "settings_voice_gain_desc" to "Trims volume for recorded voice prompts only, on top of the master gain above -- everything else (synthesized speech) is unaffected.",
            "settings_profiles_heading" to "PROFILES",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
        assertEquals("STATUSBOX TEXT COLOR", EnglishText.get("settings_term_statusbox_color", "STATUSBOX"))
        // The sentence names the Terminal's TYPING strip by the word the strip itself shows, handed in as an argument (the strip is translated now).
        assertEquals("Color of the live TYPING / shared root variable strip above the Terminal prompt.", EnglishText.get("settings_term_statusbox_desc", english.getValue("term_typing")))
        assertEquals("LOG RETENTION: 7 DAYS (ROLLING)", EnglishText.get("settings_term_retention_line", EnglishText.count("settings_term_days", 7)))
        assertEquals("LOG RETENTION: 1 DAY (ROLLING)", EnglishText.get("settings_term_retention_line", EnglishText.count("settings_term_days", 1)))
        assertEquals("Entries older than this roll off on a continuous window, not a calendar day -- up to 400 kept either way.", EnglishText.get("settings_term_retention_desc", 400))
        assertEquals("RECORDING PLAYBACK GAIN: 85%", EnglishText.get("settings_voice_gain", 85))
        // The number the sentence is given is the store's own constant (400 when this was written), not a typed number.
        assertTrue(RepoFiles.read("$base/data/TerminalLogStore.kt").contains("const val MAX_ENTRIES = 400"))
    }

    @Test
    fun partCArgumentsAreWhereTheCodePutsThem() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertTrue("$tag: the colour line names STATUSBOX", map.getValue("settings_term_statusbox_color").contains("%1\$s"))
            assertTrue("$tag: the retention line takes the worded days", map.getValue("settings_term_retention_line").contains("%1\$s"))
            assertTrue("$tag: the retention sentence takes the number kept", map.getValue("settings_term_retention_desc").contains("%1\$d"))
            assertTrue("$tag: the gain takes a percentage and a literal percent sign", map.getValue("settings_voice_gain").contains("%1\$d%%"))
            assertTrue("$tag: the strip's description takes the word on the strip", map.getValue("settings_term_statusbox_desc").contains("%1\$s"))
            for (name in partC - setOf("settings_term_statusbox_color", "settings_term_statusbox_desc", "settings_term_retention_line", "settings_term_retention_desc", "settings_voice_gain")) {
                assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
            }
        }
    }

    @Test
    fun theTraceWordStaysEnglish_andTheStripWordIsHandedInBecauseTheStripIsTranslated() {
        // RESOLVE is the word on the PATH trace lines, which the data layer writes (CommandRepository.debugResolvedPhrase) in English, so the sentence keeps it.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertTrue("$tag: RESOLVE", Regex("""\bRESOLVE\b""").containsMatchIn(map.getValue("settings_term_hide_path_desc")))
            // TYPING is the word on the Terminal's own strip, which is translated now (term_typing): the sentence takes it as an argument and no longer types it.
            assertFalse("$tag: no typed TYPING left", Regex("""\bTYPING\b""").containsMatchIn(map.getValue("settings_term_statusbox_desc")))
        }
        val settings = RepoFiles.read("$base/settings/SettingsView.kt")
        assertTrue(settings.contains("stringResource(R.string.settings_term_statusbox_desc, stringResource(R.string.term_typing)),"))
    }

    @Test
    fun theStatusboxColourLineNamesTheLabelItWasGiven_inEveryLanguage() {
        for ((tag, map) in translations) {
            assertTrue("$tag: ${map.getValue("settings_term_statusbox_color")}", FileText(tag).get("settings_term_statusbox_color", map.getValue("label_statusbox")).contains(map.getValue("label_statusbox")))
        }
    }

    @Test
    fun theRetentionLineCountsDaysAndSaysItIsRolling_inEveryLanguage() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val days = f.count("settings_term_days", 7)
            val line = f.get("settings_term_retention_line", days)
            assertTrue("$tag: the number is in the line ($line)", line.contains("7"))
            assertFalse("$tag: a resource name leaked: $line", line.contains("settings_"))
            assertNotEquals("$tag: still English", "LOG RETENTION: 7 DAYS (ROLLING)", line)
        }
    }

    @Test
    fun partCWordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "settings_term_hide_system" to "settings_term_hide_path", "settings_term_hide_path" to "settings_term_mono", "settings_term_hide_system_desc" to "settings_term_hide_path_desc",
            "settings_term_mono_desc" to "settings_term_statusbox_desc", "settings_voice_heading" to "settings_profiles_heading", "settings_voice_manage_desc" to "settings_voice_gain_desc",
            "settings_term_retention_line" to "settings_term_retention_desc",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
    }
}
