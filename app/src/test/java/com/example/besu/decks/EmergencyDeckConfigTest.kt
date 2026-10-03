// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.decks

import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

// Runs with `./gradlew :app:testDebugUnitTest` in Android Studio. It is not in tools/kotlin_check's harness because
// EmergencyDeck.kt (where the config lives) imports Compose; the same checks were run against the exact source text of the
// config declarations in a scratch project, and that is stated in the commit message.
class EmergencyDeckConfigTest {
    @Test
    fun aConfigSavedBeforeTheFieldExistedDecodesWithConfirmOff() {
        assertFalse(Json.decodeFromString<EmergencyDeckConfig>("""{"deckId":"X"}""").confirmBeforeSend)

        val oldFullConfig = """{"deckId":"X","preventTimedClear":true,"requireHoldToClear":false,"forceSpeaker":true,""" +
            """"boostVolume":true,"tone":"TONE_2"}"""
        val decoded = Json.decodeFromString<EmergencyDeckConfig>(oldFullConfig)
        assertFalse(decoded.confirmBeforeSend)
        assertTrue(decoded.forceSpeaker)                       // and nothing else about it changed
        assertEquals(EmergencyTone.TONE_2, decoded.tone)
    }

    @Test
    fun theDefaultIsOff() {
        assertFalse(EmergencyDeckConfig(deckId = "X").confirmBeforeSend)
    }

    @Test
    fun turningItOnSurvivesASaveAndALoad() {
        val saved = Json.encodeToString(EmergencyDeckConfig(deckId = "X", confirmBeforeSend = true))
        assertTrue(Json.decodeFromString<EmergencyDeckConfig>(saved).confirmBeforeSend)
    }

    @Test
    fun turningItOffAgainSurvivesASaveAndALoad() {
        val saved = Json.encodeToString(EmergencyDeckConfig(deckId = "X", confirmBeforeSend = true).copy(confirmBeforeSend = false))
        assertFalse(Json.decodeFromString<EmergencyDeckConfig>(saved).confirmBeforeSend)
    }
}
