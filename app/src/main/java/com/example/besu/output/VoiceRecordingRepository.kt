package com.example.besu.output

import android.content.Context
import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID

// What a recording is bound to. QUICK_ACTION keeps the original shape
// (deckId+groupIndex+slotIndex); the other two owners use whichever of
// the fields below actually apply to them, leaving the rest null.
@Serializable
enum class RecordingOwner {
    QUICK_ACTION, QUICK_ACCESS_KEY, MATRIX_NODE
}

@Serializable
data class VoiceRecording(
    val id: String,
    // Defaults to QUICK_ACTION so recordings saved before this field
    // existed -- which are all Quick Actions recordings -- still decode
    // correctly.
    val owner: RecordingOwner = RecordingOwner.QUICK_ACTION,
    val deckId: String? = null,
    val groupIndex: Int? = null,
    val slotIndex: Int? = null,
    // MATRIX_NODE only: deck+profile+path, matching exactly how the node's
    // own phrase text is scoped (CommandRepository.generateStorageKey) --
    // switching profile switches which recording plays, same as it already
    // switches which text is shown.
    val profile: String? = null,
    val path: String? = null,
    // MATRIX_NODE only: whether this recording currently plays. Editing a
    // node's template text after a recording is bound flips this to false
    // rather than deleting the recording -- see setMatrixRecordingEnabled.
    // Always true and unused for the other two owners.
    val enabled: Boolean = true,
    // MATRIX_NODE only: the exact template text this recording was bound
    // (or last re-enabled) against. A live mismatch against the node's
    // current text is what "stale" means for a disabled recording.
    val boundPhraseSnapshot: String? = null,
    val durationMs: Long,
    val createdAt: Long = System.currentTimeMillis()
)

// A recording plus its audio, base64-encoded -- the shape a backup carries
// (see AckBackup.voiceRecordings). Kept separate from VoiceRecording itself
// so the day-to-day metadata list (read by the MANAGE RECORDINGS popup, the
// deck's execute path, etc.) never has to hold every recording's audio
// bytes in memory just to know what exists.
@Serializable
data class VoiceRecordingBackupEntry(
    val recording: VoiceRecording,
    val sampleRate: Int,
    val audioBase64: String
)

// Stores voice recordings attached to Quick Actions prompts: small JSON
// metadata in this object's own SharedPreferences, with the actual audio
// as WAV files in internal storage -- kept out of SharedPreferences
// entirely since it's binary and can run to hundreds of KB even for a
// short clip.
object VoiceRecordingRepository {
    private const val PREFS_NAME = "ack_voice_recordings"
    private const val KEY_RECORDINGS = "recordings"
    private const val KEY_PLAYBACK_GAIN_PERCENT = "playback_gain_percent"
    const val DEFAULT_PLAYBACK_GAIN_PERCENT = 100
    const val MAX_PLAYBACK_GAIN_PERCENT = 300
    private const val KEY_SHOW_OVERLAY_ON_PREVIEW = "show_overlay_on_preview"
    private const val KEY_SEEN_HELP_OFFER = "seen_help_offer"
    private const val KEY_NORMALIZED_EXISTING_V1 = "normalized_existing_recordings_v1"

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    // A gain trim that applies only to voice recording playback -- PERSON/
    // PLACE recordings tend to sit quieter than synthesized speech at the
    // same system volume, and this lets the user compensate without
    // touching the general master gain everything else also uses. Stored
    // as a whole percent, always a multiple of 5 (the PROTOCOL slider only
    // ever writes multiples of 5, but this clamps defensively regardless
    // of what's on disk).
    fun getPlaybackGainPercent(context: Context): Int =
        prefs(context).getInt(KEY_PLAYBACK_GAIN_PERCENT, DEFAULT_PLAYBACK_GAIN_PERCENT)
            .coerceIn(0, MAX_PLAYBACK_GAIN_PERCENT)

    fun setPlaybackGainPercent(context: Context, percent: Int) {
        val snapped = (percent / 5) * 5
        prefs(context).edit()
            .putInt(KEY_PLAYBACK_GAIN_PERCENT, snapped.coerceIn(0, MAX_PLAYBACK_GAIN_PERCENT))
            .apply()
    }

    // MANAGE RECORDINGS' PLAY button -- off by default (matches the
    // original "no visual prompt" preview behavior), so a user who wants
    // a second, text-based way to confirm they've found the right
    // recording (especially one that's highly personalized and hard to
    // place by audio alone) can opt into seeing its stored text on the
    // overlay each time they tap PLAY there.
    fun getShowOverlayOnPreview(context: Context): Boolean =
        prefs(context).getBoolean(KEY_SHOW_OVERLAY_ON_PREVIEW, false)

