// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.Locale
import java.util.UUID
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

/** Something on disk can't be used. The message says what and where, in words a person can act on; nothing was changed. */
class StoreException(message: String) : Exception(message)

/** What a listing found: the items it could read, and the names of the ones it could not (their files are left exactly as they are). */
data class Listing<T>(val items: List<T>, val damaged: List<String>)

data class RecoveryReport(val sessionsClosed: Int, val clipsRecovered: Int, val clipsEmpty: Int, val problems: List<String>)

// Everything the phone keeps for training-data capture, under one folder:
//
//   scripts/<id>.json                       a text the person will read
//   sessions/<session id>/session.json      the notes for one recording session, rewritten after every change
//   sessions/<session id>/clips/0001.wav    script mode: one recording per card
//   sessions/<session id>/session.wav       free mode: the whole recording
//
// The notes are written to a temporary file, flushed to disk, then moved over the old notes in one step, so a crash or a full disk
// leaves either the old notes or the new ones, never half of each. A clip is written into the notes as OPEN *before* the first
// sample is recorded, so audio on disk always has a line in the notes, and recovery after a crash can repair it rather than lose it.
// Nothing here deletes audio unless the caller asks to delete that session (or an unwanted clip), and each of those is a separate call.
class TrainingStore(private val root: File) {
    companion object {
        val SCRIPT_ID = Regex("^[A-Za-z0-9_-]{1,40}$")
        const val MAX_SCRIPT_CHARS = 300_000
        const val MAX_TITLE_CHARS = 120
        private val LINES = setOf("join", "keep")
        private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true; prettyPrint = true }
    }

    private val scriptsDir get() = File(root, "scripts")
    private val sessionsDir get() = File(root, "sessions")

    // -- files ------------------------------------------------------------------------------------------------------------
    private fun requireSessionId(id: String) {
        if (!PackageNames.SESSION_ID.matches(id)) throw StoreException("\"${id.take(40)}\" is not a session id")
    }

    private fun requireScriptId(id: String) {
        if (!SCRIPT_ID.matches(id)) throw StoreException("\"${id.take(40)}\" is not a script id")
    }

    fun sessionDir(id: String): File { requireSessionId(id); return File(sessionsDir, id) }
    fun clipFile(sessionId: String, index: Int): File = File(sessionDir(sessionId), String.format(Locale.ROOT, "clips/%04d.wav", index))
    fun recordingFile(sessionId: String): File = File(sessionDir(sessionId), "session.wav")
    private fun notesFile(id: String) = File(sessionDir(id), "session.json")
    private fun scriptFile(id: String): File { requireScriptId(id); return File(scriptsDir, "$id.json") }

    private fun writeAtomically(target: File, text: String) {
        val dir = target.parentFile ?: throw StoreException("no folder for ${target.name}")
        if (!dir.isDirectory && !dir.mkdirs()) throw StoreException("can't create the folder ${dir.name}")
        val tmp = File(dir, target.name + ".tmp")
        FileOutputStream(tmp).use { it.write(text.toByteArray(Charsets.UTF_8)); it.fd.sync() }
        Files.move(tmp.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE)
    }

    // -- scripts ----------------------------------------------------------------------------------------------------------
    /** A new, empty-of-history script with a fresh id. Not saved until [saveScript]. */
    fun newScript(title: String, text: String, lines: String = "join", language: String = "en-US", nowMillis: Long): TrainingScript =
        TrainingScript("scr-" + UUID.randomUUID().toString().replace("-", "").take(12), title, text, lines, language, nowMillis, nowMillis)

    @Synchronized
    fun saveScript(script: TrainingScript, nowMillis: Long): TrainingScript {
        requireScriptId(script.id)
        if (script.text.length > MAX_SCRIPT_CHARS) throw StoreException("This text is too long (${script.text.length} characters; the limit is $MAX_SCRIPT_CHARS). Split it into two scripts.")
        if (script.lines !in LINES) throw StoreException("lines must be join or keep")
        val title = PackageWriter.clean(script.title, MAX_TITLE_CHARS).ifEmpty { "UNTITLED" }
        val saved = script.copy(title = title, createdAt = if (script.createdAt == 0L) nowMillis else script.createdAt, updatedAt = nowMillis)
        writeAtomically(scriptFile(script.id), json.encodeToString(saved))
        return saved
    }

    @Synchronized
    fun getScript(id: String): TrainingScript? {
        val f = scriptFile(id)
        if (!f.isFile) return null
        return try { json.decodeFromString<TrainingScript>(f.readText(Charsets.UTF_8)) }
        catch (e: Exception) { throw StoreException("The script file $id can't be read (${e.message?.take(80)}). It was left as it is.") }
    }

    @Synchronized
    fun listScripts(): Listing<TrainingScript> {
        val items = mutableListOf<TrainingScript>()
        val damaged = mutableListOf<String>()
        for (f in scriptsDir.listFiles { x -> x.isFile && x.name.endsWith(".json") }.orEmpty()) {
            try { items.add(json.decodeFromString(f.readText(Charsets.UTF_8))) } catch (e: Exception) { damaged.add(f.name) }
        }
        return Listing(items.sortedWith(compareByDescending<TrainingScript> { it.updatedAt }.thenBy { it.id }), damaged.sorted())
    }

    /** Removes the script's text. Recordings made from it are not touched. */
    @Synchronized
    fun deleteScript(id: String): Boolean = scriptFile(id).delete()

    // -- sessions: notes --------------------------------------------------------------------------------------------------
    private fun readNotes(id: String): StoredSession? {
        val f = notesFile(id)
        if (!f.isFile) return null
        return try { json.decodeFromString<StoredSession>(f.readText(Charsets.UTF_8)) }
        catch (e: Exception) { throw StoreException("The notes for session $id can't be read (${e.message?.take(80)}). Its recordings are still in the folder.") }
    }

    private fun writeNotes(s: StoredSession) = writeAtomically(notesFile(s.id), json.encodeToString(s))

    /** A session id not used by any session on the phone. */
    @Synchronized
    fun newSessionId(nowMillis: Long): String {
        while (true) {
            val id = CaptureTime.sessionId(nowMillis, UUID.randomUUID().hashCode())
            if (!sessionDir(id).exists()) return id
        }
    }

    @Synchronized
    fun createSession(session: StoredSession): StoredSession {
        requireSessionId(session.id)
        if (sessionDir(session.id).exists()) throw StoreException("session ${session.id} already exists")
        if (session.mode != "script" && session.mode != "free") throw StoreException("a session is either script or free")
        sessionDir(session.id).mkdirs()
        writeNotes(session)
        return session
    }

    @Synchronized
    fun getSession(id: String): StoredSession? = readNotes(id)

    @Synchronized
    fun listSessions(): Listing<StoredSession> {
        val items = mutableListOf<StoredSession>()
        val damaged = mutableListOf<String>()
        for (d in sessionsDir.listFiles { x -> x.isDirectory && PackageNames.SESSION_ID.matches(x.name) }.orEmpty()) {
            try { readNotes(d.name)?.let { items.add(it) } } catch (e: StoreException) { damaged.add(d.name) }
        }
        return Listing(items.sortedWith(compareByDescending<StoredSession> { it.started }.thenByDescending { it.id }), damaged.sorted())
    }

    @Synchronized
    fun update(id: String, change: (StoredSession) -> StoredSession): StoredSession {
        val current = readNotes(id) ?: throw StoreException("session $id is not on this phone")
        val next = change(current)
        if (next.id != id) throw StoreException("a session's id can't change")
        writeNotes(next)
        return next
    }

    // -- sessions: script clips -------------------------------------------------------------------------------------------
    /** Which attempt the next recording of [card] is (1 the first time, 2 after one redo, ...). */
    fun nextAttempt(s: StoredSession, card: Int): Int = (s.clips.filter { it.card == card }.maxOfOrNull { it.attempt } ?: 0) + 1

    /**
     * Writes the clip into the notes as OPEN, then returns where its audio goes. Call before the first sample is recorded.
     */
    @Synchronized
    fun beginClip(sessionId: String, card: Int, text: String, recordedUtc: String): Pair<StoredClip, File> {
        var made: StoredClip? = null
        update(sessionId) { s ->
            val clip = StoredClip(index = (s.clips.maxOfOrNull { it.index } ?: 0) + 1, card = card, attempt = nextAttempt(s, card), text = text, recorded = recordedUtc)
            made = clip
            s.copy(clips = s.clips + clip)
        }
        val clip = made!!
        clipFile(sessionId, clip.index).parentFile.mkdirs()
        return clip to clipFile(sessionId, clip.index)
    }

    /** The clip's audio is closed and complete: record its length and loudness, and keep it. */
    @Synchronized
    fun finishClip(sessionId: String, index: Int, durationS: Double, metrics: ClipMetrics, endedByLimit: Boolean): StoredClip {
        var done: StoredClip? = null
        update(sessionId) { s ->
            s.copy(clips = s.clips.map { c ->
                if (c.index != index) c else c.copy(
                    state = ClipState.DONE, durationS = LevelMath.rnd(durationS, 3), speechStartS = metrics.speech?.startS, speechEndS = metrics.speech?.endS,
                    peakDbfs = metrics.peakDbfs, rmsDbfs = metrics.rmsDbfs, clippedSamples = metrics.clippedSamples,
                    flags = c.flags.filter { it in ClipFlags.PERSON } + ClipFlags.automatic(durationS, endedByLimit),
                ).also { done = it }
            })
        }
        return done ?: throw StoreException("clip $index is not in session $sessionId")
    }

    private fun changeClip(sessionId: String, index: Int, change: (StoredClip) -> StoredClip) {
        var found = false
        update(sessionId) { s -> s.copy(clips = s.clips.map { c -> if (c.index == index) { found = true; change(c) } else c }) }
        if (!found) throw StoreException("clip $index is not in session $sessionId")
    }

    /** The person redid the card: this attempt stays on disk but is not packaged. */
    @Synchronized
    fun markRedone(sessionId: String, index: Int) = changeClip(sessionId, index) { it.copy(state = ClipState.REDONE) }

    /** A repaired clip the person listened to and wants to keep. */
    @Synchronized
    fun keepRecovered(sessionId: String, index: Int) = changeClip(sessionId, index) { if (it.state == ClipState.RECOVERED) it.copy(state = ClipState.DONE) else it }

    /** A repaired clip the person does not want packaged. The audio stays on disk until the session is deleted. */
    @Synchronized
    fun setRecoveredAside(sessionId: String, index: Int) = changeClip(sessionId, index) { if (it.state == ClipState.RECOVERED) it.copy(state = ClipState.REDONE) else it }

    /** Sets the marks the person chose on a clip. The phone's own notes (long, short, no_end) are kept as they are. */
    @Synchronized
    fun setPersonFlags(sessionId: String, index: Int, chosen: Set<String>) = changeClip(sessionId, index) { c ->
        c.copy(flags = c.flags.filter { it !in ClipFlags.PERSON } + ClipFlags.PERSON.filter { it in chosen })
    }

    /** Removes an unwanted clip's audio and notes. Refused for a kept clip: redo it, or delete the session. */
    @Synchronized
    fun deleteClip(sessionId: String, index: Int) {
        val s = readNotes(sessionId) ?: throw StoreException("session $sessionId is not on this phone")
        val c = s.clips.firstOrNull { it.index == index } ?: throw StoreException("clip $index is not in session $sessionId")
        if (c.state == ClipState.DONE) throw StoreException("A kept clip is not deleted on its own. Redo the card, or delete the whole session.")
        clipFile(sessionId, index).delete()
        writeNotes(s.copy(clips = s.clips.filter { it.index != index }))
    }

    // -- sessions: free recording -----------------------------------------------------------------------------------------
    /** Marks the recording as started and returns where its audio goes. */
    @Synchronized
    fun beginFreeRecording(sessionId: String): File {
        update(sessionId) { s ->
            if (s.mode != "free") throw StoreException("this is not a free-speech session")
            s.copy(recording = StoredRecording(state = ClipState.OPEN))
        }
        return recordingFile(sessionId)
    }

    @Synchronized
    fun finishFreeRecording(sessionId: String, recording: StoredRecording) {
        update(sessionId) { s -> s.copy(recording = recording.copy(state = ClipState.DONE)) }
    }

    // -- sessions: ending, deleting, counting -----------------------------------------------------------------------------
    @Synchronized
    fun closeSession(sessionId: String, endedUtc: String): StoredSession = update(sessionId) { it.copy(closed = true, ended = endedUtc) }

    /** Deletes a session and every recording in it. The caller must have asked the person twice. */
    @Synchronized
    fun deleteSession(id: String): Boolean {
        val dir = sessionDir(id)
        if (!dir.isDirectory) return false
        return dir.deleteRecursively()
    }

    fun sessionBytes(id: String): Long = sessionDir(id).walkTopDown().filter { it.isFile }.sumOf { it.length() }

    /** The words of every card that already has a kept clip in a session of this script, so a new session can carry on where the last stopped. */
    @Synchronized
    fun doneCardTexts(scriptId: String): Set<String> =
        listSessions().items.filter { it.scriptId == scriptId }.flatMap { it.clips }.filter { it.state == ClipState.DONE }.map { it.text }.toSet()

    // -- after the app closed unexpectedly --------------------------------------------------------------------------------
    /**
     * Finds sessions that were never ended, repairs the audio of the clip that was being recorded, and closes them. A repaired clip
     * is marked RECOVERED: it is not packaged until the person listens and keeps it. No audio is deleted, except a file with no
     * audio in it at all.
     */
    @Synchronized
    fun recoverOpenSessions(nowUtc: String): RecoveryReport {
        var closed = 0
        var recovered = 0
        var empty = 0
        val problems = mutableListOf<String>()
        for (d in sessionsDir.listFiles { x -> x.isDirectory && PackageNames.SESSION_ID.matches(x.name) }.orEmpty()) {
            val s = try { readNotes(d.name) } catch (e: StoreException) { problems.add(e.message ?: d.name); continue } ?: continue
            if (s.closed) continue
            val clips = mutableListOf<StoredClip>()
            for (c in s.clips) {
                if (c.state != ClipState.OPEN) { clips.add(c); continue }
                val f = clipFile(s.id, c.index)
                if (!f.isFile) { empty++; continue }
                try {
                    val info = WavFile.repair(f)
                    if (info.frames == 0L) { f.delete(); empty++; continue }
                    val (m, dur) = AudioScan.scanClip(f, s.thresholdDbfs)
                    clips.add(c.copy(
                        state = ClipState.RECOVERED, durationS = dur, speechStartS = m.speech?.startS, speechEndS = m.speech?.endS,
                        peakDbfs = m.peakDbfs, rmsDbfs = m.rmsDbfs, clippedSamples = m.clippedSamples, flags = ClipFlags.automatic(dur, false),
                    ))
                    recovered++
                } catch (e: WavException) {
                    problems.add("${f.name} in session ${s.id}: ${e.message}")
                    clips.add(c.copy(state = ClipState.REDONE, flags = listOf("unreadable")))
                }
            }
            var recording = s.recording
            if (recording != null && recording.state == ClipState.OPEN) {
                val f = recordingFile(s.id)
                recording = try {
                    if (!f.isFile) null else {
                        val info = WavFile.repair(f)
                        if (info.frames == 0L) { f.delete(); empty++; null }
                        else { recovered++; AudioScan.scanRecording(f, s.thresholdDbfs).copy(state = ClipState.RECOVERED) }
                    }
                } catch (e: WavException) {
                    problems.add("session.wav in session ${s.id}: ${e.message}")
                    null
                }
            }
            writeNotes(s.copy(clips = clips, recording = recording, closed = true, ended = s.ended ?: clips.lastOrNull()?.recorded ?: nowUtc))
            closed++
        }
        return RecoveryReport(closed, recovered, empty, problems)
    }

    /** A repaired free-speech recording the person listened to and wants to keep. */
    @Synchronized
    fun keepRecoveredRecording(sessionId: String) {
        update(sessionId) { s -> s.copy(recording = s.recording?.let { if (it.state == ClipState.RECOVERED) it.copy(state = ClipState.DONE) else it }) }
    }

    // -- handing a session to the package writer --------------------------------------------------------------------------
    /** The session as the package writer wants it, with only the kept clips; null when it has nothing to hand over. */
    @Synchronized
    fun toCaptureSession(s: StoredSession): CaptureSession? {
        val audio = AudioSettings(s.sampleRate, s.source, s.sourceRequested)
        val device = if (s.deviceModel != null && s.deviceSdk != null) DeviceNote(s.deviceModel, s.deviceSdk) else null
        val ended = s.ended ?: s.started
        return when (s.mode) {
            "script" -> {
                val kept = s.clips.filter { it.state == ClipState.DONE }
                if (kept.isEmpty()) return null
                ScriptSession(
                    id = s.id, label = s.label, started = s.started, ended = ended, language = s.language, audio = audio,
                    noiseFloorDbfs = s.noiseFloorDbfs, thresholdDbfs = s.thresholdDbfs, device = device,
                    script = ScriptNote(s.scriptId ?: "script", s.scriptTitle ?: "", maxOf(s.cardsTotal, 1)),
                    clips = kept.map { c ->
                        ScriptClip(
                            index = c.index, card = c.card, attempt = c.attempt, text = c.text, recorded = c.recorded, durationS = c.durationS,
                            speech = if (c.speechStartS != null && c.speechEndS != null) SpeechSpan(c.speechStartS, c.speechEndS) else null,
                            metrics = CaptureMetrics(c.peakDbfs, c.rmsDbfs, c.clippedSamples), flags = c.flags, wav = clipFile(s.id, c.index),
                        )
                    },
                )
            }
            "free" -> {
                val r = s.recording ?: return null
                if (r.state != ClipState.DONE || r.durationS <= 0.0) return null
                FreeSession(
                    id = s.id, label = s.label, started = s.started, ended = ended, language = s.language, audio = audio,
                    noiseFloorDbfs = s.noiseFloorDbfs, thresholdDbfs = s.thresholdDbfs, device = device, topic = s.topic,
                    wav = recordingFile(s.id), durationS = r.durationS, metrics = CaptureMetrics(r.peakDbfs, r.rmsDbfs, r.clippedSamples),
                    proposed = r.pieces.map { ProposedPiece(it.startS, it.endS, it.endKind, CaptureMetrics(it.peakDbfs, it.rmsDbfs, it.clippedSamples)) },
                )
            }
            else -> null
        }
    }
}
