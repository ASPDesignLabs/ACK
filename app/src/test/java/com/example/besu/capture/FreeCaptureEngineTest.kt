// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.util.concurrent.atomic.AtomicLong
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class FreeCaptureEngineTest {
    private lateinit var dir: File
    private lateinit var store: TrainingStore
    private val rate = 48_000
    private val thr = -45.0
    private val sid = "s20261002-181500-b4a0"
    private val stopped = mutableListOf<String>()
    private val free = AtomicLong(Long.MAX_VALUE)
    private var levels = 0
    private var speechHops = 0

    @Before
    fun setUp() {
        dir = Files.createTempDirectory("ack-free-test").toFile()
        store = TrainingStore(File(dir, "training_capture"))
        store.createSession(StoredSession(id = sid, mode = "free", started = "2026-10-02T18:15:00Z", sampleRate = rate, source = "UNPROCESSED", sourceRequested = "UNPROCESSED", thresholdDbfs = thr, topic = "my day"))
        stopped.clear(); free.set(Long.MAX_VALUE); levels = 0; speechHops = 0
    }

    @After
    fun tearDown() { dir.deleteRecursively() }

    private val listener = object : FreeCaptureListener {
        override fun onLevel(db: Double, isSpeech: Boolean) { levels++; if (isSpeech) speechHops++ }
        override fun onStoppedByItself(reason: PauseReason, message: String) { stopped.add(reason.toString()) }
    }

    private fun engine(maxSeconds: Int = CaptureConstants.MAX_FREE_SESSION_S) =
        FreeCaptureEngine(store, sid, rate, thr, { "2026-10-02T18:30:00Z" }, { free.get() }, maxSeconds, listener)

    private val talk = listOf(Triple(0.3, 0, 24), Triple(3.0, 8000, 24), Triple(0.6, 0, 24), Triple(6.5, 8000, 24), Triple(0.5, 0, 24), Triple(2.0, 6000, 24), Triple(0.5, 0, 24))

    private fun feedAll(e: FreeCaptureEngine, samples: ShortArray, chunk: Int) {
        var i = 0
        while (i < samples.size) { val n = minOf(chunk, samples.size - i); e.feed(samples.copyOfRange(i, i + n), n); i += n }
    }

    @Test
    fun theWholeTalkIsKeptUntouchedWithSuggestedPiecesAndTheSessionIsClosed() {
        val source = Vectors.square(talk, rate)
        val e = engine()
        e.start()
        feedAll(e, source, 1234)
        val rec = e.stop()!!
        assertEquals(ClipState.DONE, rec.state)
        assertEquals(LevelMath.rnd(source.size.toDouble() / rate, 3), rec.durationS, 0.0)
        val file = store.recordingFile(sid)
        assertArrayEquals("the audio is exactly what was heard", source, AudioScan.readSamples(file, WavFile.inspect(file)))
        val expected = CutProposer.proposeSegments(LevelMath.hopLevels(source, rate), thr)
        assertEquals(expected.map { Triple(it.startS, it.endS, it.endKind) }, rec.pieces.map { Triple(it.startS, it.endS, it.endKind) })
        val notes = store.getSession(sid)!!
        assertTrue(notes.closed)
        assertEquals("2026-10-02T18:30:00Z", notes.ended)
        assertEquals(rec, notes.recording)
        assertEquals(source.size / 480, levels)
        assertTrue(speechHops in 1100..1200)
    }

    @Test
    fun theSameTalkGivesTheSameRecordingWhateverTheChunkSize() {
        val source = Vectors.square(talk, rate)
        var reference: StoredRecording? = null
        for (chunk in listOf(1, 479, 480, 481, 4800, 48_000)) {
            tearDown(); setUp()
            val e = engine()
            e.start()
            feedAll(e, source, chunk)
            val rec = e.stop()
            if (reference == null) reference = rec
            assertEquals("chunk $chunk", reference, rec)
        }
    }

    @Test
    fun theRecordingBecomesAPackageTheVerifierAccepts() {
        val e = engine()
        e.start()
        feedAll(e, Vectors.square(talk, rate), 4800)
        e.stop()
        val session = store.toCaptureSession(store.getSession(sid)!!)!!
        val out = ByteArrayOutputStream()
        PackageWriter.write(listOf(session), out, "2026-10-02T19:30:00Z", "1.0-beta.9")
        val v = PackageVerifier.verify(ByteArrayInputStream(out.toByteArray()))
        assertTrue(v.problems.toString(), v.ok)
    }

    @Test
    fun pausedAudioIsNotRecordedAndResumingCarriesOn() {
        val e = engine()
        e.start()
        feedAll(e, Vectors.square(listOf(Triple(1.0, 8000, 24)), rate), 4800)
        e.pause()
        feedAll(e, Vectors.square(listOf(Triple(5.0, 8000, 24)), rate), 4800)
        assertEquals(1.0, e.seconds, 0.0)
        e.resume()
        feedAll(e, Vectors.square(listOf(Triple(2.0, 8000, 24)), rate), 4800)
        assertEquals(3.0, e.stop()!!.durationS, 0.0)
    }

    @Test
    fun theLongestAllowedRecordingStopsItselfAndKeepsEverything() {
        val e = engine(maxSeconds = 5)
        e.start()
        feedAll(e, Vectors.square(listOf(Triple(8.0, 8000, 24)), rate), 4800)
        assertEquals(listOf("REQUESTED"), stopped)
        assertTrue(e.isStopped)
        val notes = store.getSession(sid)!!
        assertTrue(notes.closed)
        assertEquals(5.0, notes.recording!!.durationS, 0.0)
        assertEquals(ClipState.DONE, notes.recording!!.state)
        assertEquals("a recording that stopped by itself still hands over what it found", notes.recording, e.result)
        assertEquals("stopping again returns the same result and changes nothing", notes.recording, e.stop())
    }

    @Test
    fun runningOutOfRoomStopsAndKeepsWhatWasRecorded() {
        val e = engine()
        e.start()
        feedAll(e, Vectors.square(listOf(Triple(3.0, 8000, 24)), rate), 4800)
        free.set(10L * 1024 * 1024)
        feedAll(e, Vectors.square(listOf(Triple(10.0, 8000, 24)), rate), 4800)
        assertEquals(listOf("DISK_FULL"), stopped)
        val rec = store.getSession(sid)!!.recording!!
        assertEquals(ClipState.DONE, rec.state)
        assertTrue("it kept the three seconds and some of what came after, not nothing", rec.durationS in 3.0..8.0)
    }

    @Test
    fun stoppingBeforeAnythingWasHeardLeavesAClosedSessionWithNoRecording() {
        val e = engine()
        e.start()
        assertNull(e.stop())
        val notes = store.getSession(sid)!!
        assertTrue(notes.closed)
        assertNull(notes.recording?.takeIf { it.state == ClipState.DONE })
        assertNull(store.toCaptureSession(notes))
        assertFalse(store.recordingFile(sid).exists())
    }

    @Test
    fun aRecordingThatWasNeverStoppedIsRepairedByRecoveryAndHeldBack() {
        val e = engine()
        e.start()
        feedAll(e, Vectors.square(talk, rate), 4800)          // the app dies here: no stop(), the header still says zero length
        val report = TrainingStore(File(dir, "training_capture")).recoverOpenSessions("2026-10-02T19:00:00Z")
        assertEquals(1, report.clipsRecovered)
        val rec = store.getSession(sid)!!.recording!!
        assertEquals(ClipState.RECOVERED, rec.state)
        assertEquals(13.4, rec.durationS, 0.0)
        assertNotNull(rec.pieces.firstOrNull())
    }

    @Test
    fun aRecordingThatCannotBeScannedWhenItStopsIsKeptAndRepairedLater() {
        val e = engine()
        e.start()
        feedAll(e, Vectors.square(talk, rate), 4800)
        store.recordingFile(sid).appendBytes(byteArrayOf(7))              // a stray byte: the header no longer matches the file
        assertNull(e.stop())
        assertTrue("the audio is never deleted because it could not be scanned", store.recordingFile(sid).isFile)
        val notes = store.getSession(sid)!!
        assertTrue(notes.closed)
        assertEquals(ClipState.OPEN, notes.recording!!.state)
        assertNull("not offered for packaging", store.toCaptureSession(notes))
        // an ended session with unfinished audio is still found and repaired
        val report = store.recoverOpenSessions("2026-10-02T19:00:00Z")
        assertEquals(1, report.clipsRecovered)
        assertEquals(ClipState.RECOVERED, store.getSession(sid)!!.recording!!.state)
        assertEquals(13.4, store.getSession(sid)!!.recording!!.durationS, 0.0)
    }

    @Test
    fun startingTwiceIsRefused() {
        val e = engine()
        e.start()
        try { e.start(); org.junit.Assert.fail("started twice") } catch (ex: IllegalStateException) { }
    }
}
