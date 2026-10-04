// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SendFlagsTest {

    @Test
    fun nothingIsOnByDefault() {
        val none = SendFlags()
        assertFalse(none.anyOn)
        assertTrue(none.onFlags().isEmpty())
        SendFlag.values().forEach { assertFalse(none.isOn(it)) }
    }

    @Test
    fun eachFlagTurnsOnAndOffAloneAndTheOthersAreUntouched() {
        for (flag in SendFlag.values()) {
            val on = SendFlags().with(flag, true)
            assertTrue(on.anyOn)
            assertEquals(listOf(flag), on.onFlags())
            for (other in SendFlag.values().filter { it != flag }) assertFalse("$flag changed $other", on.isOn(other))
            assertEquals(SendFlags(), on.with(flag, false))
        }
    }

    @Test
    fun theFourFlagsMapToTheFourFields() {
        assertEquals(SendFlags(quiet = true), SendFlags().with(SendFlag.QUIET, true))
        assertEquals(SendFlags(skipLog = true), SendFlags().with(SendFlag.SKIP_LOG, true))
        assertEquals(SendFlags(sticky = true), SendFlags().with(SendFlag.STICKY, true))
        assertEquals(SendFlags(emergency = true), SendFlags().with(SendFlag.EMERGENCY, true))
    }

    @Test
    fun theSummaryOrderIsFixed_soItAlwaysReadsTheSameWay() {
        val all = SendFlags(quiet = true, skipLog = true, sticky = true, emergency = true)
        assertEquals(listOf(SendFlag.QUIET, SendFlag.SKIP_LOG, SendFlag.STICKY, SendFlag.EMERGENCY), all.onFlags())
        assertEquals(listOf(SendFlag.SKIP_LOG, SendFlag.EMERGENCY), SendFlags(emergency = true, skipLog = true).onFlags())
    }

    @Test
    fun orMeansEitherSideAsks_andNeitherSideIsEverTurnedOff() {
        val typed = SendFlags(quiet = true)
        val switches = SendFlags(emergency = true)
        assertEquals(SendFlags(quiet = true, emergency = true), typed.or(switches))
        assertEquals(typed.or(switches), switches.or(typed))
        // A flag asked for on both sides stays on, once.
        assertEquals(SendFlags(quiet = true), typed.or(typed))
        // Nothing asked for on either side stays off.
        assertEquals(SendFlags(), SendFlags().or(SendFlags()))
    }

    @Test
    fun theSwitchesCountOnlyWhilePlainWordsIsOn() {
        val typed = SendFlags(sticky = true)
        val switches = SendFlags(quiet = true, emergency = true)
        assertEquals(SendFlags(quiet = true, sticky = true, emergency = true), SendSwitchPolicy.effective(typed, switches, plainWordsOn = true))
        // With PLAIN WORDS off a switch cannot be seen, so it must not act. The typed flag still does.
        assertEquals(typed, SendSwitchPolicy.effective(typed, switches, plainWordsOn = false))
        assertEquals(SendFlags(), SendSwitchPolicy.effective(SendFlags(), switches, plainWordsOn = false))
    }

    @Test
    fun aTypedFlagWorksWithPlainWordsOnOrOff_andWithNoSwitchesOn() {
        for (plain in listOf(true, false)) {
            SendFlag.values().forEach { flag ->
                val typed = SendFlags().with(flag, true)
                assertEquals(typed, SendSwitchPolicy.effective(typed, SendFlags(), plain))
            }
        }
    }
}
