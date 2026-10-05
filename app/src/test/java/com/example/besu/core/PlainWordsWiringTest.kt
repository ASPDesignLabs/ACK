// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * PLAIN WORDS touches files that cannot be compiled or run without the Android SDK (PlainWords.kt, MainActivity, SettingsView, the HELP dialogs,
 * AssistPrefs, TransferManager). The rules are in plain Kotlin and tested elsewhere (PlainLabelsTest, HelpPlaceholdersTest, AssistSettingsTest);
 * this reads those files and holds them to the promises: off for everyone and never seeded, instant with no restart, the switch always findable and
 * worded the same in both modes, HELP showing the words the person sees, and the setting backed up and described.
 */
class PlainWordsWiringTest {

    private fun source(name: String) = RepoFiles.read("app/src/main/java/com/example/besu/$name")

    private fun code(text: String): String =
        text.replace(Regex("/\\*.*?\\*/", RegexOption.DOT_MATCHES_ALL), "").lines().joinToString("\n") { it.substringBefore("//") }

    /** A top-level function: from `fun name(` to the next declaration that starts in column 0. (Brace counting would be fooled by a "{{" in a string.) */
    private fun topLevel(text: String, name: String): String {
        val at = text.indexOf("fun $name(")
        assertTrue("fun $name( not found", at >= 0)
        val next = Regex("""\n(@Composable|fun |private fun |object |val |class |/\*\*)""").find(text, at + 1)
        return text.substring(at, next?.range?.first ?: text.length)
    }

    private fun bodyOf(text: String, name: String): String {
        val at = text.indexOf("fun $name(")
        assertTrue("fun $name( not found", at >= 0)
        val open = text.indexOf('{', text.indexOf(')', at))
        var depth = 0
        var i = open
        while (i < text.length) {
            if (text[i] == '{') depth++
            if (text[i] == '}') { depth--; if (depth == 0) return text.substring(open + 1, i) }
            i++
        }
        error("unbalanced braces in $name")
    }

    /** The PLAIN WORDS item of SETTINGS: from its first line to the next `item {` (FIX PROBLEMS and the other sections are items of their own). */
    private fun plainItem(settings: String): String {
        val start = settings.indexOf("val plainOn = PlainWordsState.on")
        assertTrue("the PLAIN WORDS item was not found", start >= 0)
        val end = settings.indexOf("item {", start)
        assertTrue(end > start)
        return settings.substring(start, end)
    }

    // ---- the saved choice --------------------------------------------------------------------------------------------------------

