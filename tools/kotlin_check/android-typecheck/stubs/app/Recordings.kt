// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.output
import android.content.Context
import java.io.File

// Stubs of the recorder and the recordings store the recordings screens call (they use the microphone and files), written from their real signatures.
enum class RecordingOwner { QUICK_ACTION, QUICK_ACCESS_KEY, MATRIX_NODE }

data class VoiceRecording(
    val id: String,
    val owner: RecordingOwner = RecordingOwner.QUICK_ACTION,
    val deckId: String? = null,
    val groupIndex: Int? = null,
    val slotIndex: Int? = null,
    val profile: String? = null,
    val path: String? = null,
    val enabled: Boolean = true,
    val durationMs: Long = 0L
)

class VoiceRecorder {
    companion object { const val SAMPLE_RATE = 16000 }
    val isRecording: Boolean get() = false
    fun start(context: Context): Boolean = false
    fun currentDurationMs(): Long = 0L
    fun stop(): ShortArray = ShortArray(0)
    fun discard() {}
}

object VoiceRecordingRepository {
    fun getShowOverlayOnPreview(context: Context): Boolean = false
    fun setShowOverlayOnPreview(context: Context, enabled: Boolean) {}
    fun hasSeenHelpOffer(context: Context): Boolean = false
    fun markHelpOfferSeen(context: Context) {}
    fun getAudioFileSizeBytes(context: Context, id: String): Long = 0L
    fun getAll(context: Context): List<VoiceRecording> = emptyList()
    fun saveForQuickAction(context: Context, deckId: String, groupIndex: Int, slotIndex: Int, pcm: ShortArray, sampleRate: Int): VoiceRecording = VoiceRecording("")
    fun saveForQuickAccessKey(context: Context, slotIndex: Int, pcm: ShortArray, sampleRate: Int): VoiceRecording = VoiceRecording("")
    fun saveForMatrixNode(context: Context, deckId: String, profile: String, path: String, pcm: ShortArray, sampleRate: Int, phraseSnapshot: String): VoiceRecording = VoiceRecording("")
    fun delete(context: Context, id: String) {}
    fun writeTempPreviewFile(context: Context, pcm: ShortArray, sampleRate: Int): File = File("")
    fun formatDurationMs(ms: Long): String = ""
    fun formatFileSize(bytes: Long): String = ""
}
