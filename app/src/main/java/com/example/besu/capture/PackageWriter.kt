// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.File
import java.io.FileInputStream
import java.io.FilterOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest
import java.time.Instant
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import kotlin.math.abs
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject

/** The package can't be made. [problems] list what to fix, in words a person can act on; nothing was left half-written by this class. */
class PackageWriteException(message: String, val problems: List<String> = emptyList()) : Exception(message)

data class PackageReport(val entries: Int, val bytes: Long, val sessions: Int, val audioFiles: Int)

private data class FileRecord(val path: String, val bytes: Long, val sha256: String)

/** Counts what passes through. Closing it only flushes: the stream underneath belongs to the caller, who closes it. */
private class CountingOutputStream(out: OutputStream) : FilterOutputStream(out) {
    var count = 0L
    override fun write(b: Int) { out.write(b); count += 1 }
    override fun write(b: ByteArray, off: Int, len: Int) { out.write(b, off, len); count += len }
    override fun close() { flush() }
}

// Builds a training-capture package (docs/ACK_TRAINING_CAPTURE_FORMAT.md, sections 2 to 4). It is the Kotlin half of the contract
// with Freeform Studio's reader (tools/freeform_studio/ack_package.py): the same rules are checked here before a single byte is
// written, so a package that leaves the phone is one the PC will accept. Text the person typed (label, topic, title, phone model)
// is cleaned and cut to the allowed length; anything the app itself built (ids, counts, times, audio) has to be right or the
// export is refused with the reason.
object PackageWriter {
    private val CODE = Regex("^[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})?$")
    private val SCRIPT_ID = Regex("^[A-Za-z0-9_-]{1,40}$")
    private val SOURCE = Regex("^[A-Z][A-Z_]{0,31}$")
    private val FLAG = Regex("^[a-z_]{1,32}$")
    private val TIME = Regex("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$")
    private val END_KINDS = setOf("pause", "forced", "end")
    private const val DURATION_TOLERANCE_S = 0.05
    private const val MAX_LABEL = 120
    private const val MAX_TOPIC = 200
    private const val MAX_TITLE = 120
    private const val MAX_MODEL = 60
    private const val MAX_VERSION = 40

    const val README_TEXT = "This file was made by ACK (the training-capture export).\n" +
        "\n" +
        "It holds voice recordings and the words that were read in them. Treat it like the recordings themselves: keep it\n" +
        "on devices you control. ACK never sends it anywhere; it only saves it where you chose.\n" +
        "\n" +
        "To use it, copy this file to the computer that runs Freeform Studio and import it there:\n" +
        "    python -m freeform_studio.ack_import ack-training-....zip --dry-run     (look first, write nothing)\n" +
        "    python -m freeform_studio.ack_import ack-training-....zip\n" +
        "\n" +
        "What is inside:\n" +
        "    manifest.json                       what each recording is, with a checksum for every audio file\n" +
        "    sessions/<id>/clips/0001.wav ...    script mode: one recording per card\n" +
        "    sessions/<id>/session.wav           free-speech mode: one whole recording\n" +
        "The audio is plain 16-bit mono WAV, so any audio program can open it.\n"

    private val prettyJson = Json { prettyPrint = true }

    /**
     * Text typed by a person: each line break or control character (with any spaces after it) becomes one space, ends are trimmed, and
     * the result is cut to [max] (never inside a character).
     */
    fun clean(s: String, max: Int): String {
        val sb = StringBuilder(s.length)
        var inBreak = false
        for (c in s) {
            if (isLineBreakOrControl(c)) { inBreak = true; continue }
            if (inBreak) {
                if (c == ' ') continue
                if (sb.isNotEmpty() && sb.last() != ' ') sb.append(' ')
                inBreak = false
            }
            sb.append(c)
        }
        var t = sb.toString().trim()
        if (t.length > max) {
            t = t.substring(0, max)
            if (t.isNotEmpty() && t.last().isHighSurrogate()) t = t.dropLast(1)
            t = t.trimEnd()
        }
        return t
    }

    private fun isLineBreakOrControl(c: Char) = c.isISOControl() || c == ' ' || c == ' '

    private fun timeOk(s: String): Boolean = TIME.matches(s) && try { Instant.parse(s); true } catch (e: Exception) { false }

    private fun finiteIn(x: Double, lo: Double, hi: Double) = !x.isNaN() && !x.isInfinite() && x >= lo && x <= hi

