// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.output

import android.content.Context
import android.util.Log
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.File

// Wraps sherpa-onnx's OfflineTts (an on-device neural TTS engine bundling
// ONNX Runtime + espeak-ng) around the user's own imported Piper voice. A
// singleton, since loading the model is expensive (native init against a
// tens-of-MB file) and should happen once per process, not per utterance.
//
// sherpa-onnx's VITS loader wants a plain-text "tokens.txt" (one "<symbol>
// <id>" pair per line), not Piper's own .onnx.json config directly --
// generateTokensFile derives it from that config's "phoneme_id_map" every
// time the engine (re)loads, so it always matches whatever voice is
// currently installed. This mirrors the tokens.txt shape shipped inside
// sherpa-onnx's own released Piper voice packages (e.g.
// vits-piper-en_US-*/tokens.txt) as best reverse-engineered from public
// examples -- worth a first-run sanity check once this is actually built
// and run, since it couldn't be verified against sherpa-onnx's own docs
// site from this environment (network egress to it is blocked here).
object PiperVoiceEngine {
    private const val LOG_TAG = "ACK_CUSTOM_VOICE"

    @Volatile
    private var tts: OfflineTts? = null

    @Volatile
    private var stopRequested = false

    // Lets OutputService's kill switch abort an in-flight generation the
    // same way it already clears queued/active system-TTS work.
    fun requestStop() {
        stopRequested = true
    }

    // Public so CustomVoiceRepository.deleteVoice can remove it: it is generated from the installed voice's config, so it
    // goes when the voice does.
    fun tokensFile(context: Context): File =
        File(CustomVoiceRepository.modelFile(context).parentFile, "tokens.txt")

    // Copies the bundled espeak-ng-data asset folder to internal storage
    // once -- sherpa-onnx's native loader needs a real filesystem path, not
    // an APK asset stream.
    private fun espeakDataDir(context: Context): File {
        val dest = File(context.filesDir, "espeak-ng-data")
        if (!dest.exists() || dest.listFiles().isNullOrEmpty()) {
            dest.mkdirs()
            copyAssetDir(context, "espeak-ng-data", dest)
        }
        return dest
    }

    private fun copyAssetDir(context: Context, assetPath: String, destDir: File) {
        val entries = context.assets.list(assetPath) ?: return
        for (name in entries) {
            val childAssetPath = "$assetPath/$name"
            val childEntries = context.assets.list(childAssetPath)
            if (!childEntries.isNullOrEmpty()) {
                val childDir = File(destDir, name)
                childDir.mkdirs()
                copyAssetDir(context, childAssetPath, childDir)
            } else {
                context.assets.open(childAssetPath).use { input ->
                    File(destDir, name).outputStream().use { output -> input.copyTo(output) }
                }
            }
        }
    }

    private fun generateTokensFile(context: Context): Boolean {
        return try {
            val configText = CustomVoiceRepository.configFile(context).readText()
            val phonemeMap = Json.parseToJsonElement(configText)
                .jsonObject["phoneme_id_map"]?.jsonObject ?: return false

            tokensFile(context).bufferedWriter().use { writer ->
                phonemeMap.entries
                    .filterNot {
                        // The literal newline symbol would corrupt tokens.txt's
                        // line-based format if written -- matches sherpa-onnx's
                        // own official conversion script (scripts/piper/
                        // add_meta_data.py), which skips it for the same reason.
                        it.key == "\n" ||
                            // sherpa-onnx's tokenizer (piper-phonemize-lexicon.cc:
                            // ReadTokens) maps a single Unicode codepoint to an id
                            // -- it has no way to represent a multi-character
                            // symbol at all. piper1-gpl can optionally merge
                            // diphthongs (e.g. "eɪ") into one compound vocabulary
                            // entry via --data.vowel_clusters, which this app's
                            // training command never passes, so any such entries
                            // reflect the base checkpoint's fixed vocabulary, not
                            // something this voice's own fine-tuning actually
                            // relied on -- safe to skip rather than a lossy
                            // workaround. (If a future voice ever IS trained with
                            // vowel_clusters set, this would need real handling,
                            // not just skipping.)
                            it.key.codePointCount(0, it.key.length) != 1
                    }
                    .sortedBy { it.value.jsonArray.first().jsonPrimitive.int }
                    .forEach { (symbol, ids) ->
                        val id = ids.jsonArray.first().jsonPrimitive.int
                        writer.write("$symbol $id")
                        writer.newLine()
                    }
            }
            true
        } catch (e: Exception) {
            Log.e(LOG_TAG, "Failed to generate tokens.txt from the installed voice config", e)
            false
        }
    }

    // Lazily builds the native engine. Must be called off the main thread --
    // native model load for a medium VITS model is not instant. Returns null
    // (rather than throwing) on any failure so callers can fall back to
    // system TTS instead of going silent.
    @Synchronized
    private fun ensureLoaded(context: Context): OfflineTts? {
        tts?.let { return it }

        if (!CustomVoiceRepository.hasCustomVoice(context)) return null
        if (!generateTokensFile(context)) return null

        return try {
            val config = OfflineTtsConfig(
                model = OfflineTtsModelConfig(
                    vits = OfflineTtsVitsModelConfig(
                        model = CustomVoiceRepository.modelFile(context).absolutePath,
                        tokens = tokensFile(context).absolutePath,
                        dataDir = espeakDataDir(context).absolutePath,
                    ),
                    numThreads = 2,
                    debug = false,
                )
            )
            OfflineTts(config = config).also { tts = it }
        } catch (e: Exception) {
            Log.e(LOG_TAG, "Failed to load the custom voice engine", e)
            null
        }
    }

    // Synchronous and blocking -- callers (OutputService) must run this on a
    // background thread, exactly as they already do for playRecording/
    // previewRecording.
    fun generate(context: Context, text: String): Pair<ShortArray, Int>? {
        stopRequested = false
        val engine = ensureLoaded(context) ?: return null

        return try {
            val audio = engine.generate(text = text)
            if (stopRequested) return null
            floatsToShorts(audio.samples) to audio.sampleRate
        } catch (e: Exception) {
            Log.e(LOG_TAG, "Custom voice synthesis failed", e)
            null
        }
    }

    // Frees the native session. Called from OutputService.onDestroy(); a
    // later generate() call rebuilds it lazily from whatever voice is on
    // disk at that point (the app-restart-after-import pattern already
    // guarantees a fresh process picks up a newly imported voice, so no
    // other call site needs to force a reload).
    @Synchronized
    fun release() {
        tts?.release()
        tts = null
    }

    // sherpa-onnx returns samples as floats in [-1, 1]; the rest of ACK's
    // pipeline (applyAudioEffects, playPcm) works in 16-bit PCM shorts.
    private fun floatsToShorts(samples: FloatArray): ShortArray {
        return ShortArray(samples.size) { i ->
            (samples[i].coerceIn(-1f, 1f) * Short.MAX_VALUE).toInt().toShort()
        }
    }
}
