// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.File
import java.nio.file.Files
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AudioScanTest {
    private lateinit var dir: File

    @Before
    fun setUp() { dir = Files.createTempDirectory("ack-scan-test").toFile() }

    @After
    fun tearDown() { dir.deleteRecursively() }

    private fun write(name: String, rate: Int, parts: List<Triple<Double, Int, Int>>): Pair<File, ShortArray> {
        val samples = Vectors.square(parts, rate)
        val f = File(dir, name)
        WavStreamWriter(f, rate).use { it.write(samples) }
        return f to samples
    }

    // A signal with speech-like stretches, silence, one stretch that clips, and a length that ends part-way through a hop.
    private val signal = listOf(Triple(0.4, 0, 24), Triple(2.1, 8000, 24), Triple(0.9, 0, 24), Triple(3.3, 32767, 24), Triple(0.7, 0, 24), Triple(4.0, 5000, 31), Triple(0.5, 0, 24))

    @Test
    fun hopLevelsReadInPiecesAreTheSameAsHopLevelsOfTheWholeThing() {
        for (rate in listOf(48_000, 44_100, 16_000)) {
            val (f, samples) = write("a$rate.wav", rate, signal)
            val partial = ShortArray(samples.size + rate / 200) { if (it < samples.size) samples[it] else 3000 }     // ends half-way through a hop
            val pf = File(dir, "p$rate.wav").also { out -> WavStreamWriter(out, rate).use { it.write(partial) } }
            assertArrayEquals("whole hops, $rate Hz", LevelMath.hopLevels(samples, rate), AudioScan.hopLevels(f, WavFile.inspect(f)), 0.0)
            assertArrayEquals("partial last hop, $rate Hz", LevelMath.hopLevels(partial, rate), AudioScan.hopLevels(pf, WavFile.inspect(pf)), 0.0)
        }
    }

    @Test
    fun wholeFileMetricsAreTheSameNumbersTheInMemoryFunctionGives() {
        val (f, samples) = write("m.wav", 48_000, signal)
        val streamed = AudioScan.wholeMetrics(f, WavFile.inspect(f))
        val inMemory = LevelMath.clipMetrics(samples, 48_000, -45.0)
        assertEquals(inMemory.peakDbfs, streamed.peakDbfs, 0.0)
        assertEquals(inMemory.rmsDbfs, streamed.rmsDbfs, 0.0)
        assertEquals(inMemory.clippedSamples, streamed.clippedSamples)
        assertTrue("the clipping stretch is counted", streamed.clippedSamples > 100_000)
    }

    @Test
    fun aRangeOfSamplesIsReadExactly() {
        val (f, samples) = write("r.wav", 48_000, signal)
        val info = WavFile.inspect(f)
        assertArrayEquals(samples.copyOfRange(1000, 5000), AudioScan.readSamples(f, info, 1000, 5000))
        assertEquals(samples.size, AudioScan.readSamples(f, info).size)
        assertEquals(0, AudioScan.readSamples(f, info, 7000, 7000).size)
        assertEquals("a range past the end is cut to the end", 10, AudioScan.readSamples(f, info, info.frames - 10, info.frames + 500).size)
    }

    @Test
    fun aRecordingIsScannedIntoTheSamePiecesTheProposerGivesWithMeasuredLoudness() {
        val rate = 48_000
        val parts = listOf(Triple(0.3, 0, 24), Triple(3.0, 8000, 24), Triple(0.6, 0, 24), Triple(6.5, 8000, 24), Triple(0.5, 0, 24), Triple(2.0, 6000, 24), Triple(0.5, 0, 24))
        val (f, samples) = write("free.wav", rate, parts)
        val scanned = AudioScan.scanRecording(f, -45.0)
        val expected = CutProposer.proposeSegments(LevelMath.hopLevels(samples, rate), -45.0)
        assertEquals(ClipState.DONE, scanned.state)
        assertEquals(LevelMath.rnd(samples.size.toDouble() / rate, 3), scanned.durationS, 0.0)
        assertEquals(expected.map { Triple(it.startS, it.endS, it.endKind) }, scanned.pieces.map { Triple(it.startS, it.endS, it.endKind) })
        for ((p, e) in scanned.pieces.zip(expected)) {
            val from = Math.round(e.startS * rate).toInt()
            val to = Math.round(e.endS * rate).toInt()
            val m = LevelMath.clipMetrics(samples.copyOfRange(from, to), rate, -45.0)
            assertEquals(m.peakDbfs, p.peakDbfs, 0.0)
            assertEquals(m.rmsDbfs, p.rmsDbfs, 0.0)
        }
        assertTrue("the last piece is quieter than the others", scanned.pieces.last().peakDbfs < scanned.pieces.first().peakDbfs)
    }

    @Test
    fun aPiecesLoudnessIncludesItsLastMoments() {
        // 12 s of steady speech with a loud burst in the final 10 ms before the forced cut at 9.5 s
        val (f, _) = write("burst.wav", 48_000, listOf(Triple(0.5, 0, 24), Triple(8.99, 4000, 24), Triple(0.01, 20000, 24), Triple(3.01, 4000, 24), Triple(0.5, 0, 24)))
        val first = AudioScan.scanRecording(f, -45.0).pieces.first()
        assertEquals("forced", first.endKind)
        assertEquals(9.5, first.endS, 0.0)
        assertEquals(LevelMath.rnd(LevelMath.levelDb(20000.0), 1), first.peakDbfs, 0.0)
    }

    @Test
    fun aPiecesLoudnessIncludesItsFirstMoments() {
        // steady speech cut by force at 9.5 s, with a loud burst 10 ms after the cut: it belongs to the second piece
        val (f, _) = write("burst2.wav", 48_000, listOf(Triple(0.5, 0, 24), Triple(9.01, 4000, 24), Triple(0.01, 20000, 24), Triple(2.98, 4000, 24), Triple(0.5, 0, 24)))
        val pieces = AudioScan.scanRecording(f, -45.0).pieces
        assertEquals(9.5, pieces[0].endS, 0.0)
        assertEquals(9.5, pieces[1].startS, 0.0)
        assertEquals(LevelMath.rnd(LevelMath.levelDb(4000.0), 1), pieces[0].peakDbfs, 0.0)
        assertEquals(LevelMath.rnd(LevelMath.levelDb(20000.0), 1), pieces[1].peakDbfs, 0.0)
    }

    @Test
    fun aTimeRangeIsMappedToTheNearestSamples() {
        assertEquals(16_800L to 415_200L, AudioScan.sampleRange(0.35, 8.65, 48_000))
        assertEquals(15_435L to 381_465L, AudioScan.sampleRange(0.35, 8.65, 44_100))
        assertEquals(0L to 48_000L, AudioScan.sampleRange(0.0, 1.0, 48_000))
        assertEquals(1L to 2L, AudioScan.sampleRange(0.00003, 0.00004, 48_000))      // 1.44 and 1.92 samples: nearest, not floored
    }

    @Test
    fun aShortClipGivesItsLengthAndSpeechSpan() {
        val (f, _) = write("c.wav", 48_000, listOf(Triple(0.5, 0, 24), Triple(2.0, 8000, 24), Triple(0.6, 0, 24)))
        val (m, dur) = AudioScan.scanClip(f, -45.0)
        assertEquals(3.1, dur, 0.0)
        assertEquals(SpeechSpan(0.5, 2.5), m.speech)
    }
}