    private fun metricsProblems(where: String, m: CaptureMetrics, out: MutableList<String>) {
        if (!finiteIn(m.peakDbfs, -120.0, 1.0)) out.add("$where: the peak level should be between -120 and 0")
        if (!finiteIn(m.rmsDbfs, -120.0, 1.0)) out.add("$where: the average level should be between -120 and 0")
        if (m.clippedSamples < 0) out.add("$where: the clipped-sample count should not be negative")
    }

    private fun audioProblems(where: String, file: File, rate: Int, durationS: Double, out: MutableList<String>) {
        try {
            val info = WavFile.inspect(file)
            if (info.sampleRate != rate) out.add("$where: the audio is ${info.sampleRate} Hz but its session says $rate Hz")
            if (abs(info.seconds - durationS) > DURATION_TOLERANCE_S) {
                out.add("$where: the recording is ${LevelMath.rnd(info.seconds, 3)} s long but it is noted as ${LevelMath.rnd(durationS, 3)} s")
            }
        } catch (e: WavException) {
            out.add("$where: ${e.message}")
        }
    }

    /** Every reason this set of sessions can't be written as one package. Empty means it can. Reads each audio file's header only. */
    fun check(sessions: List<CaptureSession>, createdUtc: String): List<String> {
        val out = mutableListOf<String>()
        if (!timeOk(createdUtc)) out.add("the package time should look like 2026-10-02T18:30:00Z")
        if (sessions.isEmpty() || sessions.size > CaptureConstants.MAX_SESSIONS) {
            out.add("a package holds 1 to ${CaptureConstants.MAX_SESSIONS} sessions, not ${sessions.size}")
        }
        val ids = HashSet<String>()
        var entries = 2                                   // manifest.json and README.txt
        for (s in sessions) {
            val where = "session ${s.id}"
            if (!PackageNames.SESSION_ID.matches(s.id)) { out.add("a session id is not in the form s20261002-180411-a3f9: ${s.id.take(40)}"); continue }
            if (!ids.add(s.id)) out.add("$where appears twice")
            if (!timeOk(s.started)) out.add("$where: started should be a UTC time like 2026-10-02T18:04:11Z")
            if (!timeOk(s.ended)) out.add("$where: ended should be a UTC time like 2026-10-02T18:04:11Z")
            if (!CODE.matches(s.language)) out.add("$where: language should look like en-US")
            if (s.audio.sampleRate < WavFile.MIN_RATE || s.audio.sampleRate > WavFile.MAX_RATE) {
                out.add("$where: sample rate ${s.audio.sampleRate} is outside ${WavFile.MIN_RATE} to ${WavFile.MAX_RATE}")
            }
            if (!SOURCE.matches(s.audio.source) || !SOURCE.matches(s.audio.sourceRequested)) {
                out.add("$where: the microphone source should be a short upper-case word such as UNPROCESSED")
            }
            val nf = s.noiseFloorDbfs
            if (nf != null && !finiteIn(nf, -120.0, 0.0)) out.add("$where: the room level should be empty or between -120 and 0")
            if (!finiteIn(s.thresholdDbfs, -120.0, 0.0)) out.add("$where: the speech threshold should be between -120 and 0")
            when (s) {
                is ScriptSession -> {
                    if (!SCRIPT_ID.matches(s.script.id)) out.add("$where: the script id should be 1 to 40 letters, digits, _ or -")
                    if (s.script.cardsTotal < 1) out.add("$where: the script should have at least one card")
                    if (s.clips.isEmpty() || s.clips.size > CaptureConstants.MAX_CLIPS_PER_SESSION) {
                        out.add("$where: it should hold 1 to ${CaptureConstants.MAX_CLIPS_PER_SESSION} clips, not ${s.clips.size}")
                    }
                    var last = 0
                    for (c in s.clips) {
                        val cw = "$where, clip ${c.index}"
                        if (c.index < 1) { out.add("$where: a clip has no valid index"); continue }
                        if (c.index <= last) out.add("$cw: clips must be in increasing order")
                        last = maxOf(last, c.index)
                        if (c.card < 1) out.add("$cw: the card number should start at 1")
                        if (c.attempt < 1) out.add("$cw: the attempt number should start at 1")
                        if (c.text.isBlank() || c.text.length > CaptureConstants.MAX_CARD_CHARS || c.text.any { isLineBreakOrControl(it) }) {
                            out.add("$cw: the text should be 1 to ${CaptureConstants.MAX_CARD_CHARS} characters on one line")
                        }
                        if (!timeOk(c.recorded)) out.add("$cw: recorded should be a UTC time")
                        if (!finiteIn(c.durationS, 0.001, 86_400.0)) out.add("$cw: the length should be a positive number of seconds")
                        val sp = c.speech
                        if (sp != null && !(sp.startS >= 0 && sp.startS < sp.endS && sp.endS <= c.durationS + DURATION_TOLERANCE_S)) {
                            out.add("$cw: the speech start and end are not valid")
                        }
                        metricsProblems(cw, c.metrics, out)
                        if (c.flags.any { !FLAG.matches(it) }) out.add("$cw: a flag is not a short lower-case word")
                        audioProblems(cw, c.wav, s.audio.sampleRate, c.durationS, out)
                        entries += 1
                    }
                }
                is FreeSession -> {
                    if (!(s.durationS > 0 && s.durationS <= CaptureConstants.MAX_FREE_SESSION_S)) {
                        out.add("$where: the recording length should be more than 0 and at most ${CaptureConstants.MAX_FREE_SESSION_S} seconds")
                    }
                    metricsProblems("$where recording", s.metrics, out)
                    var prevEnd = 0.0
                    s.proposed.forEachIndexed { i, p ->
                        val pw = "$where, suggested piece ${i + 1}"
                        if (!(p.startS >= 0 && p.startS < p.endS)) { out.add("$pw: its start and end are not valid"); return@forEachIndexed }
                        if (p.endS > s.durationS + DURATION_TOLERANCE_S) out.add("$pw: it runs past the end of the recording")
                        if (p.endS - p.startS > CaptureConstants.MAX_CLIP_S + 0.001) out.add("$pw: it is longer than ${CaptureConstants.MAX_CLIP_S} seconds")
                        if (p.startS < prevEnd - 1e-6) out.add("$pw: it overlaps the one before")
                        prevEnd = maxOf(prevEnd, p.endS)
                        if (p.endKind !in END_KINDS) out.add("$pw: end_kind should be one of pause, forced, end")
                        metricsProblems(pw, p.metrics, out)
                    }
                    audioProblems("$where recording", s.wav, s.audio.sampleRate, s.durationS, out)
                    entries += 1
                }
            }
        }
        if (entries > CaptureConstants.MAX_ENTRIES) out.add("a package holds at most ${CaptureConstants.MAX_ENTRIES} files; this would need $entries")
        return out
    }

