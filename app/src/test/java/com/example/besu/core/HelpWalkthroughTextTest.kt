// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The decisions behind the HELP walkthrough text (core/HelpWalkthroughText.kt): the naming rule, reading a name or an English text not yet moved, and, above all, when the coach
 * panel may speak the translated step. Every boundary of the speaking rule is held exactly, because a wrong answer makes an English voice read Spanish or Hindi aloud.
 */
class HelpWalkthroughTextTest {
    private val english = EnglishText

    @Test
    fun theNamesFollowOneRule_andNeverCollideWithTheHelpChromesOwnNames() {
        assertEquals("helpmod_geo_protocol_title", HelpWalkthroughText.moduleTitle("geo_protocol"))
        assertEquals("helpmod_geo_protocol_summary", HelpWalkthroughText.moduleSummary("geo_protocol"))
        assertEquals("helpmod_geo_protocol_map_data_title", HelpWalkthroughText.stepTitle("geo_protocol", "map_data"))
        assertEquals("helpmod_geo_protocol_map_data_body", HelpWalkthroughText.stepBody("geo_protocol", "map_data"))
        assertEquals("helpmod_", HelpWalkthroughText.PREFIX)
        assertFalse("the chrome's names start with help_ and a walkthrough's with helpmod_", HelpWalkthroughText.stepBody("a", "b").startsWith("help_"))
    }

    @Test
    fun aNameIsRecognisedAndAnEnglishSentenceIsNot() {
        assertTrue(HelpWalkthroughText.isName("helpmod_geo_protocol_intro_body"))
        assertTrue(HelpWalkthroughText.isName("helpmod_x1_title"))
        assertFalse("an English title", HelpWalkthroughText.isName("GEO-PROTOCOL"))
        assertFalse("an English sentence", HelpWalkthroughText.isName("{{GEO_PROTOCOL:Geo-Protocol}} manages location-aware ACK behavior and zones."))
        assertFalse("capital letters are not a name", HelpWalkthroughText.isName("helpmod_Geo_title"))
        assertFalse("the prefix alone is not a name", HelpWalkthroughText.isName("helpmod_"))
        assertFalse("another family's resource", HelpWalkthroughText.isName("help_menu_title"))
        assertFalse("a trailing space", HelpWalkthroughText.isName("helpmod_geo_title "))
        assertFalse("empty", HelpWalkthroughText.isName(""))
    }

    @Test
    fun aNameReadsAsItsWords_andATextThatIsNotAResourceReadsAsItself() {
        assertEquals("ZONE CONTROLS", HelpWalkthroughText.read(english, "helpmod_geo_protocol_geo_view_title"))
        val notMoved = "Open {{DECK:Deck}} and tap the key. 100% sure."
        assertEquals("a family that has not moved shows its own English, braces and percent signs untouched", notMoved, HelpWalkthroughText.read(english, notMoved))
        assertEquals("a name that does not exist shows as itself, so a gap is visible", "helpmod_nothing_here_title", HelpWalkthroughText.read(english, "helpmod_nothing_here_title"))
    }

    // ---- the spoken guide ---------------------------------------------------------------------------------------------------------------------

    @Test
    fun theTranslatedStepIsSpokenOnlyWhenTheVoiceFollowsThePhoneAndTheScreensAreInThePhonesLanguage() {
        for (language in listOf("es", "pt", "hi", "ar", "af")) {
            assertTrue("$language: phone $language, screens $language, voice follows the phone", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, language, language))
            assertFalse("$language: the voice is set to English (US), whatever the screens say", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.ENGLISH_US, language, language))
            assertFalse("$language: the screens were chosen in $language on a phone set to English", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, language, "en"))
            assertFalse("$language: the screens were chosen in $language on a phone set to another language", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, language, if (language == "es") "pt" else "es"))
        }
    }

    @Test
    fun englishIsNeverTreatedAsTranslated_andAnUnknownLanguageIsSpokenInEnglish() {
        assertFalse("English screens on an English phone: the English step is the only step", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "en", "en"))
        assertFalse("English screens on a Spanish phone (an existing install stays English)", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "en", "es"))
        assertFalse("no screen language yet", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "", ""))
        assertFalse("blank screen language, blank phone", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "  ", "  "))
        assertFalse("a phone that reports nothing", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "es", ""))
    }

    @Test
    fun theLanguageCodesAreComparedWithoutCaseOrSpaces_butNeverByPrefix() {
        assertTrue(HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, " ES ", "es"))
        assertTrue(HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "es", " Es\n"))
        assertFalse("es is not esperanto", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "es", "eo"))
        assertFalse("a longer code is not the same language code", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "es", "es-MX"))
        assertFalse("a prefix is not a match", HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "a", "ar"))
    }

    @Test
    fun everySpeechSettingIsDecidedByTheRuleAndTheOnlyWayToSpeakTranslatedIsToFollowThePhone() {
        for (setting in SpeechLanguage.values()) {
            val answer = HelpWalkthroughText.speaksInterfaceLanguage(setting, "es", "es")
            assertEquals("$setting", setting == SpeechLanguage.DEVICE, answer)
        }
        // The default of an install that already existed is English (US): it hears the English step, exactly as before the steps were translated.
        assertFalse(HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguagePolicy.FALLBACK, "es", "es"))
        // A new install follows the phone: on a Spanish phone it hears the Spanish step.
        assertTrue(HelpWalkthroughText.speaksInterfaceLanguage(SpeechLanguagePolicy.FRESH_INSTALL, "es", "es"))
    }
}
