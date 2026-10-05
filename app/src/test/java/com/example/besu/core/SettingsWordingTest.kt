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

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringPartANamesExists_inEveryLanguage_andNoneIsLeftUnused() {
        val sources = settings + "\n" + banner + "\n" + file("core/OutputRouteText.kt")
        val referenced = Regex("""R\.string\.((?:settings|overlay_banner)_[a-z_]+)""").findAll(settings + "\n" + banner).map { it.groupValues[1] }.toSet()
        val named = Regex(""""((?:settings|overlay_banner)_[a-z_]+)"""").findAll(sources).map { it.groupValues[1] }.toSet()
        val used = referenced + named
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = used.filter { it !in map }
            assertEquals("$tag: named but not defined: $missing", emptyList<String>(), missing)
        }
        val unused = partA.filter { it !in used }
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
        for (literal in goneFromSettings) assertFalse("SettingsView.kt still holds $literal", settings.contains(literal))
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
}
