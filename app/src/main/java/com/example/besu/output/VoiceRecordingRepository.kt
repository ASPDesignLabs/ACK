package com.example.besu.output

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID

@Serializable
data class VoiceRecording(
    val id: String,
    val deckId: String,
    val groupIndex: Int,
    val slotIndex: Int,
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

    private fun recordingsDir(context: Context): File {
        val dir = File(context.filesDir, "recordings")
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    private fun audioFile(context: Context, id: String): File =
        File(recordingsDir(context), "$id.wav")

    fun getAll(context: Context): List<VoiceRecording> {
        val raw = prefs(context).getString(KEY_RECORDINGS, null) ?: return emptyList()
        return try {
            json.decodeFromString(raw)
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun getForSlot(context: Context, deckId: String, groupIndex: Int, slotIndex: Int): VoiceRecording? =
        getAll(context).find {
            it.deckId == deckId && it.groupIndex == groupIndex && it.slotIndex == slotIndex
        }

    private fun saveAll(context: Context, recordings: List<VoiceRecording>) {
        prefs(context).edit().putString(KEY_RECORDINGS, json.encodeToString(recordings)).apply()
    }

    // Writes the WAV file and records its metadata, replacing (and
    // deleting the audio file for) any existing recording already bound to
    // this exact slot -- a slot only ever holds one recording at a time.
    fun save(
        context: Context,
        deckId: String,
        groupIndex: Int,
        slotIndex: Int,
        pcm: ShortArray,
        sampleRate: Int
    ): VoiceRecording {
        deleteForSlot(context, deckId, groupIndex, slotIndex)

        val id = UUID.randomUUID().toString()
        writeWav(audioFile(context, id), pcm, sampleRate)

        val recording = VoiceRecording(
            id = id,
            deckId = deckId,
            groupIndex = groupIndex,
            slotIndex = slotIndex,
            durationMs = pcm.size.toLong() * 1000L / sampleRate
        )

        saveAll(context, getAll(context) + recording)
        return recording
    }

    fun deleteForSlot(context: Context, deckId: String, groupIndex: Int, slotIndex: Int) {
        val existing = getForSlot(context, deckId, groupIndex, slotIndex) ?: return
        delete(context, existing.id)
    }

    fun delete(context: Context, id: String) {
        audioFile(context, id).delete()
        saveAll(context, getAll(context).filter { it.id != id })
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

    // A minimal, un-routed AudioTrack player -- shared by the record/
    // preview flow in QuickActionEditorDialog and the MANAGE RECORDINGS
    // popup under PROTOCOL. Deliberately doesn't go through OutputService's
    // force-speaker/kill-switch/logging pipeline, since previewing isn't a
    // communication event; the real, routed playback only happens once a
    // recording is actually issued as a prompt (see OutputService.playRecording).
    // Applies the same playback gain a real dispatch would (see
    // OutputService.playRecording) so what you preview -- whether that's
    // mid-recording in QuickActionEditorDialog or replaying an existing
    // one from MANAGE RECORDINGS -- actually matches what you'll hear when
    // the prompt is issued for real.
    suspend fun playPreview(context: Context, pcm: ShortArray, sampleRate: Int) {
        val gained = applyGain(pcm, getPlaybackGainPercent(context) / 100f)

        withContext(Dispatchers.IO) {
            val track = AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(sampleRate)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build()
                )
                .setBufferSizeInBytes(gained.size * 2)
                .build()

            try {
                track.play()
                track.write(gained, 0, gained.size)
                while (
                    track.playState == AudioTrack.PLAYSTATE_PLAYING &&
                    track.playbackHeadPosition < gained.size
                ) {
                    delay(10)
                }
            } finally {
                track.stop()
                track.release()
            }
        }
    }

    private fun applyGain(pcm: ShortArray, gain: Float): ShortArray {
        if (gain == 1f) return pcm
        return ShortArray(pcm.size) { i ->
            (pcm[i] * gain).toInt()
                .coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
                .toShort()
        }
    }
}
