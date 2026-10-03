// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

class TrainingStoreTest {
    private lateinit var dir: File
    private lateinit var store: TrainingStore
    private val now = 1_790_000_000_000L
    private val thr = -45.0

    @Before
    fun setUp() {
        dir = Files.createTempDirectory("ack-store-test").toFile()
        store = TrainingStore(File(dir, "training_capture"))
    }

    @After
    fun tearDown() { dir.deleteRecursively() }

    private fun scriptSession(id: String = "s20261002-180411-a3f9", scriptId: String = "scr-abc"): StoredSession = store.createSession(
        StoredSession(
            id = id, mode = "script", label = "closet", started = "2026-10-02T18:04:11Z", sampleRate = 48_000, source = "UNPROCESSED",
            sourceRequested = "UNPROCESSED", noiseFloorDbfs = -62.3, thresholdDbfs = thr, deviceModel = "Pixel 8", deviceSdk = 35,
            scriptId = scriptId, scriptTitle = "Sample", cardsTotal = 3,
        ),
    )

    private fun freeSession(id: String = "s20261002-181500-b4a0"): StoredSession = store.createSession(
        StoredSession(id = id, mode = "free", started = "2026-10-02T18:15:00Z", sampleRate = 48_000, source = "UNPROCESSED", sourceRequested = "UNPROCESSED", thresholdDbfs = thr, topic = "my day"),
    )

    private fun tone(lead: Double, speech: Double, tail: Double) = listOf(Triple(lead, 0, 24), Triple(speech, 8000, 24), Triple(tail, 0, 24))

    private fun record(file: File, parts: List<Triple<Double, Int, Int>>, rate: Int = 48_000): ShortArray {
        val samples = Vectors.square(parts, rate)
        WavStreamWriter(file, rate).use { it.write(samples) }
        return samples
    }

    /** Records one card the way the app will: notes first, then audio, then the closing note. */
    private fun recordCard(sessionId: String, card: Int, text: String, parts: List<Triple<Double, Int, Int>> = tone(0.5, 2.0, 0.6), at: String = "2026-10-02T18:05:00Z"): StoredClip {
        val (clip, file) = store.beginClip(sessionId, card, text, at)
        val samples = record(file, parts)
        val m = LevelMath.clipMetrics(samples, 48_000, thr)
        return store.finishClip(sessionId, clip.index, samples.size / 48_000.0, m, endedByLimit = false)
    }

    // -- scripts ----------------------------------------------------------------------------------------------------------
    @Test
    fun aScriptIsSavedFoundAndRemovedWithoutTouchingAnythingElse() {
        val s = store.saveScript(store.newScript("  Morning\nreading  ", "The tide came in.", nowMillis = now), now)
        assertEquals("Morning reading", s.title)
        assertEquals(now, s.createdAt)
        assertEquals(s, store.getScript(s.id))
        assertEquals(listOf(s.id), store.listScripts().items.map { it.id })
        assertTrue(store.deleteScript(s.id))
        assertNull(store.getScript(s.id))
        assertFalse(store.deleteScript(s.id))
    }

    @Test
    fun editingAScriptKeepsItsCreationTimeAndMovesItToTheTop() {
        val a = store.saveScript(store.newScript("A", "one", nowMillis = now), now)
        val b = store.saveScript(store.newScript("B", "two", nowMillis = now + 10), now + 10)
        assertEquals(listOf(b.id, a.id), store.listScripts().items.map { it.id })
        val edited = store.saveScript(a.copy(text = "one more"), now + 99)
        assertEquals(a.createdAt, edited.createdAt)
        assertEquals(now + 99, edited.updatedAt)
        assertEquals(listOf(a.id, b.id), store.listScripts().items.map { it.id })
    }

    @Test
    fun aBlankTitleBecomesUntitledAndATooLongTextIsRefusedWithAReason() {
        assertEquals("UNTITLED", store.saveScript(store.newScript("   ", "x", nowMillis = now), now).title)
        try {
            store.saveScript(store.newScript("Long", "x".repeat(TrainingStore.MAX_SCRIPT_CHARS + 1), nowMillis = now), now)
            fail("should refuse")
        } catch (e: StoreException) {
            assertTrue(e.message, "too long" in e.message!!)
        }
    }

    @Test
    fun anIdThatCouldPointOutsideTheFolderIsRefusedEverywhere() {
        for (bad in listOf("../x", "a/b", "", "x".repeat(41), "..")) {
            try { store.getScript(bad); fail("script id $bad accepted") } catch (e: StoreException) { }
        }
        for (bad in listOf("../../etc", "s2026", "s20261002-180411-A3F9")) {
            try { store.sessionDir(bad); fail("session id $bad accepted") } catch (e: StoreException) { }
            try { store.clipFile(bad, 1); fail("clip path for $bad accepted") } catch (e: StoreException) { }
        }
    }

