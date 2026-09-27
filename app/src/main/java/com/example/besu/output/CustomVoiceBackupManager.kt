package com.example.besu.output

import android.content.Context
import android.net.Uri
import android.util.Log
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

// A standalone .zip export/import for the one imported custom voice --
// same reasoning as GifBackupManager: a trained voice model is a real
// binary (tens of MB), which has no business inside TransferManager's JSON
// blob. No manifest needed (there's only ever one voice, two fixed files),
// so this is much smaller than the GIF path, but follows the same shape:
// temp-file-in-cacheDir, validate, then hand off to the repository's own
// install function, which re-validates independently. Deliberately
// separate from TransferManager's EXPORT .JSON / FULL RESTORE FROM JSON,
// which don't know a custom voice exists at all.
object CustomVoiceBackupManager {
    private const val LOG_TAG = "ACK_VOICE_BACKUP"
    private const val MODEL_ENTRY_NAME = "model.onnx"
    private const val CONFIG_ENTRY_NAME = "model.onnx.json"

    // Firewall against a corrupted/hostile archive, not a practical
    // constraint -- CustomVoiceRepository's own per-file ceiling (300MB for
    // the model) already bounds a real voice well under this.
    private const val MAX_ZIP_FILE_SIZE = 400L * 1024L * 1024L

    fun exportVoice(context: Context, destinationUri: Uri): Boolean {
        if (!CustomVoiceRepository.hasCustomVoice(context)) {
            Log.e(LOG_TAG, "Export failed: no custom voice installed")
            return false
        }

        return try {
            context.contentResolver.openOutputStream(destinationUri)?.use { output ->
                ZipOutputStream(output).use { zip ->
                    zip.putNextEntry(ZipEntry(MODEL_ENTRY_NAME))
                    CustomVoiceRepository.modelFile(context).inputStream().use { it.copyTo(zip) }
                    zip.closeEntry()

                    zip.putNextEntry(ZipEntry(CONFIG_ENTRY_NAME))
                    CustomVoiceRepository.configFile(context).inputStream().use { it.copyTo(zip) }
                    zip.closeEntry()
                }
            } ?: run {
                Log.e(LOG_TAG, "Export failed: could not open output stream")
                return false
            }
            true
        } catch (e: Exception) {
            Log.e(LOG_TAG, "Export failed", e)
            false
        }
    }

    fun importBackup(context: Context, sourceUri: Uri): Boolean {
        val tempZip = File.createTempFile("voice_backup_", ".zip", context.cacheDir)
        var tempModel: File? = null
        var tempConfig: File? = null

        try {
            val copiedBytes = context.contentResolver.openInputStream(sourceUri)?.use { input ->
                tempZip.outputStream().use { output -> input.copyTo(output) }
            }

            if (copiedBytes == null) {
                Log.e(LOG_TAG, "Import failed: could not open selected file")
                return false
            }
            if (copiedBytes > MAX_ZIP_FILE_SIZE) {
                Log.e(LOG_TAG, "Import failed: file exceeds $MAX_ZIP_FILE_SIZE bytes ($copiedBytes)")
                return false
            }

            ZipFile(tempZip).use { zipFile ->
                val modelEntry = zipFile.getEntry(MODEL_ENTRY_NAME)
                val configEntry = zipFile.getEntry(CONFIG_ENTRY_NAME)

                if (modelEntry == null || configEntry == null) {
                    Log.e(LOG_TAG, "Import failed: archive is missing $MODEL_ENTRY_NAME or $CONFIG_ENTRY_NAME")
                    return false
                }

                tempModel = File.createTempFile("voice_backup_model_", ".onnx", context.cacheDir).also { dest ->
                    zipFile.getInputStream(modelEntry).use { input ->
                        dest.outputStream().use { output -> input.copyTo(output) }
                    }
                }
                tempConfig = File.createTempFile("voice_backup_config_", ".json", context.cacheDir).also { dest ->
                    zipFile.getInputStream(configEntry).use { input ->
                        dest.outputStream().use { output -> input.copyTo(output) }
                    }
                }
            }

            return CustomVoiceRepository.installFromValidatedFiles(context, tempModel!!, tempConfig!!)
        } catch (e: Exception) {
            Log.e(LOG_TAG, "Import failed", e)
            return false
        } finally {
            tempZip.delete()
            tempModel?.delete()
            tempConfig?.delete()
        }
    }
}
