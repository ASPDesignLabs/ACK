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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ScriptCaptureEngineTest {
    private lateinit var dir: File
    private lateinit var store: TrainingStore
    private val rate = 48_000
    private val thr = -45.0
    private val sid = "s20261002-180411-a3f9"
    private val events = mutableListOf<String>()
    private val free = AtomicLong(Long.MAX_VALUE)

    @Before
    fun setUp() {
        dir = Files.createTempDirectory("ack-engine-test").toFile()
        store = TrainingStore(File(dir, "training_capture"))
        events.clear()
        free.set(Long.MAX_VALUE)
    }

    @After
    fun tearDown() { dir.deleteRecursively() }

    private val listener = object : CaptureListener {
        override fun onCardStarted(cardIndex: Int, attempt: Int) { events.add("card $cardIndex attempt $attempt") }
        override fun onClipKept(clip: StoredClip, cardsLeft: Int) { events.add("kept ${clip.index} left $cardsLeft") }
        override fun onPaused(reason: PauseReason, message: String) { events.add("paused $reason") }
        override fun onFinished() { events.add("finished") }
    }

    private fun cards(n: Int) = (1..n).map { Card("Card number $it.", 3, 1.2, emptyList()) }

    private fun engine(n: Int, pending: List<Int> = (0 until n).toList(), endWait: Int = CaptureConstants.END_SILENCE_HOPS): ScriptCaptureEngine {
        if (store.getSession(sid) == null) {
            store.createSession(StoredSession(
                id = sid, mode = "script", label = "test", started = "2026-10-02T18:04:11Z", sampleRate = rate, source = "UNPROCESSED",
                sourceRequested = "UNPROCESSED", thresholdDbfs = thr, scriptId = "scr-test", scriptTitle = "Test", cardsTotal = n,
            ))
        }
        return ScriptCaptureEngine(
            store, sid, cards(n), pending, rate, thr, endSilenceHops = endWait, nowUtc = { "2026-10-02T18:05:00Z" },
            freeBytes = { free.get() }, listener = listener,
        )
    }

    private fun quiet(seconds: Double) = Triple(seconds, 0, 24)
    private fun speech(seconds: Double, amp: Int = 8000) = Triple(seconds, amp, 24)

    private fun feedAll(e: ScriptCaptureEngine, samples: ShortArray, chunk: Int) {
        var i = 0
        while (i < samples.size) {
            val n = minOf(chunk, samples.size - i)
            e.feed(samples.copyOfRange(i, i + n), n)
            i += n
        }
    }

    private fun clipSamples(index: Int): ShortArray {
        val f = store.clipFile(sid, index)
        return AudioScan.readSamples(f, WavFile.inspect(f))
    }

    private fun slice(source: ShortArray, fromHop: Int, toHop: Int) = source.copyOfRange(fromHop * 480, toHop * 480)

    // -- the plain case ---------------------------------------------------------------------------------------------------
    @Test
    fun twoCardsReadOneAfterAnotherAreCutKeptAndTheSessionIsClosed() {
        val source = Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(2.0), speech(3.0), quiet(2.0)), rate)
        val e = engine(2)
        e.start()
        feedAll(e, source, 1000)

        assertEquals(listOf("card 0 attempt 1", "kept 1 left 1", "card 1 attempt 1", "kept 2 left 0", "finished"), events)
        val notes = store.getSession(sid)!!
        assertTrue(notes.closed)
        assertEquals(listOf(ClipState.DONE, ClipState.DONE), notes.clips.map { it.state })
        assertEquals(listOf(1, 2), notes.clips.map { it.card })
        assertEquals(listOf("Card number 1.", "Card number 2."), notes.clips.map { it.text })
        // clip 1: speech starts at hop 100, lead-in 50 hops; last voiced hop 299, tail 40 hops after it
        assertArrayEquals(slice(source, 50, 340), clipSamples(1))
        assertEquals(2.9, notes.clips[0].durationS, 0.0)
        assertEquals(0.5, notes.clips[0].speechStartS!!, 0.0)
        assertEquals(2.5, notes.clips[0].speechEndS!!, 0.0)
        // clip 2: listening resumed at hop 340, speech starts at 500, lead-in reaches back to 450
        assertArrayEquals(slice(source, 450, 840), clipSamples(2))
        assertEquals(3.9, notes.clips[1].durationS, 0.0)
        assertTrue(e.isFinished)
    }

    @Test
    fun everyClipIsAValidWavAndTheSessionBecomesAPackage() {
        val source = Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(2.0), speech(3.0), quiet(2.0)), rate)
        val e = engine(2)
        e.start()
        feedAll(e, source, 4800)
        for (c in store.getSession(sid)!!.clips) WavFile.inspect(store.clipFile(sid, c.index))
        val out = ByteArrayOutputStream()
        PackageWriter.write(listOf(store.toCaptureSession(store.getSession(sid)!!)!!), out, "2026-10-02T19:30:00Z", "1.0-beta.9")
        val v = PackageVerifier.verify(ByteArrayInputStream(out.toByteArray()))
        assertTrue(v.problems.toString(), v.ok)
        assertEquals(2, v.audioFiles)
    }

    @Test
    fun theSameAudioGivesTheSameClipsWhateverSizeTheMicrophoneDeliversIt() {
        val source = Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(1.3), speech(2.0), quiet(2.0), speech(1.0), quiet(2.0)), rate)
        var reference: List<Pair<StoredClip, List<Short>>>? = null
        for (chunk in listOf(1, 7, 479, 480, 481, 1000, 4800, 48_000)) {
            setUp()
            val e = engine(3)
            e.start()
            feedAll(e, source, chunk)
            val got = store.getSession(sid)!!.clips.map { it to clipSamples(it.index).toList() }
            if (reference == null) reference = got
            assertEquals("chunk size $chunk", reference, got)
            assertEquals("chunk size $chunk", 3, got.size)
        }
    }

    // -- nothing is lost between cards --------------------------------------------------------------------------------------
    @Test
    fun aCardStartedStraightAfterTheLastOneLosesItsFirstWords() {
        // card 1's speech ends at hop 299; the end wait closes it at hop 419; card 2 starts at hop 430, after the close
        val source = Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(1.3), speech(2.0), quiet(2.0)), rate)
        val e = engine(2)
        e.start()
        feedAll(e, source, 1000)
        // the lead-in of card 2 (hops 380 to 430) reaches back before the moment card 1 was closed: it came from the carried-over audio
        assertArrayEquals(slice(source, 50, 340), clipSamples(1))
        assertArrayEquals(slice(source, 380, 670), clipSamples(2))
    }

    @Test
    fun theSecondClipNeverReachesBackIntoTheFirst() {
        // With a shorter end wait (0.8 s) card 1 closes at hop 379, and card 2's speech may begin at hop 385. Its 0.5 s lead-in would
        // reach back to hop 335, but card 1's clip ran to hop 340, so card 2's clip begins there instead: no sample is in both.
        val source = Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(0.85), speech(2.0), quiet(2.0)), rate)
        val e = engine(2, endWait = 80)
        e.start()
        feedAll(e, source, 1000)
        assertArrayEquals(slice(source, 50, 340), clipSamples(1))
        assertArrayEquals(slice(source, 340, 625), clipSamples(2))
        val clips = store.getSession(sid)!!.clips
        assertEquals(listOf(ClipState.DONE, ClipState.DONE), clips.map { it.state })
        assertEquals(0.45, clips[1].speechStartS!!, 0.0)
    }

    // -- limits and trouble ------------------------------------------------------------------------------------------------
    @Test
    fun speechThatNeverStopsIsClosedAtTheHardLimitAndFlagged() {
        val source = Vectors.square(listOf(quiet(0.5), speech(35.0)), rate)
        val e = engine(2)
        e.start()
        feedAll(e, source, 4800)
        val first = store.getSession(sid)!!.clips.first()
        assertEquals(ClipState.DONE, first.state)
        assertEquals("the hard limit is 30 s from the clip's start, which is the start of listening here", 30.0, first.durationS, 0.0)
        assertTrue(first.flags.toString(), "no_end" in first.flags && "long" in first.flags)
    }

    @Test
    fun nothingHeardForTwentySecondsPausesTheSessionAndRemovesTheEmptyCard() {
        val e = engine(2)
        e.start()
        feedAll(e, Vectors.square(listOf(quiet(25.0)), rate), 4800)
        assertEquals(listOf("card 0 attempt 1", "paused IDLE"), events)
        assertTrue(e.isPaused)
        assertEquals("the empty card's entry and file are gone", emptyList<StoredClip>(), store.getSession(sid)!!.clips)
        assertFalse(store.sessionDir(sid).resolve("clips").listFiles().orEmpty().any { it.name.endsWith(".wav") })
        // audio fed while paused is ignored
        feedAll(e, Vectors.square(listOf(speech(3.0), quiet(2.0)), rate), 4800)
        assertEquals(emptyList<StoredClip>(), store.getSession(sid)!!.clips)
        // resuming listens afresh from now: the clip is cut from the audio fed after the resume, not from the start of the session
        e.resume()
        val after = Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(2.0)), rate)
        feedAll(e, after, 4800)
        val kept = store.getSession(sid)!!.clips.filter { it.state == ClipState.DONE }
        assertEquals(1, kept.size)
        assertArrayEquals(slice(after, 50, 340), clipSamples(kept.single().index))
    }

    @Test
    fun pausingWhileTheCardIsStillSilentDropsItButPausingMidSentenceKeepsTheAudio() {
        val e = engine(2)
        e.start()
        feedAll(e, Vectors.square(listOf(quiet(1.0)), rate), 4800)
        e.pause()
        assertEquals(emptyList<StoredClip>(), store.getSession(sid)!!.clips)

        e.resume()
        feedAll(e, Vectors.square(listOf(quiet(0.5), speech(1.5)), rate), 4800)         // in the middle of a sentence
        e.pause()
        val clips = store.getSession(sid)!!.clips
        assertEquals(listOf(ClipState.REDONE), clips.map { it.state })
        assertTrue("the half-said card's audio is kept on disk", store.clipFile(sid, clips[0].index).length() > 100_000)
        assertNull(store.toCaptureSession(store.getSession(sid)!!))
    }

    private fun assertNull(x: Any?) = org.junit.Assert.assertNull(x)

    @Test
    fun redoingTheLastCardRecordsItAgainAndPackagesOnlyTheNewAttempt() {
        val first = Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(1.3)), rate)        // card 1 read; card 2 is now being listened for
        val e = engine(2)
        e.start()
        feedAll(e, first, 4800)
        assertTrue(e.canRedo)
        assertTrue(e.redoLast())
        assertFalse("only the last card can be redone, once", e.canRedo)
        feedAll(e, Vectors.square(listOf(quiet(0.5), speech(2.5), quiet(2.0)), rate), 4800)      // the second try
        feedAll(e, Vectors.square(listOf(quiet(0.5), speech(1.5), quiet(2.0)), rate), 4800)      // then card 2
        val clips = store.getSession(sid)!!.clips
        assertEquals(listOf(ClipState.REDONE, ClipState.DONE, ClipState.DONE), clips.map { it.state })
        assertEquals(listOf(1, 1, 2), clips.map { it.card })
        assertEquals(listOf(1, 2, 1), clips.map { it.attempt })
        assertTrue(events.toString(), events.contains("card 0 attempt 2"))
        assertTrue("the first attempt is still on disk", store.clipFile(sid, clips[0].index).isFile)
        assertEquals(listOf(2, 3), (store.toCaptureSession(store.getSession(sid)!!) as ScriptSession).clips.map { it.index })
    }

    @Test
    fun theThumpOfATapJustAfterRedoOrResumeIsNotHeardAsSpeech() {
        val e = engine(2)
        e.start()
        // card 1 read and kept; the person taps REDO LAST, which thumps the phone for 0.2 s; then they read it again
        feedAll(e, Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(1.3)), rate), 4800)
        assertTrue(e.redoLast())
        val second = Vectors.square(listOf(speech(0.2, 20000), quiet(1.0), speech(2.0), quiet(2.0)), rate)
        feedAll(e, second, 4800)
        val clips = store.getSession(sid)!!.clips.filter { it.state == ClipState.DONE }
        assertEquals("the first try was set aside; the second is the one kept", listOf(1), clips.map { it.card })
        assertEquals(listOf(2), clips.map { it.attempt })
        // Hops 0 to 29 of what was heard after the tap are ignored. The speech starts at hop 120, so its lead-in begins at hop 70 and the
        // tail ends 40 hops after its last voiced hop (319), at 360. The thump is nowhere in the clip.
        assertArrayEquals(slice(second, 70, 360), clipSamples(clips.last().index))
        assertTrue(clipSamples(clips.last().index).none { Math.abs(it.toInt()) == 20000 })

        // a tap on RESUME is treated the same way: the thump is not mistaken for a card being read
        e.pause()
        e.resume()
        feedAll(e, Vectors.square(listOf(speech(0.2, 20000), quiet(25.0)), rate), 4800)
        assertTrue(events.toString(), events.contains("paused IDLE"))
        assertEquals("the thump did not become a clip", 1, store.getSession(sid)!!.clips.count { it.state == ClipState.DONE })
    }

    @Test
    fun runningOutOfRoomPausesWithoutLosingWhatWasKept() {
        val e = engine(3)
        e.start()
        feedAll(e, Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(2.0)), rate), 4800)      // card 1 kept
        free.set(50L * 1024 * 1024)
        feedAll(e, Vectors.square(listOf(quiet(1.0), speech(1.0), quiet(3.0)), rate), 4800)
        assertTrue(events.toString(), events.contains("paused DISK_FULL"))
        val clips = store.getSession(sid)!!.clips
        assertEquals("the clip that was kept is still kept", ClipState.DONE, clips.first().state)
        assertTrue(store.clipFile(sid, 1).isFile)
        assertTrue("whatever was being said when the room ran out is kept on disk, set aside", clips.drop(1).all { it.state == ClipState.REDONE && store.clipFile(sid, it.index).isFile })
        assertTrue(clips.none { it.state == ClipState.OPEN })
    }

    @Test
    fun endingEarlyClosesTheSessionAndKeepsEverythingKept() {
        val e = engine(3)
        e.start()
        feedAll(e, Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(2.0)), rate), 4800)
        e.finish()
        val notes = store.getSession(sid)!!
        assertTrue(notes.closed)
        assertEquals(listOf(ClipState.DONE), notes.clips.map { it.state })
        assertEquals("finished", events.last())
        e.finish()                                                   // harmless twice
        assertEquals(1, events.count { it == "finished" })
    }

    @Test
    fun aSessionCarriesOnFromTheCardsNotYetRecorded() {
        val e = engine(4, pending = listOf(2, 3))
        e.start()
        feedAll(e, Vectors.square(listOf(quiet(1.0), speech(2.0), quiet(2.0), speech(2.0), quiet(2.0)), rate), 4800)
        assertEquals(listOf(3, 4), store.getSession(sid)!!.clips.map { it.card })
        assertEquals(listOf("card 2 attempt 1", "kept 1 left 1", "card 3 attempt 1", "kept 2 left 0", "finished"), events)
    }

    @Test
    fun aLongerEndWaitKeepsASlowReadersPausesInOneClip() {
        val source = Vectors.square(listOf(quiet(0.5), speech(2.0), quiet(1.6), speech(2.0), quiet(3.0)), rate)
        val normal = engine(2)
        normal.start()
        feedAll(normal, source, 4800)
        assertEquals("a 1.6 s pause ends a clip with the normal wait", 2, store.getSession(sid)!!.clips.size)
        setUp()
        val patient = engine(1, endWait = 200)
        patient.start()
        feedAll(patient, source, 4800)
        assertEquals("with a 2.0 s wait it is one clip", 1, store.getSession(sid)!!.clips.size)
        assertNotNull(store.getSession(sid)!!.clips.single().speechStartS)
    }

    @Test
    fun theLevelMeterGetsOneReadingPerHop() {
        var readings = 0
        var sawSpeech = false
        val l = object : CaptureListener {
            override fun onLevel(db: Double, inSpeech: Boolean) { readings++; if (inSpeech) sawSpeech = true }
        }
        store.createSession(StoredSession(id = sid, mode = "script", started = "2026-10-02T18:04:11Z", sampleRate = rate, source = "UNPROCESSED", sourceRequested = "UNPROCESSED", thresholdDbfs = thr))
        val e = ScriptCaptureEngine(store, sid, cards(1), listOf(0), rate, thr, nowUtc = { "2026-10-02T18:05:00Z" }, listener = l)
        e.start()
        feedAll(e, Vectors.square(listOf(quiet(1.0), speech(1.0)), rate), 777)
        assertEquals(200, readings)
        assertTrue(sawSpeech)
    }
}