    @Test
    fun aDamagedScriptFileIsReportedAndLeftAlone() {
        val good = store.saveScript(store.newScript("Good", "text", nowMillis = now), now)
        val bad = File(dir, "training_capture/scripts/scr-broken.json").also { it.writeText("{ not json") }
        val listing = store.listScripts()
        assertEquals(listOf(good.id), listing.items.map { it.id })
        assertEquals(listOf("scr-broken.json"), listing.damaged)
        assertEquals("{ not json", bad.readText())
        try { store.getScript("scr-broken"); fail("should say it can't be read") } catch (e: StoreException) { assertTrue("left as it is" in e.message!!) }
    }

    // -- a script session -------------------------------------------------------------------------------------------------
    @Test
    fun aClipIsInTheNotesBeforeItsAudioExistsAndKeptOnceItIsFinished() {
        val s = scriptSession()
        val (clip, file) = store.beginClip(s.id, card = 1, text = "The tide came in.", recordedUtc = "2026-10-02T18:05:00Z")
        assertEquals(ClipState.OPEN, store.getSession(s.id)!!.clips.single().state)
        assertFalse("no audio yet", file.exists())
        assertEquals(1, clip.index)
        assertEquals(1, clip.attempt)
        val samples = record(file, tone(0.5, 2.0, 0.6))
        val done = store.finishClip(s.id, clip.index, samples.size / 48_000.0, LevelMath.clipMetrics(samples, 48_000, thr), endedByLimit = false)
        assertEquals(ClipState.DONE, done.state)
        assertEquals(3.1, done.durationS, 0.0)
        assertEquals(0.5, done.speechStartS!!, 0.0)
        assertEquals(2.5, done.speechEndS!!, 0.0)
        assertEquals(emptyList<String>(), done.flags)
    }

    @Test
    fun theNotesSurviveClosingAndReopeningTheStore() {
        val s = scriptSession()
        recordCard(s.id, 1, "The tide came in.")
        val again = TrainingStore(File(dir, "training_capture"))
        assertEquals(store.getSession(s.id), again.getSession(s.id))
        assertEquals(listOf(s.id), again.listSessions().items.map { it.id })
    }

    @Test
    fun redoingACardKeepsTheOldAttemptOnDiskAndPackagesOnlyTheNewOne() {
        val s = scriptSession()
        val first = recordCard(s.id, 1, "The tide came in.")
        store.markRedone(s.id, first.index)
        val second = recordCard(s.id, 1, "The tide came in.", tone(0.5, 2.5, 0.6))
        assertEquals(2, second.attempt)
        assertEquals(2, second.index)
        val loaded = store.getSession(s.id)!!
        assertEquals(listOf(ClipState.REDONE, ClipState.DONE), loaded.clips.map { it.state })
        assertTrue("the redone attempt's audio is still there", store.clipFile(s.id, first.index).isFile)
        val exported = store.toCaptureSession(loaded) as ScriptSession
        assertEquals(listOf(2), exported.clips.map { it.index })
        assertEquals(listOf(2), exported.clips.map { it.attempt })
    }

    @Test
    fun theCardsAlreadyRecordedForAScriptAreFoundAcrossSessionsSoANewSessionCanCarryOn() {
        val a = scriptSession("s20261002-180411-a3f9")
        recordCard(a.id, 1, "First card.")
        val redo = recordCard(a.id, 2, "Second card.")
        store.markRedone(a.id, redo.index)                                   // redone and not yet re-recorded: card 2 is not done
        val b = scriptSession("s20261003-090000-b1b1")
        recordCard(b.id, 3, "Third card.")
        scriptSession("s20261003-100000-c2c2", scriptId = "scr-other").let { recordCard(it.id, 1, "Other script card.") }
        assertEquals(setOf("First card.", "Third card."), store.doneCardTexts("scr-abc"))
    }

