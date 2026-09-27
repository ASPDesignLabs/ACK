package com.example.besu.output

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import android.util.Log
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.io.File

// Stores the single custom Piper-trained voice a user has imported: the
// .onnx model and its .onnx.json config, copied into internal storage.
// Deliberately holds at most one voice -- no list, no ids, just two fixed
// files. "Installed" is judged by both files existing on disk rather than a
// separate flag, so metadata and files can never disagree.
object CustomVoiceRepository {
    private const val LOG_TAG = "ACK_CUSTOM_VOICE"

    // Firewalls against a corrupted/wrong file, not practical limits -- a
    // real medium/high quality Piper .onnx runs well under this, and a real
    // config.json is only ever a few KB.
    private const val MAX_MODEL_SIZE_BYTES = 300L * 1024L * 1024L
    private const val MAX_CONFIG_SIZE_BYTES = 1L * 1024L * 1024L

    private fun voiceDir(context: Context): File {
        val dir = File(context.filesDir, "custom_voice")
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    fun modelFile(context: Context): File = File(voiceDir(context), "model.onnx")
    fun configFile(context: Context): File = File(voiceDir(context), "model.onnx.json")

    fun hasCustomVoice(context: Context): Boolean =
        modelFile(context).exists() && configFile(context).exists()

    private fun displayName(context: Context, uri: Uri): String {
        context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            val idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (idx >= 0 && cursor.moveToFirst()) return cursor.getString(idx) ?: ""
        }
        return ""
    }

    // Copies from arbitrary content Uris (in whatever order the picker
    // returns them) into validated temp files first, and only replaces the
    // installed voice once both check out -- an existing working voice is
    // never left partially overwritten by a bad import.
    fun importVoice(context: Context, uris: List<Uri>): Boolean {
        if (uris.size != 2) {
            Log.e(LOG_TAG, "Import failed: expected exactly 2 files, got ${uris.size}")
            return false
        }

        val onnxUri = uris.find { displayName(context, it).endsWith(".onnx", ignoreCase = true) }
        val jsonUri = uris.find { displayName(context, it).endsWith(".onnx.json", ignoreCase = true) }

        if (onnxUri == null || jsonUri == null) {
            Log.e(LOG_TAG, "Import failed: could not identify a .onnx and a .onnx.json among the selected files")
            return false
        }

        val tempModel = File.createTempFile("voice_import_", ".onnx", context.cacheDir)
        val tempConfig = File.createTempFile("voice_import_", ".json", context.cacheDir)

        try {
            val modelBytes = copyUriToFile(context, onnxUri, tempModel)
            val configBytes = copyUriToFile(context, jsonUri, tempConfig)

            if (modelBytes == null || configBytes == null) {
                Log.e(LOG_TAG, "Import failed: could not read one or both selected files")
                return false
            }
            if (modelBytes <= 0L || modelBytes > MAX_MODEL_SIZE_BYTES) {
                Log.e(LOG_TAG, "Import failed: model size $modelBytes bytes out of bounds")
                return false
            }
            if (configBytes <= 0L || configBytes > MAX_CONFIG_SIZE_BYTES) {
                Log.e(LOG_TAG, "Import failed: config size $configBytes bytes out of bounds")
                return false
            }

            return installFromValidatedFiles(context, tempModel, tempConfig)
        } catch (e: Exception) {
            Log.e(LOG_TAG, "Import failed", e)
            return false
        } finally {
            tempModel.delete()
            tempConfig.delete()
        }
    }

    // Defense-in-depth, same reasoning as GifRepository.restoreEntry: this
    // re-validates regardless of what the caller already checked, since it's
    // also the shared landing point for CustomVoiceBackupManager's restore
    // path (which extracts from a zip rather than a content Uri).
    fun installFromValidatedFiles(context: Context, modelSource: File, configSource: File): Boolean {
        if (!looksLikePiperConfig(configSource)) {
            Log.e(LOG_TAG, "Install failed: config does not look like a Piper voice config")
            return false
        }
        if (modelSource.length() <= 0L || modelSource.length() > MAX_MODEL_SIZE_BYTES) {
            Log.e(LOG_TAG, "Install failed: model size ${modelSource.length()} bytes out of bounds")
            return false
        }

        return try {
            modelSource.copyTo(modelFile(context), overwrite = true)
            configSource.copyTo(configFile(context), overwrite = true)
            true
        } catch (e: Exception) {
            Log.e(LOG_TAG, "Install failed", e)
            false
        }
    }

    fun deleteVoice(context: Context) {
        modelFile(context).delete()
        configFile(context).delete()
    }

    // Every real Piper voice config carries these two keys -- cheap,
    // meaningful protection against pointing the picker at some unrelated
    // JSON file rather than the actual exported voice config.
    private fun looksLikePiperConfig(file: File): Boolean {
        return try {
            val obj = Json.parseToJsonElement(file.readText()).jsonObject
            obj.containsKey("phoneme_id_map") && obj.containsKey("audio")
        } catch (_: Exception) {
            false
        }
    }

    private fun copyUriToFile(context: Context, uri: Uri, dest: File): Long? {
        return context.contentResolver.openInputStream(uri)?.use { input ->
            dest.outputStream().use { output -> input.copyTo(output) }
        }
    }
}
