// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The learned words touch files that cannot be compiled or run without the Android SDK (LearnedWordsRepository, AssistPrefs,
 * TransferManager, AckBackup). The rules are in plain Kotlin and tested elsewhere (WordModelTest, LearnedWordsStoreTest); this reads
 * those files and holds them to the promises: the switch gates everything, nothing typed reaches a log, the backup is additive and
 * checked, and the words are deleted and described where the person is told they are.
 */
class LearnedWordsWiringTest {

    private fun source(name: String) = RepoFiles.read("app/src/main/java/com/example/besu/$name")

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

    // ---- the switch ------------------------------------------------------------------------------------------------------

    @Test
    fun theSwitchKeepsTheNamesTheCoreSays_andFallsBackToOff() {
        val prefs = source("data/AssistPrefs.kt")
        assertEquals(AssistSettings.KEY_WORD_SUGGESTIONS, Regex("""const val KEY_WORD_SUGGESTIONS = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        assertEquals(AssistSettings.KEY_WORD_OFFER_DISMISSED, Regex("""const val KEY_WORD_OFFER_DISMISSED = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        assertTrue(RepoFiles.declarationOf(prefs, "isWordSuggestionsOn").contains("AssistSettings.WORD_SUGGESTIONS_FALLBACK"))
    }

    @Test
    fun theSwitchIsNeverSeeded_andNeverTravelsInTheBackup() {
        // It learns from what the person types and is a choice about THIS phone: a new install starts it off, and a restore leaves it alone.
        assertFalse(bodyOf(source("data/AssistPrefs.kt"), "seedFreshInstallDefaults").contains("WORD"))
        assertFalse(bodyOf(source("data/InstallState.kt"), "seedFreshInstallDefaults").contains("WordSuggestions"))
        val backup = source("backup/AckBackup.kt")
        assertFalse("the switch must not be a backup field", Regex("""val \w*(?i:wordSuggestion)\w*\s*:""").containsMatchIn(backup))
        assertFalse(source("backup/TransferManager.kt").contains("setWordSuggestions"))
    }

    @Test
    fun turningTheSwitchOnOrOff_alsoAnswersTheOneTimeOffer() {
        val body = bodyOf(source("data/AssistPrefs.kt"), "setWordSuggestions")
        assertTrue(body.contains("KEY_WORD_SUGGESTIONS"))
        assertTrue("choosing in SETTINGS must retire the offer", body.contains("KEY_WORD_OFFER_DISMISSED"))
        assertTrue("commit(), so the choice is on disk before the person leaves the screen", body.contains(".commit()"))
    }

    @Test
    fun answeringTheOfferNotNow_changesNoSetting() {
        val body = bodyOf(source("data/AssistPrefs.kt"), "dismissWordSuggestionsOffer")
        assertTrue(body.contains("KEY_WORD_OFFER_DISMISSED"))
        assertFalse(body.contains("KEY_WORD_SUGGESTIONS,"))
    }

    // ---- the repository --------------------------------------------------------------------------------------------------

    @Test
    fun theFolderIsTheOneTheStoreAndTheCatalogueName() {
        val repository = source("data/LearnedWordsRepository.kt")
        assertEquals(LearnedWordsStore.FOLDER, Regex("""File\(\s*context\.filesDir,\s*"([^"]+)"\s*\)""").find(repository)?.groupValues?.get(1))
        assertTrue(LearnedWordsStore.FOLDER in StorageCatalogue.area(StorageCatalogue.ID_MESSAGES_AND_DECKS).folders)
    }

    @Test
    fun learningAndSuggestingAreBothGatedOnTheSwitch_insideTheRepository_soNoCallSiteCanForgetIt() {
        val repository = source("data/LearnedWordsRepository.kt")
        for (name in listOf("learn", "predict")) {
            val body = bodyOf(repository, name)
            assertTrue("$name must check the switch itself", body.contains("AssistPrefs.isWordSuggestionsOn(context)"))
        }
    }

    @Test
    fun forgettingAndListingAreNotGatedOnTheSwitch_soWordsCanAlwaysBeSeenAndRemoved() {
        val repository = source("data/LearnedWordsRepository.kt")
        for (name in listOf("listWords", "forget", "forgetAll", "wordCount")) {
            assertFalse("$name must work with the switch off", RepoFiles.declarationOf(repository, name).contains("isWordSuggestionsOn"))
        }
    }

    @Test
    fun nothingTypedIsEverLogged() {
        for (name in listOf("data/LearnedWordsRepository.kt", "core/LearnedWordsStore.kt")) {
            // The only shape allowed is Log.x(TAG, "a fixed sentence"): no variable, no interpolation, no exception (its message could hold text).
            for (line in source(name).lines().filter { it.contains("Log.") }) {
                assertTrue(
                    "$name logs something that could be typed text: ${line.trim()}",
                    Regex("""Log\.[a-z]\(\s*TAG\s*,\s*"[^"$\\]*"\s*\)""").containsMatchIn(line),
                )
            }
        }
        assertFalse("the store has no logging at all", source("core/LearnedWordsStore.kt").contains("Log."))
    }

    // ---- the backup ------------------------------------------------------------------------------------------------------

    @Test
    fun theBackupFieldIsNullable_describedByTheExportWarning_andNotInTheFingerprint() {
        assertTrue(Regex("""val learnedWords: WordModelData\? = null""").containsMatchIn(source("backup/AckBackup.kt")))
        assertTrue("learnedWords" in ExportContents.mappedFields)
        assertTrue("learnedWords" in BackupFingerprint.IGNORED_FIELDS)
    }

    @Test
    fun exportReadsTheStore_withoutTheSwitchGate_becauseTheWordsAreThePersonsDataEitherWay() {
        assertTrue(bodyOf(source("backup/TransferManager.kt"), "buildBackup").contains("learnedWords = LearnedWordsRepository.exportForBackup(context)"))
        assertFalse(RepoFiles.declarationOf(source("data/LearnedWordsRepository.kt"), "exportForBackup").contains("isWordSuggestionsOn"))
    }

    @Test
    fun importRefusesAFileWhoseWordsFailTheChecks_logsWhyWithoutAnyWord_andComesBeforeAnythingIsWritten() {
        val body = bodyOf(source("backup/TransferManager.kt"), "validateDataIntegrity")
        val at = body.indexOf("learnedWords")
        assertTrue("validateDataIntegrity must check learnedWords", at >= 0)
        val block = body.substring(at, minOf(body.length, at + 400))
        assertTrue(block.contains(".validate()"))
        val logAt = block.indexOf("""Log.e("ACK_IMPORT"""")
        val returnAt = block.indexOf("return false")
        assertTrue("the specific reason must be logged to ACK_IMPORT before return false", logAt in 0 until returnAt)
    }

    @Test
    fun importMergesTheWords_neverReplacesThem() {
        val body = bodyOf(source("backup/TransferManager.kt"), "applyBackupToStorage")
        assertTrue(body.contains("LearnedWordsRepository.mergeFromBackup(context, "))
        assertFalse(body.contains("LearnedWordsRepository.forgetAll"))
    }

    // ---- the wipe ------------------------------------------------------------------------------------------------------------

    @Test
    fun deleteDataSaysTheLearnedWordsAreIncluded_andFindsTheFolder() {
        val area = StorageCatalogue.area(StorageCatalogue.ID_MESSAGES_AND_DECKS)
        assertTrue(StorageCatalogue.holds(EnglishText, area).contains("LEARNED WORDS"))
        assertTrue(LearnedWordsStore.FOLDER in area.folders)
    }
}
