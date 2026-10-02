// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

class PackageWriterTest {
    private lateinit var dir: File
    private val created = "2026-10-02T19:30:00Z"

    @Before
    fun setUp() { dir = Files.createTempDirectory("ack-capture-test").toFile() }

    @After
    fun tearDown() { dir.deleteRecursively() }

    // -- builders ---------------------------------------------------------------------------------------------------------
    private fun tone(lead: Double, speech: Double, tail: Double, amp: Int = 8000) =
        listOf(Triple(lead, 0, 24), Triple(speech, amp, 24), Triple(tail, 0, 24))

    private fun wavFile(name: String, rate: Int, parts: List<Triple<Double, Int, Int>>): Pair<File, ShortArray> {
        val samples = Vectors.square(parts, rate)
        val f = File(dir, name)
        WavStreamWriter(f, rate).use { it.write(samples) }
        return f to samples
    }

    private fun scriptSession(
        id: String = "s20261002-180411-a3f9", rate: Int = 48_000, floor: Double? = -62.3,
        texts: List<String> = listOf("The tide came in.", "We walked along the shore.", "Gulls circled overhead."),
    ): ScriptSession {
        val thr = LevelMath.thresholdDb(floor)
        val clips = texts.mapIndexed { i, text ->
            val (file, samples) = wavFile("$id-${i + 1}.wav", rate, tone(0.5, 2.0 + i * 0.5, 0.6))
            val m = LevelMath.clipMetrics(samples, rate, thr)
            ScriptClip(
                index = i + 1, card = i + 1, attempt = 1, text = text, recorded = String.format(Locale.ROOT, "2026-10-02T18:05:%02dZ", i),
                durationS = LevelMath.rnd(samples.size.toDouble() / rate, 3), speech = m.speech, metrics = CaptureMetrics.of(m), flags = emptyList(), wav = file,
            )
        }
        return ScriptSession(
            id = id, label = "closet, phone on stand, 30 cm", started = "2026-10-02T18:04:11Z", ended = "2026-10-02T18:09:00Z", language = "en-US",
            audio = AudioSettings(rate, "UNPROCESSED", "UNPROCESSED"), noiseFloorDbfs = floor, thresholdDbfs = thr, device = DeviceNote("Pixel 8", 35),
            script = ScriptNote("sample-script", "Sample script", texts.size), clips = clips,
        )
    }

    private fun freeSession(id: String = "s20261002-181500-b4a0", rate: Int = 48_000): FreeSession {
        val thr = LevelMath.thresholdDb(null)
        val parts = listOf(Triple(0.3, 0, 24), Triple(3.0, 8000, 24), Triple(0.6, 0, 24), Triple(6.5, 8000, 24), Triple(0.5, 0, 24), Triple(2.0, 8000, 24), Triple(0.5, 0, 24))
        val (file, samples) = wavFile("$id.wav", rate, parts)
        val proposals = CutProposer.proposeSegments(LevelMath.hopLevels(samples, rate), thr).map { p ->
            val piece = samples.copyOfRange((p.startS * rate).toInt(), minOf(samples.size, (p.endS * rate).toInt()))
            ProposedPiece(p.startS, p.endS, p.endKind, CaptureMetrics.of(LevelMath.clipMetrics(piece, rate, thr)))
        }
        return FreeSession(
            id = id, label = "kitchen", started = "2026-10-02T18:15:00Z", ended = "2026-10-02T18:15:13Z", language = "en-US",
            audio = AudioSettings(rate, "UNPROCESSED", "UNPROCESSED"), noiseFloorDbfs = null, thresholdDbfs = thr, device = null,
            topic = "my day", wav = file, durationS = LevelMath.rnd(samples.size.toDouble() / rate, 3),
            metrics = CaptureMetrics.of(LevelMath.clipMetrics(samples, rate, thr)), proposed = proposals,
        )
    }

    private fun write(vararg sessions: CaptureSession): Pair<ByteArray, PackageReport> {
        val out = ByteArrayOutputStream()
        val report = PackageWriter.write(sessions.toList(), out, created, "1.0-beta.9")
        return out.toByteArray() to report
    }

    private fun entries(zip: ByteArray): Map<String, ByteArray> {
        val out = linkedMapOf<String, ByteArray>()
        ZipInputStream(ByteArrayInputStream(zip)).use { z ->
            while (true) { val e = z.nextEntry ?: break; out[e.name] = z.readBytes() }
        }
        return out
    }

