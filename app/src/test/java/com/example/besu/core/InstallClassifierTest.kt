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
        assertEquals(
            mapOf(
                "ack_prefs" to setOf("USER_VOX_PROFILE"),
                "ack_visual_presets" to setOf("saved_presets", "active_preset_id"),
            ),
            InstallClassifier.SEED_KEYS,
        )
    }
}
