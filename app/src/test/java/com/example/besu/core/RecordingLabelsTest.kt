// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The words MANAGE RECORDINGS decides: the overlay switch, and what stands in for a prompt with no text. */
class RecordingLabelsTest {

    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    @Test
    fun theOverlaySwitchSaysOnOrOffInWords_exactlyAsItAlwaysDid() {
        assertEquals("[OVERLAY: ON]", RecordingLabels.overlayToggle(EnglishText, true))
        assertEquals("[OVERLAY: OFF]", RecordingLabels.overlayToggle(EnglishText, false))
    }

    @Test
    fun theOverlaySwitchUsesTheSameOnAndOffWordsAsEverySwitch_inEveryLanguage() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val on = RecordingLabels.overlayToggle(f, true)
            val off = RecordingLabels.overlayToggle(f, false)
            assertTrue("$tag: ON", on.contains(map.getValue("common_on")))
            assertTrue("$tag: OFF", off.contains(map.getValue("common_off")))
            assertNotEquals("$tag: ON and OFF read the same", on, off)
            assertTrue("$tag: still bracketed", on.startsWith("[") && on.endsWith("]"))
            assertFalse("$tag: a resource name was shown: $on", on.contains("manage_rec_"))
        }
    }

    @Test
    fun whatTheOverlayIsSentIsNeverTranslated_whateverTheLanguage() {
        // The overlay is for whoever is looking at the screen; the visual overlay and everything spoken stay as they were.
        assertEquals("(EMPTY PROMPT)", RecordingLabels.Missing.EMPTY_PROMPT.overlayText)
        assertEquals("(UNKNOWN NODE)", RecordingLabels.Missing.UNKNOWN_NODE.overlayText)
    }

    @Test
    fun theListShowsTheEnglishPlaceholdersAsTheyWere_andTheLanguagesOwnWordsOtherwise() {
        assertEquals("(EMPTY PROMPT)", RecordingLabels.missingText(EnglishText, RecordingLabels.Missing.EMPTY_PROMPT))
        assertEquals("(UNKNOWN NODE)", RecordingLabels.missingText(EnglishText, RecordingLabels.Missing.UNKNOWN_NODE))
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val empty = RecordingLabels.missingText(f, RecordingLabels.Missing.EMPTY_PROMPT)
            val unknown = RecordingLabels.missingText(f, RecordingLabels.Missing.UNKNOWN_NODE)
            assertNotEquals("$tag: still English", RecordingLabels.Missing.EMPTY_PROMPT.overlayText, empty)
            assertNotEquals("$tag: still English", RecordingLabels.Missing.UNKNOWN_NODE.overlayText, unknown)
            assertNotEquals("$tag: the two read the same", empty, unknown)
            assertTrue("$tag: kept the brackets", empty.startsWith("(") && empty.endsWith(")") && unknown.startsWith("(") && unknown.endsWith(")"))
        }
    }
}