    private fun manifestOf(zip: ByteArray): JsonObject = Json.parseToJsonElement(String(entries(zip).getValue("manifest.json"), Charsets.UTF_8)).jsonObject

    private fun sha(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { String.format(Locale.ROOT, "%02x", it) }

    private fun rezip(zip: ByteArray, change: (String, ByteArray) -> Pair<String, ByteArray>?): ByteArray {
        val out = ByteArrayOutputStream()
        ZipOutputStream(out).use { z ->
            for ((name, data) in entries(zip)) {
                val (n, d) = change(name, data) ?: continue
                z.putNextEntry(ZipEntry(n)); z.write(d); z.closeEntry()
            }
        }
        return out.toByteArray()
    }

    private fun withEntry(zip: ByteArray, name: String, data: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        ZipOutputStream(out).use { z ->
            for ((n, d) in entries(zip)) { z.putNextEntry(ZipEntry(n)); z.write(d); z.closeEntry() }
            z.putNextEntry(ZipEntry(name)); z.write(data); z.closeEntry()
        }
        return out.toByteArray()
    }

    private fun refused(sessions: List<CaptureSession>, fragment: String, createdUtc: String = created) {
        val out = ByteArrayOutputStream()
        try {
            PackageWriter.write(sessions, out, createdUtc, "1.0-beta.9")
            fail("expected the package to be refused (looking for \"$fragment\")")
        } catch (e: PackageWriteException) {
            assertTrue("expected a problem mentioning \"$fragment\", got: ${e.problems}", e.problems.any { fragment in it })
            assertEquals("nothing may be written when a package is refused", 0, out.size())
        }
    }

    // -- a good package -----------------------------------------------------------------------------------------------------
    @Test
    fun aScriptPackageHoldsExactlyTheAllowedEntriesAndVerifies() {
        val s = scriptSession()
        val (bytes, report) = write(s)
        val names = entries(bytes).keys
        assertEquals(setOf("README.txt", "manifest.json") + s.clips.map { PackageNames.clip(s.id, it.index) }, names)
        assertEquals(5, report.entries)
        assertEquals(bytes.size.toLong(), report.bytes)
        val v = PackageVerifier.verify(ByteArrayInputStream(bytes))
        assertTrue(v.problems.toString(), v.ok)
        assertEquals(1, v.sessions)
        assertEquals(3, v.audioFiles)
    }

    @Test
    fun theManifestSaysWhatWasRecordedWithTrueChecksums() {
        val s = scriptSession()
        val (bytes, _) = write(s)
        val m = manifestOf(bytes)
        assertEquals("ack-training-capture/1", m["schema"]!!.jsonPrimitive.content)
        assertEquals(created, m["created"]!!.jsonPrimitive.content)
        assertEquals("1.0-beta.9", m["app"]!!.jsonObject["version"]!!.jsonPrimitive.content)
        val session = m["sessions"]!!.jsonArray.single().jsonObject
        assertEquals("script", session["mode"]!!.jsonPrimitive.content)
        assertEquals("Pixel 8", session["device"]!!.jsonObject["model"]!!.jsonPrimitive.content)
        assertEquals(LevelMath.rnd(s.noiseFloorDbfs!!, 1), session["noise_floor_dbfs"]!!.jsonPrimitive.double, 0.0)
        val clips = session["clips"]!!.jsonArray
        assertEquals(s.clips.map { it.text }, clips.map { it.jsonObject["text"]!!.jsonPrimitive.content })
        assertEquals(s.clips.map { PackageNames.clip(s.id, it.index) }, clips.map { it.jsonObject["file"]!!.jsonPrimitive.content })
        for (c in s.clips) {
            val listed = m["files"]!!.jsonArray.map { it.jsonObject }.single { it["path"]!!.jsonPrimitive.content == PackageNames.clip(s.id, c.index) }
            assertEquals(sha(c.wav.readBytes()), listed["sha256"]!!.jsonPrimitive.content)
            assertEquals(c.wav.length(), listed["bytes"]!!.jsonPrimitive.content.toLong())
        }
        assertEquals(s.clips.first().speech!!.startS, clips[0].jsonObject["speech"]!!.jsonObject["start_s"]!!.jsonPrimitive.double, 0.0)
    }

    @Test
    fun theAudioInThePackageIsTheAudioThatWasRecordedUntouched() {
        val s = scriptSession()
        val (bytes, _) = write(s)
        val inside = entries(bytes)
        for (c in s.clips) assertArrayEquals(c.wav.readBytes(), inside.getValue(PackageNames.clip(s.id, c.index)))
    }

    @Test
    fun aFreeSessionCarriesItsSuggestedCutsAndTheWholeRecording() {
        val f = freeSession()
        assertTrue("the test recording should give at least two suggestions", f.proposed.size >= 2)
        val (bytes, _) = write(f)
        val rec = manifestOf(bytes)["sessions"]!!.jsonArray.single().jsonObject["recording"]!!.jsonObject
        assertEquals(PackageNames.recording(f.id), rec["file"]!!.jsonPrimitive.content)
        assertEquals(f.proposed.map { it.endKind }, rec["proposed_segments"]!!.jsonArray.map { it.jsonObject["end_kind"]!!.jsonPrimitive.content })
        assertEquals(f.proposed.map { it.startS }, rec["proposed_segments"]!!.jsonArray.map { it.jsonObject["start_s"]!!.jsonPrimitive.double })
        assertArrayEquals(f.wav.readBytes(), entries(bytes).getValue(PackageNames.recording(f.id)))
        assertTrue(PackageVerifier.verify(ByteArrayInputStream(bytes)).ok)
    }

    @Test
    fun severalSessionsShareOnePackage() {
        val (bytes, report) = write(scriptSession(), freeSession())
        assertEquals(2, report.sessions)
        assertEquals(4, report.audioFiles)
        val v = PackageVerifier.verify(ByteArrayInputStream(bytes))
        assertTrue(v.problems.toString(), v.ok)
        assertEquals(2, v.sessions)
    }

    @Test
    fun theSameSessionsMakeTheSameBytes() {
        val s = scriptSession()
        assertArrayEquals(write(s).first, write(s).first)
    }

    @Test
    fun noPersonalDetailsBeyondModelAndAndroidVersionAreWritten() {
        val m = manifestOf(write(scriptSession()).first)
        val device = m["sessions"]!!.jsonArray.single().jsonObject["device"]!!.jsonObject
        assertEquals(setOf("model", "sdk"), device.keys)
        assertEquals(35, device["sdk"]!!.jsonPrimitive.int)
    }

    // -- refusing a package that the PC would refuse ------------------------------------------------------------------------
    @Test
    fun refusesNothingToPack() = refused(emptyList(), "1 to ${CaptureConstants.MAX_SESSIONS} sessions")

    @Test
    fun refusesTwoSessionsWithOneId() = refused(listOf(scriptSession(), scriptSession()), "appears twice")

    @Test
    fun refusesAnIdOutsideTheForm() = refused(listOf(scriptSession(id = "session-1")), "not in the form")

    @Test
    fun refusesATimeThatIsNotUtcSeconds() = refused(listOf(scriptSession()), "package time", createdUtc = "2026-10-02 19:30")

    @Test
    fun refusesALanguageThatIsNotACode() = refused(listOf(scriptSession().copy(language = "english please")), "language")

    @Test
    fun refusesAMicrophoneSourceThatIsNotAShortUpperCaseWord() = refused(listOf(scriptSession().let { it.copy(audio = it.audio.copy(source = "unprocessed")) }), "microphone source")

    @Test
    fun refusesCardTextWithALineBreakOrNothingInIt() {
        val s = scriptSession()
        refused(listOf(s.copy(clips = listOf(s.clips[0].copy(text = "two\nlines")) + s.clips.drop(1))), "on one line")
        refused(listOf(s.copy(clips = listOf(s.clips[0].copy(text = "   ")) + s.clips.drop(1))), "on one line")
        refused(listOf(s.copy(clips = listOf(s.clips[0].copy(text = "x".repeat(CaptureConstants.MAX_CARD_CHARS + 1))) + s.clips.drop(1))), "on one line")
    }

    @Test
    fun refusesClipsOutOfOrder() {
        val s = scriptSession()
        refused(listOf(s.copy(clips = listOf(s.clips[1], s.clips[0], s.clips[2]))), "increasing order")
    }

    @Test
    fun refusesAudioAtTheWrongRateOrWrongLength() {
        val s = scriptSession()
        refused(listOf(s.copy(audio = s.audio.copy(sampleRate = 44_100))), "Hz but its session says")
        refused(listOf(s.copy(clips = listOf(s.clips[0].copy(durationS = s.clips[0].durationS + 1.0)) + s.clips.drop(1))), "long but it is noted as")
    }

    @Test
    fun refusesAMissingFile() {
        val s = scriptSession()
        s.clips[1].wav.delete()
        refused(listOf(s), "is missing")
    }

    @Test
    fun refusesARecordingThatWasInterruptedAndSaysSo() {
        val s = scriptSession()
        val f = s.clips[0].wav
        val bytes = f.readBytes()
        f.writeBytes(WavFile.header(48_000, 0) + bytes.copyOfRange(WavFile.HEADER_BYTES, bytes.size))     // length never filled in
        refused(listOf(s), "interrupted")
    }

    @Test
    fun refusesSuggestionsThatOverlapOrRunTooLong() {
        val f = freeSession()
        val a = f.proposed[0]
        refused(listOf(f.copy(proposed = listOf(a, a.copy(startS = a.endS - 0.5, endS = a.endS + 1.0)))), "overlaps")
        refused(listOf(f.copy(proposed = listOf(a.copy(startS = 0.0, endS = 12.5)))), "longer than")
        refused(listOf(f.copy(proposed = listOf(a.copy(endKind = "whenever")))), "end_kind")
    }

    @Test
    fun refusesALevelThatIsNotANumber() {
        val s = scriptSession()
        refused(listOf(s.copy(thresholdDbfs = Double.NaN)), "speech threshold")
        refused(listOf(s.copy(clips = listOf(s.clips[0].copy(metrics = s.clips[0].metrics.copy(peakDbfs = Double.POSITIVE_INFINITY))) + s.clips.drop(1))), "peak level")
    }

    @Test
    fun aFileThatGrowsWhileItIsBeingPackagedStopsTheExportInsteadOfWritingAPackageThatLies() {
        val s = scriptSession()
        var grown = false
        try {
            PackageWriter.write(listOf(s), ByteArrayOutputStream(), created, "1.0-beta.9") { _, _ ->
                if (!grown) { grown = true; s.clips[0].wav.appendBytes(ByteArray(10)) }
            }
            fail("expected the export to stop")
        } catch (e: PackageWriteException) {
            assertTrue(e.message, "changed while it was being packaged" in e.message!!)
        }
        assertTrue(grown)
    }

    @Test
    fun levelsInTheManifestAreRoundedToOneDecimal() {
        val s = scriptSession().copy(noiseFloorDbfs = -62.34, thresholdDbfs = -52.349)
        val session = manifestOf(write(s).first)["sessions"]!!.jsonArray.single().jsonObject
        assertEquals(-62.3, session["noise_floor_dbfs"]!!.jsonPrimitive.double, 0.0)
        assertEquals(-52.3, session["threshold_dbfs"]!!.jsonPrimitive.double, 0.0)
    }

    // -- text the person typed is cleaned, not refused ----------------------------------------------------------------------
    @Test
    fun typedTextIsCleanedAndCutToLength() {
        val s = scriptSession().let { it.copy(label = "closet\n\tnear the window " + "x".repeat(200), script = it.script.copy(title = "a".repeat(300)), device = DeviceNote("P".repeat(100), 35)) }
        val session = manifestOf(write(s).first)["sessions"]!!.jsonArray.single().jsonObject
        val label = session["label"]!!.jsonPrimitive.content
        assertTrue(label.length <= 120)
        assertTrue(label, label.startsWith("closet near the window "))
        assertTrue(label.none { it.isISOControl() || it == ' ' })
        assertEquals(120, session["script"]!!.jsonObject["title"]!!.jsonPrimitive.content.length)
        assertEquals(60, session["device"]!!.jsonObject["model"]!!.jsonPrimitive.content.length)
    }

    @Test
    fun cuttingTextNeverSplitsACharacterInTwo() {
        val cut = PackageWriter.clean("a".repeat(119) + "😀 more", 120)       // the emoji would straddle the limit
        assertEquals("a".repeat(119), cut)
        assertEquals("a b", PackageWriter.clean("  a\r\nb  ", 120))
        assertEquals("a b c", PackageWriter.clean("a \n  b\u0007\tc", 120))
    }

    // -- reading it back ----------------------------------------------------------------------------------------------------
    @Test
    fun theVerifierNoticesAudioThatChangedAfterItWasListed() {
        val (bytes, _) = write(scriptSession())
        val damaged = rezip(bytes) { n, d -> if (n.endsWith("0002.wav")) n to d.copyOf().also { it[100] = (it[100] + 1).toByte() } else n to d }
        val v = PackageVerifier.verify(ByteArrayInputStream(damaged))
        assertFalse(v.ok)
        assertTrue(v.problems.toString(), v.problems.any { "0002.wav" in it && "checksum" in it })
    }

    @Test
    fun theVerifierNoticesASizeThatDoesNotMatchEvenWhenTheChecksumDoes() {
        val (bytes, _) = write(scriptSession())
        val edited = rezip(bytes) { n, d ->
            if (n != "manifest.json") return@rezip n to d
            val text = String(d, Charsets.UTF_8)
            val m = Regex("\"bytes\": (\\d+)").find(text)!!                    // the first listed file's size, one byte too many
            n to text.replaceRange(m.range, "\"bytes\": ${m.groupValues[1].toLong() + 1}").toByteArray(Charsets.UTF_8)
        }
        val v = PackageVerifier.verify(ByteArrayInputStream(edited))
        assertTrue(v.problems.toString(), v.problems.any { "saved size differs" in it })
        assertFalse(v.problems.any { "checksum" in it })
    }

    @Test
    fun theVerifierNoticesAnExtraFileAMissingFileAndAMissingManifest() {
        val (bytes, _) = write(scriptSession())
        val extra = withEntry(bytes, "notes.txt", ByteArray(1))
        assertTrue(PackageVerifier.verify(ByteArrayInputStream(extra)).problems.any { "notes.txt" in it && "not a file the format allows" in it })
        val missing = rezip(bytes) { n, d -> if (n.endsWith("0003.wav")) null else n to d }
        assertTrue(PackageVerifier.verify(ByteArrayInputStream(missing)).problems.any { "0003.wav" in it && "listed but not" in it })
        val noManifest = rezip(bytes) { n, d -> if (n == "manifest.json") null else n to d }
        assertTrue(PackageVerifier.verify(ByteArrayInputStream(noManifest)).problems.any { "manifest.json is missing" in it })
    }

    @Test
    fun theVerifierSaysSoWhenTheSavedFileIsCutShort() {
        val (bytes, _) = write(scriptSession())
        val v = PackageVerifier.verify(ByteArrayInputStream(bytes.copyOf(bytes.size / 2)))
        assertFalse(v.ok)
    }

    // -- splitting into packages --------------------------------------------------------------------------------------------
    private val sizes = HashMap<File, Long>()
    private val sizeOf: (File) -> Long = { sizes[it] ?: it.length() }

    /** A session whose audio file is only pretended to be [bytes] long, so the planner can be tried with sizes no test disk should hold. */
    private fun big(id: String, bytes: Long): FreeSession {
        val pretend = File(dir, "pretend-$id")
        sizes[pretend] = bytes
        return FreeSession(
            id = id, label = "", started = "2026-10-02T18:00:00Z", ended = "2026-10-02T18:00:01Z", language = "en-US",
            audio = AudioSettings(48_000, "UNPROCESSED", "UNPROCESSED"), noiseFloorDbfs = null, thresholdDbfs = -45.0, device = null,
            topic = "", wav = pretend, durationS = 1.0, metrics = CaptureMetrics(-6.0, -20.0, 0), proposed = emptyList(),
        )
    }

    @Test
    fun sessionsAreGroupedUnderTheLimitInOrderAndNeverSplit() {
        val a = big("s20261002-100000-0001", 700_000_000); val b = big("s20261002-100100-0002", 700_000_000)
        val c = big("s20261002-100200-0003", 700_000_000); val d = big("s20261002-100300-0004", 1_900_000_000)
        val plan = PackagePlanner.plan(listOf(a, b, c, d), sizeOf)
        assertEquals(listOf(listOf(a.id, b.id), listOf(c.id), listOf(d.id)), plan.packages.map { g -> g.map { it.id } })
        assertEquals(emptyList<String>(), plan.tooBig)
    }

    @Test
    fun aSessionTooBigForAnyPackageIsReportedNotDropped() {
        val a = big("s20261002-100000-0001", 2_100_000_000); val b = big("s20261002-100100-0002", 1_000)
        val plan = PackagePlanner.plan(listOf(a, b), sizeOf)
        assertEquals(listOf(a.id), plan.tooBig)
        assertEquals(listOf(listOf(b.id)), plan.packages.map { g -> g.map { it.id } })
    }

    @Test
    fun aPackageHoldsNoMoreThanTheLimitOfSessions() {
        val list = (1..(CaptureConstants.MAX_SESSIONS + 1)).map { big(String.format(Locale.ROOT, "s20261002-100000-%04x", it), 1_000) }
        val plan = PackagePlanner.plan(list, sizeOf)
        assertEquals(listOf(CaptureConstants.MAX_SESSIONS, 1), plan.packages.map { it.size })
    }

    @Test
    fun aPackageHoldsNoMoreThanTheLimitOfFiles() {
        val one = scriptSession(texts = listOf("a b c.")).clips.single()
        sizes[one.wav] = 1_000                                   // all the pretend clips share one file; count it as small
        fun many(id: String, n: Int) = scriptSession(id = id, texts = listOf("a b c.")).copy(clips = (1..n).map { one.copy(index = it) })
        val plan = PackagePlanner.plan((1..5).map { many(String.format(Locale.ROOT, "s20261002-100000-%04x", it), 4_000) }, sizeOf)
        assertEquals(listOf(4, 1), plan.packages.map { it.size })
    }

    // -- names and times ----------------------------------------------------------------------------------------------------
    @Test
    fun namesAndTimesHaveTheFormTheFormatAsksFor() {
        val t = java.time.Instant.parse("2026-10-02T18:04:11Z").toEpochMilli()
        assertEquals("s20261002-180411-a3f9", CaptureTime.sessionId(t, 0xa3f9))
        assertEquals("s20261002-180411-00ff", CaptureTime.sessionId(t, 0x1_00ff))                 // only four hex digits are kept
        assertEquals("2026-10-02T18:04:11Z", CaptureTime.utc(t + 999))
        assertEquals("1970-01-01T00:00:00Z", CaptureTime.utc(0))
        assertEquals("ack-training-20261002-180411.zip", CaptureTime.packageFileName(t))
        assertEquals("ack-training-20261002-180411-part2.zip", CaptureTime.packageFileName(t, 2))
        assertEquals("sessions/s20261002-180411-a3f9/clips/0014.wav", PackageNames.clip("s20261002-180411-a3f9", 14))
        assertTrue(PackageNames.SESSION_ID.matches(CaptureTime.sessionId(t, 12345)))
    }

    @Test
    fun namesStayPlainDigitsWhateverLanguageThePhoneUses() {
        val before = Locale.getDefault()
        try {
            Locale.setDefault(Locale.forLanguageTag("ar-SA-u-nu-arab"))
            val t = java.time.Instant.parse("2026-10-02T18:04:11Z").toEpochMilli()
            assertEquals("s20261002-180411-a3f9", CaptureTime.sessionId(t, 0xa3f9))
            assertEquals("sessions/s20261002-180411-a3f9/clips/0014.wav", PackageNames.clip("s20261002-180411-a3f9", 14))
            assertEquals("ack-training-20261002-180411.zip", CaptureTime.packageFileName(t))
        } finally {
            Locale.setDefault(before)
        }
    }

    // -- the contract with Freeform Studio's reader --------------------------------------------------------------------------
    @Test
    fun writesPackagesForFreeformStudioToOpenWhenAskedTo() {
        val target = System.getenv("ACK_KOTLIN_PACKAGES") ?: return          // set by tools/freeform_studio/tests/test_kotlin_package_contract.py
        val out = File(target)
        out.mkdirs()
        File(out, "script.zip").writeBytes(write(scriptSession()).first)
        File(out, "free.zip").writeBytes(write(freeSession()).first)
        File(out, "mixed.zip").writeBytes(write(scriptSession(id = "s20261002-190000-c001", rate = 44_100), freeSession(id = "s20261002-190500-c002")).first)
    }
}
