// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The words around the profile-change warning say what it does and, as plainly, what it does not cover. */
class ProfileWarningTextTest {

    @Test
    fun theSwitchSaysOnOrOffInWords_notOnlyByColour() {
        assertEquals("WARN BEFORE PROFILE CHANGES: ON", ProfileWarningText.switchLabel(true))
        assertEquals("WARN BEFORE PROFILE CHANGES: OFF", ProfileWarningText.switchLabel(false))
        assertNotEquals(ProfileWarningText.switchLabel(true), ProfileWarningText.switchLabel(false))
    }

    @Test
    fun theExplanation_saysItIsAboutTheMatrixOnly_andThatTheWidgetAndWatchAreNotCovered() {
        val text = ProfileWarningText.SWITCH_EXPLANATION
        assertTrue(text.contains("MATRIX"))
        assertTrue(text.contains("QUICK ACTIONS"))
        assertTrue(text.contains("WIDGET"))
        assertTrue(text.contains("WATCH"))
        assertTrue(text.contains("WITHOUT ASKING"))
    }

    @Test
    fun theDialogsTwoButtons_areDistinct_andTheBoxSaysWhereToTurnItBackOn() {
        assertNotEquals(ProfileWarningText.STAY, ProfileWarningText.CHANGE)
        assertTrue(ProfileWarningText.DONT_SHOW_AGAIN_NOTE.contains("SETTINGS"))
    }

    @Test
    fun theOffer_saysItIsOffAndThatNothingChangesUnlessTheyTurnItOn() {
        val text = ProfileWarningText.OFFER_TEXT
        assertTrue(text.contains("OFF FOR YOU"))
        assertTrue(text.contains("UNLESS YOU TURN IT ON"))
        assertNotEquals(ProfileWarningText.OFFER_TURN_ON, ProfileWarningText.OFFER_NOT_NOW)
    }

    @Test
    fun noWordingIsInLowerCase_theAppsHouseStyle() {
        val all = listOf(
            ProfileWarningText.SWITCH_EXPLANATION, ProfileWarningText.OFFER_TEXT, ProfileWarningText.DIALOG_TITLE,
            ProfileWarningText.DONT_SHOW_AGAIN, ProfileWarningText.DONT_SHOW_AGAIN_NOTE, ProfileWarningText.STAY,
            ProfileWarningText.CHANGE, ProfileWarningText.switchLabel(true), ProfileWarningText.switchLabel(false),
        )
        for (t in all) assertEquals(t.uppercase(), t)
    }
}
