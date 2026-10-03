// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The starter seed touches code that cannot be compiled or run without the Android SDK (InstallState, DataWipe,
 * CommandRepository, StarterSeed). So the decisions are in plain Kotlin and tested (StarterSeedPlanTest, PhraseKeysTest), and
 * this file holds what can still be checked from here: that the classifier treats the seed's own keys as a fresh install and
 * nothing else does, and that each Android file really calls the seed where it must, and nowhere it must not.
 */
class StarterSeedWiringTest {

    private fun source(name: String) = RepoFiles.read("app/src/main/java/com/example/besu/$name")

    /** The text between the braces of the first `fun <name>` in [text], found by counting braces. */
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

    // ---- the classifier ----------------------------------------------------------------------------------------------

    private val allSeeds: Map<String, Set<String>>
        get() = mapOf(
            "ack_prefs" to setOf("USER_VOX_PROFILE"),
            "ack_visual_presets" to setOf("saved_presets", "active_preset_id"),
            StarterSets.MATRIX_FILE to StarterSets.matrixSeedKeys,
            StarterSets.RECORD_FILE to StarterSets.recordKeys,
            AssistSettings.FILE to AssistSettings.SEED_KEYS,
        )

    @Test
    fun theSeedKeysAreExactlyWhatTheSeedWrites() {
        assertEquals(allSeeds, InstallClassifier.SEED_KEYS)
    }

    @Test
    fun theSeedWritesTheTwelveBarePathsTheDeckListAndTheStartersDeck() {
        val expected = StarterSets.matrixPhrases.map { it.path }.toSet() +
            setOf("custom_decks_meta", "quick_actions_DECK_STARTERS_config")
        assertEquals(expected, StarterSets.matrixSeedKeys)
        assertEquals(12, StarterSets.recordKeys.size) // one record key per phrase
    }

    @Test
    fun aFinishedOrHalfFinishedStarterSeed_stillReadsAsFresh() {
        assertTrue(InstallClassifier.isFreshInstall(allSeeds))
        // every subset of the seed keys, one file at a time
        assertTrue(InstallClassifier.isFreshInstall(mapOf(StarterSets.MATRIX_FILE to setOf("/std/id/0"))))
        assertTrue(InstallClassifier.isFreshInstall(mapOf(StarterSets.MATRIX_FILE to setOf("custom_decks_meta"))))
        assertTrue(InstallClassifier.isFreshInstall(mapOf(StarterSets.RECORD_FILE to setOf("seeded:/std/con/3"))))
    }

    @Test
    fun anythingElseInTheMatrixConfig_meansAnExistingInstall() {
        for (key in listOf("DECK_1_/std/id/0", "WORK_/std/id/0", "/custom/X/1", "active_deck_id", "/std/id/12")) {
            assertFalse(key, InstallClassifier.isFreshInstall(allSeeds + (StarterSets.MATRIX_FILE to StarterSets.matrixSeedKeys + key)))
        }
    }

    @Test
    fun aSeedKeyNameInTheWrongFile_isNotASeedKey() {
        assertFalse(InstallClassifier.isFreshInstall(mapOf("ack_prefs" to setOf("/std/id/0"))))
        assertFalse(InstallClassifier.isFreshInstall(mapOf(StarterSets.MATRIX_FILE to setOf("seeded:/std/id/0"))))
        assertFalse(InstallClassifier.isFreshInstall(mapOf(StarterSets.RECORD_FILE to setOf("/std/id/0"))))
    }

    // ---- the Android files really call the seed where they must ----------------------------------------------------------

    @Test
    fun aFreshInstallIsSeededOnce_insideTheFreshBranch() {
        val body = bodyOf(source("data/InstallState.kt"), "ensureRecorded")
        assertTrue(
            "ensureRecorded must call StarterSeed.seedFreshInstall only when the install is fresh",
            Regex("""if \(fresh\) \{[^}]*StarterSeed\.seedFreshInstall\(context\)[^}]*\}""").containsMatchIn(body)
        )
    }