    fun setShowOverlayOnPreview(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_SHOW_OVERLAY_ON_PREVIEW, enabled).apply()
    }

    // One-shot flag behind the small HELP tip shown either the first time
    // someone taps RECORD in a VoiceRecordingPanel, or the first time they
    // open MANAGE RECORDINGS -- whichever happens first. Shared across both
    // trigger points so dismissing it anywhere hides it everywhere.
    fun hasSeenHelpOffer(context: Context): Boolean =
        prefs(context).getBoolean(KEY_SEEN_HELP_OFFER, false)

    fun markHelpOfferSeen(context: Context) {
        prefs(context).edit().putBoolean(KEY_SEEN_HELP_OFFER, true).apply()
    }

    // One-time migration for recordings saved before AudioDsp.normalizeLoudness
    // existed -- they kept whatever raw level they happened to be captured
    // at, which is exactly the inconsistent-volume bug that function fixes
    // for new recordings. Re-processes every existing recording's stored
    // audio in place (same id, same metadata -- normalization never
    // changes sample count, so durationMs stays accurate) so old
    // recordings land on the same baseline new ones do. Safe to call
    // unconditionally on every app start: no-ops immediately after the
    // first successful run, via its own flag.
    suspend fun migrateNormalizeExistingRecordingsIfNeeded(context: Context) {
        if (prefs(context).getBoolean(KEY_NORMALIZED_EXISTING_V1, false)) return

        withContext(Dispatchers.IO) {
            getAll(context).forEach { recording ->
                val (pcm, sampleRate) = loadPcm(context, recording.id) ?: return@forEach
                val normalized = AudioDsp.normalizeLoudness(pcm)
                writeWav(audioFile(context, recording.id), normalized, sampleRate)
            }
        }

        prefs(context).edit().putBoolean(KEY_NORMALIZED_EXISTING_V1, true).apply()
    }

    private fun recordingsDir(context: Context): File {
        val dir = File(context.filesDir, "recordings")
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    private fun audioFile(context: Context, id: String): File =
        File(recordingsDir(context), "$id.wav")

    // File.length() already returns 0 for a missing file, matching how
    // loadPcm/loadPcmFromFile already treat "no file" as "nothing to load"
    // rather than an error -- callers don't need a null case here.
    fun getAudioFileSizeBytes(context: Context, id: String): Long =
        audioFile(context, id).length()

    fun getAll(context: Context): List<VoiceRecording> {
        val raw = prefs(context).getString(KEY_RECORDINGS, null) ?: return emptyList()
        return try {
            json.decodeFromString(raw)
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun findByOwnerKey(
        context: Context,
        owner: RecordingOwner,
        deckId: String? = null,
        groupIndex: Int? = null,
        slotIndex: Int? = null,
        profile: String? = null,
        path: String? = null
    ): VoiceRecording? = getAll(context).find {
        it.owner == owner && it.deckId == deckId && it.groupIndex == groupIndex &&
            it.slotIndex == slotIndex && it.profile == profile && it.path == path
    }

    fun getForQuickAction(context: Context, deckId: String, groupIndex: Int, slotIndex: Int): VoiceRecording? =
        findByOwnerKey(context, RecordingOwner.QUICK_ACTION, deckId = deckId, groupIndex = groupIndex, slotIndex = slotIndex)

    // Quick-Access keys are a flat, global, always-exactly-3 list (see
    // CommandRepository.HeaderShortcut) -- no deckId, just the fixed 0-2
    // index.
    fun getForQuickAccessKey(context: Context, slotIndex: Int): VoiceRecording? =
        findByOwnerKey(context, RecordingOwner.QUICK_ACCESS_KEY, slotIndex = slotIndex)

    // Matches CommandRepository.generateStorageKey's own deck+profile+path
    // scoping for a node's phrase text.
    fun getForMatrixNode(context: Context, deckId: String, profile: String, path: String): VoiceRecording? =
        findByOwnerKey(context, RecordingOwner.MATRIX_NODE, deckId = deckId, profile = profile, path = path)

    private fun saveAll(context: Context, recordings: List<VoiceRecording>) {
        prefs(context).edit().putString(KEY_RECORDINGS, json.encodeToString(recordings)).apply()
    }

    // Writes the WAV file and records its metadata, replacing (and
    // deleting the audio file for) any existing recording already bound to
    // this exact owner key -- an owner key only ever holds one recording
    // at a time.
    private fun saveInternal(
        context: Context,
        owner: RecordingOwner,
        deckId: String?,
        groupIndex: Int?,
        slotIndex: Int?,
        profile: String?,
        path: String?,
        pcm: ShortArray,
        sampleRate: Int,
        boundPhraseSnapshot: String?
    ): VoiceRecording {
        findByOwnerKey(context, owner, deckId, groupIndex, slotIndex, profile, path)?.let {
            delete(context, it.id)
        }

        val id = UUID.randomUUID().toString()
        writeWav(audioFile(context, id), pcm, sampleRate)

        val recording = VoiceRecording(
            id = id,
            owner = owner,
            deckId = deckId,
            groupIndex = groupIndex,
            slotIndex = slotIndex,
            profile = profile,
            path = path,
            enabled = true,
            boundPhraseSnapshot = boundPhraseSnapshot,
            durationMs = pcm.size.toLong() * 1000L / sampleRate
        )

        saveAll(context, getAll(context) + recording)
        return recording
    }

    fun saveForQuickAction(
        context: Context,
        deckId: String,
        groupIndex: Int,
        slotIndex: Int,
        pcm: ShortArray,
        sampleRate: Int
    ): VoiceRecording = saveInternal(
        context, RecordingOwner.QUICK_ACTION, deckId, groupIndex, slotIndex, null, null,
        pcm, sampleRate, boundPhraseSnapshot = null
    )

    fun saveForQuickAccessKey(
        context: Context,
        slotIndex: Int,
        pcm: ShortArray,
        sampleRate: Int
    ): VoiceRecording = saveInternal(
        context, RecordingOwner.QUICK_ACCESS_KEY, null, null, slotIndex, null, null,
        pcm, sampleRate, boundPhraseSnapshot = null
    )

    // phraseSnapshot is the node's exact template text at the moment this
    // recording was accepted -- setMatrixRecordingEnabled compares against
    // it later to tell whether the template has since changed underneath
    // an enabled recording.
    fun saveForMatrixNode(
        context: Context,
        deckId: String,
        profile: String,
        path: String,
        pcm: ShortArray,
        sampleRate: Int,
        phraseSnapshot: String
    ): VoiceRecording = saveInternal(
        context, RecordingOwner.MATRIX_NODE, deckId, null, null, profile, path,
        pcm, sampleRate, boundPhraseSnapshot = phraseSnapshot
    )

    fun deleteForQuickAction(context: Context, deckId: String, groupIndex: Int, slotIndex: Int) {
        getForQuickAction(context, deckId, groupIndex, slotIndex)?.let { delete(context, it.id) }
    }

    fun deleteForQuickAccessKey(context: Context, slotIndex: Int) {
        getForQuickAccessKey(context, slotIndex)?.let { delete(context, it.id) }
    }

    fun deleteForMatrixNode(context: Context, deckId: String, profile: String, path: String) {
        getForMatrixNode(context, deckId, profile, path)?.let { delete(context, it.id) }
    }

    fun delete(context: Context, id: String) {
        audioFile(context, id).delete()
        saveAll(context, getAll(context).filter { it.id != id })
    }

    // MATRIX_NODE only. Flips playback on/off without deleting the
    // recording -- used both when a template edit invalidates an enabled
    // recording (enabled=false, snapshot left as-is so staleness is still
    // detectable) and when the user deliberately re-enables one
    // (enabled=true, newSnapshot brings the bound text back in sync with
    // whatever the template says now, since there's no way to un-change
    // live-saved text).
    fun setMatrixRecordingEnabled(context: Context, id: String, enabled: Boolean, newSnapshot: String? = null) {
        val updated = getAll(context).map {
            if (it.id == id) {
                it.copy(enabled = enabled, boundPhraseSnapshot = newSnapshot ?: it.boundPhraseSnapshot)
            } else {
                it
            }
        }
        saveAll(context, updated)
    }

    // Returns the recording's PCM plus its own sample rate, or null if the
    // metadata exists but the file is somehow missing/corrupt -- callers
    // treat that as "no recording" and fall back to TTS rather than fail.
    fun loadPcm(context: Context, id: String): Pair<ShortArray, Int>? {
        val file = audioFile(context, id)
        if (!file.exists()) return null
        return try {
            readWav(file)
        } catch (_: Exception) {
            null
        }
    }

    // Same as loadPcm, but by an arbitrary file path rather than a saved
    // recording's id -- backs previewing a not-yet-accepted recording
    // (see writeTempPreviewFile), which has no id of its own yet.
    fun loadPcmFromFile(path: String): Pair<ShortArray, Int>? {
        val file = File(path)
        if (!file.exists()) return null
        return try {
            readWav(file)
        } catch (_: Exception) {
            null
        }
    }

    // Writes an in-progress (not yet accepted) recording to a scratch file
    // in the cache dir so OutputService's PREVIEW_RECORDING action can play
    // it the same way it plays an already-saved one -- overwritten on each
    // call, since only one preview is ever in flight within a single EDIT
    // QUICK ACTION session.
    fun writeTempPreviewFile(context: Context, pcm: ShortArray, sampleRate: Int): File {
        val file = File(context.cacheDir, "voice_preview_temp.wav")
        writeWav(file, pcm, sampleRate)
        return file
    }

    // --- BACKUP ---

    fun exportForBackup(context: Context): List<VoiceRecordingBackupEntry> {
        return getAll(context).mapNotNull { recording ->
            val file = audioFile(context, recording.id)
            if (!file.exists()) return@mapNotNull null

            val (pcm, sampleRate) = try {
                readWav(file)
            } catch (_: Exception) {
                return@mapNotNull null
            }

            VoiceRecordingBackupEntry(
                recording = recording,
                sampleRate = sampleRate,
                audioBase64 = Base64.encodeToString(pcmToBytes(pcm), Base64.NO_WRAP)
            )
        }
    }

    // Restore-only: mirrors the backup exactly, same convention as
    // ComputerRepository.replaceCategories -- wipes whatever's already
    // stored (metadata and audio files alike) and replaces it wholesale.
    fun replaceFromBackup(context: Context, entries: List<VoiceRecordingBackupEntry>) {
        recordingsDir(context).listFiles()?.forEach { it.delete() }

        val restored = entries.mapNotNull { entry ->
            try {
                val pcm = bytesToPcm(Base64.decode(entry.audioBase64, Base64.NO_WRAP))
                writeWav(audioFile(context, entry.recording.id), pcm, entry.sampleRate)
                entry.recording
            } catch (_: Exception) {
                null
            }
        }

        saveAll(context, restored)
    }

    // --- WAV (standard 44-byte PCM header, mono 16-bit -- the same layout
    // OutputService's own TTS-synthesized WAV files already use) ---

    private fun writeWav(file: File, pcm: ShortArray, sampleRate: Int) {
        val pcmBytes = pcmToBytes(pcm)
        val byteRate = sampleRate * 2

        val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN).apply {
            put("RIFF".toByteArray())
            putInt(36 + pcmBytes.size)
            put("WAVE".toByteArray())
            put("fmt ".toByteArray())
            putInt(16)
            putShort(1) // PCM
            putShort(1) // mono
            putInt(sampleRate)
            putInt(byteRate)
            putShort(2) // block align
            putShort(16) // bits per sample
            put("data".toByteArray())
            putInt(pcmBytes.size)
        }.array()

        file.outputStream().use { out ->
            out.write(header)
            out.write(pcmBytes)
        }
    }

    private fun readWav(file: File): Pair<ShortArray, Int> {
        val bytes = file.readBytes()
        val sampleRate = ByteBuffer.wrap(bytes, 24, 4).order(ByteOrder.LITTLE_ENDIAN).int
        val pcm = bytesToPcm(bytes.copyOfRange(44, bytes.size))
        return pcm to sampleRate
    }

    private fun pcmToBytes(pcm: ShortArray): ByteArray {
        val buffer = ByteBuffer.allocate(pcm.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (sample in pcm) buffer.putShort(sample)
        return buffer.array()
    }

    private fun bytesToPcm(bytes: ByteArray): ShortArray {
        val shortBuffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        val pcm = ShortArray(shortBuffer.remaining())
        shortBuffer.get(pcm)
        return pcm
    }

    fun formatDurationMs(ms: Long): String {
        val totalSeconds = ms / 1000
        val minutes = totalSeconds / 60
        val seconds = totalSeconds % 60
        return "%d:%02d".format(minutes, seconds)
    }

    fun formatFileSize(bytes: Long): String {
        if (bytes < 1024) return "$bytes B"
        val kb = bytes / 1024.0
        if (kb < 1024) return "%.1f KB".format(kb)
        return "%.1f MB".format(kb / 1024.0)
    }

}
