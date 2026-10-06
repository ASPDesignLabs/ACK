// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The limits statement (core/LimitsNotice.kt): what it says, in which words, in every language, and where its one-time banner may and may not appear.
 * The screens are held to this in LimitsNoticeWiringTest; the match with the website is LimitsNoticeWebsiteTest.
 */
class LimitsNoticeTest {

    private val english = listOf(
        "NOT A SUBSTITUTE FOR PROFESSIONAL AAC EVALUATION OR SPEECH-LANGUAGE THERAPY.",
        "BUILT BY ONE PERSON AS A PERSONAL TOOL, SHARED AS-IS.",
        "KEEP ANOTHER WAY TO COMMUNICATE AVAILABLE AT ALL TIMES.",
    )

    // ---- the words ---------------------------------------------------------------------------------------------------------------

    @Test
    fun theEnglishStatementIsExactlyTheThreeAgreedSentences_inOrder() {
        assertEquals(english, LimitsNotice.sentences(EnglishText))
        assertEquals(english.joinToString(" "), LimitsNotice.statement(EnglishText))
    }

    @Test
    fun theStatementIsThreeSeparateResources_joinedWithASpaceInCode() {
        // Android trims a space at the end of a string, so the sentences are joined here and never by a trailing space in the resource.
        assertEquals(3, LimitsNotice.SENTENCES.size)
        assertEquals("a name is used twice", LimitsNotice.SENTENCES.size, LimitsNotice.SENTENCES.toSet().size)
        for (name in LimitsNotice.SENTENCES) {
            val raw = EnglishText.get(name)
            assertEquals("$name must not start or end with a space", raw.trim(), raw)
        }
    }

    @Test
    fun theEnglishIsInCapitalsLikeTheRestOfTheApp_andEachSentenceEndsWithAFullStop() {
        for (s in LimitsNotice.sentences(EnglishText) + EnglishText.get(LimitsNotice.ABOUT_TITLE) + EnglishText.get(LimitsNotice.GOT_IT)) assertEquals(s.uppercase(), s)
        for (s in LimitsNotice.sentences(EnglishText)) assertTrue(s, s.endsWith("."))
    }

    @Test
    fun theStatementNeverClaimsAnythingAboutWhatACKDoesForAnyone() {
        // The evaluation found no evidence yet that ACK helps. These words would say it does, or that it is a medical product.
        val all = LimitsNotice.statement(EnglishText) + " " + EnglishText.get(LimitsNotice.ABOUT_TITLE)
        for (word in listOf("PROVEN", "EFFECTIVE", "CLINICALLY", "IMPROVE", "CURE", "TREAT ", "GUARANTEE", "MEDICAL DEVICE", "APPROVED", "CERTIFIED")) {
            assertFalse("the statement must not say '$word'", all.contains(word))
        }
    }

    @Test
    fun theTitleAndTheButtonAreThePlainWordsTheyWereAskedFor() {
        assertEquals("ABOUT ACK", EnglishText.get(LimitsNotice.ABOUT_TITLE))
        assertEquals("GOT IT", EnglishText.get(LimitsNotice.GOT_IT))
    }

    // ---- the line that says where to read it again --------------------------------------------------------------------------------------

    @Test
    fun theWhereLineNamesTheSettingsButtonAndTheSectionAsTheyAreCalled() {
        assertEquals("YOU CAN READ THIS AGAIN IN PROTOCOL, UNDER ABOUT ACK.", LimitsNotice.whereToReadAgain(EnglishText, "PROTOCOL"))
        // With PLAIN WORDS on, the button is called SETTINGS and the sentence follows it.
        assertEquals("YOU CAN READ THIS AGAIN IN SETTINGS, UNDER ABOUT ACK.", LimitsNotice.whereToReadAgain(EnglishText, "SETTINGS"))
    }

    @Test
    fun aNameHandedInIsShownAsItIs_notReadAsAFormat() {
        val odd = "50% %s \$1 \"QUOTED\""
        assertTrue(LimitsNotice.whereToReadAgain(EnglishText, odd).contains(odd))
    }