    @Test
    fun aSettingsWipe_neverSeedsPhrases_soAnExistingPersonsUntouchedButtonsAreNotFlipped() {
        // seedDefaultsAfterWipe runs after DELETE DATA > SETTINGS, which leaves every phrase alone. Seeding phrases there
        // would give a person who never edited a slot a different phrase in it.
        val state = source("data/InstallState.kt")
        assertFalse(bodyOf(state, "seedFreshInstallDefaults").contains("StarterSeed"))
        assertFalse(Regex("""fun seedDefaultsAfterWipe\([^)]*\)[^\n]*StarterSeed""").containsMatchIn(state))
    }

    @Test
    fun aMessagesAndDecksWipe_seedsTheMatrixPhrasesAgain() {
        val body = bodyOf(source("data/DataWipe.kt"), "wipe")
        assertTrue(
            "wipe() must re-seed the Matrix phrases after MESSAGES AND DECKS is deleted",
            Regex("""ID_MESSAGES_AND_DECKS in deletedIds\)\s*\{[^}]*StarterSeed\.seedAfterWipe\(context\)""").containsMatchIn(body)
        )
    }

    @Test
    fun aNewMatrixDeck_isSeededOnlyOnAPhoneThatWasSeeded() {
        val body = bodyOf(source("data/CommandRepository.kt"), "createDeck")
        assertTrue(
            "createDeck must call StarterSeed.seedNewMatrixDeck for a MATRIX deck",
            Regex("""DeckType\.MATRIX\)?\s*\{?[^}]*StarterSeed\.seedNewMatrixDeck\(context, newDeck\.id\)""").containsMatchIn(body)
        )
        val seed = source("data/StarterSeed.kt")
        assertTrue(
            "seedNewMatrixDeck must do nothing unless this phone was seeded",
            bodyOf(seed, "seedNewMatrixDeck").contains("if (!wasSeeded(context)) return")
        )
    }

    // ---- the files and keys the seed uses agree with the rest of the app --------------------------------------------------

    @Test
    fun theSeedFileNamesAndKeysMatchTheirOwners() {
        val repository = source("data/CommandRepository.kt")
        assertEquals(StarterSets.MATRIX_FILE, Regex("""const val PREFS_NAME = "([^"]+)"""").find(repository)?.groupValues?.get(1))
        assertEquals(StarterSets.DECKS_KEY, Regex("""const val DECKS_KEY = "([^"]+)"""").find(repository)?.groupValues?.get(1))
        val prefix = Regex("""const val QUICK_ACTIONS_PREFIX = "([^"]+)"""").find(repository)?.groupValues?.get(1)
        val suffix = Regex("""const val QUICK_ACTIONS_SUFFIX = "([^"]+)"""").find(repository)?.groupValues?.get(1)
        assertEquals(StarterSets.quickActionsConfigKey("X"), "${prefix}X$suffix")
        assertEquals(
            StarterSets.RECORD_FILE,
            Regex("""const val PREFS_NAME = "([^"]+)"""").find(source("data/StarterSeed.kt"))?.groupValues?.get(1)
        )
    }

    @Test
    fun theRecordFileIsOwnedByInstallStateAndClearedWithMessagesAndDecks() {
        val list = Regex("OWNED_PREFS_FILES\\s*=\\s*listOf\\(([^)]*)\\)").find(source("data/InstallState.kt"))?.groupValues?.get(1)
            ?: error("OWNED_PREFS_FILES not found")
        assertTrue(list.contains("\"${StarterSets.RECORD_FILE}\""))
        val area = StorageCatalogue.area(StorageCatalogue.ID_MESSAGES_AND_DECKS)
        assertTrue(StarterSets.RECORD_FILE in area.prefsFilesCleared)
    }

    @Test
    fun theWipeConfirmationsSayTheMatrixIsStarterPhrasesAfterwards() {
        val area = StorageCatalogue.area(StorageCatalogue.ID_MESSAGES_AND_DECKS)
        assertTrue(StorageCatalogue.firstConfirmation(area, "X").any { it.contains("STARTER PHRASES") })
        assertTrue(StorageCatalogue.firstConfirmationEverything("X").any { it.contains("STARTER PHRASES") })
    }
}
