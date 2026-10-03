// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import com.example.besu.capture.Vectors.d
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class LevelMathTest {
    @Test
    fun metricsMatchTheSharedCases() {
        val diffs = Differences()
        for (case in Vectors.load("metrics.json").jsonArray) {
            val name = case.jsonObject["name"]!!.jsonPrimitive.content
            val input = case.jsonObject["input"]!!.jsonObject
            val expected = case.jsonObject["expected"]!!.jsonObject
            val rate = input["rate"]!!.jsonPrimitive.int
            val floor = input["noise_floor_dbfs"]!!.let { if (it is JsonNull) null else it.jsonPrimitive.double }
            val thr = LevelMath.thresholdDb(floor)
            val m = LevelMath.clipMetrics(Vectors.square(input["parts"]!!.jsonArray, rate), rate, thr)
            diffs.expect("$name: threshold", expected.d("threshold_dbfs"), LevelMath.rnd(thr, 1))
            diffs.expect("$name: peak", expected.d("peak_dbfs"), m.peakDbfs)
            diffs.expect("$name: rms", expected.d("rms_dbfs"), m.rmsDbfs)
            diffs.expect("$name: clipped", expected["clipped_samples"]!!.jsonPrimitive.int, m.clippedSamples)
            val sp = expected["speech"]!!
            if (sp is JsonNull) assertNull("$name: speech", m.speech)
            else diffs.expect("$name: speech", SpeechSpan(sp.jsonObject.d("start_s"), sp.jsonObject.d("end_s")), m.speech)
        }
        diffs.assertNone()
    }

    @Test
    fun roundingGoesAwayFromZeroAndNeverGivesNegativeZero() {
        assertEquals(1.0, LevelMath.rnd(0.5, 0), 0.0)
        assertEquals(-1.0, LevelMath.rnd(-0.5, 0), 0.0)
        assertEquals(2.0, LevelMath.rnd(1.5, 0), 0.0)
        assertEquals(3.0, LevelMath.rnd(2.5, 0), 0.0)          // not "to even"
        assertEquals(-2.5, LevelMath.rnd(-2.46, 1), 0.0)
        assertEquals(Double.POSITIVE_INFINITY, 1.0 / LevelMath.rnd(-0.04, 1), 0.0)   // 1 / +0.0 is +Infinity; -0.0 would give -Infinity
    }

    @Test
    fun theThresholdFollowsTheRoomWithinLimits() {
        assertEquals(-45.0, LevelMath.thresholdDb(null), 0.0)
        assertEquals(-52.0, LevelMath.thresholdDb(-62.0), 0.0)
        assertEquals(-55.0, LevelMath.thresholdDb(-90.0), 0.0)   // a very quiet room doesn't make it ever more sensitive
        assertEquals(-30.0, LevelMath.thresholdDb(-10.0), 0.0)   // a noisy room doesn't make it deaf
    }

    @Test
    fun hopsAreTenMillisecondsAtAnyRateAndTheLastOneMayBePartial() {
        val a = LevelMath.hopLevels(ShortArray(48_000 + 100) { 1000 }, 48_000)
        assertEquals(101, a.size)                                 // 100 whole hops of 480 samples, plus 100 more samples
        val b = LevelMath.hopLevels(ShortArray(44_100) { 1000 }, 44_100)
        assertEquals(100, b.size)                                 // 441-sample hops
        assertEquals(a[0], a[100], 1e-9)                          // the partial hop is measured over what it has
    }

    @Test
    fun regionsJoinCloseRunsAndDropBlips() {
        fun levels(vararg runs: Pair<Int, Double>) = runs.flatMap { (n, db) -> List(n) { db } }.toDoubleArray()
        val joined = LevelMath.regionsHops(levels(20 to -20.0, 29 to -70.0, 20 to -20.0), -45.0)
        assertEquals(listOf(listOf(0, 69)), joined.map { it.toList() })       // a 29-hop gap is closed up
        val apart = LevelMath.regionsHops(levels(20 to -20.0, 30 to -70.0, 20 to -20.0), -45.0)
        assertEquals(2, apart.size)                                           // 30 hops is a real pause
        assertEquals(0, LevelMath.regionsHops(levels(9 to -20.0, 50 to -70.0), -45.0).size)   // 9 hops is a blip
        assertEquals(1, LevelMath.regionsHops(levels(10 to -20.0, 50 to -70.0), -45.0).size)
    }
}
