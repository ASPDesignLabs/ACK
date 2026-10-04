// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The words around the PLAIN WORDS switch: said in words, the same in both modes, honest that nothing works differently, and that typed commands keep working. */
class PlainWordsTextTest {

    private val strings: Map<String, String> by lazy { StringsXml.map(StringsXml.default) }
    private fun s(name: String) = strings.getValue(name)

    @Test
    fun theSwitchSaysOnOrOffInWords_notOnlyByColour() {
        assertEquals("PLAIN WORDS: ON", s("plain_words_switch_on"))
        assertEquals("PLAIN WORDS: OFF", s("plain_words_switch_off"))
        assertNotEquals(s("plain_words_switch_on"), s("plain_words_switch_off"))
    }

    @Test
    fun theSwitchWordingIsNotAPlainLabel_soItReadsTheSameInBothModesAndCanAlwaysBeFound() {
        // The label table is what PLAIN WORDS changes; the switch itself must never be in it.
        assertTrue(LabelKey.values().none { it.name.contains("PLAIN_WORDS") })
        assertTrue(strings.keys.none { it.startsWith("label_") && it.contains("plain_words") })
    }

    @Test
    fun theExplanation_saysNothingChangesHowAMessageGoesOutUnlessASwitchIsTurnedOn_itTakesEffectAtOnce_andTypedCommandsKeepWorking() {
        val text = s("plain_words_explanation")
        // The buttons it adds (SEND QUIETLY and the others) do change how a message goes out once the person turns one on, so it must not claim
        // that nothing works differently at all.
        assertTrue(text.contains("NOTHING CHANGES HOW A MESSAGE GOES OUT UNLESS YOU TURN ONE OF THOSE ON"))
        assertTrue(!text.contains("NOTHING WORKS DIFFERENTLY"))
        assertTrue(text.contains("AT ONCE"))
        assertTrue(text.contains("TYPED COMMANDS KEEP WORKING"))
    }

    @Test
    fun theOffer_saysItIsOff_andThatNothingChangesUnlessTheyTurnItOn() {
        val text = s("plain_words_offer")
        assertTrue(text.contains("IT IS OFF"))
        assertTrue(text.contains("UNLESS YOU TURN IT ON"))
        assertNotEquals(s("plain_words_turn_on"), s("plain_words_not_now"))
    }

    @Test
    fun theEnglishWordingIsInCapitals_theAppsHouseStyle() {
        for (name in listOf(
            "plain_words_switch_on", "plain_words_switch_off", "plain_words_explanation", "plain_words_offer", "plain_words_turn_on", "plain_words_not_now",
        )) assertEquals(name, s(name).uppercase(), s(name))
    }
}