    /** The audio files a package of these sessions holds, as (entry name, file), in name order. */
    fun audioFiles(sessions: List<CaptureSession>): List<Pair<String, File>> {
        val list = mutableListOf<Pair<String, File>>()
        for (s in sessions) when (s) {
            is ScriptSession -> s.clips.forEach { list.add(PackageNames.clip(s.id, it.index) to it.wav) }
            is FreeSession -> list.add(PackageNames.recording(s.id) to s.wav)
        }
        return list.sortedBy { it.first }
    }

    private fun num(x: Double, digits: Int) = JsonPrimitive(LevelMath.rnd(x, digits))

    private fun metricsJson(m: CaptureMetrics): JsonObject = buildJsonObject {
        put("peak_dbfs", num(m.peakDbfs, 1))
        put("rms_dbfs", num(m.rmsDbfs, 1))
        put("clipped_samples", m.clippedSamples)
    }

    private fun sessionJson(s: CaptureSession): JsonObject = buildJsonObject {
        put("id", s.id)
        put("mode", if (s is ScriptSession) "script" else "free")
        put("label", clean(s.label, MAX_LABEL))
        put("started", s.started)
        put("ended", s.ended)
        put("language", s.language)
        putJsonObject("audio") {
            put("sample_rate", s.audio.sampleRate)
            put("source", s.audio.source)
            put("source_requested", s.audio.sourceRequested)
        }
        put("noise_floor_dbfs", s.noiseFloorDbfs?.let { num(it, 1) } ?: JsonNull)
        put("threshold_dbfs", num(s.thresholdDbfs, 1))
        s.device?.let { d ->
            putJsonObject("device") {
                put("model", clean(d.model, MAX_MODEL))
                put("sdk", d.sdk)
            }
        }
        when (s) {
            is ScriptSession -> {
                putJsonObject("script") {
                    put("id", s.script.id)
                    put("title", clean(s.script.title, MAX_TITLE))
                    put("cards_total", s.script.cardsTotal)
                }
                putJsonArray("clips") {
                    for (c in s.clips) add(buildJsonObject {
                        put("index", c.index)
                        put("card", c.card)
                        put("attempt", c.attempt)
                        put("file", PackageNames.clip(s.id, c.index))
                        put("text", c.text)
                        put("recorded", c.recorded)
                        put("duration_s", num(c.durationS, 3))
                        put("speech", c.speech?.let { sp -> buildJsonObject { put("start_s", num(sp.startS, 3)); put("end_s", num(sp.endS, 3)) } } ?: JsonNull)
                        put("metrics", metricsJson(c.metrics))
                        put("flags", buildJsonArray { c.flags.forEach { add(JsonPrimitive(it)) } })
                    })
                }
            }
            is FreeSession -> {
                put("topic", clean(s.topic, MAX_TOPIC))
                putJsonObject("recording") {
                    put("file", PackageNames.recording(s.id))
                    put("duration_s", num(s.durationS, 3))
                    put("metrics", metricsJson(s.metrics))
                    putJsonArray("proposed_segments") {
                        for (p in s.proposed) add(buildJsonObject {
                            put("start_s", num(p.startS, 3))
                            put("end_s", num(p.endS, 3))
                            put("end_kind", p.endKind)
                            put("metrics", metricsJson(p.metrics))
                        })
                    }
                }
            }
        }
    }

