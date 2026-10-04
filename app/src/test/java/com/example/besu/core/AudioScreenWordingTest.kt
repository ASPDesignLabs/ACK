// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * AUDIO ARCHITECT (settings/AudioView.kt) reads its words from string resources, in the chosen language. The screen cannot be compiled here, so this reads it: the
 * old English literals are gone, every string it names exists and none is unused, the stored names and ids it works with are exactly as they were, the four built-in
 * voice names stay names in every language (the developer's decision) and are passed into the sentences instead of being retyped in them, a toast reads its words
 * through the context, and a profile is only deleted after the second tap.
 */
class AudioScreenWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val screen get() = file("settings/AudioView.kt")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    /** The strings this commit adds for the screen and its two core text objects. */
    private val audioNames get() = english.keys.filter { it.startsWith("audio_") || it.startsWith("speech_language_") || it.startsWith("voice_list_note_") }

    @Test
    fun everyStringTheScreenNamesExists_andNoneIsLeftUnused() {
        val sources = screen + "\n" + file("core/SpeechLanguage.kt") + "\n" + file("core/VoiceListing.kt") + "\n" + file("core/StorageCatalogue.kt")
        val referenced = Regex("""R\.string\.((?:audio_|common_|speech_language_|voice_list_note_)[a-z0-9_]+)""").findAll(screen).map { it.groupValues[1] }.toSet()
        val missing = referenced.filter { it !in english.keys }
        assertEquals("named but not defined: $missing", emptyList<String>(), missing)
        // Names the core objects write as plain strings (they are read through a TextSource, not R.string).
        val named = Regex(""""((?:audio_|speech_language_|voice_list_note_)[a-z0-9_]+)"""").findAll(sources).map { it.groupValues[1] }.toSet()
        val unused = audioNames.toSet() - referenced - named
        assertTrue("defined but never used: $unused", unused.isEmpty())
        for (name in listOf("common_on", "common_off", "common_commit", "common_close", "common_save", "common_delete", "common_cancel")) {
            assertTrue("$name is not used by the screen", name in referenced)
        }
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawn() {
        val gone = listOf(
            "\"MASTER GAIN", "\"MANAGE PROFILES\"", "\"+ NEW\"", "\"STATUS: INSTALLED\"", "\"STATUS: NOT IMPORTED\"", "\"EXPORT VOICE BACKUP\"", "\"IMPORT VOICE BACKUP\"",
            "THE VOICE BACKUP IS AS PRIVATE", "MY VOICE ACTIVE", "FACTORY PRESET LOCKED", "NO DSP CONTROLS", "\"SELECT SYSTEM VOICE\"", "\"UNSAVED CHANGES*\"", "\"UP TO DATE\"", "\"DEFAULT\"",
            "\"BASE VOICE: ", "\"USE MY VOICE\"", "\"NO VOICE IMPORTED\"", "\"PITCH\"", "\"SPEED\"", "\"RESET TO HUMAN\"", "\"ROBOTIC FREQ (HZ)\"", "\"ROBOTIC DEPTH (%)\"", "\"PREVIEW\"",
            "\"DISCARD\"", "\"COMMIT\"", "\"CLOSE\"", "\"CANCEL\"", "\"SAVE\"", "\"RENAME\"", "\"DELETE\"", "\"+ NEW SLOT\"", "SLOT LIMIT REACHED", "\"MANAGE CUSTOM PROFILES\"", "\"NO CUSTOM PROFILES YET.\"",
            "\"DELETE PROFILE?\"", "permanently? This cannot be undone.", "\"VOICE IMPORTED", "\"IMPORT FAILED", "\"VOICE BACKUP RESTORED", "\"RESTORE FAILED", "\"ON\"", "\"OFF\"",
            "SpeechLanguageText.EXPLANATION", "VoiceListing.LIST_NOTE",
        )
        for (literal in gone) assertFalse("AudioView.kt still holds $literal", screen.contains(literal))
        assertTrue("AudioView.kt needs an explicit R import outside the base package", screen.contains("import com.example.besu.R"))
        assertTrue(screen.contains("import androidx.compose.ui.res.stringResource"))
    }

    @Test
    fun theWordsOfTheCoreDecisionsAreReadThroughTheScreensTextSource() {
        assertTrue(screen.contains("val text = rememberText()"))
        assertTrue(screen.contains("SpeechLanguageText.label(text, speechLanguage),"))
        assertTrue(screen.contains("SpeechLanguageText.explanation(text),"))
        assertTrue(screen.contains("Text(VoiceListing.listNote(text), color"))
    }

    // ---- what is stored and what is sent is exactly as it was -------------------------------------------------------------------------

    @Test
    fun theStoredNamesIdsAndMessagesAreNotTranslated() {
        // Preset ids, the saved name of a new slot, the preference keys and the messages to OutputService are logic, not words.
        assertTrue(screen.contains("prefs.getString(\"USER_VOX_PROFILE\", \"CYBER\") ?: \"CYBER\""))
        assertTrue(screen.contains("listOf(\"CYBER\", \"MECH\", \"ORGANIC\").forEach { name ->"))
        assertTrue(screen.contains("AudioProfileChip(name, userProfile == name, primaryColor) {"))
        assertTrue(screen.contains("val newLabel = \"CUSTOM \${'A' + customVoices.size}\""))
        assertTrue(screen.contains("userProfile = \"ORGANIC\""))
        assertTrue(screen.contains("userProfile = CustomVoiceRemoval.MY_VOICE_ID"))
        assertTrue(screen.contains("AudioProfileChip(CustomVoiceRemoval.MY_VOICE_LABEL, userProfile == CustomVoiceRemoval.MY_VOICE_ID, primaryColor) {"))
        assertTrue(screen.contains("action = \"UPDATE_DSP\""))
        assertTrue(screen.contains("playIntent.action = \"TEST_SIGNAL\""))
        assertTrue(screen.contains(".putString(\"USER_VOX_PROFILE\", userProfile)"))
        assertEquals("MY_VOICE", CustomVoiceRemoval.MY_VOICE_ID)
        assertEquals("MY VOICE", CustomVoiceRemoval.MY_VOICE_LABEL)
    }

    @Test
    fun theBuiltInVoiceNamesStayNamesInEveryLanguage_andAreHandedToTheSentencesNotRetypedInThem() {
        // The developer's decision: CYBER, MECH, ORGANIC and MY VOICE read the same everywhere (chips, widget, HELP, sentences). A sentence that mentions MY VOICE takes it as an argument.
        for (name in listOf("audio_my_voice_active", "audio_use_my_voice", "speech_language_explanation_who")) {
            for ((tag, map) in listOf("en" to english) + translations.toList()) {
                val text = map.getValue(name)
                assertTrue("$tag/$name must take the name as %1\$s", text.contains("%1\$s"))
                assertFalse("$tag/$name must not retype the name", text.contains("MY VOICE"))
            }
        }
        assertTrue(screen.contains("stringResource(R.string.audio_my_voice_active, CustomVoiceRemoval.MY_VOICE_LABEL)"))
        assertTrue(screen.contains("stringResource(R.string.audio_use_my_voice, CustomVoiceRemoval.MY_VOICE_LABEL)"))
        for ((tag, map) in translations) {
            val said = SpeechLanguageText.explanation(FileText(tag))
            assertTrue("$tag: the explanation names MY VOICE", said.contains("MY VOICE"))
            assertTrue("$tag: both sentences", said.contains(map.getValue("speech_language_explanation_missing")))
            assertEquals("$tag: nothing left at the ends", said.trim(), said)
        }
    }

    // ---- each word sits on the control that does the thing --------------------------------------------------------------------------

    private fun wordThenAction(word: String, action: String, within: Int = 450): Boolean =
        Regex("""R\.string\.${Regex.escape(word)}[\s\S]{0,$within}?${Regex.escape(action)}""").containsMatchIn(screen)

    @Test
    fun everyButtonWordIsOnTheControlThatDoesWhatItSays() {
        assertTrue("SAVE (rename)", wordThenAction("common_save", "renameProfile(profile.id, draftLabel)"))
        assertTrue("RENAME", wordThenAction("common_rename", "renaming = true"))
        assertTrue("DELETE in the list only opens the question", wordThenAction("common_delete", "deleteTargetId = profile.id", 300))
        assertTrue("DELETE in the question removes", wordThenAction("common_delete", "deleteProfile(it)", 500))
        assertTrue("CANCEL in the picker", wordThenAction("common_cancel", "showVoicePicker = false", 300))
        assertTrue("CANCEL in the question", wordThenAction("common_cancel", "deleteTargetId = null", 300))
        assertTrue("PREVIEW", wordThenAction("audio_preview", "previewCurrentEdit()", 200))
        assertTrue("DISCARD", wordThenAction("audio_discard", "discardEditingProfile()", 200))
        assertTrue("COMMIT", wordThenAction("common_commit", "saveEditingProfile()", 300))
        assertTrue("CLOSE the DSP editor", wordThenAction("common_close", "showDspChainEditor = false", 300))
        assertTrue("CLOSE the profile list", wordThenAction("common_close", "showManageProfiles = false", 300))
        assertTrue("MANAGE PROFILES", wordThenAction("audio_manage_profiles", "showManageProfiles = true", 300))
        assertTrue("+ NEW SLOT", wordThenAction("audio_new_slot", "createProfile()", 300))
        assertTrue("+ NEW chip", wordThenAction("audio_chip_new", "createProfile()", 200))
        assertTrue("EXPORT VOICE BACKUP", wordThenAction("audio_export_voice_backup", "exportVoiceBackupLauncher.launch(", 200))
        assertTrue("IMPORT VOICE BACKUP", wordThenAction("audio_import_voice_backup", "importVoiceBackupLauncher.launch(", 200))
        assertTrue("RESET TO HUMAN", wordThenAction("audio_reset_human", "pitch = 1.0f, speed = 1.0f, modDepth = 0f", 400))
    }

    @Test
    fun theTwoStateWordsAreChosenByTheStateTheySay() {
        assertTrue(screen.contains("stringResource(if (hasCustomVoice) R.string.audio_status_installed else R.string.audio_status_not_imported)"))
        assertTrue(screen.contains("stringResource(if (isUnsaved) R.string.audio_dsp_unsaved else R.string.audio_dsp_up_to_date)"))
        assertTrue(screen.contains("stringResource(if (p.useCustomVoice) R.string.common_on else R.string.common_off)"))
        assertTrue(screen.contains("stringResource(if (isRobotic) R.string.common_on else R.string.common_off)"))
        assertTrue(screen.contains("if (p.systemVoiceName.isNotEmpty()) p.systemVoiceName.takeLast(15) else stringResource(R.string.audio_default_voice)"))
        // The two lines in the locked box say which engine it is: MY VOICE has no DSP controls of its own, a factory preset is locked.
        assertTrue(screen.contains("if (userProfile == CustomVoiceRemoval.MY_VOICE_ID) {\n                        stringResource(R.string.audio_my_voice_active, CustomVoiceRemoval.MY_VOICE_LABEL) + \"\\n\" + stringResource(R.string.audio_no_dsp_controls)"))
        assertTrue(screen.contains("stringResource(R.string.audio_factory_locked) + \"\\n\" + stringResource(R.string.audio_select_or_create)"))
        // A voice is picked by tapping it, and the one already in use is the one shown selected.
        assertTrue(screen.contains("val isSelected = editingProfile?.systemVoiceName == voice.name"))
    }

    // ---- toasts, buttons and the delete flow ----------------------------------------------------------------------------------------

    @Test
    fun aToastReadsItsWordsThroughTheContext_notThroughAComposableCall() {
        for (name in listOf("audio_toast_imported", "audio_toast_import_failed", "audio_toast_restored", "audio_toast_restore_failed")) {
            assertTrue("$name is not read with context.getString", screen.contains("context.getString(R.string.$name)"))
        }
        assertFalse(Regex("""Toast\.makeText\([^)]*stringResource""").containsMatchIn(screen))
        // The restart after an import, and after a restore, is still the delayed, shared one.
        assertEquals("one restart request after an import and one after a restore", 2, Regex("""pendingCustomVoiceRestart = true""").findAll(screen).count())
        assertTrue(screen.contains("delay(1500)\n            restartApp(context)"))
    }

    @Test
    fun theOnAndOffButtonsGrowWithTheirWord_andOnIsNotOffInAnyLanguage() {
        assertFalse("a fixed 60 dp would clip a longer ON or OFF", screen.contains("Modifier.width(60.dp)"))
        assertEquals(2, Regex("""Modifier\.widthIn\(min = 60\.dp\)""").findAll(screen).count())
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertNotEquals("$tag: ON and OFF", map.getValue("common_on"), map.getValue("common_off"))
        }
    }

    @Test
    fun aProfileIsOnlyDeletedAfterTheSecondTap_andTheQuestionNamesTheProfile() {
        // The list's DELETE only opens the question; the question's DELETE is the one that removes.
        assertTrue(screen.contains("modifier = Modifier.clickable { deleteTargetId = profile.id }.padding(6.dp)"))
        assertTrue(screen.contains("deleteTargetId?.let { deleteProfile(it) }\n                            deleteTargetId = null"))
        assertEquals("the definition and one call", 2, Regex("""deleteProfile\(""").findAll(screen).count())
        assertTrue(screen.contains("stringResource(R.string.audio_delete_profile_body, target?.label ?: \"\"),"))
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertTrue("$tag: the question names the profile", map.getValue("audio_delete_profile_body").contains("%1\$s"))
            assertNotEquals("$tag: DELETE is not CANCEL", map.getValue("common_delete"), map.getValue("common_cancel"))
        }
        for ((tag, map) in translations) {
            assertNotEquals("$tag: the question is still English", english.getValue("audio_delete_profile_body"), map.getValue("audio_delete_profile_body"))
            assertNotEquals("$tag: the title is still English", english.getValue("audio_delete_profile_title"), map.getValue("audio_delete_profile_title"))
        }
    }

    @Test
    fun theNumbersAreFormattedByTheStringNotJoinedOn() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertEquals("$tag/audio_master_gain", listOf("%1\$d"), StringsXml.placeholders(map.getValue("audio_master_gain")))
            assertTrue("$tag/audio_master_gain keeps the percent sign", map.getValue("audio_master_gain").contains("%%"))
            assertEquals("$tag/audio_slot_limit", listOf("%1\$d"), StringsXml.placeholders(map.getValue("audio_slot_limit")))
            assertEquals("$tag/audio_base_voice", listOf("%1\$s"), StringsXml.placeholders(map.getValue("audio_base_voice")))
        }
        assertTrue(screen.contains("stringResource(R.string.audio_master_gain, (masterGain * 100).toInt())"))
        assertTrue(screen.contains("stringResource(R.string.audio_slot_limit, MAX_CUSTOM_PROFILES)"))
        // The units that are not words stay in the code, beside the translated name.
        assertTrue(screen.contains("\"\${stringResource(R.string.audio_robotic_freq)} (HZ)\""))
        assertTrue(screen.contains("\"\${stringResource(R.string.audio_robotic_depth)} (%)\""))
    }

    @Test
    fun wordsThatAnswerOppositeQuestionsAreDifferentInEveryLanguage() {
        val pairs = listOf(
            "audio_dsp_unsaved" to "audio_dsp_up_to_date", "audio_status_installed" to "audio_status_not_imported", "audio_pitch" to "audio_speed",
            "audio_robotic_freq" to "audio_robotic_depth", "audio_export_voice_backup" to "audio_import_voice_backup", "audio_preview" to "audio_discard",
            "audio_toast_imported" to "audio_toast_import_failed", "audio_toast_restored" to "audio_toast_restore_failed", "audio_new_slot" to "audio_slot_limit",
            "audio_chip_new" to "audio_new_slot", "speech_language_device" to "speech_language_english", "common_rename" to "audio_manage_profiles",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) {
            assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
        }
    }

    // ---- the voice backup button, named by the notes that point to it ---------------------------------------------------------------

    @Test
    fun theTrainedVoiceBackupNoteNamesTheButtonInTheChosenLanguage() {
        val area = StorageCatalogue.area(StorageCatalogue.ID_TRAINED_VOICE)
        for ((tag, map) in translations) {
            val note = StorageCatalogue.backupNote(FileText(tag), area)
            assertTrue("$tag: the note names the button as it reads on the screen", note.contains(map.getValue("audio_export_voice_backup")))
            assertTrue("$tag: and the screen", note.contains(map.getValue("label_audio_architect")))
            assertFalse("$tag: no English button name left", note.contains("EXPORT VOICE BACKUP"))
        }
        assertEquals("EXPORT VOICE BACKUP", english.getValue("audio_export_voice_backup"))
        assertTrue(screen.contains("NeonButton(stringResource(R.string.audio_export_voice_backup), Modifier.weight(1f), mainColor = primaryColor) {"))
    }

    // ---- the words that decide ------------------------------------------------------------------------------------------------------

    @Test
    fun theSpeechLanguageAndVoiceListWordsAreRealInEveryLanguage() {
        for ((tag, _) in translations) {
            val t = FileText(tag)
            val device = SpeechLanguageText.label(t, SpeechLanguage.DEVICE)
            val us = SpeechLanguageText.label(t, SpeechLanguage.ENGLISH_US)
            assertNotEquals("$tag: the two settings read differently", device, us)
            for (said in listOf(device, us, SpeechLanguageText.explanation(t), VoiceListing.listNote(t))) {
                assertTrue("$tag: a resource name was shown instead of words: $said", !said.contains("speech_language_") && !said.contains("voice_list_note_"))
            }
            assertNotEquals("$tag: still English", VoiceListing.listNote(EnglishText), VoiceListing.listNote(t))
            assertNotEquals("$tag: still English", SpeechLanguageText.explanation(EnglishText), SpeechLanguageText.explanation(t))
        }
        // The two settings are exactly as they were stored and read.
        assertEquals("SPEECH LANGUAGE: ENGLISH (US)", SpeechLanguageText.label(EnglishText, SpeechLanguage.ENGLISH_US))
    }
}