    @Test
    fun theClipsLengthsAreNotedAsFlagsAndThePersonsMarksAreKeptApart() {
        val s = scriptSession()
        val (c1, f1) = store.beginClip(s.id, 1, "Short.", "2026-10-02T18:05:00Z")
        val samples = record(f1, tone(0.1, 0.4, 0.2))
        store.finishClip(s.id, c1.index, samples.size / 48_000.0, LevelMath.clipMetrics(samples, 48_000, thr), endedByLimit = false)
        assertEquals(listOf("short"), store.getSession(s.id)!!.clips.single().flags)
        store.setPersonFlags(s.id, c1.index, setOf("stumble", "bogus", "noise"))
        assertEquals(listOf("short", "noise", "stumble"), store.getSession(s.id)!!.clips.single().flags)
        store.setPersonFlags(s.id, c1.index, setOf("cough"))
        assertEquals(listOf("short", "cough"), store.getSession(s.id)!!.clips.single().flags)
        assertEquals(listOf("no_end", "long"), ClipFlags.automatic(12.0, true).sorted().reversed())
    }

    @Test
    fun aMarkSetWhileTheClipIsStillBeingRecordedIsKeptWhenItFinishes() {
        val s = scriptSession()
        val (clip, file) = store.beginClip(s.id, 1, "Card.", "2026-10-02T18:05:00Z")
        store.setPersonFlags(s.id, clip.index, setOf("cough"))
        val samples = record(file, tone(0.5, 2.0, 0.6))
        val done = store.finishClip(s.id, clip.index, samples.size / 48_000.0, LevelMath.clipMetrics(samples, 48_000, thr), endedByLimit = false)
        assertEquals(listOf("cough"), done.flags)
    }

    @Test
    fun theNextClipNumberIsAboveTheHighestEvenAfterOneWasRemoved() {
        val s = scriptSession()
        val a = recordCard(s.id, 1, "One.")
        val b = recordCard(s.id, 2, "Two.")
        val c = recordCard(s.id, 3, "Three.")
        store.markRedone(s.id, b.index)
        store.deleteClip(s.id, b.index)
        val d = recordCard(s.id, 4, "Four.")
        assertEquals(listOf(a.index, c.index, d.index), store.getSession(s.id)!!.clips.map { it.index })
        assertEquals(4, d.index)
        assertTrue("three clips still have three different files", listOf(a, c, d).all { store.clipFile(s.id, it.index).isFile })
    }

    @Test
    fun theClipLengthLimitsAreExactlyTheFormatsLimits() {
        assertEquals(emptyList<String>(), ClipFlags.automatic(CaptureConstants.MIN_CLIP_S, false))
        assertEquals(listOf("short"), ClipFlags.automatic(CaptureConstants.MIN_CLIP_S - 0.001, false))
        assertEquals(emptyList<String>(), ClipFlags.automatic(CaptureConstants.MAX_CLIP_S, false))
        assertEquals(listOf("long"), ClipFlags.automatic(CaptureConstants.MAX_CLIP_S + 0.001, false))
        assertEquals(listOf("no_end"), ClipFlags.automatic(5.0, true))
    }

    // -- safety of the notes ----------------------------------------------------------------------------------------------
    @Test
    fun aHalfWrittenNotesFileLeftByACrashDoesNotHideTheGoodOne() {
        val s = scriptSession()
        recordCard(s.id, 1, "The tide came in.")
        File(store.sessionDir(s.id), "session.json.tmp").writeText("{ \"id\": \"half writ")        // a crash before the move
        assertEquals(1, store.getSession(s.id)!!.clips.size)
        recordCard(s.id, 2, "We walked along the shore.")                                          // the next write replaces the leftover
        assertEquals(2, store.getSession(s.id)!!.clips.size)
        assertFalse("the notes are moved into place, so no temporary file is left", File(store.sessionDir(s.id), "session.json.tmp").exists())
    }

    @Test
    fun damagedNotesAreReportedWithoutLosingTheRecordingsBesideThem() {
        val s = scriptSession()
        val clip = recordCard(s.id, 1, "The tide came in.")
        val good = scriptSession("s20261003-090000-b1b1")
        File(store.sessionDir(s.id), "session.json").writeText("garbage")
        val listing = store.listSessions()
        assertEquals(listOf(good.id), listing.items.map { it.id })
        assertEquals(listOf(s.id), listing.damaged)
        assertTrue(store.clipFile(s.id, clip.index).isFile)
        try { store.getSession(s.id); fail("should say it can't be read") } catch (e: StoreException) { assertTrue("recordings are still in the folder" in e.message!!) }
    }

    @Test
    fun asessionCannotBeCreatedTwiceOrUnderAnotherMode() {
        val s = scriptSession()
        try { scriptSession(); fail("duplicate accepted") } catch (e: StoreException) { assertTrue("already exists" in e.message!!) }
        try { store.createSession(s.copy(id = "s20261003-090000-b1b1", mode = "other")); fail("mode accepted") } catch (e: StoreException) { }
    }