    private fun manifestJson(createdUtc: String, appVersion: String, sessions: List<CaptureSession>, files: List<FileRecord>): JsonObject = buildJsonObject {
        put("schema", "ack-training-capture/1")
        put("created", createdUtc)
        putJsonObject("app") {
            put("name", "ACK")
            put("version", clean(appVersion, MAX_VERSION))
        }
        putJsonArray("sessions") { sessions.forEach { add(sessionJson(it)) } }
        putJsonArray("files") {
            for (f in files) add(buildJsonObject { put("path", f.path); put("bytes", f.bytes); put("sha256", f.sha256) })
        }
    }

    private fun hex(bytes: ByteArray): String {
        val digits = "0123456789abcdef"
        val sb = StringBuilder(bytes.size * 2)
        for (b in bytes) { sb.append(digits[(b.toInt() shr 4) and 0xf]); sb.append(digits[b.toInt() and 0xf]) }
        return sb.toString()
    }

    /**
     * Writes one package to [out] (which the caller opens and closes). Checks everything first, then streams each audio file into the
     * zip while working out its checksum in the same pass, and writes the manifest last. If anything goes wrong an exception is
     * thrown ([PackageWriteException] for a package that can't be made, or the [java.io.IOException] from [out] itself, for example
     * when the storage fills up) and the caller must throw the partial output away; this class never keeps a half-made package alive.
     * [progress] is called with (bytes of audio done, bytes of audio in all).
     */
    fun write(
        sessions: List<CaptureSession>, out: OutputStream, createdUtc: String, appVersion: String,
        progress: ((Long, Long) -> Unit)? = null,
    ): PackageReport {
        val problems = check(sessions, createdUtc)
        if (problems.isNotEmpty()) throw PackageWriteException("This package can't be made yet.", problems)
        val audio = audioFiles(sessions)
        val totalAudio = audio.sumOf { it.second.length() }
        val counting = CountingOutputStream(out)
        val zip = ZipOutputStream(counting)
        try {
            return writeEntries(zip, counting, sessions, audio, totalAudio, createdUtc, appVersion, progress)
        } finally {
            try { zip.close() } catch (e: Exception) { /* the real problem, if any, is already on its way out */ }
        }
    }

