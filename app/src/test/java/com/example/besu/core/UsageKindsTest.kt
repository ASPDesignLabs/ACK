// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Which channel and kind a message counts under (core/UsageKinds.kt). */
class UsageKindsTest {

    // ---- channels ---------------------------------------------------------------------------------------------------------------------

    @Test
    fun everyTagTheAppSendsTodayMapsToItsChannel() {
        for ((tag, channel) in UsageKinds.KNOWN_SOURCES) {
            val concrete = tag.replace("*", "IDENTITY")
            assertEquals(tag, channel, UsageKinds.channelOf(concrete))
        }
        assertEquals(UsageChannel.MATRIX, UsageKinds.channelOf("MTX/IDENTITY"))
        assertEquals(UsageChannel.QUICK_ACTIONS, UsageKinds.channelOf("QUICK_ACTION"))
        assertEquals(UsageChannel.EMERGENCY, UsageKinds.channelOf("EMERGENCY"))
        assertEquals(UsageChannel.TERMINAL, UsageKinds.channelOf("TERM/PROMPT"))
        assertEquals(UsageChannel.MANUAL_OVERRIDE, UsageKinds.channelOf("TERM/INPUT"))
        assertEquals(UsageChannel.MANUAL_OVERRIDE, UsageKinds.channelOf("BANK/GREETING"))
        assertEquals(UsageChannel.COMPOSER, UsageKinds.channelOf("COMPOSER/SPEAK"))
        assertEquals(UsageChannel.COMPOSER, UsageKinds.channelOf("COMPOSER/BANK"))
        assertEquals(UsageChannel.REPLAY, UsageKinds.channelOf("LOG/REPLAY"))
        assertEquals(UsageChannel.REPLAY, UsageKinds.channelOf("CACHE/REPLAY"))
        assertEquals(UsageChannel.WATCH, UsageKinds.channelOf("HW/WATCH"))
        assertEquals(UsageChannel.SHORTCUT, UsageKinds.channelOf("M-KEY"))
        assertEquals(UsageChannel.PEOPLE, UsageKinds.channelOf("COMPUTER/CONTACT"))
    }

    @Test
    fun aDecksOwnNameIsNeverKept_everyMatrixTagIsJustMatrix() {
        for (title in listOf("", "IDENTITY", "WORK MODE", "MY SECRET DECK NAME", "a/b/c", "x > y", "مرحبا", "50% OFF", "\n")) {
            assertEquals(title, UsageChannel.MATRIX, UsageKinds.channelOf("MTX/$title"))
            // A saved phrase's own tag from Manual Override is the person's word too, and is never kept either.
            assertEquals(title, UsageChannel.MANUAL_OVERRIDE, UsageKinds.channelOf("BANK/$title"))
        }
    }

    @Test
    fun aTagNotOnTheListIsOther_soANewEntryPointIsCountedNotLost_andHelpNarrationIsNotAChannel() {
        for (tag in listOf("", "EXT", "HELP/intro", "HELP/", "mtx/x", "MTX", "quick_action", "EMERGENCY2", "TERM/", "COMPOSER", "GIF_DECK", " EMERGENCY", "HW/WATCH ")) {
            assertEquals("'$tag'", UsageChannel.OTHER, UsageKinds.channelOf(tag))
        }
    }

    // ---- kinds ------------------------------------------------------------------------------------------------------------------------

    @Test
    fun everyStarterPhraseCountsAsItsOwnKind() {
        for (p in StarterSets.matrixPhrases) assertEquals(p.phrase, UsageKinds.kindOf(p.function), UsageKinds.kindOf(p.phrase))
        for (g in StarterSets.quickActionsGroups) for (s in g.slots) assertEquals(s.phrase, UsageKinds.kindOf(s.function), UsageKinds.kindOf(s.phrase))
        assertEquals(UsageKind.YES, UsageKinds.kindOf("Yes."))
        assertEquals(UsageKind.NO, UsageKinds.kindOf("No."))
        assertEquals(UsageKind.HELP, UsageKinds.kindOf("I need help."))
        assertEquals(UsageKind.REPAIR, UsageKinds.kindOf("Please say that again."))
        assertEquals(UsageKind.TURN_HOLDING, UsageKinds.kindOf("Please wait, I am typing."))
        assertEquals(UsageKind.UNSURE, UsageKinds.kindOf("I don't know."))
    }

    @Test
    fun theMatchIgnoresCapitalsAndSpaceAtEitherEnd_andNothingElse() {
        assertEquals(UsageKind.YES, UsageKinds.kindOf("yes."))
        assertEquals(UsageKind.YES, UsageKinds.kindOf("YES."))
        assertEquals(UsageKind.YES, UsageKinds.kindOf("  Yes.  "))
        assertEquals(UsageKind.YES, UsageKinds.kindOf("\tYes.\n"))
        assertEquals("a missing full stop is different words", UsageKind.OTHER, UsageKinds.kindOf("Yes"))
        assertEquals("an extra word is different words", UsageKind.OTHER, UsageKinds.kindOf("Yes, please."))
        assertEquals("space inside is not ignored", UsageKind.OTHER, UsageKinds.kindOf("Please  say that again."))
        assertEquals(UsageKind.OTHER, UsageKinds.kindOf(""))
        assertEquals(UsageKind.OTHER, UsageKinds.kindOf("   "))
        assertEquals(UsageKind.OTHER, UsageKinds.kindOf("My own words, which are nobody's business."))
    }

    @Test
    fun aPhoneSetToTurkishMatchesTheSameWay() {
        val saved = Locale.getDefault()
        try {
            Locale.setDefault(Locale("tr", "TR"))
            assertEquals(UsageKind.HELP, UsageKinds.kindOf("I NEED HELP."))
            assertEquals(UsageKind.HELP, UsageKinds.kindOf("i need help."))
            assertEquals(UsageKind.NO, UsageKinds.kindOf("NO."))
        } finally {
            Locale.setDefault(saved)
        }
    }

    @Test
    fun twoStartersWithTheSameWordsAreNeverGivenDifferentKinds() {
        val byWords = UsageKinds.starterPhrases.groupBy({ UsageKinds.normalised(it.first) }, { it.second })
        for ((words, kinds) in byWords) assertEquals("'$words' has more than one kind: $kinds", 1, kinds.toSet().size)
    }

    @Test
    fun everyStarterKindIsReachable_andEveryStarterFunctionHasAKind() {
        assertEquals(
            StarterFunction.values().map { it.name }.toSet(),
            UsageKind.values().filter { it != UsageKind.OTHER }.map { it.name }.toSet(),
        )
        val reached = UsageKinds.starterPhrases.map { it.second }.toSet()
        assertEquals(UsageKind.values().filter { it != UsageKind.OTHER }.toSet(), reached)
    }

    @Test
    fun theKindMatchKeepsNoStateAndNoWords_itIsAFixedTable() {
        // Every field of the object is a constant: nothing a message says is ever stored in it.
        for (field in UsageKinds::class.java.declaredFields.filter { !it.isSynthetic }) {
            assertTrue("${field.name} must be final", java.lang.reflect.Modifier.isFinal(field.modifiers))
        }
    }
}