    // -- recovery after the app closed unexpectedly ------------------------------------------------------------------------
    private fun halfWrittenClip(sessionId: String, text: String, seconds: Double): StoredClip {
        val (clip, file) = store.beginClip(sessionId, 1, text, "2026-10-02T18:05:00Z")
        val samples = Vectors.square(tone(0.5, seconds, 0.0), 48_000)
        val bytes = ByteArray(samples.size * 2) { i -> if (i % 2 == 0) (samples[i / 2].toInt() and 0xff).toByte() else (samples[i / 2].toInt() shr 8).toByte() }
        file.writeBytes(WavFile.header(48_000, 0) + bytes)                  // what a recording that was never closed looks like
        return clip
    }

    @Test
    fun aClipThatWasBeingRecordedWhenTheAppClosedIsRepairedAndHeldBackUntilThePersonKeepsIt() {
        val s = scriptSession()
        recordCard(s.id, 1, "First card.")
        val open = halfWrittenClip(s.id, "Second card.", 1.5)
        val report = store.recoverOpenSessions("2026-10-02T19:00:00Z")
        assertEquals(RecoveryReport(1, 1, 0, emptyList()), report)
        val loaded = store.getSession(s.id)!!
        assertTrue(loaded.closed)
        assertEquals("2026-10-02T18:05:00Z", loaded.ended)
        val rec = loaded.clips.first { it.index == open.index }
        assertEquals(ClipState.RECOVERED, rec.state)
        assertEquals(2.0, rec.durationS, 0.0)
        assertEquals(0.5, rec.speechStartS!!, 0.0)
        assertEquals("only the first, finished clip is packaged", listOf(1), (store.toCaptureSession(loaded) as ScriptSession).clips.map { it.index })

        store.keepRecovered(s.id, open.index)
        assertEquals(listOf(1, 2), (store.toCaptureSession(store.getSession(s.id)!!) as ScriptSession).clips.map { it.index })
    }

    @Test
    fun recoveryNeverDeletesAudioExceptAFileWithNoAudioInIt() {
        val s = scriptSession()
        val (headerOnly, f1) = store.beginClip(s.id, 1, "Empty.", "2026-10-02T18:05:00Z")
        f1.writeBytes(WavFile.header(48_000, 0))
        val (never, _) = store.beginClip(s.id, 2, "Never started.", "2026-10-02T18:05:10Z")
        val (stray, f3) = store.beginClip(s.id, 3, "Not ours.", "2026-10-02T18:05:20Z")
        f3.writeText("this is somebody's file, not a recording " + "x".repeat(100))
        val report = store.recoverOpenSessions("2026-10-02T19:00:00Z")
        assertEquals(2, report.clipsEmpty)
        assertEquals(1, report.problems.size)
        assertFalse(f1.exists())
        assertTrue("a file that isn't ours is left exactly as it was", f3.readText().startsWith("this is somebody's file"))
        val loaded = store.getSession(s.id)!!
        assertEquals(listOf(stray.index), loaded.clips.map { it.index })
        assertEquals(ClipState.REDONE, loaded.clips.single().state)
        assertNotNull(headerOnly)
        assertNotNull(never)
    }

    @Test
    fun aFreeRecordingThatWasNeverClosedIsRepairedScannedAndHeldBack() {
        val s = freeSession()
        val file = store.beginFreeRecording(s.id)
        val samples = Vectors.square(listOf(Triple(0.3, 0, 24), Triple(3.0, 8000, 24), Triple(0.6, 0, 24), Triple(6.5, 8000, 24), Triple(0.5, 0, 24)), 48_000)
        val bytes = ByteArray(samples.size * 2) { i -> if (i % 2 == 0) (samples[i / 2].toInt() and 0xff).toByte() else (samples[i / 2].toInt() shr 8).toByte() }
        file.writeBytes(WavFile.header(48_000, 0) + bytes)
        assertEquals(RecoveryReport(1, 1, 0, emptyList()), store.recoverOpenSessions("2026-10-02T19:00:00Z"))
        val loaded = store.getSession(s.id)!!
        assertEquals(ClipState.RECOVERED, loaded.recording!!.state)
        assertEquals(10.9, loaded.recording!!.durationS, 0.0)
        assertEquals("both stretches of speech fit in one piece (10.1 s, under the 11 s limit)", 1, loaded.recording!!.pieces.size)
        assertNull("not packaged until kept", store.toCaptureSession(loaded))
        store.keepRecoveredRecording(s.id)
        assertNotNull(store.toCaptureSession(store.getSession(s.id)!!))
    }

