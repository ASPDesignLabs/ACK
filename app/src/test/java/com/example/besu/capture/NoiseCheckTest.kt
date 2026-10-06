// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import com.example.besu.core.CaptureText
import com.example.besu.core.EnglishText
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NoiseCheckTest {
    private val rate = 48_000

    private fun heard(parts: List<Triple<Double, Int, Int>>): NoiseCheck {
        val c = NoiseCheck(rate)
        val samples = Vectors.square(parts, rate)
        var i = 0
        while (i < samples.size) { val n = minOf(777, samples.size - i); c.feed(samples.copyOfRange(i, i + n), n); i += n }
        return c
    }

    @Test
    fun aQuietRoomIsGoodAndItsLevelIsTheAverageOverEverythingHeard() {
        val c = heard(listOf(Triple(2.0, 30, 24)))                    // a square wave of 30 has an rms of 30
        assertTrue(c.isDone)
        assertEquals(2.0, c.seconds, 0.0)
        assertEquals(LevelMath.rnd(LevelMath.levelDb(30.0), 1), c.floorDbfs()!!, 0.0)
        assertEquals(NoiseVerdict.GOOD, c.verdict())
        assertEquals("ROOM LEVEL -60.8 dB: GOOD.", CaptureText.noiseVerdict(EnglishText, c.verdict(), c.floorDbfs()))
    }

    @Test
    fun theCheckIsNotDoneUntilTwoSecondsHaveBeenHeard() {
        assertFalse(heard(listOf(Triple(1.99, 30, 24))).isDone)
        assertTrue(heard(listOf(Triple(2.0, 30, 24))).isDone)
        assertNull(NoiseCheck(rate).floorDbfs())
        assertEquals(NoiseVerdict.NO_SIGNAL, NoiseCheck(rate).verdict())
    }

    @Test
    fun aLoudRoomIsReportedBecauseItRaisesTheSpeechThreshold() {
        val c = heard(listOf(Triple(2.0, 2000, 24)))                   // about -24 dBFS
        assertEquals(NoiseVerdict.LOUD_ROOM, c.verdict())
        assertEquals(-30.0, LevelMath.thresholdDb(c.floorDbfs()), 0.0)
        val floor = c.floorDbfs()!!
        assertEquals(
            "ROOM LEVEL $floor dB: LOUD. QUIET WORDS MAY BE MISSED. A QUIETER SPOT WILL GIVE BETTER TRAINING DATA.",
            CaptureText.noiseVerdict(EnglishText, c.verdict(), floor),
        )
    }

    @Test
    fun digitalSilenceMeansTheMicrophoneIsCoveredOrMuted() {
        val c = heard(listOf(Triple(2.0, 0, 24)))
        assertEquals(-120.0, c.floorDbfs()!!, 0.0)
        assertEquals(NoiseVerdict.NO_SIGNAL, c.verdict())
        assertEquals("NOTHING WAS HEARD. IS THE MICROPHONE COVERED OR MUTED?", CaptureText.noiseVerdict(EnglishText, c.verdict(), c.floorDbfs()))
    }

    @Test
    fun aSoundDuringTheCheckIsNoticedEvenThoughItDragsTheAverageUpWithIt() {
        val c = heard(listOf(Triple(1.0, 30, 24), Triple(0.05, 3000, 24), Triple(0.95, 30, 24)))
        assertEquals(NoiseVerdict.INTERRUPTED, c.verdict())
        assertEquals("A SOUND INTERRUPTED THE QUIET CHECK. STAY QUIET AND TRY AGAIN.", CaptureText.noiseVerdict(EnglishText, c.verdict(), c.floorDbfs()))
    }

    @Test
    fun theLoudRoomLimitIsExactlyMinusFortyAndTheRoomsLevelIsRoundedFirst() {
        assertEquals(-40.0, heard(listOf(Triple(2.0, 328, 24))).floorDbfs()!!, 0.0)
        assertEquals("exactly at the limit is not louder than it", NoiseVerdict.GOOD, heard(listOf(Triple(2.0, 328, 24))).verdict())
        assertEquals(-39.9, heard(listOf(Triple(2.0, 330, 24))).floorDbfs()!!, 0.0)
        assertEquals(NoiseVerdict.LOUD_ROOM, heard(listOf(Triple(2.0, 330, 24))).verdict())
        assertEquals("a room at -35 dB is loud", NoiseVerdict.LOUD_ROOM, heard(listOf(Triple(2.0, 583, 24))).verdict())
    }

    @Test
    fun theNoSignalLimitIsExactlyMinusNinety() {
        fun floorOf(everyNth: Int): NoiseCheck {
            val c = NoiseCheck(rate)
            c.feed(ShortArray(2 * rate) { i -> if (everyNth > 0 && i % everyNth == 0) 2 else 1 })        // only ever +1 and +2: the tiniest signals
            return c
        }
        assertEquals(-90.3, floorOf(0).floorDbfs()!!, 0.0)
        assertEquals(NoiseVerdict.NO_SIGNAL, floorOf(0).verdict())
        assertEquals(-90.0, floorOf(40).floorDbfs()!!, 0.0)
        assertEquals("exactly at the limit is still a signal", NoiseVerdict.GOOD, floorOf(40).verdict())
    }

    @Test
    fun theSameRoomGivesTheSameLevelAtAnySampleRate() {
        for (r in listOf(48_000, 44_100, 16_000)) {
            val c = NoiseCheck(r)
            val s = Vectors.square(listOf(Triple(2.0, 30, 24)), r)
            c.feed(s)
            assertEquals("rate $r", -60.8, c.floorDbfs()!!, 0.0)
        }
    }
}
