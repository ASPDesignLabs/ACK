// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.File
import java.io.RandomAccessFile
import kotlin.math.abs
import kotlin.math.min

// Reads a recording from disk in pieces and works out what the format needs to know about it (levels, loudness notes, suggested
// cuts), without ever holding a whole long recording in memory: a 90-minute free-speech session is about 500 MB of audio.
// The streamed results are the same numbers the in-memory functions in LevelMath give; AudioScanTest checks that.
object AudioScan {
    private const val CHUNK_HOPS = 100              // one second of audio per read

    /** Samples [fromFrame, toFrame) of a finished 16-bit mono WAV file. */
    fun readSamples(file: File, info: WavInfo, fromFrame: Long = 0, toFrame: Long = info.frames): ShortArray {
        val from = fromFrame.coerceIn(0, info.frames)
        val to = toFrame.coerceIn(from, info.frames)
        val n = (to - from).toInt()
        val bytes = ByteArray(n * 2)
        RandomAccessFile(file, "r").use { raf ->
            raf.seek(info.dataOffset + from * 2)
            raf.readFully(bytes)
        }
        return ShortArray(n) { i -> ((bytes[2 * i].toInt() and 0xff) or (bytes[2 * i + 1].toInt() shl 8)).toShort() }
    }

    private inline fun forEachChunk(file: File, info: WavInfo, chunkFrames: Int, action: (ShortArray) -> Unit) {
        RandomAccessFile(file, "r").use { raf ->
            raf.seek(info.dataOffset.toLong())
            var left = info.frames
            val buf = ByteArray(chunkFrames * 2)
            while (left > 0) {
                val n = min(left, chunkFrames.toLong()).toInt()
                raf.readFully(buf, 0, n * 2)
                action(ShortArray(n) { i -> ((buf[2 * i].toInt() and 0xff) or (buf[2 * i + 1].toInt() shl 8)).toShort() })
                left -= n
            }
        }
    }

    /** One level per 10 ms hop, exactly as [LevelMath.hopLevels] would give for the whole file read into memory. */
    fun hopLevels(file: File, info: WavInfo): DoubleArray {
        val hop = info.sampleRate / 100
        val out = ArrayList<Double>((info.frames / hop + 1).toInt())
        forEachChunk(file, info, hop * CHUNK_HOPS) { chunk -> LevelMath.hopLevels(chunk, info.sampleRate).forEach { out.add(it) } }
        return out.toDoubleArray()
    }

    /** Loudness notes for the whole file (no speech span). */
    fun wholeMetrics(file: File, info: WavInfo): ClipMetrics {
        var peak = 0
        var clipped = 0
        var sum = 0.0
        forEachChunk(file, info, info.sampleRate) { chunk ->
            for (s in chunk) {
                val a = abs(s.toInt())
                if (a > peak) peak = a
                if (a >= 32767) clipped++
                sum += s.toDouble() * s.toDouble()
            }
        }
        return LevelMath.metricsFromTotals(peak, sum, info.frames, clipped, null)
    }

    /** Metrics and length of a short clip, with its speech span at [thresholdDb]. */
    fun scanClip(file: File, thresholdDb: Double): Pair<ClipMetrics, Double> {
        val info = WavFile.inspect(file)
        val samples = readSamples(file, info)
        return LevelMath.clipMetrics(samples, info.sampleRate, thresholdDb) to LevelMath.rnd(info.seconds, 3)
    }

    /** The samples [from, to) that a time range in seconds covers, to the nearest sample (0.35 s at 48 kHz is sample 16800, not 16799). */
    fun sampleRange(startS: Double, endS: Double, sampleRate: Int): Pair<Long, Long> =
        Math.round(startS * sampleRate) to Math.round(endS * sampleRate)

    /** Works out a finished free-speech recording: its length, loudness, and the pieces the phone suggests cutting it into. */
    fun scanRecording(file: File, thresholdDb: Double): StoredRecording {
        val info = WavFile.inspect(file)
        val proposals = CutProposer.proposeSegments(hopLevels(file, info), thresholdDb)
        val whole = wholeMetrics(file, info)
        val pieces = proposals.map { p ->
            val (from, to) = sampleRange(p.startS, p.endS, info.sampleRate)
            val m = LevelMath.clipMetrics(readSamples(file, info, from, to), info.sampleRate, thresholdDb)
            StoredPiece(p.startS, p.endS, p.endKind, m.peakDbfs, m.rmsDbfs, m.clippedSamples)
        }
        return StoredRecording(
            state = ClipState.DONE, durationS = LevelMath.rnd(info.seconds, 3),
            peakDbfs = whole.peakDbfs, rmsDbfs = whole.rmsDbfs, clippedSamples = whole.clippedSamples, pieces = pieces,
        )
    }
}
