// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.File
import java.io.RandomAccessFile
import java.nio.file.Files
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

class WavFileTest {
    private lateinit var dir: File

    @Before
    fun setUp() { dir = Files.createTempDirectory("ack-wav-test").toFile() }

    @After
    fun tearDown() { dir.deleteRecursively() }

    private fun wavWith(name: String, header: ByteArray, data: ByteArray): File = File(dir, name).also { it.writeBytes(header + data) }

    private fun rejected(file: File, fragment: String) {
        try {
            WavFile.inspect(file)
            fail("expected ${file.name} to be rejected (\"$fragment\")")
        } catch (e: WavException) {
            assertTrue("expected \"$fragment\" in: ${e.message}", fragment in e.message!!)
        }
    }

    @Test
    fun aRecordingWrittenThenClosedIsAValidWavWithTheRightLength() {
        val samples = ShortArray(48_000) { ((it % 100) - 50).toShort() }
        val f = File(dir, "a.wav")
        WavStreamWriter(f, 48_000).use { it.write(samples, 0, 30_000); it.write(samples, 30_000, 18_000) }
        val info = WavFile.inspect(f)
        assertEquals(48_000, info.sampleRate)
        assertEquals(48_000L, info.frames)
        assertEquals(1.0, info.seconds, 0.0)
        assertEquals(44L + 96_000L, f.length())
        // the samples are stored little-endian, exactly as given
        val bytes = f.readBytes()
        assertEquals((samples[1234].toInt() and 0xff).toByte(), bytes[44 + 2 * 1234])
        assertEquals(((samples[1234].toInt() shr 8) and 0xff).toByte(), bytes[44 + 2 * 1234 + 1])
    }

    @Test
    fun theStandardHeaderIsByteForByteWhatTheFormatAsksFor() {
        val h = WavFile.header(48_000, 96_000)
        assertEquals(44, h.size)
        assertArrayEquals("RIFF".toByteArray(), h.copyOfRange(0, 4))
        assertEquals(36 + 96_000, java.nio.ByteBuffer.wrap(h, 4, 4).order(java.nio.ByteOrder.LITTLE_ENDIAN).int)
        assertArrayEquals("WAVEfmt ".toByteArray(), h.copyOfRange(8, 16))
        assertEquals(16, java.nio.ByteBuffer.wrap(h, 16, 4).order(java.nio.ByteOrder.LITTLE_ENDIAN).int)
        val bb = java.nio.ByteBuffer.wrap(h, 20, 16).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        assertEquals(1, bb.short.toInt())           // PCM
        assertEquals(1, bb.short.toInt())           // mono
        assertEquals(48_000, bb.int)
        assertEquals(96_000, bb.int)                // bytes per second
        assertEquals(2, bb.short.toInt())
        assertEquals(16, bb.short.toInt())
        assertArrayEquals("data".toByteArray(), h.copyOfRange(36, 40))
    }

    @Test
    fun aCheckpointKeepsAFileThatCouldBeLeftBehindUsable() {
        val f = File(dir, "b.wav")
        val w = WavStreamWriter(f, 44_100)
        w.write(ShortArray(10_000) { 7 })
        w.checkpoint()
        w.write(ShortArray(500) { 7 })               // written after the checkpoint, then the app dies
        val frozen = File(dir, "frozen.wav")
        f.copyTo(frozen)
        w.close()
        // the copy is what a crash would leave: the header only knows about the first 10,000 frames, the file holds 10,500
        rejected(frozen, "interrupted")
        val repaired = WavFile.repair(frozen)
        assertEquals(10_500L, repaired.frames)
        assertEquals(10_500L, WavFile.inspect(frozen).frames)
    }

    @Test
    fun aRecordingThatNeverGotItsLengthFilledInIsRepairedToWhatItHolds() {
        val data = ByteArray(2 * 4800) { (it % 7).toByte() }
        val f = wavWith("c.wav", WavFile.header(48_000, 0), data)
        rejected(f, "interrupted")
        val info = WavFile.repair(f)
        assertEquals(4800L, info.frames)
        assertArrayEquals("the audio itself is untouched", data, f.readBytes().copyOfRange(44, f.length().toInt()))
    }

