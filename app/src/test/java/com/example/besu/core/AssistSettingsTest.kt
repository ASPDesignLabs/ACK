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
    fun theSeedWritesTheTwoNewInstallDefaults_notTheDismissedNotes() {
        // The dismissed note is only ever written by a tap, so it is not a key the seed writes.
        assertEquals(setOf("warn_profile_change", "speech_language", "interface_language"), AssistSettings.SEED_KEYS)
        assertFalse(AssistSettings.KEY_WARN_OFFER_DISMISSED in AssistSettings.SEED_KEYS)
    }

    @Test
    fun theSpeechLanguageKeyIsStable() {
        assertEquals("speech_language", AssistSettings.KEY_SPEECH_LANGUAGE)
    }

    @Test
    fun theFileAndKeyNamesAreStable() {
        assertEquals("ack_assist_prefs", AssistSettings.FILE)
        assertEquals("warn_profile_change", AssistSettings.KEY_WARN_PROFILE_CHANGE)
        assertEquals("warn_profile_change_offer_dismissed", AssistSettings.KEY_WARN_OFFER_DISMISSED)
    }

    // ---- WORD SUGGESTIONS (L5) -----------------------------------------------------------------------------------------------

    @Test
    fun wordSuggestionsAreOffWhenNothingIsStored_andNewInstallsAreNotSeededWithThem() {
        // Off until the person turns it on, on every install, new or old: it learns from what they type, so it needs a tap.
        assertFalse(AssistSettings.WORD_SUGGESTIONS_FALLBACK)
        assertFalse(AssistSettings.KEY_WORD_SUGGESTIONS in AssistSettings.SEED_KEYS)
        assertFalse(AssistSettings.KEY_WORD_OFFER_DISMISSED in AssistSettings.SEED_KEYS)
    }

    @Test
    fun theWordSuggestionKeysAreStableAndDistinct() {
        assertEquals("word_suggestions", AssistSettings.KEY_WORD_SUGGESTIONS)
        assertEquals("word_suggestions_offer_dismissed", AssistSettings.KEY_WORD_OFFER_DISMISSED)
        val keys = listOf(
            AssistSettings.KEY_WARN_PROFILE_CHANGE, AssistSettings.KEY_WARN_OFFER_DISMISSED,
            AssistSettings.KEY_WORD_SUGGESTIONS, AssistSettings.KEY_WORD_OFFER_DISMISSED,
        )
        assertEquals("a key is used twice", keys.size, keys.toSet().size)
    }

    @Test
    fun theWordOfferIsShownOnlyWhileTheSwitchIsOffAndTheOfferWasNeverDismissed() {
        assertTrue(AssistSettings.shouldOfferWordSuggestions(switchOn = false, offerDismissed = false))
        assertFalse(AssistSettings.shouldOfferWordSuggestions(switchOn = false, offerDismissed = true))
        assertFalse(AssistSettings.shouldOfferWordSuggestions(switchOn = true, offerDismissed = false))
        assertFalse(AssistSettings.shouldOfferWordSuggestions(switchOn = true, offerDismissed = true))
    }

    // ---- LIMITS NOTICE (C4) --------------------------------------------------------------------------------------------------------

    @Test
    fun theLimitsNoticeNoteIsOnlyWrittenByATap_soItIsNotASeedKey_andItsKeyIsStableAndDistinct() {
        assertEquals("limits_notice_seen", AssistSettings.KEY_LIMITS_NOTICE_SEEN)
        assertFalse(AssistSettings.KEY_LIMITS_NOTICE_SEEN in AssistSettings.SEED_KEYS)
        val keys = listOf(
            AssistSettings.KEY_WARN_PROFILE_CHANGE, AssistSettings.KEY_WARN_OFFER_DISMISSED, AssistSettings.KEY_WORD_SUGGESTIONS,
            AssistSettings.KEY_WORD_OFFER_DISMISSED, AssistSettings.KEY_SPEECH_LANGUAGE, AssistSettings.KEY_INTERFACE_LANGUAGE,
            AssistSettings.KEY_PLAIN_WORDS, AssistSettings.KEY_PLAIN_WORDS_OFFER_DISMISSED, AssistSettings.KEY_LIMITS_NOTICE_SEEN,
        )
        assertEquals("a key is used twice", keys.size, keys.toSet().size)
    }

    // ---- PLAIN WORDS (L2) ---------------------------------------------------------------------------------------------------------

    @Test
    fun plainWordsIsOffWhenNothingIsStored_isNeverSeeded_andIsNotInTheSeedKeys() {
        // The developer's decision: OFF for everyone, a new install included, with one dismissible offer. So nothing seeds it.
        assertFalse(AssistSettings.PLAIN_WORDS_FALLBACK)
        assertFalse(AssistSettings.KEY_PLAIN_WORDS in AssistSettings.SEED_KEYS)
        assertFalse(AssistSettings.KEY_PLAIN_WORDS_OFFER_DISMISSED in AssistSettings.SEED_KEYS)
    }

    @Test
    fun thePlainWordsKeysAreStableAndDistinct() {
        assertEquals("plain_words", AssistSettings.KEY_PLAIN_WORDS)
        assertEquals("plain_words_offer_dismissed", AssistSettings.KEY_PLAIN_WORDS_OFFER_DISMISSED)
        val keys = listOf(
            AssistSettings.KEY_WARN_PROFILE_CHANGE, AssistSettings.KEY_WARN_OFFER_DISMISSED, AssistSettings.KEY_WORD_SUGGESTIONS,
            AssistSettings.KEY_WORD_OFFER_DISMISSED, AssistSettings.KEY_SPEECH_LANGUAGE, AssistSettings.KEY_PLAIN_WORDS,
            AssistSettings.KEY_PLAIN_WORDS_OFFER_DISMISSED,
        )
        assertEquals("a key is used twice", keys.size, keys.toSet().size)
    }

    @Test
    fun theOfferGoesToEveryoneWhileTheSwitchIsOffAndTheOfferWasNeverAnswered() {
        assertTrue(AssistSettings.shouldOfferPlainWords(switchOn = false, offerDismissed = false))
        assertFalse(AssistSettings.shouldOfferPlainWords(switchOn = false, offerDismissed = true))
        assertFalse(AssistSettings.shouldOfferPlainWords(switchOn = true, offerDismissed = false))
        assertFalse(AssistSettings.shouldOfferPlainWords(switchOn = true, offerDismissed = true))
    }
}
