// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The one-time offer of the newer defaults (the banner and the review in AUDIO ARCHITECT) reads its words from string resources, in the chosen language. The
 * decision of what is offered is DefaultsOfferTest's; this holds the words: the banner's three sentences (choosing one is a core decision), the screen's literals gone,
 * the names that stay names (ORGANIC, CYBER) passed in and not retyped, the English names still on screen (ALERT:, FULL TEXT, SHOW FULL MESSAGE) kept exactly, and
 * what applying does (only what was switched on, nothing before the tap, a backup first if asked) exactly as it was.
 */
class DefaultsWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val prompt get() = file("settings/DefaultsPrompt.kt")
    private val audio get() = file("settings/AudioView.kt")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val defaultsNames get() = english.keys.filter { it.startsWith("defaults_") }

    private val voiceOnly = DefaultsOffer(unprocessedVoice = true, fullMessage = false)
    private val fullOnly = DefaultsOffer(unprocessedVoice = false, fullMessage = true)
    private val both = DefaultsOffer(unprocessedVoice = true, fullMessage = true)
    private val none = DefaultsOffer(unprocessedVoice = false, fullMessage = false)

    // ---- the banner's sentence is a decision --------------------------------------------------------------------------------------

    @Test
    fun theBannerSaysWhatIsOnOffer_inEnglishExactlyAsBefore() {
        val tail = "YOURS IS UNCHANGED, AND NOTHING CHANGES UNLESS YOU CHOOSE."
        assertEquals("NEW INSTALLS NOW START WITH THE UNPROCESSED VOICE. $tail", DefaultsText.banner(EnglishText, voiceOnly))
        assertEquals("NEW INSTALLS NOW START WITH FULL MESSAGES ON SCREEN. $tail", DefaultsText.banner(EnglishText, fullOnly))
        assertEquals("NEW INSTALLS NOW START WITH THE UNPROCESSED VOICE AND FULL MESSAGES ON SCREEN. $tail", DefaultsText.banner(EnglishText, both))
        assertEquals("", DefaultsText.banner(EnglishText, none))
    }

    @Test
    fun theBannerIsThreeDifferentRealSentencesInEveryLanguage() {
        for ((tag, _) in translations) {
            val t = FileText(tag)
            val said = listOf(voiceOnly, fullOnly, both).map { DefaultsText.banner(t, it) }
            assertEquals("$tag: three different sentences", 3, said.toSet().size)
            for (line in said) {
                assertTrue("$tag: blank", line.isNotBlank())
                assertFalse("$tag: a resource name was shown: $line", line.contains("defaults_"))
            }
            for (offer in listOf(voiceOnly, fullOnly, both)) {
                assertNotEquals("$tag: still English", DefaultsText.banner(EnglishText, offer), DefaultsText.banner(t, offer))
            }
        }
    }

    // ---- the screen reads its words from resources ---------------------------------------------------------------------------------

    @Test
    fun everyStringTheOfferNamesExists_andNoneIsLeftUnused() {
        val sources = prompt + "\n" + audio + "\n" + file("core/DefaultsText.kt")
        val referenced = Regex("""R\.string\.(defaults_[a-z_]+)""").findAll(sources).map { it.groupValues[1] }.toSet() +
            Regex(""""(defaults_[a-z_]+)"""").findAll(sources).map { it.groupValues[1] }.toSet()
        val missing = referenced.filter { it !in english.keys }
        assertEquals("named but not defined: $missing", emptyList<String>(), missing)
        val unused = defaultsNames.toSet() - referenced
        assertTrue("defined but never used: $unused", unused.isEmpty())
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawn() {
        val gone = listOf(
            "\"[REVIEW]\"", "\"[NOT NOW]\"", "\"NEWER DEFAULTS\"", "New installs start with these settings", "\"USE THE UNPROCESSED VOICE (ORGANIC)\"", "Now: CYBER,",
            "\"SHOW THE FULL MESSAGE ON SCREEN\"", "a message over 5 words is cut", "\"BACK UP FIRST\"", "Saves a copy of your whole setup", "\"CANCEL\"", "\"APPLY\"",
            "NEW INSTALLS NOW START WITH", "THE UNPROCESSED VOICE\"", "FULL MESSAGES ON SCREEN\"",
        )
        for (literal in gone) assertFalse("DefaultsPrompt.kt still holds $literal", prompt.contains(literal))
        for (literal in listOf("\"BACKUP SAVED", "\"BACKUP FAILED", "\"SETTINGS UPDATED\"")) assertFalse("AudioView.kt still holds $literal", audio.contains(literal))
        assertTrue("DefaultsPrompt.kt needs an explicit R import outside the base package", prompt.contains("import com.example.besu.R"))
        assertTrue(prompt.contains("import androidx.compose.ui.res.stringResource"))
    }

    @Test
    fun theBannerIsChosenByTheCoreDecision_andTheNamesAreHandedIn() {
        assertTrue(prompt.contains("text = DefaultsText.banner(words, offer),"))
        assertTrue(prompt.contains("title = stringResource(R.string.defaults_voice_title, DefaultsText.ORGANIC),"))
        assertTrue(prompt.contains("detail = stringResource(R.string.defaults_voice_detail, DefaultsText.CYBER),"))
        assertEquals("ORGANIC", DefaultsText.ORGANIC)
        assertEquals("CYBER", DefaultsText.CYBER)
        // The sentence under BACK UP FIRST names the button as it reads on the SETTINGS screen now, and the intro names the button below it.
        assertTrue(prompt.contains("stringResource(R.string.defaults_back_up_hint, labelFor(LabelKey.EXPORT_JSON))"))
        assertTrue(prompt.contains("stringResource(R.string.defaults_intro, stringResource(R.string.defaults_apply))"))
    }

    @Test
    fun theStatusesAndTheToastReadThroughTheContext_notAComposableCall() {
        assertTrue(audio.contains("defaultsBackupStatus = context.getString(R.string.defaults_backup_saved)"))
        assertTrue(audio.contains("defaultsBackupStatus = context.getString(R.string.defaults_backup_failed)"))
        assertTrue(audio.contains("Toast.makeText(context, context.getString(R.string.defaults_updated), Toast.LENGTH_SHORT).show()"))
        assertFalse(Regex("""Toast\.makeText\([^)]*stringResource""").containsMatchIn(audio))
        // A failed backup does not look like a saved one: they are different words in every language.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertNotEquals("$tag: saved and failed read the same", map.getValue("defaults_backup_saved"), map.getValue("defaults_backup_failed"))
            assertNotEquals("$tag: REVIEW and NOT NOW read the same", map.getValue("defaults_review"), map.getValue("defaults_not_now"))
            assertNotEquals("$tag: APPLY and CANCEL read the same", map.getValue("defaults_apply"), map.getValue("common_cancel"))
        }
        // In English both statuses say nothing was changed, which is what makes it safe to carry on.
        assertTrue(english.getValue("defaults_backup_saved").contains("NOTHING HAS BEEN CHANGED"))
        assertTrue(english.getValue("defaults_backup_failed").contains("NOTHING WAS CHANGED"))
    }

    @Test
    fun everyButtonWordIsOnTheControlThatDoesWhatItSays() {
        // A label swapped between two buttons passes every "the string exists" check, so each word is tied to the action beside it.
        assertTrue("CANCEL closes the review", prompt.contains("NeonButton(stringResource(R.string.common_cancel), Modifier.weight(1f), mainColor = Color.Gray) { onDismiss() }"))
        assertTrue(
            "APPLY applies only when something is chosen",
            prompt.contains("NeonButton(stringResource(R.string.defaults_apply), Modifier.weight(1f), isActive = anyChosen, mainColor = primaryColor) {\n                    if (anyChosen) {")
        )
        assertTrue("BACK UP FIRST starts the save", prompt.contains("NeonButton(stringResource(R.string.defaults_back_up_first), Modifier.fillMaxWidth(), mainColor = primaryColor) { onBackUpFirst() }"))
        assertTrue("[REVIEW] opens the review", Regex("""R\.string\.defaults_review\)[\s\S]{0,400}?\.clickable\(onClick = onReview\)""").containsMatchIn(prompt))
        assertTrue("[NOT NOW] only hides the offer", Regex("""R\.string\.defaults_not_now\)[\s\S]{0,400}?\.clickable\(onClick = onNotNow\)""").containsMatchIn(prompt))
    }

    // ---- names that stay names, and English names still on screen ------------------------------------------------------------------

    @Test
    fun theVoiceNamesAndTheApplyButtonAreHandedToTheSentences_notRetypedInThem() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in listOf("defaults_voice_title", "defaults_voice_detail", "defaults_intro", "defaults_back_up_hint")) {
                assertTrue("$tag/$name must take its name as %1\$s", map.getValue(name).contains("%1\$s"))
            }
            for (name in listOf("defaults_voice_title", "defaults_voice_detail")) {
                val text = map.getValue(name)
                assertFalse("$tag/$name must not retype ORGANIC or CYBER", text.contains("ORGANIC") || text.contains("CYBER"))
            }
            assertFalse("$tag: the intro must not retype the button", map.getValue("defaults_intro").contains(map.getValue("defaults_apply")))
            assertFalse("$tag: the hint must not retype EXPORT .JSON", map.getValue("defaults_back_up_hint").contains("EXPORT .JSON"))
        }
    }

    @Test
    fun theEnglishNamesStillOnScreenAreKeptExactlyInTheLongExplanation() {
        // ALERT: is what the display shows, FULL TEXT is the saved name of the preset this adds, SHOW FULL MESSAGE is the editor's switch (the editor is not translated yet).
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val text = map.getValue("defaults_full_detail")
            for (name in listOf("ALERT:", "FULL TEXT", "SHOW FULL MESSAGE")) assertTrue("$tag: the explanation must keep $name exactly", text.contains(name))
            assertTrue("$tag: and the number of words", text.contains("5") && text.contains("3"))
        }
        assertTrue(prompt.contains("name = \"FULL TEXT\", bypassTruncation = true)"))
    }

    // ---- what applying does is exactly as it was -------------------------------------------------------------------------------------

    @Test
    fun nothingChangesBeforeTheTap_everySwitchStartsOff_andOnlyWhatWasSwitchedOnIsApplied() {
        assertEquals("both switches start off", 2, Regex("""mutableStateOf\(false\)""").findAll(prompt).count())
        assertTrue(prompt.contains("val anyChosen = (offer.unprocessedVoice && chooseVoice) || (offer.fullMessage && chooseFullMessage)"))
        assertTrue(prompt.contains("if (anyChosen) {\n                        onApply(offer.unprocessedVoice && chooseVoice, offer.fullMessage && chooseFullMessage)"))
        assertTrue(prompt.contains("isActive = anyChosen"))
        // The screen applies the voice through the ORGANIC chip's own path, adds the preset only if asked, and is not offered again after either answer.
        assertTrue(audio.contains("if (useUnprocessedVoice) {\n                    userProfile = \"ORGANIC\"\n                    syncDsp()"))
        assertTrue(audio.contains("if (useFullMessage) {\n                    addFullTextPreset(context)"))
        assertEquals("dismissed after NOT NOW and after APPLY", 2, Regex("""InstallState\.dismissDefaultsPrompt\(context\)""").findAll(audio).count())
        assertTrue("BACK UP FIRST only starts a save", audio.contains("onBackUpFirst = { defaultsBackupLauncher.launch("))
        // The banner points at the review and never applies anything itself.
        assertTrue(audio.contains("defaultsBackupStatus = null\n                    showDefaultsReview = true"))
    }
}
