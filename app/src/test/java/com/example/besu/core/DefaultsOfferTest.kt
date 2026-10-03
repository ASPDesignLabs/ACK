// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DefaultsOfferTest {
    private val nothing = DefaultsOffer(unprocessedVoice = false, fullMessage = false)

    @Test
    fun anExistingInstallOnTheOldDefaultsIsOfferedBoth() {
        val offer = defaultsOffer(isExistingInstall = true, dismissed = false, voiceIsCyber = true, presetTruncates = true)
        assertEquals(DefaultsOffer(unprocessedVoice = true, fullMessage = true), offer)
        assertTrue(offer.any)
    }

    @Test
    fun onlyTheThingThatIsStillOnTheOldDefaultIsOffered() {
        assertEquals(
            DefaultsOffer(unprocessedVoice = true, fullMessage = false),
            defaultsOffer(isExistingInstall = true, dismissed = false, voiceIsCyber = true, presetTruncates = false)
        )
        assertEquals(
            DefaultsOffer(unprocessedVoice = false, fullMessage = true),
            defaultsOffer(isExistingInstall = true, dismissed = false, voiceIsCyber = false, presetTruncates = true)
        )
    }

    @Test
    fun anExistingInstallThatAlreadyChoseBothIsOfferedNothing() {
        val offer = defaultsOffer(isExistingInstall = true, dismissed = false, voiceIsCyber = false, presetTruncates = false)
        assertEquals(nothing, offer)
        assertFalse(offer.any)
    }

    @Test
    fun aNewInstallIsNeverOfferedAnything() {
        // A fresh install already starts on the safer defaults; it must never be nagged about them.
        assertEquals(nothing, defaultsOffer(isExistingInstall = false, dismissed = false, voiceIsCyber = true, presetTruncates = true))
    }

    @Test
    fun onceDismissedItIsNeverOfferedAgain_whateverTheSettingsAre() {
        for (cyber in listOf(true, false)) for (truncates in listOf(true, false)) {
            assertEquals(nothing, defaultsOffer(isExistingInstall = true, dismissed = true, voiceIsCyber = cyber, presetTruncates = truncates))
        }
    }

    @Test
    fun everyCombinationFollowsTheRule() {
        for (existing in listOf(true, false)) for (dismissed in listOf(true, false))
            for (cyber in listOf(true, false)) for (truncates in listOf(true, false)) {
                val shown = existing && !dismissed
                assertEquals(
                    "existing=$existing dismissed=$dismissed cyber=$cyber truncates=$truncates",
                    DefaultsOffer(unprocessedVoice = shown && cyber, fullMessage = shown && truncates),
                    defaultsOffer(existing, dismissed, cyber, truncates)
                )
            }
    }
}
