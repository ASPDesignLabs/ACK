// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.output
import android.content.Context
import android.net.Uri

// Stubs of the voice stores and the visual preset store the AUDIO ARCHITECT screen calls (they read and write files and preferences), written from their real signatures.
data class VisualPreset(val id: String = "", val name: String = "NEW PRESET", val bypassTruncation: Boolean = false)
object VisualPresetRepository {
    fun getActivePreset(context: Context): VisualPreset = VisualPreset()
    fun savePreset(context: Context, preset: VisualPreset) {}
    fun setActivePreset(context: Context, id: String) {}
}
object CustomVoiceRepository {
    fun hasCustomVoice(context: Context): Boolean = false
    fun importVoice(context: Context, uris: List<Uri>): Boolean = false
    fun deleteVoice(context: Context): Boolean = false
}
object CustomVoiceBackupManager {
    fun exportVoice(context: Context, destinationUri: Uri): Boolean = false
    fun importBackup(context: Context, sourceUri: Uri): Boolean = false
}