    @Test
    fun recoveryLeavesEndedSessionsAloneAndIsHarmlessToRunTwice() {
        val s = scriptSession()
        recordCard(s.id, 1, "First card.")
        store.closeSession(s.id, "2026-10-02T18:30:00Z")
        val before = store.getSession(s.id)
        assertEquals(RecoveryReport(0, 0, 0, emptyList()), store.recoverOpenSessions("2026-10-02T19:00:00Z"))
        assertEquals(before, store.getSession(s.id))
        halfWrittenClip(scriptSession("s20261003-090000-b1b1").id, "x", 1.0)
        assertEquals(1, store.recoverOpenSessions("2026-10-03T10:00:00Z").sessionsClosed)
        assertEquals(0, store.recoverOpenSessions("2026-10-03T10:00:00Z").sessionsClosed)
    }

    // -- removing things --------------------------------------------------------------------------------------------------
    @Test
    fun aKeptClipIsNeverDeletedOnItsOwnButASetAsideOneCanBe() {
        val s = scriptSession()
        val kept = recordCard(s.id, 1, "First card.")
        try { store.deleteClip(s.id, kept.index); fail("a kept clip was deleted") } catch (e: StoreException) { assertTrue("Redo the card" in e.message!!) }
        store.markRedone(s.id, kept.index)
        val file = store.clipFile(s.id, kept.index)
        assertTrue(file.isFile)
        store.deleteClip(s.id, kept.index)
        assertFalse(file.exists())
        assertEquals(emptyList<StoredClip>(), store.getSession(s.id)!!.clips)
    }

    @Test
    fun deletingASessionRemovesItsRecordingsAndNothingElse() {
        val a = scriptSession()
        val b = scriptSession("s20261003-090000-b1b1")
        recordCard(a.id, 1, "First card.")
        recordCard(b.id, 1, "First card.")
        val script = store.saveScript(store.newScript("Keep me", "text", nowMillis = now), now)
        assertTrue(store.sessionBytes(a.id) > 100_000)
        assertTrue(store.deleteSession(a.id))
        assertFalse(store.sessionDir(a.id).exists())
        assertTrue(store.clipFile(b.id, 1).isFile)
        assertNotNull(store.getScript(script.id))
        assertFalse(store.deleteSession(a.id))
    }

    // -- the whole way to a package ---------------------------------------------------------------------------------------
    @Test
    fun aRecordedSessionBecomesAPackageTheVerifierAccepts() {
        val s = scriptSession()
        recordCard(s.id, 1, "The tide came in.")
        recordCard(s.id, 2, "We walked along the shore.", tone(0.5, 3.0, 0.6))
        store.closeSession(s.id, "2026-10-02T18:30:00Z")
        val f = freeSession()
        val file = store.beginFreeRecording(f.id)
        record(file, listOf(Triple(0.3, 0, 24), Triple(3.0, 8000, 24), Triple(0.6, 0, 24), Triple(6.5, 8000, 24), Triple(0.5, 0, 24)))
        store.finishFreeRecording(f.id, AudioScan.scanRecording(file, thr))
        store.closeSession(f.id, "2026-10-02T18:40:00Z")

        val sessions = listOf(store.getSession(s.id)!!, store.getSession(f.id)!!).map { store.toCaptureSession(it)!! }
        val out = ByteArrayOutputStream()
        val report = PackageWriter.write(sessions, out, "2026-10-02T19:30:00Z", "1.0-beta.9")
        assertEquals(2, report.sessions)
        val verified = PackageVerifier.verify(ByteArrayInputStream(out.toByteArray()))
        assertTrue(verified.problems.toString(), verified.ok)
        assertEquals(3, verified.audioFiles)
    }

    @Test
    fun aSessionWithNothingKeptHasNothingToExport() {
        val s = scriptSession()
        assertNull(store.toCaptureSession(store.getSession(s.id)!!))
        assertNull(store.toCaptureSession(freeSession().let { store.getSession(it.id)!! }))
    }

    // -- room on the phone ------------------------------------------------------------------------------------------------
    @Test
    fun recordingNeedsRoomToStartAndStopsBeforeTheLastOfIt() {
        val mb = 1024L * 1024
        assertFalse(DiskGuard.canStart(299 * mb))
        assertTrue(DiskGuard.canStart(300 * mb))
        assertTrue(DiskGuard.mustStop(99 * mb))
        assertFalse(DiskGuard.mustStop(100 * mb))
        assertEquals(0L, DiskGuard.minutesLeft(50 * mb, 48_000))
        assertEquals(60L, DiskGuard.minutesLeft(100 * mb + 60L * 48_000 * 2 * 60, 48_000))
        assertTrue(DiskGuard.describe(500 * mb, 48_000).startsWith("500 MB free"))
    }
}
