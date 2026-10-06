// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The limits statement touches files that cannot be compiled or run without the Android SDK (AssistPrefs, MainActivity, SettingsView, the banner and the
 * section). The words and the rule for where it may appear are plain Kotlin, tested in LimitsNoticeTest; this reads those files and holds them to the
 * promises: it is only a notice (it never blocks speech, asks a question, starts HELP or navigates), the banner is shown on the Terminal and Settings only and
 * dismissing it writes nothing but "seen", it is never seeded, never backed up, nothing in it is smaller than 12 sp, and the section is in SETTINGS.
 */
class LimitsNoticeWiringTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line.substringBefore(" // ")
    }

    // ---- the saved note -----------------------------------------------------------------------------------------------------------

    @Test
    fun theKeyInAssistPrefsMatchesTheCoreAndIsStable() {
        val prefs = source("data/AssistPrefs.kt")
        assertEquals(AssistSettings.KEY_LIMITS_NOTICE_SEEN, Regex("""const val KEY_LIMITS_NOTICE_SEEN = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        assertEquals("limits_notice_seen", AssistSettings.KEY_LIMITS_NOTICE_SEEN)
    }

    @Test
    fun readingItNeverWrites_andNothingStoredMeansTheBannerIsShownOnce() {
        val read = RepoFiles.declarationOf(source("data/AssistPrefs.kt"), "isLimitsNoticeSeen")
        assertFalse("reading must not write", read.contains("edit()"))
        assertTrue("with nothing stored it must read as not seen", read.contains("getBoolean(KEY_LIMITS_NOTICE_SEEN, false)"))
    }

    @Test
    fun dismissingWritesOnlyTheSeenNote_withCommit_andDoesNothingElse() {
        val write = RepoFiles.declarationOf(source("data/AssistPrefs.kt"), "markLimitsNoticeSeen")
        assertTrue(write.contains("putBoolean(KEY_LIMITS_NOTICE_SEEN, true).commit()"))
        assertEquals("exactly one preference is written", 1, Regex("""put(Boolean|String|Int|Long|Float)\(""").findAll(write).count())
        for (forbidden in listOf("startActivity", "helpManager", "viewMode", "Toast", "restartApp")) assertFalse(forbidden, write.contains(forbidden))
    }

    @Test
    fun theNoteIsNeverSeeded_soNoInstallStartsWithTheBannerAlreadyDismissed() {
        val prefs = source("data/AssistPrefs.kt")
        val seed = prefs.substring(prefs.indexOf("fun seedFreshInstallDefaults("), prefs.indexOf("fun isWordSuggestionsOn("))
        assertFalse(seed.contains("LIMITS"))
        assertFalse(AssistSettings.KEY_LIMITS_NOTICE_SEEN in AssistSettings.SEED_KEYS)
    }

    @Test
    fun theNoteIsPerPhone_soItIsNeverInABackup() {
        for (file in listOf("backup/AckBackup.kt", "backup/TransferManager.kt")) {
            val text = source(file)
            assertFalse("$file must not carry the limits note", text.contains("LimitsNotice") || text.contains("limitsNotice") || text.contains("limits_notice"))
        }
    }

    // ---- the banner ---------------------------------------------------------------------------------------------------------------

    @Test
    fun mainActivityAsksTheCoreRuleWithItsCurrentScreen_andTheBannerIsDrawnOnlyThere() {
        val main = noComments(source("MainActivity.kt"))
        assertTrue(main.contains("LimitsNotice.shouldShowBanner(limitsNoticeSeen, viewMode)"))
        assertEquals("the banner is drawn once", 1, Regex("""LimitsNoticeBanner\(""").findAll(main).count())
        val call = main.substring(main.indexOf("LimitsNotice.shouldShowBanner("))
        assertTrue("the banner call must sit inside the rule's if", call.indexOf("LimitsNoticeBanner(") in 1..120)
    }

    @Test
    fun theBannersDismissOnlyRemembersItWasSeen_itStartsNothingAndGoesNowhere() {
        val main = noComments(source("MainActivity.kt"))
        val from = main.indexOf("LimitsNoticeBanner(")
        val block = main.substring(from, main.indexOf("modifier = Modifier.padding(bottom = 8.dp)", from))
        val dismiss = block.substring(block.indexOf("onDismiss"))
        assertTrue(dismiss.contains("AssistPrefs.markLimitsNoticeSeen(context)"))
        assertTrue(dismiss.contains("limitsNoticeSeen = true"))
        for (forbidden in listOf("helpManager", "viewMode =", "startActivity", "Toast", "restartApp", "showBackup")) assertFalse(forbidden, dismiss.contains(forbidden))
    }

    @Test
    fun theBannerStateStartsFromTheSavedNote_soADismissedBannerStaysGoneAfterARestart() {
        val main = noComments(source("MainActivity.kt"))
        assertTrue(main.contains("var limitsNoticeSeen by remember { mutableStateOf(AssistPrefs.isLimitsNoticeSeen(context)) }"))
    }

    @Test
    fun theBannerNamesTheSettingsButtonThroughTheLabelTable_soItFollowsPlainWords() {
        val main = noComments(source("MainActivity.kt"))
        val from = main.indexOf("LimitsNoticeBanner(")
        assertTrue(main.substring(from, from + 300).contains("settingsName = labelFor(LabelKey.SETTINGS_ENTRY)"))
        // And the banner file itself reads no labels: the name is handed in.
        assertFalse(noComments(source("ui/LimitsNoticeBanner.kt")).contains("labelFor("))
    }

    // ---- both screens -------------------------------------------------------------------------------------------------------------

    private fun fontSizes(text: String): List<Double> =
        Regex("""fontSize\s*=\s*(\d+(?:\.\d+)?)\.sp""").findAll(text).map { it.groupValues[1].toDouble() }.toList()

    @Test
    fun nothingInTheBannerOrTheSectionIsSmallerThanTwelveSp() {
        for (file in listOf("ui/LimitsNoticeBanner.kt", "settings/AboutSection.kt")) {
            val text = noComments(source(file))
            assertTrue("$file must set its own sizes only at 12 sp or more", fontSizes(text).all { it >= 12.0 })
        }
        // The shared body text the screens use is 12 sp.
        assertTrue(fontSizes(noComments(source("settings/ConfirmDialogParts.kt"))).all { it >= 12.0 })
    }

    @Test
    fun theBannerAndTheSectionAreOnlyWords_noSoundNoAnimationNoNavigationNoHelp() {
        for (file in listOf("ui/LimitsNoticeBanner.kt", "settings/AboutSection.kt")) {
            val text = noComments(source(file))
            for (forbidden in listOf(
                "helpManager", "LocalHelpManager", "startActivity", "Intent(", "Toast", "viewMode", "animate", "Animated", "MediaPlayer", "ToneGenerator",
                "TextToSpeech", "OutputService", "vibrat", "HapticFeedback", "SharedPreferences", "AssistPrefs",
            )) assertFalse("$file must not use '$forbidden'", text.contains(forbidden))
        }
    }

    @Test
    fun bothScreensReadTheirWordsOnlyThroughTheCoreRule() {
        for (file in listOf("ui/LimitsNoticeBanner.kt", "settings/AboutSection.kt")) {
            val text = noComments(source(file))
            assertTrue("$file must read its words from LimitsNotice", text.contains("LimitsNotice.sentences("))
            assertFalse("$file must not type the statement itself", text.contains("SUBSTITUTE") || text.contains("SHARED AS-IS"))
            assertFalse("$file must not read a string resource by name; the core rule names them", text.contains("R.string"))
        }
    }

    // ---- the permanent section ------------------------------------------------------------------------------------------------------

    @Test
    fun theSectionIsInSettings_afterTheOtherSections_andOnlyShowsWords() {
        val settings = noComments(source("settings/SettingsView.kt"))
        assertEquals("the section is drawn once", 1, Regex("""AboutSection\(""").findAll(settings).count())
        assertTrue("it comes after the last existing section", settings.indexOf("AboutSection(") > settings.indexOf("AckTags.AUTOCOMPLETE_MANAGE_BTN)"))
        val section = noComments(source("settings/AboutSection.kt"))
        for (control in listOf("NeonButton", "clickable", "Switch", "Button(", "selectable", "onClick")) assertFalse("the section must not hold a control: $control", section.contains(control))
    }

    @Test
    fun everyStringTheStatementAddsIsUsedByTheCoreRule_andNothingIsLeftOver() {
        val defined = StringsXml.read(StringsXml.default).map { it.name }.filter { it.startsWith("about_") }.toSet()
        val used = (LimitsNotice.SENTENCES + LimitsNotice.ABOUT_TITLE + LimitsNotice.GOT_IT + "about_banner_where").toSet()
        assertEquals("defined but never used: ${defined - used}; used but not defined: ${used - defined}", used, defined)
    }
}
