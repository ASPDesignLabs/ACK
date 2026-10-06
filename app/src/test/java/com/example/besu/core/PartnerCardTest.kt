// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** What the partner card says (core/PartnerCard.kt), in English and in every language. The wording is the developer's choice and a draft for a speech-language pathologist. */
class PartnerCardTest {

    private val english = StringsXml.map(StringsXml.default)
    private val translations = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private fun words(tag: String): TextSource = if (tag == "en") EnglishText else FileText(tag)
    private val languages = listOf("en") + StringsXml.translations().keys
    private fun all(tag: String): Map<String, String> = if (tag == "en") english else translations.getValue(tag)

    // ---- English, exactly -----------------------------------------------------------------------------------------------------------------

    @Test
    fun theCardIsTheFiveSentencesTheDeveloperChose_inOrder() {
        // Chosen by the developer from three drafts (option C, with a boundary). A change to these is a change to what a person says, so it is theirs to make.
        val expected = listOf(
            "I use this app to talk.",
            "I can hear you and I understand you.",
            "Please wait while I answer.",
            "Please do not take my phone.",
            "If you are not sure what I need, ask me and I will show you.",
        )
        assertEquals(expected, PartnerCard.lines(EnglishText))
        assertEquals(expected.joinToString(" "), PartnerCard.message(EnglishText))
        assertEquals(5, PartnerCard.SENTENCES.size)
    }

    @Test
    fun theQuestionThatAsksFirstIsExactlyThisInEnglish() {
        assertEquals("PLAY THE PARTNER CARD?", EnglishText.get(PartnerCard.ASK_TITLE))
        assertEquals("ACK WILL SAY THIS OUT LOUD AND SHOW IT ON THE SCREEN, LIKE ANY OTHER MESSAGE:", EnglishText.get(PartnerCard.ASK_INTRO))
        assertEquals("IT USES YOUR NORMAL OUTPUT. IF SILENT MODE IS ON, IT IS SHOWN AND NOT SPOKEN.", EnglishText.get(PartnerCard.ASK_SILENT, "SILENT MODE"))
        assertEquals("PLAY IT", EnglishText.get(PartnerCard.ASK_PLAY))
        assertEquals("PARTNER CARD", EnglishText.get(PartnerCard.NAME))
        assertEquals("PARTNER/CARD", PartnerCard.SOURCE)
    }

    // ---- every language ---------------------------------------------------------------------------------------------------------------------

    @Test
    fun everyLanguageHasAllFiveSentences_eachOneALineOfPlainText() {
        for (tag in languages) {
            val lines = PartnerCard.lines(words(tag))
            assertEquals("$tag", 5, lines.size)
            for ((i, line) in lines.withIndex()) {
                assertEquals("$tag sentence ${i + 1} is a real string, not its own name", false, line == PartnerCard.SENTENCES[i])
                assertTrue("$tag sentence ${i + 1} is not blank", line.isNotBlank())
                assertEquals("$tag sentence ${i + 1} has no spaces at either end", line.trim(), line)
                assertFalse("$tag sentence ${i + 1} has no line break (it is joined into one message)", line.contains('\n') || line.contains('\r') || line.contains('\t'))
                assertFalse("$tag sentence ${i + 1} holds no placeholder or markup", Regex("""%|\{|\}|<|>|&|\$""").containsMatchIn(line))
                assertTrue("$tag sentence ${i + 1} is short enough to be read at a glance: '${line}'", line.length <= 80)
            }
            // The message is the sentences with one space between, so what is spoken is what the dialog shows line by line.
            assertEquals(lines.joinToString(" "), PartnerCard.message(words(tag)))
        }
    }

    @Test
    fun eachSentenceEndsLikeASentence_inItsOwnScript() {
        val stops = mapOf("en" to ".", "es" to ".", "pt" to ".", "af" to ".", "ar" to ".", "hi" to "।")
        for (tag in languages) for ((i, line) in PartnerCard.lines(words(tag)).withIndex()) {
            assertTrue("$tag sentence ${i + 1} ends with '${stops.getValue(tag)}': '$line'", line.endsWith(stops.getValue(tag)))
        }
    }

    @Test
    fun aTranslationIsNotTheEnglish_andTheFiveAreDifferentFromEachOther() {
        for (tag in languages) {
            val lines = PartnerCard.lines(words(tag))
            assertEquals("$tag: five different sentences", 5, lines.toSet().size)
            if (tag != "en") for ((i, line) in lines.withIndex()) assertNotEquals("$tag sentence ${i + 1} is still the English", PartnerCard.lines(EnglishText)[i], line)
        }
    }

