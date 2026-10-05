// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The words around the profile-change warning say what it does and, as plainly, what it does not cover, in English exactly as they always were and in every language. The dialog's own list
 * (the heading's plural form, each gesture's line) is held here too; ProfileSwapDiffTest holds the decision, ProfileWarningWiringTest where the warning is and is not wired.
 */
class ProfileWarningTextTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    // ---- English is exactly what it always said -------------------------------------------------------------------------------------

    @Test
    fun theSwitchSaysOnOrOffInWords_notOnlyByColour() {
        assertEquals("WARN BEFORE PROFILE CHANGES: ON", ProfileWarningText.switchLabel(t, true))
        assertEquals("WARN BEFORE PROFILE CHANGES: OFF", ProfileWarningText.switchLabel(t, false))
        assertNotEquals(ProfileWarningText.switchLabel(t, true), ProfileWarningText.switchLabel(t, false))
    }

    @Test
    fun theExplanation_isExactlyTheThreeSentencesItAlwaysWas_joinedByOneSpace() {
        assertEquals(
            "WHEN CHANGING PROFILE WOULD MAKE A MATRIX GESTURE SAY SOMETHING DIFFERENT, ACK SHOWS WHAT WOULD CHANGE AND ASKS FIRST. " +
                "THIS IS ABOUT THE MATRIX DECK ONLY: QUICK ACTIONS, EMERGENCY, EMOJI AND GIF DECKS HAVE NO PROFILES, SO THEIR BUTTONS NEVER MOVE. " +
                "IT ONLY APPLIES TO THE PROFILE MENU IN THE APP. THE HOME-SCREEN WIDGET AND THE WATCH CHANGE PROFILE WITHOUT ASKING.",
            ProfileWarningText.switchExplanation(t)
        )
    }

    @Test
    fun theExplanation_saysItIsAboutTheMatrixOnly_andThatTheWidgetAndWatchAreNotCovered() {
        val text = ProfileWarningText.switchExplanation(t)
        assertTrue(text.contains("MATRIX"))
        assertTrue(text.contains("QUICK ACTIONS"))
        assertTrue(text.contains("WIDGET"))
        assertTrue(text.contains("WATCH"))
        assertTrue(text.contains("WITHOUT ASKING"))
    }

    @Test
    fun theDialogAndOfferWordsAreHeldExactly() {
        val expected = mapOf(
            "profile_warn_dialog_title" to "CHANGE PROFILE?", "profile_warn_stay" to "STAY", "profile_warn_change" to "CHANGE PROFILE",
            "profile_warn_dont_show" to "DO NOT SHOW THIS WARNING AGAIN", "profile_warn_dont_show_note" to "YOU CAN TURN IT BACK ON IN SETTINGS.",
            "profile_warn_offer" to "NEW: ACK CAN WARN YOU BEFORE A PROFILE CHANGE MAKES A GESTURE SAY SOMETHING DIFFERENT. IT IS OFF FOR YOU, AND NOTHING CHANGES UNLESS YOU TURN IT ON.",
            "profile_warn_offer_turn_on" to "TURN ON", "profile_warn_offer_not_now" to "NOT NOW", "profile_swap_blank" to "(BLANK)",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
        assertEquals("SLOT 1: old 1, becomes: new 1", t.get("profile_swap_line", "SLOT 1", "old 1", "new 1"))
        assertEquals("AND 5 MORE", t.get("profile_swap_more", 5))
    }

    @Test
    fun theDialogsTwoButtons_areDistinct_andTheBoxSaysWhereToTurnItBackOn() {
        assertNotEquals(english.getValue("profile_warn_stay"), english.getValue("profile_warn_change"))
        assertTrue(english.getValue("profile_warn_dont_show_note").contains("SETTINGS"))
    }

    @Test
    fun theOffer_saysItIsOffAndThatNothingChangesUnlessTheyTurnItOn() {
        val text = english.getValue("profile_warn_offer")
        assertTrue(text.contains("OFF FOR YOU"))
        assertTrue(text.contains("UNLESS YOU TURN IT ON"))
        assertNotEquals(english.getValue("profile_warn_offer_turn_on"), english.getValue("profile_warn_offer_not_now"))
    }

    @Test
    fun noEnglishWordingIsInLowerCase_theAppsHouseStyle_exceptTheConnectorBetweenTwoPhrasesThePersonTyped() {
        // (A format specifier like %1$s is lower case by nature, so it is taken out before the check.)
        for ((name, text) in english.filter { it.key.startsWith("profile_warn_") }) {
            val words = text.replace(Regex("""%\d+\$[sd]"""), "")
            assertEquals(name, words.uppercase(), words)
        }
        assertEquals("(BLANK)", english.getValue("profile_swap_blank").uppercase())
        // "becomes:" is lower case on purpose: it sits between two phrases the person typed, so it is the one word that is not theirs.
        assertTrue(english.getValue("profile_swap_line").contains("becomes:"))
    }

    // ---- the dialog's list -----------------------------------------------------------------------------------------------------------

    private fun change(i: Int) = SlotChange("p$i", "SLOT $i", "old $i", "new $i")

    @Test
    fun theHeadingCountsTheGesturesInTheLanguagesPluralForm_andNamesTheProfile() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val said = ProfileSwapText.heading(f, 7, "WORK")
            assertTrue("$tag: the count in '$said'", said.contains("7"))
            assertTrue("$tag: the profile in '$said'", said.contains("WORK"))
            assertFalse("$tag: a resource name or a placeholder leaked: $said", said.contains("profile_swap") || said.contains("%"))
            assertNotEquals("$tag: still English", "7 GESTURES WILL SAY SOMETHING DIFFERENT IF YOU CHANGE TO WORK:", said)
        }
    }

    @Test
    fun eachListedLineHoldsTheGesturesNameAndBothPhrasesExactly_inEveryLanguage() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val line = ProfileSwapText.lines(f, listOf(change(1))).single()
            assertTrue("$tag: gesture name in '$line'", line.contains("SLOT 1"))
            assertTrue("$tag: old phrase in '$line'", line.contains("old 1"))
            assertTrue("$tag: new phrase in '$line'", line.contains("new 1"))
            assertTrue("$tag: the old phrase comes before the new one in '$line'", line.indexOf("old 1") < line.indexOf("new 1"))
            assertFalse("$tag: a placeholder leaked: $line", line.contains("%"))
        }
    }

    @Test
    fun aGestureIsNamedByTheNameItIsGiven_andByTheStoredOneWhenNoneIsGiven() {
        val changes = (1..3).map { change(it) }
        val named = ProfileSwapText.lines(t, changes, listOf("ONE", "TWO", "THREE"))
        assertEquals("ONE: old 1, becomes: new 1", named[0])
        assertEquals("THREE: old 3, becomes: new 3", named[2])
        // A short list of names is not a crash: the rest fall back to the stored names.
        val short = ProfileSwapText.lines(t, changes, listOf("ONE"))
        assertEquals("ONE: old 1, becomes: new 1", short[0])
        assertEquals("SLOT 2: old 2, becomes: new 2", short[1])
    }

    @Test
    fun theAndMoreLineCountsWhatIsLeft_inEveryLanguage() {
        for ((tag, _) in translations) {
            val lines = ProfileSwapText.lines(FileText(tag), (1..9).map { change(it) })
            assertEquals("$tag: four listed and one more line", ProfileSwapText.MAX_LISTED + 1, lines.size)
            assertTrue("$tag: ${lines.last()}", lines.last().contains("5"))
            assertNotEquals("$tag: still English", "AND 5 MORE", lines.last())
        }
    }

    @Test
    fun aBlankPhraseIsSaidToBeBlankInTheLanguage_notShownAsNothing() {
        for ((tag, map) in translations) {
            val line = ProfileSwapText.lines(FileText(tag), listOf(SlotChange("p", "SLOT", "", "Hello."))).single()
            assertTrue("$tag: ${map.getValue("profile_swap_blank")} in '$line'", line.contains(map.getValue("profile_swap_blank")))
            assertNotEquals("$tag: still English", "(BLANK)", map.getValue("profile_swap_blank"))
        }
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------

    @Test
    fun theSwitchSaysOnOrOffInTheLanguage_withTheSharedWords() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            assertTrue("$tag: ON", ProfileWarningText.switchLabel(f, true).contains(map.getValue("common_on")))
            assertTrue("$tag: OFF", ProfileWarningText.switchLabel(f, false).contains(map.getValue("common_off")))
            assertNotEquals("$tag: on and off read the same", ProfileWarningText.switchLabel(f, true), ProfileWarningText.switchLabel(f, false))
        }
    }

    @Test
    fun theExplanationIsThreeSentences_andNamesTheDeckTypesTheWayTheLanguagesOwnLabelsDo() {
        for ((tag, map) in translations) {
            val said = ProfileWarningText.switchExplanation(FileText(tag))
            for (kind in listOf("matrix", "quick", "emergency", "emoji", "gif")) {
                assertTrue("$tag: ${map.getValue("label_deck_type_$kind")} is in the explanation", said.contains(map.getValue("label_deck_type_$kind")))
            }
            for (part in listOf("profile_warn_explain_1", "profile_warn_explain_2", "profile_warn_explain_3")) assertTrue("$tag: $part is in the explanation", said.contains(map.getValue(part)))
            // The second sentence is the one that says which decks have no profiles, so it is the one that names all five.
            for (kind in listOf("matrix", "quick", "emergency", "emoji", "gif")) {
                assertTrue("$tag: ${map.getValue("label_deck_type_$kind")} is in the sentence about the decks", map.getValue("profile_warn_explain_2").contains(map.getValue("label_deck_type_$kind")))
            }
            assertFalse("$tag: no double space where the sentences join", said.contains("  "))
        }
    }

    @Test
    fun theTwoButtonsAndTheTwoOfferButtonsReadDifferentlyInEveryLanguage_soTheWrongOneCannotBeTappedByReading() {
        val pairs = listOf(
            "profile_warn_stay" to "profile_warn_change", "profile_warn_offer_turn_on" to "profile_warn_offer_not_now", "profile_warn_dialog_title" to "profile_warn_change",
            "profile_warn_dont_show" to "profile_warn_dont_show_note", "profile_warn_offer" to "profile_warn_explain_1",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
    }

    @Test
    fun theArgumentsAreWhereTheCodePutsThem() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertTrue("$tag: the switch takes ON or OFF", map.getValue("profile_warn_switch").contains("%1\$s"))
            val line = map.getValue("profile_swap_line")
            assertTrue("$tag: name, old, new in that order", line.indexOf("%1\$s") in 0 until line.indexOf("%2\$s") && line.indexOf("%2\$s") < line.indexOf("%3\$s"))
            assertTrue("$tag: the more line takes the number", map.getValue("profile_swap_more").contains("%1\$d"))
            for (name in map.keys.filter { it.startsWith("profile_warn_") } - "profile_warn_switch") {
                assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
            }
        }
    }
}
