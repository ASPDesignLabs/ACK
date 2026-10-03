// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import com.example.besu.core.CustomVoiceRemoval.Profile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CustomVoiceRemovalTest {

    private val plain = Profile("USER_A", "CUSTOM A", useCustomVoice = false)
    private val usesVoice = Profile("USER_B", "CUSTOM B", useCustomVoice = true)
    private val alsoUsesVoice = Profile("USER_C", "CUSTOM C", useCustomVoice = true)

    @Test
    fun nothingUsesTheVoiceSoNothingChanges() {
        val impact = CustomVoiceRemoval.impact("ORGANIC", listOf(plain))
        assertFalse(impact.anyAffected)
        assertEquals(emptyList<String>(), impact.affectedLabels)
        assertEquals("ORGANIC", impact.newActiveProfileId)
        assertFalse(impact.activeProfileChanges)
        assertEquals(emptySet<String>(), impact.profileIdsToClear)
    }

    @Test
    fun noProfilesAtAllIsFine() {
        val impact = CustomVoiceRemoval.impact("CYBER", emptyList())
        assertFalse(impact.anyAffected)
        assertEquals("CYBER", impact.newActiveProfileId)
    }

    @Test
    fun theActiveMyVoicePresetSwitchesToTheNormalVoice() {
        val impact = CustomVoiceRemoval.impact("MY_VOICE", listOf(plain))
        assertEquals(listOf("MY VOICE"), impact.affectedLabels)
        assertEquals("ORGANIC", impact.newActiveProfileId)
        assertTrue(impact.activeProfileChanges)
        assertEquals(emptySet<String>(), impact.profileIdsToClear)
    }

    @Test
    fun aCustomProfileThatUsesTheVoiceHasThatTurnedOffButStaysSelected() {
        val impact = CustomVoiceRemoval.impact("USER_B", listOf(plain, usesVoice))
        assertEquals(listOf("CUSTOM B"), impact.affectedLabels)
        assertEquals("USER_B", impact.newActiveProfileId)
        assertFalse(impact.activeProfileChanges)
        assertEquals(setOf("USER_B"), impact.profileIdsToClear)
    }

    @Test
    fun aCustomProfileThatIsNotActiveIsStillCleared() {
        val impact = CustomVoiceRemoval.impact("CYBER", listOf(usesVoice))
        assertEquals(setOf("USER_B"), impact.profileIdsToClear)
        assertEquals("CYBER", impact.newActiveProfileId)
        assertFalse(impact.activeProfileChanges)
    }

    @Test
    fun theMyVoicePresetIsListedFirstThenCustomProfilesInOrder() {
        val impact = CustomVoiceRemoval.impact("MY_VOICE", listOf(alsoUsesVoice, plain, usesVoice))
        assertEquals(listOf("MY VOICE", "CUSTOM C", "CUSTOM B"), impact.affectedLabels)
        assertEquals(setOf("USER_C", "USER_B"), impact.profileIdsToClear)
        assertEquals("ORGANIC", impact.newActiveProfileId)
    }

    @Test
    fun onlyProfilesThatUseTheVoiceAreListed() {
        val impact = CustomVoiceRemoval.impact("ORGANIC", listOf(plain, usesVoice, plain.copyId("USER_D")))
        assertEquals(listOf("CUSTOM B"), impact.affectedLabels)
        assertEquals(setOf("USER_B"), impact.profileIdsToClear)
    }

    private fun Profile.copyId(newId: String) = Profile(newId, label, useCustomVoice)
}
