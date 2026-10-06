// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** SPEECH LANGUAGE: which language a profile with no chosen voice speaks in, what each install starts with, and what happens when the engine says no. */
class SpeechLanguageTest {

    @Test
    fun theStoredNamesAreStable_andParseBack() {
        assertEquals("DEVICE", SpeechLanguage.DEVICE.stored)
        assertEquals("ENGLISH_US", SpeechLanguage.ENGLISH_US.stored)
        assertEquals(SpeechLanguage.DEVICE, SpeechLanguage.fromStored("DEVICE"))
        assertEquals(SpeechLanguage.ENGLISH_US, SpeechLanguage.fromStored("ENGLISH_US"))
    }

    @Test
    fun anythingElseIsNotASetting() {
        assertNull(SpeechLanguage.fromStored(null))
        assertNull(SpeechLanguage.fromStored(""))
        assertNull(SpeechLanguage.fromStored("device"))
        assertNull(SpeechLanguage.fromStored("GERMAN"))
    }

    @Test
    fun withNothingStored_anInstallThatAlreadyExistedKeepsEnglish_andANewInstallFollowsThePhone() {
        // The existing-install fallback must stay English (US): a phone set to German that always spoke English phrases must not change under anyone.
        assertEquals(SpeechLanguage.ENGLISH_US, SpeechLanguagePolicy.FALLBACK)
        assertEquals(SpeechLanguage.DEVICE, SpeechLanguagePolicy.FRESH_INSTALL)
    }

    @Test
    fun englishUsIsAlwaysEnglishUs_whateverThePhoneIsSetTo() {
        assertEquals("en-US", SpeechLanguagePolicy.localeTag(SpeechLanguage.ENGLISH_US, "de-DE"))
        assertEquals("en-US", SpeechLanguagePolicy.localeTag(SpeechLanguage.ENGLISH_US, ""))
    }

    @Test
    fun deviceFollowsThePhone() {
        assertEquals("de-DE", SpeechLanguagePolicy.localeTag(SpeechLanguage.DEVICE, "de-DE"))
        assertEquals("ar", SpeechLanguagePolicy.localeTag(SpeechLanguage.DEVICE, "ar"))
    }

    @Test
    fun deviceWithNoUsableTagFallsBackToEnglishUs_neverToNothing() {
        assertEquals("en-US", SpeechLanguagePolicy.localeTag(SpeechLanguage.DEVICE, ""))
        assertEquals("en-US", SpeechLanguagePolicy.localeTag(SpeechLanguage.DEVICE, "   "))
        assertEquals("en-US", SpeechLanguagePolicy.localeTag(SpeechLanguage.DEVICE, "und"))
    }

    @Test
    fun theEngineResultCodes_exactBoundaries() {
        // TextToSpeech: LANG_AVAILABLE 0, LANG_COUNTRY_AVAILABLE 1, LANG_COUNTRY_VAR_AVAILABLE 2, LANG_MISSING_DATA -1, LANG_NOT_SUPPORTED -2
        assertTrue(SpeechLanguagePolicy.engineAccepted(0))
        assertTrue(SpeechLanguagePolicy.engineAccepted(1))
        assertTrue(SpeechLanguagePolicy.engineAccepted(2))
        assertFalse(SpeechLanguagePolicy.engineAccepted(-1))
        assertFalse(SpeechLanguagePolicy.engineAccepted(-2))
    }

    @Test
    fun aLanguageIsReappliedWhenTheSettingChanges_orAfterAProfileVoiceWasSet_butNotEveryUtterance() {
        // applied nothing yet: apply
        assertTrue(SpeechLanguagePolicy.needsApplying(desiredTag = "en-US", appliedTag = null, voiceSetByProfile = false))
        // already applied and nothing disturbed it: leave the engine alone
        assertFalse(SpeechLanguagePolicy.needsApplying(desiredTag = "en-US", appliedTag = "en-US", voiceSetByProfile = false))
        // the setting changed
        assertTrue(SpeechLanguagePolicy.needsApplying(desiredTag = "de-DE", appliedTag = "en-US", voiceSetByProfile = false))
        // a profile chose a voice earlier and the engine kept it: a profile with no voice must not inherit it
        assertTrue(SpeechLanguagePolicy.needsApplying(desiredTag = "en-US", appliedTag = "en-US", voiceSetByProfile = true))
    }

    @Test
    fun theLabelsSayTheSettingInWords()  {
        assertEquals("SPEECH LANGUAGE: THIS PHONE'S LANGUAGE", SpeechLanguageText.label(EnglishText, SpeechLanguage.DEVICE))
        assertEquals("SPEECH LANGUAGE: ENGLISH (US)", SpeechLanguageText.label(EnglishText, SpeechLanguage.ENGLISH_US))
    }

    @Test
    fun theExplanation_saysWhoItAffects_whatItDoesNotTouch_andThatSilenceNeverHappens() {
        val text = SpeechLanguageText.explanation(EnglishText)
        assertTrue(text.contains("NO VOICE OF ITS OWN"))
        assertTrue(text.contains("CHOSEN A VOICE"))
        assertTrue(text.contains("MY VOICE"))
        assertTrue(text.contains("NOT AVAILABLE"))
        assertEquals(text.uppercase(), text)
        // Both sentences, with one space between them and none left over.
        assertEquals(text.trim(), text)
        assertTrue(text.contains("NOT AFFECTED. IF THE PHONE'S SPEECH ENGINE"))
    }

    @Test
    fun theExplanationTakesTheNameMyVoiceAsAnArgument_soTheChipAndTheSentenceCannotDisagree() {
        val named = SpeechLanguageText.explanation(object : TextSource {
            override fun get(name: String, vararg args: Any): String = if (args.isEmpty()) name else "$name(${args.joinToString("|")})"
            override fun count(name: String, quantity: Int): String = name
        })
        assertEquals("speech_language_explanation_who(MY VOICE) speech_language_explanation_missing", named)
    }
}
