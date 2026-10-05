// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** What SETTINGS > AUDIO OUTPUT ROUTING says about where speech goes, in English exactly as it always was and in every language. */
class OutputRouteTextTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    @Test
    fun theEnglishSummaryIsExactlyWhatTheScreenAlwaysSaid() {
        assertEquals("OVERRIDDEN BY FORCE SPEAKER ABOVE", OutputRouteText.summary(t, true, "AUTO", null, "FORCE SPEAKER"))
        assertEquals("OVERRIDDEN BY FORCE SPEAKER ABOVE", OutputRouteText.summary(t, true, "BLUETOOTH", "Pixel Buds", "FORCE SPEAKER"))
        assertEquals("Pixel Buds", OutputRouteText.summary(t, false, "BLUETOOTH", "Pixel Buds", "FORCE SPEAKER"))
        assertEquals("BLUETOOTH DEVICE", OutputRouteText.summary(t, false, "BLUETOOTH", null, "FORCE SPEAKER"))
        assertEquals("ACK WATCH", OutputRouteText.summary(t, false, "WATCH", null, "FORCE SPEAKER"))
        assertEquals("AUTO (SYSTEM DEFAULT)", OutputRouteText.summary(t, false, "AUTO", null, "FORCE SPEAKER"))
        // A mode this screen does not know falls back to AUTO, as the screen always did.
        assertEquals("AUTO (SYSTEM DEFAULT)", OutputRouteText.summary(t, false, "SOMETHING_ELSE", null, "FORCE SPEAKER"))
        assertEquals("CONNECTED", OutputRouteText.watchHint(t, true))
        assertEquals("NOT CURRENTLY CONNECTED -- FALLS BACK TO AUTO WHEN UNREACHABLE", OutputRouteText.watchHint(t, false))
        assertEquals("BLUETOOTH DEVICE", OutputRouteText.bluetoothName(t, null))
    }

    @Test
    fun theThreeModeNamesAreTheStoredOnesAndNeverTranslated() {
        assertEquals("AUTO", OutputRouteText.AUTO)
        assertEquals("BLUETOOTH", OutputRouteText.BLUETOOTH)
        assertEquals("WATCH", OutputRouteText.WATCH)
        // The service that routes the sound and the backup that validates the choice read these exact strings.
        val service = RepoFiles.read("app/src/main/java/com/example/besu/output/OutputService.kt")
        assertTrue(service.contains("outputRouteMode == \"WATCH\""))
        assertTrue(service.contains("outputRouteMode != \"BLUETOOTH\""))
        val backup = RepoFiles.read("app/src/main/java/com/example/besu/backup/TransferManager.kt")
        assertTrue(backup.contains("setOf(\"AUTO\", \"BLUETOOTH\", \"WATCH\")"))
    }

    @Test
    fun eachRouteReadsInTheLanguage_andAnotherWordForEachRoute() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val auto = OutputRouteText.summary(f, false, "AUTO", null, "X")
            val watch = OutputRouteText.summary(f, false, "WATCH", null, "X")
            val bluetooth = OutputRouteText.summary(f, false, "BLUETOOTH", null, "X")
            assertEquals("$tag: auto", map.getValue("settings_route_auto"), auto)
            assertEquals("$tag: watch", map.getValue("settings_route_watch"), watch)
            assertEquals("$tag: bluetooth", map.getValue("settings_route_bt_device"), bluetooth)
            assertEquals("$tag: three different routes read three different ways", 3, setOf(auto, watch, bluetooth).size)
            assertNotEquals("$tag: auto is still English", "AUTO (SYSTEM DEFAULT)", auto)
        }
    }

    @Test
    fun whileForceSpeakerIsOnTheLineNamesTheSwitchItWasGiven_inEveryLanguage() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val said = OutputRouteText.summary(f, true, "WATCH", null, map.getValue("label_force_speaker"))
            assertTrue("$tag: names the switch ($said)", said.contains(map.getValue("label_force_speaker")))
            assertFalse("$tag: a forced speaker is not shown as the watch", said.contains(map.getValue("settings_route_watch")))
            assertFalse("$tag: a placeholder was left in: $said", said.contains("%1"))
        }
    }

    @Test
    fun aBluetoothDevicesOwnNameIsShownExactlyAsTheCachedLabel_evenWhenItReadsLikeAWordOfOurs() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            for (label in listOf("Pixel Buds", "AUTO", map.getValue("settings_route_auto"), "WATCH")) {
                assertEquals("$tag: $label", label, OutputRouteText.summary(f, false, "BLUETOOTH", label, "X"))
                assertEquals("$tag: $label (bluetoothName)", label, OutputRouteText.bluetoothName(f, label))
            }
        }
    }

    @Test
    fun theNotConnectedHintNamesTheAutoRouteByTheSameWordAsTheOptionDoes() {
        // "FALLS BACK TO AUTO" must point at the option that is called AUTO (SYSTEM DEFAULT): the first word of that label is in the hint, in every language.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val word = map.getValue("settings_route_auto").substringBefore(" (")
            assertTrue("$tag: '$word' is in '${map.getValue("settings_route_not_connected")}'", map.getValue("settings_route_not_connected").contains(word))
            assertNotEquals("$tag: connected and not connected read the same", map.getValue("settings_route_connected"), map.getValue("settings_route_not_connected"))
        }
    }

    @Test
    fun theWatchHintIsOneOfTwoWords_inEveryLanguage() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            assertEquals("$tag: connected", map.getValue("settings_route_connected"), OutputRouteText.watchHint(f, true))
            assertEquals("$tag: not connected", map.getValue("settings_route_not_connected"), OutputRouteText.watchHint(f, false))
        }
    }
}