    // ---- where the banner may appear ---------------------------------------------------------------------------------------------------

    @Test
    fun theBannerShowsOnTheTerminalAndSettings_whileItHasNotBeenDismissed() {
        assertTrue(LimitsNotice.shouldShowBanner(seen = false, viewMode = "TERMINAL"))
        assertTrue(LimitsNotice.shouldShowBanner(seen = false, viewMode = "SETTINGS"))
    }

    @Test
    fun onceDismissedItNeverShowsAgain_onAnyScreen() {
        for (screen in listOf("TERMINAL", "SETTINGS", "MATRIX", "TYPE", "AUDIO", "TARGETS", "GEO", "")) {
            assertFalse(screen, LimitsNotice.shouldShowBanner(seen = true, viewMode = screen))
        }
    }

    @Test
    fun itNeverShowsOnADeckOrAnyOtherScreen_soItCannotMoveAButtonAboutToBeTapped() {
        // MATRIX is the view mode of every deck-shaped screen (Matrix, Quick Actions, Emergency, Emoji, GIF); TYPE is the Statement Composer.
        for (screen in listOf("MATRIX", "TYPE", "AUDIO", "TARGETS", "GEO", "", "terminal", "settings", "TERMINAL ")) {
            assertFalse(screen, LimitsNotice.shouldShowBanner(seen = false, viewMode = screen))
        }
        assertEquals(setOf("TERMINAL", "SETTINGS"), LimitsNotice.BANNER_SCREENS)
    }

    // ---- every language ----------------------------------------------------------------------------------------------------------------

    @Test
    fun everyLanguageHasEveryWordOfTheStatement_andNoneIsEnglishOrBlank() {
        val names = LimitsNotice.SENTENCES + LimitsNotice.ABOUT_TITLE + LimitsNotice.GOT_IT + "about_banner_where"
        for (tag in StringsXml.translations().keys) {
            val words = FileText(tag)
            for (name in names) {
                val text = words.get(name, "A", "B")
                assertTrue("$tag/$name is missing", text != name)
                assertTrue("$tag/$name is blank", text.isNotBlank())
                assertNotEquals("$tag/$name is still English", EnglishText.get(name, "A", "B"), text)
            }
        }
    }

    @Test
    fun theWhereLineHoldsBothNamesInEveryLanguage_inWhateverOrderThatLanguageNeeds() {
        for (tag in StringsXml.translations().keys) {
            val line = LimitsNotice.whereToReadAgain(FileText(tag), "SETTINGS-NAME")
            assertTrue("$tag: the settings name is missing", line.contains("SETTINGS-NAME"))
            assertTrue("$tag: the section title is missing", line.contains(FileText(tag).get(LimitsNotice.ABOUT_TITLE)))
        }
    }

    @Test
    fun theThreeSentencesAreAllPresentInEveryLanguage_asThreeDistinctSentences() {
        for (tag in StringsXml.translations().keys) {
            val sentences = LimitsNotice.sentences(FileText(tag))
            assertEquals("$tag", 3, sentences.toSet().size)
            assertEquals("$tag", sentences.joinToString(" "), LimitsNotice.statement(FileText(tag)))
        }
    }

    @Test
    fun theDraftTranslationsKeepTheLatinCapitalsStyle_andNameACKAndAAC() {
        for (tag in listOf("es", "pt", "af")) {
            val words = FileText(tag)
            for (name in LimitsNotice.SENTENCES + LimitsNotice.ABOUT_TITLE + LimitsNotice.GOT_IT) {
                val text = words.get(name)
                assertEquals("$tag/$name", text.uppercase(), text)
            }
        }
        // The first sentence names AAC as every other translated string in the app does (the acronym is kept as it is).
        for (tag in StringsXml.translations().keys) assertTrue(tag, FileText(tag).get(LimitsNotice.SENTENCES[0]).contains("AAC"))
        assertTrue(FileText("es").get(LimitsNotice.ABOUT_TITLE).contains("ACK"))
    }
}