    private fun writeEntries(
        zip: ZipOutputStream, counting: CountingOutputStream, sessions: List<CaptureSession>, audio: List<Pair<String, File>>,
        totalAudio: Long, createdUtc: String, appVersion: String, progress: ((Long, Long) -> Unit)?,
    ): PackageReport {
        zip.setLevel(1)                                   // audio barely compresses; keep the phone quick
        val millis = Instant.parse(createdUtc).toEpochMilli()
        fun entry(name: String) = ZipEntry(name).also { it.time = millis }

        zip.putNextEntry(entry(PackageNames.README))
        zip.write(README_TEXT.toByteArray(Charsets.UTF_8))
        zip.closeEntry()

        val records = mutableListOf<FileRecord>()
        val buf = ByteArray(64 * 1024)
        var done = 0L
        for ((name, file) in audio) {
            val expected = file.length()
            val digest = MessageDigest.getInstance("SHA-256")
            var n = 0L
            zip.putNextEntry(entry(name))
            FileInputStream(file).use { input ->
                while (true) {
                    val r = input.read(buf)
                    if (r < 0) break
                    digest.update(buf, 0, r)
                    zip.write(buf, 0, r)
                    n += r
                    done += r
                    if (counting.count > CaptureConstants.MAX_PACKAGE_BYTES) {
                        throw PackageWriteException("This package would be larger than ${CaptureConstants.MAX_PACKAGE_BYTES / 1_000_000} MB. Export fewer sessions at a time.")
                    }
                    progress?.invoke(done, totalAudio)
                }
            }
            zip.closeEntry()
            if (n != expected) throw PackageWriteException("$name changed while it was being packaged. Nothing was exported; try again.")
            records.add(FileRecord(name, n, hex(digest.digest())))
        }

        val manifest = prettyJson.encodeToString(JsonElement.serializer(), manifestJson(createdUtc, appVersion, sessions, records)) + "\n"
        val manifestBytes = manifest.toByteArray(Charsets.UTF_8)
        if (manifestBytes.size > CaptureConstants.MAX_MANIFEST_BYTES) throw PackageWriteException("The list of recordings is too large for one package. Export fewer sessions at a time.")
        zip.putNextEntry(entry(PackageNames.MANIFEST))
        zip.write(manifestBytes)
        zip.closeEntry()
        zip.finish()
        zip.flush()                                       // the central directory is written; the caller's stream is flushed, not closed
        if (counting.count > CaptureConstants.MAX_PACKAGE_BYTES) {
            throw PackageWriteException("This package is larger than ${CaptureConstants.MAX_PACKAGE_BYTES / 1_000_000} MB. Export fewer sessions at a time.")
        }
        return PackageReport(entries = audio.size + 2, bytes = counting.count, sessions = sessions.size, audioFiles = audio.size)
    }
}

/** Splits sessions into packages that each stay under the format's limits. A session is never split across packages. */
object PackagePlanner {
    /** A recording screen should start a new session once the audio in one reaches this much, so no session outgrows a package on its own. */
    const val ROLLOVER_BYTES = 1_500_000_000L

    class Plan(val packages: List<List<CaptureSession>>, val tooBig: List<String>)

    private fun audioBytes(s: CaptureSession, sizeOf: (File) -> Long): Long = when (s) {
        is ScriptSession -> s.clips.sumOf { sizeOf(it.wav) }
        is FreeSession -> sizeOf(s.wav)
    }

    private fun audioCount(s: CaptureSession): Int = when (s) {
        is ScriptSession -> s.clips.size
        is FreeSession -> 1
    }

    /** A cautious size for one session inside a package: the audio, a little for deflate on audio that won't shrink, zip headers and the list. */
    fun estimateBytes(s: CaptureSession, sizeOf: (File) -> Long = File::length): Long {
        val audio = audioBytes(s, sizeOf)
        val n = audioCount(s)
        val manifest = 1_500L + when (s) {
            is ScriptSession -> s.clips.sumOf { 900L + it.text.length }
            is FreeSession -> 300L * s.proposed.size
        }
        return audio + audio / 1000 + 64L * n + 220L * n + 2 * manifest
    }

    /** [sizeOf] says how big an audio file is; the default asks the file system. */
    fun plan(sessions: List<CaptureSession>, sizeOf: (File) -> Long = File::length): Plan {
        val groups = mutableListOf<MutableList<CaptureSession>>()
        val tooBig = mutableListOf<String>()
        var bytes = 0L
        var entries = 0
        for (s in sessions) {
            val est = estimateBytes(s, sizeOf) + 4_000
            val n = audioCount(s)
            if (est > CaptureConstants.MAX_PACKAGE_BYTES || n + 2 > CaptureConstants.MAX_ENTRIES) { tooBig.add(s.id); continue }
            val fits = groups.isNotEmpty() && bytes + est <= CaptureConstants.MAX_PACKAGE_BYTES &&
                entries + n + 2 <= CaptureConstants.MAX_ENTRIES && groups.last().size < CaptureConstants.MAX_SESSIONS
            if (!fits) { groups.add(mutableListOf()); bytes = 0L; entries = 0 }
            groups.last().add(s)
            bytes += est
            entries += n
        }
        return Plan(groups, tooBig)
    }
}

data class VerifyResult(val problems: List<String>, val sessions: Int, val audioFiles: Int, val bytes: Long) {
    val ok: Boolean get() = problems.isEmpty()
}

