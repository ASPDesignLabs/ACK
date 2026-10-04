// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * PLAIN WORDS: every jargon label has an everyday name, kept as data in `res/values/strings.xml` (the same place its translations go), and a
 * test keeps the two columns honest. Nothing here changes what a button does, only what it is called.
 */
class PlainLabelsTest {

    private val strings: Map<String, String> by lazy { StringsXml.map(StringsXml.default) }

    private fun standard(key: LabelKey) = strings.getValue(key.resourceName(plain = false))
    private fun plain(key: LabelKey) = strings.getValue(key.resourceName(plain = true))

    // ---- the table is complete --------------------------------------------------------------------------------------------------

    @Test
    fun everyKeyHasAStandardAndAPlainText() {
        for (key in LabelKey.values()) {
            assertTrue("${key.name}: missing ${key.resourceName(false)}", key.resourceName(false) in strings)
            assertTrue("${key.name}: missing ${key.resourceName(true)}", key.resourceName(true) in strings)
            assertTrue("${key.name}: blank standard text", standard(key).isNotBlank())
            assertTrue("${key.name}: blank plain text", plain(key).isNotBlank())
        }
    }

    @Test
    fun noLabelStringExistsWithoutAKey_soNothingIsLeftBehindWhenAKeyIsRenamed() {
        val known = LabelKey.values().flatMap { listOf(it.resourceName(false), it.resourceName(true)) }.toSet()
        val orphans = strings.keys.filter { it.startsWith("label_") && it !in known }
        assertTrue("label strings with no LabelKey: $orphans", orphans.isEmpty())
    }

    @Test
    fun theResourceNamesAreDerivedTheSameWayEverywhere() {
        assertEquals("label_target_computer", LabelKey.TARGET_COMPUTER.resourceName(plain = false))
        assertEquals("label_target_computer_plain", LabelKey.TARGET_COMPUTER.resourceName(plain = true))
        assertEquals("label_twist_0_mapped_plain", LabelKey.TWIST_0_MAPPED.resourceName(plain = true))
    }

    // ---- the plain words really are plain -----------------------------------------------------------------------------------------

    /** Keys whose standard wording already is everyday English, so the plain text is the same on purpose. */
    private val alreadyPlain = setOf(LabelKey.NAV_TYPE, LabelKey.DECK_TYPE_EMERGENCY, LabelKey.DECK_TYPE_EMOJI)

    @Test
    fun aPlainTextDiffersFromTheStandardOne_exceptTheThreeAlreadyPlainOnes() {
        val same = LabelKey.values().filter { standard(it).equals(plain(it), ignoreCase = true) }.toSet()
        assertEquals("plain text equal to the standard text: ${same.map { it.name }}", alreadyPlain, same)
    }

    @Test
    fun thePlainTextNeverUsesTheJargonItReplaces() {
        // Words an outsider cannot be expected to know. "TWIST" and "TYPE" are ordinary words and are not on the list.
        val jargon = listOf(
            "DECK", "MATRIX", "POSE", "TERMINAL", "VARIABLE", "PROTOCOL", "ARCHITECT", "DSP", "GEO", "STATUSBOX", "TARGET", "NODE",
            "GRID", "VOX", "CRYO", "OVERRIDE", "JSON", "BITCRUSH", "ROBOTIC", "IDENTITY", "DEFEND", "CONNECT",
        )
        for (key in LabelKey.values()) {
            val words = Regex("[A-Z]+").findAll(plain(key).uppercase()).map { it.value }.toSet()
            val used = jargon.filter { it in words }
            assertTrue("${key.name} plain text still uses jargon $used: \"${plain(key)}\"", used.isEmpty())
        }
    }

    /** Two keys may share a plain text only when they are the same thing named from two places (the tab, and its own screen's heading). */
    private val sharedPlain: Map<String, Set<LabelKey>> = mapOf(
        "HISTORY" to setOf(LabelKey.NAV_LOGS, LabelKey.TERMINAL_LOG),
        "PEOPLE AND PLACES" to setOf(LabelKey.NAV_TARGETS, LabelKey.TARGET_COMPUTER),
        "LOCATION ALERTS" to setOf(LabelKey.NAV_ZONES, LabelKey.GEO_PROTOCOL),
        "VOICE AND SOUND" to setOf(LabelKey.NAV_AUDIO, LabelKey.AUDIO_ARCHITECT),
    )

    @Test
    fun twoDifferentButtonsNeverShareAPlainName_exceptTheFourListedSamePlaceNames() {
        val shared = LabelKey.values().groupBy { plain(it).uppercase() }.filterValues { it.size > 1 }.mapValues { it.value.toSet() }
        // A key that is already plain shares its text with its own standard form, not with another key, so only real clashes are left.
        assertEquals("plain names used for two different keys", sharedPlain, shared)
    }

