// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import com.example.besu.capture.Vectors.d
import com.example.besu.capture.Vectors.s
import java.util.Random
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CutProposerTest {
    private fun expectedSegments(arr: JsonArray) = arr.map { ProposedSegment(it.jsonObject.d("start_s"), it.jsonObject.d("end_s"), it.jsonObject.s("end_kind")) }

    private fun check(diffs: Differences, name: String, input: JsonObject, expected: JsonArray) {
        val got = CutProposer.proposeSegments(Vectors.levelsFromRuns(input["runs"]!!.jsonArray), input.d("threshold_dbfs"))
        diffs.expect(name, expectedSegments(expected), got)
    }

    @Test
    fun proposalsMatchTheSharedCases() {
        val diffs = Differences()
        for (case in Vectors.load("segments.json").jsonArray) {
            val o = case.jsonObject
            check(diffs, o.s("name"), o["input"]!!.jsonObject, o["expected"]!!.jsonArray)
        }
        diffs.assertNone()
    }

    @Test
    fun proposalsMatchTheGeneratedCases() {
        val diffs = Differences()
        val cases = Vectors.load("fuzz.json").jsonObject["segments"]!!.jsonArray
        assertTrue(cases.size >= 50)
        cases.forEachIndexed { i, c -> check(diffs, "generated segment case $i", c.jsonObject["input"]!!.jsonObject, c.jsonObject["expected"]!!.jsonArray) }
        diffs.assertNone()
    }

    @Test
    fun proposalsAreAlwaysInOrderInsideTheRecordingAndShortEnough() {
        val rnd = Random(11)
        val kinds = setOf("pause", "forced", "end")
        repeat(400) {
            val levels = ArrayList<Double>()
            repeat(3 + rnd.nextInt(30)) {
                val db = if (rnd.nextInt(3) == 0) -70.0 else if (rnd.nextInt(8) == 0) -46.0 else -20.0
                repeat(1 + (Math.pow(rnd.nextDouble(), 2.0) * 900).toInt()) { levels.add(db) }
            }
            val duration = levels.size * CaptureConstants.HOP_S
            var prevEnd = 0.0
            for (p in CutProposer.proposeSegments(levels.toDoubleArray(), -45.0)) {
                assertTrue(p.startS >= 0.0 && p.startS < p.endS)
                assertTrue("past the end: ${p.endS} > $duration", p.endS <= duration + 1e-9)
                assertTrue("longer than a clip may be: ${p.endS - p.startS}", p.endS - p.startS <= CaptureConstants.MAX_CLIP_S + 0.001)
                assertTrue("overlap", p.startS >= prevEnd - 1e-6)
                assertTrue(p.endKind in kinds)
                prevEnd = p.endS
            }
        }
    }

    @Test
    fun silenceHasNothingToPropose() {
        assertEquals(emptyList<ProposedSegment>(), CutProposer.proposeSegments(DoubleArray(5000) { -80.0 }, -45.0))
        assertEquals(emptyList<ProposedSegment>(), CutProposer.proposeSegments(DoubleArray(0), -45.0))
    }
}