    @Test
    fun theSentencesAreOrdinaryCase_notCapitals_becauseASpeechEngineMaySpellOutCapitalWords() {
        // The rest of the screens are in capitals; this one is spoken, and so it is written the way a person writes a sentence.
        for (tag in listOf("en", "es", "pt", "af")) for ((i, line) in PartnerCard.lines(words(tag)).withIndex()) {
            assertNotEquals("$tag sentence ${i + 1} must not be all capitals", line.uppercase(Locale.ROOT), line)
        }
    }

    @Test
    fun hindiAndArabicAreWrittenInTheirOwnScriptOnly() {
        for (tag in listOf("hi", "ar")) for ((i, line) in PartnerCard.lines(words(tag)).withIndex()) {
            assertFalse("$tag sentence ${i + 1} holds a Latin letter: '$line'", Regex("[A-Za-z]").containsMatchIn(line))
        }
    }

    @Test
    fun theQuestionNamesSilentModeAsAnArgument_inEveryLanguage_soItFollowsPlainWords() {
        for (tag in languages) {
            val raw = all(tag).getValue(PartnerCard.ASK_SILENT)
            assertEquals("$tag: exactly one place for the silent-mode name", 1, Regex("%1\\$" + "s").findAll(raw).count())
            val said = words(tag).get(PartnerCard.ASK_SILENT, "NAME-GOES-HERE")
            assertTrue("$tag: the name is handed in", said.contains("NAME-GOES-HERE"))
            assertFalse("$tag: no placeholder is left", said.contains("%"))
        }
    }

    @Test
    fun theNameAndTheIconDescriptionAndTheUsageChannelAgree_inEveryLanguage() {
        for (tag in languages) {
            val map = all(tag)
            val name = map.getValue(PartnerCard.NAME)
            assertTrue("$tag: the icon's description starts with the name", map.getValue(PartnerCard.ICON_DESCRIPTION).startsWith(name))
            assertEquals("$tag: the usage summary names the card the same way", name, map.getValue("usage_channel_partner_card"))
            assertTrue("$tag: the question's title names the card", map.getValue(PartnerCard.ASK_TITLE).contains(name))
        }
    }

    @Test
    fun theQuestionsButtonsAreNotBlank_andPlayIsNotCancel_inEveryLanguage() {
        for (tag in languages) {
            val map = all(tag)
            assertTrue(map.getValue(PartnerCard.ASK_PLAY).isNotBlank())
            assertNotEquals("$tag: PLAY must not read like CANCEL", map.getValue("common_cancel"), map.getValue(PartnerCard.ASK_PLAY))
        }
    }

    // ---- which language is spoken -------------------------------------------------------------------------------------------------------

    @Test
    fun theTranslatedCardIsSpokenOnlyWhenTheVoiceFollowsThePhoneAndTheScreensAreInThePhonesLanguage() {
        assertTrue(PartnerCard.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "es", "es"))
        assertTrue(PartnerCard.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "AR", "ar"))
        assertFalse("an install on English (US) speech keeps the English card", PartnerCard.speaksInterfaceLanguage(SpeechLanguage.ENGLISH_US, "es", "es"))
        assertFalse("English screens speak the English card", PartnerCard.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "en", "en"))
        assertFalse("screens in a language the phone is not set to", PartnerCard.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "es", "de"))
        assertFalse("no language known", PartnerCard.speaksInterfaceLanguage(SpeechLanguage.DEVICE, "", "es"))
        // It is the same rule as the HELP walkthrough's spoken guide, on purpose.
        for (speech in SpeechLanguage.values()) for (screens in listOf("en", "es", "ar", "")) for (phone in listOf("en", "es", "ar", "de")) {
            assertEquals(HelpWalkthroughText.speaksInterfaceLanguage(speech, screens, phone), PartnerCard.speaksInterfaceLanguage(speech, screens, phone))
        }
    }

    @Test
    fun theCoreFileIsPlainKotlin() {
        val text = RepoFiles.read("app/src/main/java/com/example/besu/core/PartnerCard.kt")
        assertFalse(text.contains("import android."))
        assertTrue(text.contains("SPDX-License-Identifier: GPL-3.0-or-later"))
    }
}