    @Test
    fun theEnglishWordsAreInCapitals_theAppsHouseStyle() {
        for (key in LabelKey.values()) {
            // The mixed-case slot names are stored data (Twist 1) and are standard text only; the plain text is always capitals.
            // A format placeholder such as %1$s is lower case by design; everything around it is capitals.
            val words = plain(key).replace(Regex("""%\d+\$[sdf]"""), "")
            assertEquals("${key.name} plain", words.uppercase(), words)
        }
    }

    @Test
    fun theFormatPlaceholdersMatchBetweenTheStandardAndPlainText() {
        for (key in LabelKey.values()) {
            assertEquals("${key.name}: placeholders differ", StringsXml.placeholders(standard(key)), StringsXml.placeholders(plain(key)))
        }
        assertEquals(listOf("%1\$s"), StringsXml.placeholders(standard(LabelKey.VARIABLE_TAG)))
    }

    // ---- the decisions the developer made ----------------------------------------------------------------------------------------

    @Test
    fun theThreeGroupsAreNamedAboutMeINeedSpaceAndSocial() {
        assertEquals("ABOUT ME", plain(LabelKey.POSE_IDENTITY))
        assertEquals("I NEED SPACE", plain(LabelKey.POSE_DEFEND))
        assertEquals("SOCIAL", plain(LabelKey.POSE_CONNECT))
    }

    @Test
    fun theStandardTextOfEachStoredNameIsExactlyWhatTheAppAlreadyShows() {
        // These are the labels CommandRepository stores and the screens draw; standard mode must show them unchanged.
        assertEquals("Twist 0 (Default)", standard(LabelKey.TWIST_0))
        assertEquals("Twist 1", standard(LabelKey.TWIST_1))
        assertEquals("Twist 3 (Mapped)", standard(LabelKey.TWIST_3_MAPPED))
        assertEquals("PROTOCOL", standard(LabelKey.SETTINGS_ENTRY))
        assertEquals("TARGET COMPUTER", standard(LabelKey.TARGET_COMPUTER))
        assertEquals("SHARED ROOT VARIABLES", standard(LabelKey.SHARED_VARIABLES))
    }

    // ---- stored slot names ---------------------------------------------------------------------------------------------------------

    @Test
    fun aStoredSlotNameIsRecognisedOnlyWhenItIsExactlyOneOfTheKnownOnes() {
        assertEquals(LabelKey.TWIST_0, PlainLabels.slotLabelKey("Twist 0 (Default)"))
        assertEquals(LabelKey.TWIST_2, PlainLabels.slotLabelKey("Twist 2"))
        assertEquals(LabelKey.TWIST_1_MAPPED, PlainLabels.slotLabelKey("Twist 1 (Mapped)"))
        // A name the person typed is never translated or renamed.
        assertNull(PlainLabels.slotLabelKey("Twist 1 (mine)"))
        assertNull(PlainLabels.slotLabelKey("twist 1"))
        assertNull(PlainLabels.slotLabelKey("Twist 4"))
        assertNull(PlainLabels.slotLabelKey(" Twist 1"))
        assertNull(PlainLabels.slotLabelKey(""))
    }

    @Test
    fun everySlotKeyIsRecognisedFromItsOwnStandardText() {
        for (key in LabelKey.values().filter { Regex("""TWIST_\d(_MAPPED)?""").matches(it.name) }) {
            assertEquals(key, PlainLabels.slotLabelKey(standard(key)))
        }
    }

    @Test
    fun aPoseNameIsRecognisedOnlyWhenItIsExactlyOneOfTheThree() {
        assertEquals(LabelKey.POSE_IDENTITY, PlainLabels.poseLabelKey("IDENTITY"))
        assertEquals(LabelKey.POSE_DEFEND, PlainLabels.poseLabelKey("DEFEND"))
        assertEquals(LabelKey.POSE_CONNECT, PlainLabels.poseLabelKey("CONNECT"))
        // A custom layer's own name, in any case, is never renamed.
        assertNull(PlainLabels.poseLabelKey("identity"))
        assertNull(PlainLabels.poseLabelKey("WORK"))
        assertNull(PlainLabels.poseLabelKey(""))
    }

    @Test
    fun theKeyNamesCanBeLookedUpSafely() {
        assertEquals(LabelKey.DECK, LabelKey.fromName("DECK"))
        assertNull(LabelKey.fromName("deck"))
        assertNull(LabelKey.fromName("NOT_A_KEY"))
        assertNull(LabelKey.fromName(""))
    }
}
