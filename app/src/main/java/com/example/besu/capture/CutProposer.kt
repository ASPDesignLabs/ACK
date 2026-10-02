// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import kotlin.math.max
import kotlin.math.min

/** A suggested piece of a free-speech recording: where it starts and ends, and how the end was chosen. */
data class ProposedSegment(val startS: Double, val endS: Double, val endKind: String)

// Where a free-speech recording could be cut (format document, section 8). The phone never cuts the audio: it only suggests, from the
// recording's speech regions, and Freeform Studio decides with the benefit of word timings. Everything here is whole hops.
// A line-for-line port of ack_capture_reference.propose_segments; CutProposerTest holds it to the shared test cases.
object CutProposer {
    private class Raw(
        val a: Int, val b: Int, val kind: String, val startExact: Boolean, val endExact: Boolean, val prevB: Int?, val nextA: Int?,
    )

    fun proposeSegments(levels: DoubleArray, thr: Double): List<ProposedSegment> {
        val durationHops = levels.size
        val regions = LevelMath.regionsHops(levels, thr)
        val raw = mutableListOf<Raw>()
        var i = 0
        var startExact = false
        while (i < regions.size) {
            val segA = regions[i][0]
            val startI = i
            val prevB = if (i > 0 && !startExact) regions[i - 1][1] else null
            var j = i
            while (true) {
                val a = regions[j][0]
                val b = regions[j][1]
                if (b - segA > CaptureConstants.FORCE_AT_HOPS) {
                    // this region would carry the piece past the limit: prefer the latest real pause before it
                    var k = -1
                    for (kk in j - 1 downTo startI) {
                        if (regions[kk][1] - segA >= CaptureConstants.MIN_SEG_HOPS) { k = kk; break }
                    }
                    if (k >= 0) {
                        raw.add(Raw(segA, regions[k][1], "pause", startExact, false, prevB, regions[k + 1][0]))
                        i = k + 1
                        startExact = false
                        break
                    }
                    val w0 = max(a, segA + CaptureConstants.FORCE_AT_HOPS - CaptureConstants.FORCE_WINDOW_HOPS)
                    val w1 = segA + CaptureConstants.FORCE_AT_HOPS
                    if (w0 > w1) {                            // the window falls in the quiet before this region
                        raw.add(Raw(segA, regions[j - 1][1], "pause", startExact, false, prevB, regions[j][0]))
                        i = j
                        startExact = false
                        break
                    }
                    val lo = w0
                    val hi = w1 - 1                            // hops fully inside [w0, w1)
                    var cut = w1
                    if (hi >= lo) {
                        cut = lo
                        for (h in lo..hi) if (levels[h] < levels[cut]) cut = h      // the START of the quietest hop; earliest on a tie
                    }
                    raw.add(Raw(segA, cut, "forced", startExact, true, prevB, null))
                    regions[j][0] = cut
                    i = j
                    startExact = true
                    break
                }
                if (j + 1 < regions.size && b - segA >= CaptureConstants.CUT_AFTER_HOPS) {
                    raw.add(Raw(segA, b, "pause", startExact, false, prevB, regions[j + 1][0]))
                    i = j + 1
                    startExact = false
                    break
                }
                if (j + 1 >= regions.size) {
                    raw.add(Raw(segA, b, "end", startExact, false, prevB, null))
                    i = regions.size
                    break
                }
                j += 1
            }
        }
        return raw.map { s ->
            var start = if (s.startExact) s.a.toDouble() else (s.a - CaptureConstants.PAD_LEAD_HOPS).toDouble()
            if (!s.startExact && s.prevB != null) start = max(start, (s.prevB + s.a) / 2.0)
            var end = if (s.endExact) s.b.toDouble() else (s.b + CaptureConstants.PAD_TAIL_HOPS).toDouble()
            if (!s.endExact && s.nextA != null) end = min(end, (s.b + s.nextA) / 2.0)
            start = max(0.0, start)
            end = min(durationHops.toDouble(), end)
            ProposedSegment(LevelMath.sec(start), LevelMath.sec(end), s.kind)
        }
    }
}