/**
 * Reads a package back from where it was saved and checks that what is stored is what was meant: only allowed entries, a manifest that
 * parses, every audio file listed with the right size and checksum, nothing listed that is missing. It is the "did the save really
 * work" check the export screen runs after writing; Freeform Studio does the full check again on its side. [verify] closes [input].
 */
object PackageVerifier {
    fun verify(input: InputStream): VerifyResult {
        val problems = mutableListOf<String>()
        val seen = HashMap<String, Pair<Long, String>>()
        val names = HashSet<String>()
        var manifestBytes: ByteArray? = null
        var total = 0L
        var count = 0
        try {
            ZipInputStream(input).use { zip ->
                val buf = ByteArray(64 * 1024)
                while (true) {
                    val e = zip.nextEntry ?: break
                    count += 1
                    val name = e.name
                    if (count > CaptureConstants.MAX_ENTRIES) { problems.add("the package holds more than ${CaptureConstants.MAX_ENTRIES} files"); break }
                    if (!names.add(name)) problems.add("$name is in the package twice")
                    if (e.isDirectory) {
                        if (!PackageNames.DIRECTORY.matches(name)) problems.add("the folder $name is not one the format allows")
                        continue
                    }
                    val audio = PackageNames.AUDIO_PATH.matches(name)
                    if (!audio && name != PackageNames.MANIFEST && name != PackageNames.README) {
                        problems.add("$name is not a file the format allows"); continue
                    }
                    val digest = MessageDigest.getInstance("SHA-256")
                    var n = 0L
                    val keep = if (name == PackageNames.MANIFEST) java.io.ByteArrayOutputStream() else null
                    while (true) {
                        val r = zip.read(buf)
                        if (r < 0) break
                        n += r
                        total += r
                        digest.update(buf, 0, r)
                        if (keep != null) {
                            keep.write(buf, 0, r)
                            if (keep.size() > CaptureConstants.MAX_MANIFEST_BYTES) { problems.add("manifest.json is larger than allowed"); break }
                        }
                    }
                    if (audio) seen[name] = n to hexOf(digest.digest())
                    if (keep != null && keep.size() <= CaptureConstants.MAX_MANIFEST_BYTES) manifestBytes = keep.toByteArray()
                }
            }
        } catch (e: java.io.IOException) {
            problems.add("the saved file can't be read back as a zip: ${e.message}")
        }

        var sessions = 0
        val mb = manifestBytes
        if (mb == null) {
            problems.add("manifest.json is missing")
        } else {
            try {
                val m = Json.parseToJsonElement(String(mb, Charsets.UTF_8)).jsonObject
                if (m["schema"]?.jsonPrimitive?.content != "ack-training-capture/1") problems.add("manifest.json does not say it is an ACK training capture")
                val listed = HashMap<String, JsonObject>()
                for (f in (m["files"] ?: JsonArray(emptyList())).jsonArray) {
                    val fo = f.jsonObject
                    val path = fo["path"]?.jsonPrimitive?.content ?: continue
                    listed[path] = fo
                }
                for ((path, fo) in listed) {
                    val got = seen[path]
                    if (got == null) { problems.add("$path is listed but not in the saved file"); continue }
                    if (fo["bytes"]?.jsonPrimitive?.longOrNull != got.first) problems.add("$path: the saved size differs from the list")
                    if (fo["sha256"]?.jsonPrimitive?.content != got.second) problems.add("$path: the saved audio does not match its checksum")
                }
                for (path in seen.keys) if (path !in listed) problems.add("$path is in the saved file but not listed")
                val arr = (m["sessions"] ?: JsonArray(emptyList())).jsonArray
                sessions = arr.size
                for (s in arr) {
                    val so = s.jsonObject
                    val refs = mutableListOf<String>()
                    so["clips"]?.jsonArray?.forEach { c -> c.jsonObject["file"]?.jsonPrimitive?.content?.let { refs.add(it) } }
                    so["recording"]?.jsonObject?.get("file")?.jsonPrimitive?.content?.let { refs.add(it) }
                    for (r in refs) if (r !in listed) problems.add("$r is used by a session but not listed")
                }
            } catch (e: Exception) {
                problems.add("manifest.json can't be read: ${e.message}")
            }
        }
        return VerifyResult(problems, sessions, seen.size, total)
    }

    private fun hexOf(bytes: ByteArray): String {
        val digits = "0123456789abcdef"
        val sb = StringBuilder(bytes.size * 2)
        for (b in bytes) { sb.append(digits[(b.toInt() shr 4) and 0xf]); sb.append(digits[b.toInt() and 0xf]) }
        return sb.toString()
    }
}
