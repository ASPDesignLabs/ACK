// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/** Where speech starts and ends inside a clip, in seconds from its start. */
data class SpeechSpan(val startS: Double, val endS: Double)

/** The loudness notes written for every clip (format document, section 5.1). */
data class ClipMetrics(val peakDbfs: Double, val rmsDbfs: Double, val clippedSamples: Int, val speech: SpeechSpan?)

// Levels, regions and clip measurements, exactly as the format document defines them. Everything that decides a boundary is
// worked out in whole 10 ms hops (integers), so the phone and the PC cannot disagree about rounding.
object LevelMath {
    /** Rounds half away from zero, never to the nearest even number. Negative zero comes out as 0.0. */
    fun rnd(x: Double, digits: Int): Double {
        var f = 1.0
        repeat(digits) { f *= 10.0 }
        val r = floor(abs(x) * f + 0.5) / f
        return if (x < 0 && r != 0.0) -r else r
    }

    /** Hops to seconds, to three decimals. */
    fun sec(hops: Double): Double = rnd(hops * CaptureConstants.HOP_S, 3)

    /** Level in dB relative to full scale: 20 * log10(max(rms, 1e-9) / 32768). */
    fun levelDb(rms: Double): Double = 20.0 * log10(max(rms, 1e-9) / 32768.0)

    private fun floorAtMinus120(db: Double): Double = max(db, -120.0)

    /** One level per 10 ms hop (`rate / 100` samples, rounded down); the last, partial hop is measured over what it has. */
    fun hopLevels(samples: ShortArray, rate: Int): DoubleArray {
        val hop = rate / 100
        val n = (samples.size + hop - 1) / hop
        val out = DoubleArray(n)
        for (h in 0 until n) {
            val from = h * hop
            val to = min(samples.size, from + hop)
            var sum = 0.0
            for (i in from until to) {
                val v = samples[i].toDouble()
                sum += v * v
            }
            out[h] = levelDb(sqrt(sum / (to - from)))
        }
        return out
    }

    /** The speech threshold: a fixed default, or the room's level plus an offset, kept within limits (section 5.2). */
    fun thresholdDb(noiseFloorDbfs: Double?): Double {
        if (noiseFloorDbfs == null) return CaptureConstants.THRESH_DEFAULT_DB
        return min(max(noiseFloorDbfs + CaptureConstants.THRESH_OFFSET_DB, CaptureConstants.THRESH_MIN_DB), CaptureConstants.THRESH_MAX_DB)
    }

    /**
     * Freeform's voiced_regions, in whole hops: runs louder than the threshold, runs closer together than REGION_MIN_SILENCE_HOPS
     * joined, joined runs shorter than REGION_MIN_LEN_HOPS dropped. Each region is [start, end) in hops.
     */
    fun regionsHops(levels: DoubleArray, thr: Double): MutableList<IntArray> {
        val runs = mutableListOf<IntArray>()
        var start = -1
        for (i in levels.indices) {
            val on = levels[i] > thr
            if (on && start < 0) {
                start = i
            } else if (!on && start >= 0) {
                runs.add(intArrayOf(start, i))
                start = -1
            }
        }
        if (start >= 0) runs.add(intArrayOf(start, levels.size))
        val merged = mutableListOf<IntArray>()
        for (r in runs) {
            if (merged.isNotEmpty() && r[0] - merged.last()[1] < CaptureConstants.REGION_MIN_SILENCE_HOPS) {
                merged.last()[1] = r[1]
            } else {
                merged.add(intArrayOf(r[0], r[1]))
            }
        }
        return merged.filter { it[1] - it[0] >= CaptureConstants.REGION_MIN_LEN_HOPS }.toMutableList()
    }

    /**
     * The loudness notes worked out from running totals: the largest absolute sample, the sum of the squares of every sample, how
     * many samples there were, and how many reached full scale. One calculation for clips held in memory and for long recordings
     * read in pieces, so the two can never round differently.
     */
    fun metricsFromTotals(peak: Int, sumSquares: Double, count: Long, clipped: Int, speech: SpeechSpan?): ClipMetrics {
        val rms = if (count <= 0L) 0.0 else sqrt(sumSquares / count)
        return ClipMetrics(
            peakDbfs = rnd(floorAtMinus120(levelDb(peak.toDouble())), 1),
            rmsDbfs = rnd(floorAtMinus120(levelDb(rms)), 1),
            clippedSamples = clipped,
            speech = speech,
        )
    }

    /** Peak, average level, clipped samples and the speech span for one clip's samples. */
    fun clipMetrics(samples: ShortArray, rate: Int, thr: Double): ClipMetrics {
        var peak = 0
        var clipped = 0
        var sum = 0.0
        for (s in samples) {
            val a = abs(s.toInt())
            if (a > peak) peak = a
            if (a >= 32767) clipped++
            sum += s.toDouble() * s.toDouble()
        }
        val regions = regionsHops(hopLevels(samples, rate), thr)
        val span = if (regions.isEmpty()) null else SpeechSpan(sec(regions.first()[0].toDouble()), sec(regions.last()[1].toDouble()))
        return metricsFromTotals(peak, sum, samples.size.toLong(), clipped, span)
    }
}
