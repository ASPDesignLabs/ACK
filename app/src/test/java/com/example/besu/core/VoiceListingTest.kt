// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The system-voice picker: every language, sorted so a person can find theirs, and never a voice that needs the internet or is not installed. */
class VoiceListingTest {

    private fun v(name: String, language: String, network: Boolean = false, installed: Boolean = true) =
        VoiceInfo(name = name, languageTag = language, languageDisplay = language, networkRequired = network, installed = installed)

    @Test
    fun aVoiceThatNeedsTheInternet_isNeverListed() {
        val listed = VoiceListing.usable(listOf(v("a", "English (US)"), v("b", "English (US)", network = true)))
        assertEquals(listOf("a"), listed.map { it.name })
    }

    @Test
    fun aVoiceThatIsNotInstalled_isNeverListed() {
        val listed = VoiceListing.usable(listOf(v("a", "German"), v("b", "German", installed = false)))
        assertEquals(listOf("a"), listed.map { it.name })
    }

    @Test
    fun aVoiceThatIsBothIsNotListedEither() {
        assertTrue(VoiceListing.usable(listOf(v("a", "German", network = true, installed = false))).isEmpty())
    }

    @Test
    fun everyLanguageIsListed_notOnlyEnglish() {
        val listed = VoiceListing.usable(listOf(v("de-1", "German"), v("fr-1", "French"), v("en-1", "English")))
        assertEquals(setOf("de-1", "fr-1", "en-1"), listed.map { it.name }.toSet())
    }

    @Test
    fun sortedByLanguageNameThenVoiceName() {
        val listed = VoiceListing.usable(
            listOf(v("z-voice", "English"), v("b-voice", "German"), v("a-voice", "German"), v("m-voice", "English"), v("c-voice", "Arabic"))
        )
        assertEquals(listOf("c-voice", "m-voice", "z-voice", "a-voice", "b-voice"), listed.map { it.name })
    }

    @Test
    fun languageOrderIgnoresCaseAndAccents_soEveryScriptSortsWhereItsLetterIs() {
        val listed = VoiceListing.usable(
            listOf(v("1", "Zulu"), v("2", "Čeština"), v("3", "danish"), v("4", "Catalan"), v("5", "Åland"))
        )
        // Catalan, Čeština (C-E), danish, Zulu; Åland sorts with A, first
        assertEquals(listOf("5", "4", "2", "3", "1"), listed.map { it.name })
    }

    @Test
    fun theSameVoiceNameInTwoLanguages_keepsTheLanguageOrder() {
        val listed = VoiceListing.usable(listOf(v("same", "Spanish"), v("same", "French")))
        assertEquals(listOf("French", "Spanish"), listed.map { it.languageDisplay })
    }

    @Test
    fun noVoices_isNoList() {
        assertTrue(VoiceListing.usable(emptyList()).isEmpty())
    }

    @Test
    fun theOrderDoesNotDependOnTheOrderTheEngineReportedThem() {
        val voices = listOf(v("b", "Italian"), v("a", "Italian"), v("c", "Dutch"))
        assertEquals(VoiceListing.usable(voices), VoiceListing.usable(voices.reversed()))
    }

    @Test
    fun aVoiceNameIsNeverChanged() {
        // Mixed case, as some engines name them: a profile stores the name exactly, so it must come back exactly.
        val listed = VoiceListing.usable(listOf(v("de-DE-Standard-A", "German")))
        assertEquals("de-DE-Standard-A", listed.single().name)
    }

    @Test
    fun theRowTextNamesTheLanguageNotJustTheCode() {
        val info = VoiceInfo("de-de-x-nfh-local", "de-DE", "German (Germany)", networkRequired = false, installed = true)
        assertEquals("German (Germany)", VoiceListing.languageLine(info))
        // A blank display name falls back to the tag so a row is never left without a language
        assertEquals("xx-YY", VoiceListing.languageLine(VoiceInfo("n", "xx-YY", "  ", networkRequired = false, installed = true)))
    }

    @Test
    fun theNoteSaysWhyVoicesAreMissing_andThatAChosenVoiceIsKept() {
        val note = VoiceListing.LIST_NOTE
        assertTrue(note.contains("INTERNET"))
        assertTrue(note.contains("NOT INSTALLED"))
        assertTrue(note.contains("ALREADY CHOSE"))
        assertEquals(note.uppercase(), note)
    }
}
