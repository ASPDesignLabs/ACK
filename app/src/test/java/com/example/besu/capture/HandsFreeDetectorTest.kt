// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import com.example.besu.capture.Vectors.d
import com.example.besu.capture.Vectors.s
import java.util.Random
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HandsFreeDetectorTest {
    private fun expectedEvents(arr: JsonArray): List<DetectorEvent> = arr.map { e ->
        val o = e.jsonObject
        when (val kind = o.s("event")) {
            "clip" -> DetectorEvent.Clip(o.d("start_s"), o.d("end_s"), o.d("speech_start_s"), o.d("speech_end_s"), o.s("reason"))
            "idle_timeout" -> DetectorEvent.IdleTimeout(o.d("at_s"))
            else -> error("unknown event $kind")
        }
    }

    private fun run(levels: DoubleArray, thr: Double, wait: Int): List<DetectorEvent> {
        val det = HandsFreeDetector(thr, wait)
        return levels.toList().mapNotNull { det.feed(it) }
    }

    private fun check(diffs: Differences, name: String, input: JsonObject, expected: JsonArray) {
        val got = run(Vectors.levelsFromRuns(input["runs"]!!.jsonArray), input.d("threshold_dbfs"), input["end_silence_hops"]!!.jsonPrimitive.int)
        diffs.expect(name, expectedEvents(expected), got)
    }

    @Test
    fun clipsMatchTheSharedCases() {
        val diffs = Differences()
        for (case in Vectors.load("handsfree.json").jsonArray) {
            val o = case.jsonObject
            check(diffs, o.s("name"), o["input"]!!.jsonObject, o["expected"]!!.jsonArray)
        }
        diffs.assertNone()
    }

    @Test
    fun clipsMatchTheGeneratedCases() {
        val diffs = Differences()
        val cases = Vectors.load("fuzz.json").jsonObject["handsfree"]!!.jsonArray
        assertTrue(cases.size >= 50)
        cases.forEachIndexed { i, c -> check(diffs, "generated hands-free case $i", c.jsonObject["input"]!!.jsonObject, c.jsonObject["expected"]!!.jsonArray) }
        diffs.assertNone()
    }

    @Test
    fun clipsAlwaysHoldTheirSpeechAndNeverOverlap() {
        val rnd = Random(7)
        repeat(300) {
            val levels = DoubleArray(500 + rnd.nextInt(6000)) { if (rnd.nextInt(100) < 55) -20.0 else -70.0 }
            // random flicker makes lots of short runs; make some stretches steady so real clips form
            var i = 0
            while (i < levels.size) { val len = 20 + rnd.nextInt(400); val v = if (rnd.nextBoolean()) -20.0 else -70.0; for (k in i until minOf(levels.size, i + len)) levels[k] = v; i += len }
            var prevEnd = 0.0
            for (e in run(levels, -45.0, CaptureConstants.END_SILENCE_HOPS)) {
                if (e !is DetectorEvent.Clip) continue
                assertTrue(e.startS <= e.speechStartS)
                assertTrue(e.speechStartS < e.speechEndS)
                assertTrue(e.speechEndS <= e.endS)
                assertTrue("clip longer than the hard limit", e.endS - e.startS <= CaptureConstants.HARD_CLIP_HOPS * CaptureConstants.HOP_S + 1e-9)
                assertTrue("clips overlap: ${e.startS} < $prevEnd", e.startS >= prevEnd - 1e-9)
                prevEnd = e.endS
            }
        }
    }

    @Test
    fun aCardStartedStraightAwayLosesNothing() {
        // 1.0 s of speech, the 1.2 s end-of-card wait, then the next card's speech begins at once (hop 220)
        val levels = (List(100) { -20.0 } + List(120) { -70.0 } + List(150) { -20.0 } + List(200) { -70.0 }).toDoubleArray()
        val clips = run(levels, -45.0, 120).filterIsInstance<DetectorEvent.Clip>()
        assertEquals(2, clips.size)
        assertEquals(0.0, clips[0].startS, 1e-9)
        assertEquals(1.4, clips[0].endS, 1e-9)               // speech ended at 1.0 s, plus the 0.4 s tail
        assertEquals(2.2, clips[1].speechStartS, 1e-9)       // the next card's first word is heard...
        assertEquals(1.7, clips[1].startS, 1e-9)             // ...with its 0.5 s lead-in, which begins after the first clip ended
        assertTrue(clips[1].startS >= clips[0].endS)
    }

    @Test
    fun resumingAfterAPauseStartsListeningFromWhereTheAppSays() {
        val det = HandsFreeDetector(-45.0)
        repeat(30) { assertNull(det.feed(-70.0)) }
        det.resumeAt(det.hopsSeen)
        repeat(100) { det.feed(-20.0) }
        val clip = (0 until 200).mapNotNull { det.feed(-70.0) }.filterIsInstance<DetectorEvent.Clip>().single()
        assertEquals(0.3, clip.speechStartS, 1e-9)
    }

    @Test
    fun onceItGivesUpItStaysQuietUntilToldToResume() {
        val det = HandsFreeDetector(-45.0)
        val events = (0 until CaptureConstants.NO_SPEECH_TIMEOUT_HOPS + 500).mapNotNull { det.feed(-70.0) }
        assertEquals(listOf<DetectorEvent>(DetectorEvent.IdleTimeout(20.0)), events)
        assertNull(det.feed(-20.0))
    }
}