    @Test
    fun repairDropsAHalfWrittenLastSampleAndNothingElse() {
        val data = ByteArray(2 * 1000 + 1) { 3 }
        val f = wavWith("d.wav", WavFile.header(48_000, 0), data)
        assertEquals(1000L, WavFile.repair(f).frames)
        assertEquals(44L + 2000L, f.length())
    }

    @Test
    fun repairLeavesAFileItDidNotWriteExactlyAsItWas() {
        val notWav = File(dir, "notes.wav").also { it.writeText("this is not audio, it is somebody's notes " + "x".repeat(100)) }
        val before = notWav.readBytes()
        try { WavFile.repair(notWav); fail("should refuse") } catch (e: WavException) { assertTrue("not a recording this app wrote" in e.message!!) }
        assertArrayEquals(before, notWav.readBytes())
        val short = File(dir, "short.wav").also { it.writeBytes(ByteArray(10)) }
        try { WavFile.repair(short); fail("should refuse") } catch (e: WavException) { assertTrue("too short" in e.message!!) }
        assertEquals(10L, short.length())
    }

    @Test
    fun inspectRefusesAnythingThatIsNotPlain16BitMonoWithinTheRateRange() {
        val data = ByteArray(2000)
        fun patched(name: String, at: Int, value: Int, bytes: Int): File {
            val h = WavFile.header(48_000, 2000)
            for (i in 0 until bytes) h[at + i] = ((value shr (8 * i)) and 0xff).toByte()
            return wavWith(name, h, data)
        }
        rejected(patched("stereo.wav", 22, 2, 2), "2 channel")
        rejected(patched("eight.wav", 34, 8, 2), "8-bit")
        rejected(patched("float.wav", 20, 3, 2), "format 3")
        rejected(patched("slow.wav", 24, 8_000, 4), "outside")
        rejected(patched("fast.wav", 24, 192_000, 4), "outside")
        rejected(File(dir, "x.wav").also { it.writeBytes(ByteArray(100)) }, "not a WAV file")
        rejected(File(dir, "tiny.wav").also { it.writeBytes(ByteArray(10)) }, "not a WAV file")
        rejected(File(dir, "gone.wav"), "is missing")
        rejected(wavWith("odd.wav", WavFile.header(48_000, 2001), ByteArray(2001)), "whole number of samples")
    }

    @Test
    fun aHeaderThatPromisesMoreThanTheFileHoldsIsRefused() {
        rejected(wavWith("lie.wav", WavFile.header(48_000, 5000), ByteArray(2000)), "header says the audio is 5000 bytes")
    }

    @Test
    fun closingTwiceIsHarmlessAndWritingAfterCloseIsRefused() {
        val w = WavStreamWriter(File(dir, "e.wav"), 48_000)
        w.write(ShortArray(100))
        w.close()
        w.close()
        try { w.write(ShortArray(1)); fail("should refuse") } catch (e: IllegalStateException) { }
        assertEquals(100L, WavFile.inspect(File(dir, "e.wav")).frames)
    }

    @Test
    fun aRateOutsideTheFormatIsNotAccepted() {
        try { WavStreamWriter(File(dir, "f.wav"), 8_000); fail("should refuse") } catch (e: IllegalArgumentException) { }
    }

    @Test
    fun framesWrittenCountsWhatWasWrittenSoFar() {
        val w = WavStreamWriter(File(dir, "g.wav"), 48_000)
        assertEquals(0L, w.framesWritten)
        w.write(ShortArray(300), 100, 50)
        assertEquals(50L, w.framesWritten)
        w.close()
        RandomAccessFile(File(dir, "g.wav"), "r").use { assertEquals(44L + 100L, it.length()) }
    }
}
