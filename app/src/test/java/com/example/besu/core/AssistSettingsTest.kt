// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** The person-chosen switches in ack_assist_prefs: what each is when nothing is stored, what a new install gets, and who is offered it. */
class AssistSettingsTest {

    @Test
    fun withNothingStored_theProfileWarningIsOff_soAnExistingInstallIsUnchanged() {
        assertFalse(AssistSettings.WARN_FALLBACK)
    }

    @Test
    fun aNewInstallIsGivenTheWarningOn() {
        assertTrue(AssistSettings.WARN_FRESH_INSTALL)
    }

    @Test
    fun theOfferGoesToAnInstallWhereNothingWasChosenAndItWasNeverDismissed() {
        assertTrue(AssistSettings.shouldOfferWarning(switchStored = false, offerDismissed = false))
    }

    @Test
    fun anInstallThatHasAValueStored_isNeverOffered_whetherItWasSeededOrTheyChoseIt() {
        assertFalse(AssistSettings.shouldOfferWarning(switchStored = true, offerDismissed = false))
        assertFalse(AssistSettings.shouldOfferWarning(switchStored = true, offerDismissed = true))
    }

    @Test
    fun onceDismissed_theOfferIsNeverShownAgain() {
        assertFalse(AssistSettings.shouldOfferWarning(switchStored = false, offerDismissed = true))
    }

    @Test
    fun theSeedWritesOnlyTheSwitch_notTheDismissedNote() {
        // The dismissed note is only ever written by a tap, so it is not a key the seed writes.
        assertEquals(setOf("warn_profile_change"), AssistSettings.SEED_KEYS)
        assertFalse(AssistSettings.KEY_WARN_OFFER_DISMISSED in AssistSettings.SEED_KEYS)
    }

    @Test
    fun theFileAndKeyNamesAreStable() {
        assertEquals("ack_assist_prefs", AssistSettings.FILE)
        assertEquals("warn_profile_change", AssistSettings.KEY_WARN_PROFILE_CHANGE)
        assertEquals("warn_profile_change_offer_dismissed", AssistSettings.KEY_WARN_OFFER_DISMISSED)
    }
}
