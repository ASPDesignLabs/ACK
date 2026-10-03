// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The voice list and SPEECH LANGUAGE touch files that cannot be compiled or run without the Android SDK (MainActivity, OutputService, AudioView,
 * AssistPrefs, TransferManager, the Voice mapping). The rules are in plain Kotlin and tested elsewhere (VoiceListingTest, SpeechLanguageTest);
 * this reads those files and holds them to the promises: an existing install still speaks English (US), a missing language is never silence,
 * a voice that needs the network is never offered, and the new setting is backed up, checked and described.
 */
class SpeechLanguageWiringTest {

    private fun source(name: String) = RepoFiles.read("app/src/main/java/com/example/besu/$name")

    private fun code(text: String): String =
        text.replace(Regex("/\\*.*?\\*/", RegexOption.DOT_MATCHES_ALL), "").lines().joinToString("\n") { it.substringBefore("//") }

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

    // ---- the preference ---------------------------------------------------------------------------------------------------

    @Test
    fun theKeyMatchesTheCore_andReadingFallsBackToEnglishUsSoAnExistingInstallIsUnchanged() {
        val prefs = source("data/AssistPrefs.kt")
        assertEquals(AssistSettings.KEY_SPEECH_LANGUAGE, Regex("""const val KEY_SPEECH_LANGUAGE = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        val read = RepoFiles.declarationOf(prefs, "speechLanguage")
        assertTrue(read.contains("SpeechLanguagePolicy.FALLBACK"))
        assertFalse("reading must not write", read.contains("edit()"))
    }

    @Test
    fun aNewInstallIsSeededWithTheDevicesLanguage_onlyWhereNothingIsStored() {
        val body = bodyOf(source("data/AssistPrefs.kt"), "seedFreshInstallDefaults")
        assertTrue(body.contains("SpeechLanguagePolicy.FRESH_INSTALL"))
        assertTrue("the seed must write nothing that is already there", body.contains("contains(KEY_SPEECH_LANGUAGE)"))
    }

    @Test
    fun theChoiceIsWrittenWithCommit_soItIsOnDiskBeforeTheScreenIsLeft() {
        assertTrue(RepoFiles.declarationOf(source("data/AssistPrefs.kt"), "setSpeechLanguage").contains(".commit()"))
    }

    // ---- the speech service -------------------------------------------------------------------------------------------------

    @Test
    fun theHardWiredEnglishIsGone_andTheLanguageIsAskedThroughThePolicy() {
        val c = code(source("output/OutputService.kt"))
        assertFalse("OutputService must not hard-wire Locale.US any more", c.contains("setLanguage(Locale.US)"))
        val apply = bodyOf(c, "applySpeechLanguage")
        assertTrue(apply.contains("SpeechLanguagePolicy.localeTag("))
        assertTrue(apply.contains("AssistPrefs.speechLanguage("))
        assertTrue(apply.contains("SpeechLanguagePolicy.needsApplying("))
        assertTrue(apply.contains("SpeechLanguagePolicy.engineAccepted("))
    }

    @Test
    fun aMissingLanguageIsNeverSilence_theFunctionNeverReturnsOrThrowsBecauseTheEngineSaidNo() {
        val c = code(source("output/OutputService.kt"))
        val apply = bodyOf(c, "applySpeechLanguage")
        val afterAsk = apply.substring(apply.indexOf("tts?.setLanguage("))
        assertFalse("nothing after asking the engine may return", afterAsk.contains("return"))
        assertFalse("nothing after asking the engine may throw", afterAsk.contains("throw"))
        assertTrue("a failure is said once in the log, not a reason to stop", afterAsk.contains("broadcastLog("))
        // The engine being ready is not conditional on the language.
        val init = bodyOf(c, "onInit")
        assertTrue(init.indexOf("applySpeechLanguage()") in 0 until init.indexOf("isTtsReady = true"))
    }

    @Test
    fun aProfileWithNoVoiceUsesTheSpeechLanguage_andOneThatChoseAVoiceStillDoes() {
        val c = code(source("output/OutputService.kt"))
        val speak = bodyOf(c, "speakWithSystemTts")
        assertTrue("a profile's chosen voice is still set by name", speak.contains("tts?.voice = desiredVoice"))
        assertTrue("remembered so the next profile with no voice does not inherit it", speak.contains("voiceSetByProfile = true"))
        val elseBranch = speak.substring(speak.indexOf("} else {"), speak.indexOf("val uniqueId"))
        assertTrue(elseBranch.contains("applySpeechLanguage()"))
    }

    @Test
    fun theCustomClonedVoiceIsUntouched() {
        val c = code(source("output/OutputService.kt"))
        val speakCustom = c.substring(c.indexOf("useCustomVoice"), c.indexOf("useCustomVoice") + 600)
        assertFalse(speakCustom.contains("applySpeechLanguage"))
    }

    // ---- the voice list -------------------------------------------------------------------------------------------------

    @Test
    fun theEnglishOnlyFilterIsGone_andTheListGoesThroughTheCoreRule() {
        val c = code(source("MainActivity.kt"))
        assertFalse("the English-only filter must not come back", Regex("""language\s*==\s*"en"""").containsMatchIn(c))
        val init = bodyOf(c, "onInit")
        assertTrue(init.contains("VoiceListing.usable("))
        assertTrue(init.contains("toVoiceInfo()"))
    }

    @Test
    fun aVoiceThatNeedsTheNetworkOrIsNotInstalledIsReadFromTheEngine() {
        val c = code(source("output/VoiceInfoMapping.kt"))
        assertTrue(c.contains("isNetworkConnectionRequired"))
        assertTrue(c.contains("KEY_FEATURE_NOT_INSTALLED"))
        assertTrue("the language by name in the phone's own language", c.contains("getDisplayName(Locale.getDefault())"))
    }

    @Test
    fun thePickerShowsEachVoicesLanguage_theNote_andNoSmallText() {
        val audio = code(source("settings/AudioView.kt"))
        assertTrue(audio.contains("VoiceListing.languageLine("))
        assertTrue(audio.contains("VoiceListing.LIST_NOTE"))
        assertTrue(audio.contains("SpeechLanguageText.label(speechLanguage)"))
        assertTrue(audio.contains("AssistPrefs.setSpeechLanguage(context, speechLanguage)"))
        val picker = bodyOf(audio, "AudioArchitectView")
        val pickerBlock = picker.substring(picker.indexOf("if (showVoicePicker)"), picker.indexOf("if (showDspChainEditor"))
        for (m in Regex("""fontSize = (\d+)\.sp""").findAll(pickerBlock)) assertTrue("small text in the picker: ${m.value}", m.groupValues[1].toInt() >= 12)
    }

    // ---- backup, checks and the wipe -----------------------------------------------------------------------------------------

    @Test
    fun theSettingIsInTheBackupAsANullableField_describedByTheExportWarning() {
        assertTrue(Regex("""val speechLanguage: String\? = null""").containsMatchIn(source("backup/AckBackup.kt")))
        assertTrue("speechLanguage" in ExportContents.mappedFields)
        val transfer = source("backup/TransferManager.kt")
        assertTrue(bodyOf(transfer, "buildBackup").contains("speechLanguage = AssistPrefs.speechLanguageStored(context)"))
    }

    @Test
    fun importRefusesAnUnknownValue_logsWhy_andApplyLeavesTheChoiceAloneWhenTheFileSaysNothing() {
        val transfer = source("backup/TransferManager.kt")
        val validate = bodyOf(transfer, "validateDataIntegrity")
        val at = validate.indexOf("backup.speechLanguage")
        assertTrue(at >= 0)
        val block = validate.substring(at, minOf(validate.length, at + 400))
        assertTrue(block.contains("SpeechLanguage.fromStored("))
        assertTrue(block.indexOf("Log.e(\"ACK_IMPORT\"") in 0 until block.indexOf("return false"))
        val apply = bodyOf(transfer, "applyBackupToStorage")
        assertTrue("null means nothing to say: fromStored(null) is null, so nothing is written", apply.contains("SpeechLanguage.fromStored(backup.speechLanguage)?.let"))
    }

    @Test
    fun deleteDataSettingsSaysThePhonesLanguageIsTheDefaultAfterwards() {
        val settings = StorageCatalogue.area(StorageCatalogue.ID_SETTINGS)
        assertTrue(StorageCatalogue.firstConfirmation(settings, "X").any { it.contains("SPEECH IN THIS PHONE'S OWN LANGUAGE") })
        assertTrue(StorageCatalogue.firstConfirmationEverything("X").any { it.contains("SPEECH IN THIS PHONE'S OWN LANGUAGE") })
    }
}
