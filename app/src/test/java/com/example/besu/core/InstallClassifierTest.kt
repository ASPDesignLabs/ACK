// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InstallClassifierTest {
    @Test
    fun anEmptyMapIsAFreshInstall() {
        assertTrue(InstallClassifier.isFreshInstall(emptyMap()))
    }

    @Test
    fun filesThatExistButHoldNoKeysAreStillFresh() {
        val files = mapOf("ack_prefs" to emptySet<String>(), "ack_matrix_config" to emptySet<String>())
        assertTrue(InstallClassifier.isFreshInstall(files))
    }

    @Test
    fun oneKeyInTheMatrixConfigMeansAnExistingInstall() {
        assertFalse(InstallClassifier.isFreshInstall(mapOf("ack_matrix_config" to setOf("deck_list"))))
    }

    @Test
    fun onlyTheSeedKeysIsStillFresh_soARerunAfterAHalfFinishedSeedWorks() {
        val seeded = mapOf(
            "ack_prefs" to setOf("USER_VOX_PROFILE"),
            "ack_visual_presets" to setOf("saved_presets", "active_preset_id"),
        )
        assertTrue(InstallClassifier.isFreshInstall(seeded))
    }

    @Test
    fun eachSeedKeyAloneIsFresh() {
        assertTrue(InstallClassifier.isFreshInstall(mapOf("ack_prefs" to setOf("USER_VOX_PROFILE"))))
        assertTrue(InstallClassifier.isFreshInstall(mapOf("ack_visual_presets" to setOf("saved_presets"))))
        assertTrue(InstallClassifier.isFreshInstall(mapOf("ack_visual_presets" to setOf("active_preset_id"))))
    }

    @Test
    fun seedKeysPlusOneOtherKeyIsExisting() {
        val files = mapOf(
            "ack_prefs" to setOf("USER_VOX_PROFILE", "CUSTOM_VOICES"),
            "ack_visual_presets" to setOf("saved_presets", "active_preset_id"),
        )
        assertFalse(InstallClassifier.isFreshInstall(files))
    }

    @Test
    fun aVisualPresetsKeyThatIsNotASeedKeyIsExisting() {
        // force_device_rotation is a setting the person chose; it lives in the same file as the seeded presets.
        assertFalse(InstallClassifier.isFreshInstall(mapOf("ack_visual_presets" to setOf("saved_presets", "force_device_rotation"))))
    }

    @Test
    fun keysInAppPrefsAloneCountAsExisting() {
        assertFalse(InstallClassifier.isFreshInstall(mapOf("app_prefs" to setOf("theme"))))
    }

    @Test
    fun aSeedKeyNameInTheWrongFileIsNotASeedKey() {
        // The exemption is per file: USER_VOX_PROFILE only counts as a seed in ack_prefs.
        assertFalse(InstallClassifier.isFreshInstall(mapOf("ack_matrix_config" to setOf("USER_VOX_PROFILE"))))
        assertFalse(InstallClassifier.isFreshInstall(mapOf("ack_prefs" to setOf("saved_presets"))))
    }

    @Test
    fun theSeedKeysAreExactlyWhatTheSeedWrites() {
        // If the seed gains a key, this list and InstallState must change together; fail loudly rather than drift.
        // Written out in full on purpose, independent of StarterSets, so the two cannot drift together unnoticed.
        assertEquals(
            mapOf(
                "ack_prefs" to setOf("USER_VOX_PROFILE"),
                "ack_visual_presets" to setOf("saved_presets", "active_preset_id"),
                "ack_matrix_config" to setOf(
                    "/std/id/0", "/std/id/1", "/std/id/2", "/std/id/3",
                    "/std/def/0", "/std/def/1", "/std/def/2", "/std/def/3",
                    "/std/con/0", "/std/con/1", "/std/con/2", "/std/con/3",
                    "custom_decks_meta", "quick_actions_DECK_STARTERS_config",
                ),
                "ack_starter_seed" to setOf(
                    "seeded:/std/id/0", "seeded:/std/id/1", "seeded:/std/id/2", "seeded:/std/id/3",
                    "seeded:/std/def/0", "seeded:/std/def/1", "seeded:/std/def/2", "seeded:/std/def/3",
                    "seeded:/std/con/0", "seeded:/std/con/1", "seeded:/std/con/2", "seeded:/std/con/3",
                ),
                "ack_assist_prefs" to setOf("warn_profile_change"),
            ),
            InstallClassifier.SEED_KEYS,
        )
    }
}