    @Test
    fun theKeysMatchTheCore_andReadingFallsBackToOff() {
        val prefs = source("data/AssistPrefs.kt")
        assertEquals(AssistSettings.KEY_PLAIN_WORDS, Regex("""const val KEY_PLAIN_WORDS = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        assertEquals(AssistSettings.KEY_PLAIN_WORDS_OFFER_DISMISSED, Regex("""const val KEY_PLAIN_WORDS_OFFER_DISMISSED = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        assertTrue(RepoFiles.declarationOf(prefs, "isPlainWordsOn").contains("AssistSettings.PLAIN_WORDS_FALLBACK"))
    }

    @Test
    fun itIsNeverSeeded_soNoInstallEverStartsWithItOn() {
        assertFalse(bodyOf(source("data/AssistPrefs.kt"), "seedFreshInstallDefaults").contains("PLAIN", ignoreCase = true))
        assertFalse(bodyOf(source("data/InstallState.kt"), "seedFreshInstallDefaults").contains("PlainWords"))
    }

    @Test
    fun choosingEitherWayAnswersTheOffer_andIsWrittenWithCommit() {
        val body = bodyOf(source("data/AssistPrefs.kt"), "setPlainWords")
        assertTrue(body.contains("KEY_PLAIN_WORDS"))
        assertTrue("choosing in SETTINGS must retire the offer", body.contains("KEY_PLAIN_WORDS_OFFER_DISMISSED"))
        assertTrue(body.contains(".commit()"))
    }

    @Test
    fun notNowChangesNoSetting() {
        val body = bodyOf(source("data/AssistPrefs.kt"), "dismissPlainWordsOffer")
        assertTrue(body.contains("KEY_PLAIN_WORDS_OFFER_DISMISSED"))
        assertFalse(body.contains("KEY_PLAIN_WORDS,"))
    }

    // ---- instant, in place, no restart ----------------------------------------------------------------------------------------------

    @Test
    fun theModeIsComposeState_readAtTheRoot_andProvidedBesideTheHelpManager() {
        // Raw text: code() would trip over the "*/*" in a file-picker call in this file.
        val main = source("MainActivity.kt")
        val provider = main.substring(main.indexOf("CompositionLocalProvider("), main.indexOf("CompositionLocalProvider(") + 260)
        assertTrue(provider.contains("LocalHelpManager provides helpManager"))
        assertTrue(provider.contains("LocalPlainWords provides PlainWordsState.on"))
        assertTrue("the saved choice is read before the first draw", main.contains("PlainWordsState.load(context)"))
        val plain = code(source("ui/PlainWords.kt"))
        assertTrue(plain.contains("by mutableStateOf("))
    }

    @Test
    fun flippingItNeverRestartsTheApp_theRestartPatternIsNotUsed() {
        assertFalse(code(source("ui/PlainWords.kt")).contains("restartApp"))
        val settings = code(source("settings/SettingsView.kt"))
        val item = plainItem(settings)
        assertFalse(item.contains("restartApp"))
        assertFalse(item.contains("pendingRestart"))
        assertFalse(item.contains("Toast"))
    }

    @Test
    fun theSwitchWritesTheChoice_andUpdatesTheLiveStateSoTheChangeIsInstant() {
        val plain = code(source("ui/PlainWords.kt"))
        val set = RepoFiles.declarationOf(plain, "set")
        assertTrue(set.contains("AssistPrefs.setPlainWords(context, value)"))
        assertTrue("the live state must be updated, or nothing redraws", set.contains("on = value"))
        assertTrue(RepoFiles.declarationOf(plain, "load").contains("AssistPrefs.isPlainWordsOn(context)"))
    }

    @Test
    fun aLabelReadsTheModeTheLanguageAndTheRightResourceName() {
        val plain = code(source("ui/PlainWords.kt"))
        val label = topLevel(plain, "labelFor")
        assertTrue(label.contains("LocalPlainWords.current"))
        assertTrue("a change of language re-reads the resource", label.contains("LocalConfiguration.current"))
        assertTrue(plain.contains("key.resourceName(plain)"))
        assertTrue("a missing name is visible, not a crash", RepoFiles.declarationOf(plain, "resolve").contains("?: key.name"))
    }

    // ---- the switch ---------------------------------------------------------------------------------------------------------------

    @Test
    fun theSwitchIsTheFirstThingInSettings_andIsWordedTheSameInBothModes() {
        val settings = code(source("settings/SettingsView.kt"))
        val switchAt = settings.indexOf("AckTags.PLAIN_WORDS_SWITCH")
        val firstSection = settings.indexOf("Text(stringResource(R.string.settings_audio_routing_heading)")
        assertTrue("PLAIN WORDS must come before every other section", switchAt in 0 until firstSection)
        val item = plainItem(settings)
        assertTrue(item.contains("stringResource(if (plainOn) R.string.plain_words_switch_on else R.string.plain_words_switch_off)"))
        assertFalse("the switch must not go through the label table", item.contains("labelFor(LabelKey"))
        assertTrue(item.contains("PlainWordsState.set(context, !plainOn)"))
    }

    @Test
    fun theOfferIsShownOnlyUnderTheCoreRule_turnsOnOnlyWhenTapped_andNotNowChangesNothing() {
        val settings = code(source("settings/SettingsView.kt"))
        val item = plainItem(settings)
        assertTrue(item.contains("AssistSettings.shouldOfferPlainWords("))
        val notNow = item.substring(item.indexOf("R.string.plain_words_not_now"))
        assertTrue(notNow.substring(0, 200).contains("AssistPrefs.dismissPlainWordsOffer(context)"))
        assertFalse(notNow.substring(0, 200).contains("PlainWordsState.set"))
    }

    @Test
    fun theSwitchAndOfferTextIs12spOrLarger() {
        val settings = code(source("settings/SettingsView.kt"))
        val item = plainItem(settings)
        val sizes = Regex("""fontSize = (\d+)\.sp""").findAll(item).map { it.groupValues[1].toInt() }.toList()
        assertTrue(sizes.isNotEmpty())
        assertTrue("text under 12 sp: $sizes", sizes.all { it >= 12 })
    }

    // ---- HELP shows the words the person sees ----------------------------------------------------------------------------------------

    @Test
    fun everyPlaceHelpTextIsDrawnGoesThroughHelpText() {
        val coach = code(source("help/HelpCoachDialog.kt"))
        assertTrue(coach.contains("text = helpText(step.title)"))
        assertTrue(coach.contains("text = helpText(step.body)"))
        assertFalse("raw step text must not be drawn", Regex("""text = step\.(title|body)\b""").containsMatchIn(coach))
        // The "awaiting input" line holds a placeholder too.
        assertTrue(coach.contains("text = helpText(helpActionInstruction(step.action))"))
        val menu = code(source("help/HelpMenuDialog.kt"))
        assertTrue(menu.contains("text = helpText(module.title)"))
        assertTrue(menu.contains("text = helpText(module.summary)"))
        // A family's names come from string resources and may hold a placeholder, so each is read through the text source and then through helpText.
        assertTrue(menu.contains("helpText(HelpMenuText.categoryTitle(text, selectedCategory.name))"))
        assertTrue(menu.contains("helpText(HelpMenuText.categorySubtitle(text, selectedCategory.name))"))
        assertTrue(menu.contains("helpText(HelpMenuText.categoryChip(text, category.name))"))
        assertFalse(Regex("""text = module\.(title|summary)\b""").containsMatchIn(menu))
    }

    @Test
    fun theTextHelpSpeaksAloudIsSubstitutedToo_soBracesAreNeverRead() {
        // Raw text, with the comments that mention step.title removed line by line (code() would trip over a "*/*" literal in this file).
        val main = source("MainActivity.kt").lines().joinToString("\n") { it.substringBefore("//") }
        val at = main.indexOf("val spokenText = buildString")
        assertTrue("the spoken text block was not found", at >= 0)
        val from = main.lastIndexOf("fun spoken(", at)
        assertTrue("fun spoken( was not found before it", from >= 0)
        val block = main.substring(from, at + 200)
        assertTrue(block.contains("HelpPlaceholders.substitute("))
        assertTrue(block.contains("append(spoken(step.title))"))
        assertTrue(block.contains("append(spoken(step.body))"))
        assertFalse("raw step text must not be spoken", Regex("""append\(step\.(title|body)\)""").containsMatchIn(main))
    }

    @Test
    fun helpTextLeavesATextWithNoPlaceholderAloneAndSubstitutesThroughTheCore() {
        val plain = code(source("ui/PlainWords.kt"))
        val help = topLevel(plain, "helpText")
        assertTrue(help.contains("""if (!text.contains("{{")) return text"""))
        assertTrue(help.contains("HelpPlaceholders.substitute("))
    }

    @Test
    fun theHelpIdsAndTagsAreNeverTouchedByPlaceholders() {
        // A placeholder may only sit in text a person reads, never in an id, a tag or a destination.
        val dir = RepoFiles.file("app/src/main/java/com/example/besu/help")
        for (file in dir.listFiles()!!.filter { it.extension == "kt" }) {
            for (line in file.readLines()) {
                if (!line.contains("{{")) continue
                val t = line.trim()
                assertTrue("${file.name}: a placeholder in a line with no string literal: $t", t.contains("\""))
                assertFalse("${file.name}: a placeholder in an id or tag: $t", Regex("""\bid\s*=|AckTags|targetTag|destination""").containsMatchIn(t))
            }
        }
    }

    // ---- backup ---------------------------------------------------------------------------------------------------------------------

    @Test
    fun theSettingIsInTheBackupAsANullableField_describedByTheExportWarning_andNotInTheFingerprint() {
        assertTrue(Regex("""val plainWords: Boolean\? = null""").containsMatchIn(source("backup/AckBackup.kt")))
        assertTrue("plainWords" in ExportContents.mappedFields)
        assertTrue("plainWords" in BackupFingerprint.IGNORED_FIELDS)
        val transfer = source("backup/TransferManager.kt")
        assertTrue(bodyOf(transfer, "buildBackup").contains("plainWords = AssistPrefs.plainWordsStored(context)"))
        assertTrue("null means nothing to say: the choice is left alone", bodyOf(transfer, "applyBackupToStorage").contains("backup.plainWords?.let { AssistPrefs.setPlainWords(context, it) }"))
    }

    @Test
    fun theNewTagIsDeclaredAndUsed() {
        assertTrue(source("AckTags.kt").contains("const val PLAIN_WORDS_SWITCH = \"PLAIN_WORDS_SWITCH\""))
        assertTrue(source("settings/SettingsView.kt").contains("AckTags.PLAIN_WORDS_SWITCH"))
    }
}
