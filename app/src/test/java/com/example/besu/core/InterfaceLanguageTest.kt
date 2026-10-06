// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class InterfaceLanguageTest {

    @Test
    fun theStoredNamesAreFixed_soABackupFromAnotherPhoneStillReads() {
        assertEquals(
            listOf("DEVICE", "ENGLISH", "ES", "PT", "HI", "AR", "AF"),
            InterfaceLanguage.values().map { it.stored }
        )
        assertEquals(InterfaceLanguage.values().size, InterfaceLanguage.values().map { it.stored }.toSet().size)
    }

    @Test
    fun fromStoredReadsExactlyAStoredName_andIgnoresAnythingElse() {
        for (language in InterfaceLanguage.values()) assertEquals(language, InterfaceLanguage.fromStored(language.stored))
        assertNull(InterfaceLanguage.fromStored(null))
        assertNull(InterfaceLanguage.fromStored(""))
        assertNull(InterfaceLanguage.fromStored("es"))        // the tag is not the stored name
        assertNull(InterfaceLanguage.fromStored("Spanish"))
        assertNull(InterfaceLanguage.fromStored("ENGLISH "))
        assertNull(InterfaceLanguage.fromStored("device"))
    }

    @Test
    fun theTagsAreTheRealLanguageCodes_andOnlyDeviceHasNone() {
        assertEquals(listOf(null, "en", "es", "pt", "hi", "ar", "af"), InterfaceLanguage.values().map { it.tag })
        assertEquals(listOf("ENGLISH", "ESPAÑOL", "PORTUGUÊS", "हिन्दी", "العربية", "AFRIKAANS"), InterfaceLanguage.named.map { it.nativeName })
        assertEquals(6, InterfaceLanguage.named.size)
        assertFalse(InterfaceLanguage.DEVICE in InterfaceLanguage.named)
    }

    @Test
    fun anExistingInstallStaysEnglish_aNewOneFollowsThePhone() {
        assertEquals(InterfaceLanguage.ENGLISH, InterfaceLanguagePolicy.FALLBACK)
        assertEquals(InterfaceLanguage.DEVICE, InterfaceLanguagePolicy.FRESH_INSTALL)
    }

    @Test
    fun aChosenLanguageIsUsedWhateverThePhoneIsSetTo() {
        for (language in InterfaceLanguage.named) {
            for (device in listOf("en", "es", "ar", "de", "", "und")) {
                assertEquals("${language.stored} on a '$device' phone", language.tag, InterfaceLanguagePolicy.effectiveTag(language, device))
            }
        }
    }

    @Test
    fun followingThePhoneUsesItsLanguageOnlyWhenACKHasWordsForIt() {
        for (tag in listOf("es", "pt", "hi", "ar", "af")) assertEquals(tag, InterfaceLanguagePolicy.effectiveTag(InterfaceLanguage.DEVICE, tag))
        // Anything else, including nothing, is English: never a blank screen.
        for (other in listOf("en", "de", "fr", "zh", "iw", "", "und", "xx")) assertEquals(other, "en", InterfaceLanguagePolicy.effectiveTag(InterfaceLanguage.DEVICE, other))
    }

    @Test
    fun theDeviceLanguageIsReadWithoutFussAboutCaseOrSpaces() {
        assertEquals("es", InterfaceLanguagePolicy.effectiveTag(InterfaceLanguage.DEVICE, " ES "))
        assertEquals("ar", InterfaceLanguagePolicy.effectiveTag(InterfaceLanguage.DEVICE, "Ar"))
        // A language with a region is not what the phone's language field holds, so it is not matched loosely.
        assertEquals("en", InterfaceLanguagePolicy.effectiveTag(InterfaceLanguage.DEVICE, "es-MX"))
    }

    @Test
    fun theTranslatedTagsAreTheFiveLanguagesBesidesEnglish() {
        assertEquals(setOf("es", "pt", "hi", "ar", "af"), InterfaceLanguagePolicy.translatedTags)
    }

    @Test
    fun onlyANamedLanguageIsApplied_followingThePhoneLeavesAndroidAlone() {
        assertFalse(InterfaceLanguagePolicy.mustApply(InterfaceLanguage.DEVICE))
        // English is applied too, so an existing install on a Spanish phone really does stay English.
        for (language in InterfaceLanguage.named) assertTrue(language.stored, InterfaceLanguagePolicy.mustApply(language))
    }

    @Test
    fun letterSpacingIsDroppedForArabicOnly() {
        assertTrue(InterfaceLanguagePolicy.joinsLetters("ar"))
        for (tag in listOf("en", "es", "pt", "hi", "af", "", "AR", "ar-EG")) assertFalse(tag, InterfaceLanguagePolicy.joinsLetters(tag))
    }
}
