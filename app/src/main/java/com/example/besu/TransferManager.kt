package com.example.besu

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.BufferedReader
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.InputStreamReader
import java.util.Base64
import java.util.zip.GZIPInputStream

// Note: Data classes (AckBackup, DspConfig) are now imported from AckBackup.kt

object TransferManager {
    private const val PREFS_MATRIX = "ack_matrix_config"
    private const val PREFS_DSP = "ack_prefs"
    
    // Internal Keys (We filter these out of the raw matrix dump)
    private const val KEY_QUICK = "saved_quick_phrases"
    private const val KEY_DECKS = "custom_decks_meta"
    private const val KEY_CATS = "custom_categories"

    private const val KEY_ACTIVE_DECK_ID = "active_deck_id"
    private const val KEY_ACTIVE_DECK_COLOR = "active_deck_color_idx"
    private const val KEY_ACTIVE_PROFILE = "ACTIVE_PROFILE"
    private const val KEY_ACTIVE_CATEGORY = "active_category_focus"
    private const val KEY_HEADER_SHORTCUTS = "header_shortcuts"

    private const val ROOT_OVERRIDE_PREFIX = "root_override_"

    // --- SECURITY CONSTANTS ---
    private const val MAX_DECOMPRESSED_SIZE = 1024 * 1024 // 1MB Limit
    private const val MAX_PHRASE_LENGTH = 300 
    private const val MAX_KEY_LENGTH = 150 
    // Regex: Alphanumeric, underscores, hyphens, slashes, spaces. 
    private val SAFE_KEY_PATTERN = Regex("^[a-zA-Z0-9_\\-/ ]+$")

    private val json = Json { ignoreUnknownKeys = true; prettyPrint = true; encodeDefaults = true }

    // --- EXPORT (GENERATOR) ---
    fun generateBackupJson(context: Context): String {
        // 1. Gather DSP Settings & Custom Voices
        val dspPrefs = context.getSharedPreferences(PREFS_DSP, Context.MODE_PRIVATE)
        
        // Deserialize Custom Voices from string storage to Object List
        val customVoicesRaw = dspPrefs.getString("CUSTOM_VOICES", "[]") ?: "[]"
        val customVoicesList = try {
            json.decodeFromString<List<VoiceProfile>>(customVoicesRaw)
        } catch (e: Exception) { emptyList() }

        val dspConfig = DspConfig(
            userProfile = dspPrefs.getString("USER_VOX_PROFILE", "CYBER") ?: "CYBER",
            tutorialProfile = dspPrefs.getString("TUT_VOX_PROFILE", "MECH") ?: "MECH",
            crush = dspPrefs.getFloat("VOX_CRUSH", 0f),
            cadence = dspPrefs.getFloat("VOX_CADENCE", 0f),
            forceSpeaker = dspPrefs.getBoolean("FORCE_SPEAKER", false),
            toneTheme = dspPrefs.getInt("TONE_THEME", 1),
            toneVolume = dspPrefs.getFloat("TONE_VOLUME", 0.8f),
            isVoxEnabled = dspPrefs.getBoolean("TUTORIAL_VOX", true),
            // V2 Fields
            masterGain = dspPrefs.getFloat("MASTER_GAIN", 1.0f),
            motionTwist = dspPrefs.getFloat("MOT_TWIST", 7.0f),
            motionPose = dspPrefs.getFloat("MOT_POSE", 6.0f),
            crownSens = dspPrefs.getInt("CROWN_SENS", 2),
            autoCryoMinutes = dspPrefs.getInt("AUTO_CRYO", 10),
            customVoices = customVoicesList
        )

        // 2. Gather Matrix Data (sparse export).
        val matrixPrefs = context.getSharedPreferences(
            PREFS_MATRIX,
            Context.MODE_PRIVATE
        )

        val allMatrixEntries = matrixPrefs.all
        val matrixMap = mutableMapOf<String, String>()

// 3. Deserialize deck metadata before collecting typed deck data.
        val decksRaw = matrixPrefs.getString(KEY_DECKS, "[]") ?: "[]"

        val decksList = try {
            json.decodeFromString<List<DeckMeta>>(decksRaw)
        } catch (_: Exception) {
            emptyList()
        }

// 4. Gather Quick Actions configuration for Quick Actions decks only.
        val quickActionsDecks = decksList
            .filter { deck ->
                deck.type == DeckType.QUICK_ACTIONS
            }
            .map { deck ->
                CommandRepository.getQuickActionsConfig(
                    context = context,
                    deckId = deck.id
                )
            }

// Create a lookup map of system defaults: path -> factory phrase.
        val systemDefaults = CommandRepository.BASE_TEMPLATE.associate {
            it.path to it.defaultPhrase
        }

// Filter out system keys and retain actual sparse matrix/deck phrase data.
        allMatrixEntries.forEach { (key, value) ->
            if (
                value is String &&
                key != KEY_QUICK &&
                key != KEY_DECKS &&
                key != KEY_CATS &&
                key != KEY_ACTIVE_DECK_ID &&
                key != KEY_ACTIVE_DECK_COLOR &&
                key != KEY_ACTIVE_PROFILE &&
                key != KEY_ACTIVE_CATEGORY &&
                key != KEY_HEADER_SHORTCUTS &&
                !key.startsWith(ROOT_OVERRIDE_PREFIX)
            ) {
                var shouldExport = true

                val pathStart = key.indexOf("/std/")
                if (pathStart != -1) {
                    val path = key.substring(pathStart)
                    val defaultPhrase = systemDefaults[path]

                    if (value == defaultPhrase) {
                        shouldExport = false
                    }
                }

                if (shouldExport) {
                    matrixMap[key] = value
                }
            }
        }

// 5. Gather Quick Phrases.
        val quickPhrases = CommandRepository.getQuickPhrases(context)

        // 5. Gather root override configurations.
//
// Root overrides are category-scoped rather than phrase-scoped. Store them
// explicitly so restore behavior is not dependent on raw preference keys.
        val rootOverrides = matrixPrefs.all
            .filter { (key, value) ->
                key.startsWith(ROOT_OVERRIDE_PREFIX) && value is String
            }
            .mapNotNull { (key, value) ->
                val category = key.removePrefix(ROOT_OVERRIDE_PREFIX)
                val rawConfig = value as? String ?: return@mapNotNull null

                val config = try {
                    Json.decodeFromString<RootOverrideConfig>(rawConfig)
                } catch (_: Exception) {
                    return@mapNotNull null
                }

                category to config
            }
            .toMap()

// 6. Gather current operating context.
        val activeDeckId = CommandRepository.getActiveDeckId(context)
        val activeDeckColorIndex = CommandRepository.getActiveColorIndex(context)
        val activeProfile = CommandRepository.getActiveProfile(context)
        val activeCategoryFocus = CommandRepository.getActiveCategoryFocus(context)

// 7. Gather header shortcuts.
        val headerShortcuts = CommandRepository.getHeaderShortcuts(context)

// 8. Wrap and encode.
        val backup = AckBackup(
            dsp = dspConfig,
            matrixData = matrixMap,
            decks = decksList,
            quickPhrases = quickPhrases,
            rootOverrides = rootOverrides,
            activeDeckId = activeDeckId,
            activeDeckColorIndex = activeDeckColorIndex,
            activeProfile = activeProfile,
            activeCategoryFocus = activeCategoryFocus,
            headerShortcuts = headerShortcuts,
            quickActionsDecks = quickActionsDecks,
        )

        return json.encodeToString(backup)
    }

    // --- RESTORE (SECURE) ---
    fun restoreBackup(context: Context, rawPayload: String): Boolean {
        return try {
            // STEP 1: PARSE
            val backup = parseQrPayload(rawPayload) ?: return false

            // STEP 2: SANITIZE (The Firewall)
            if (!validateDataIntegrity(backup)) {
                Log.e("ACK_IMPORT", "Data integrity check failed.")
                return false
            }


            // STEP 3: APPLY
            applyBackupToStorage(context, backup)
            true
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    // --- SECURITY LOGIC ---
    private fun validateDataIntegrity(backup: AckBackup): Boolean {
        // 1. Validate DSP Limits
        if (backup.dsp.crush !in 0.0f..1.0f) return false
        if (backup.dsp.cadence !in 0.0f..1.0f) return false
        if (backup.dsp.masterGain !in 0.0f..5.0f) return false
        
        // Physics Sanity
        if (backup.dsp.motionTwist !in 1.0f..20.0f) return false 
        if (backup.dsp.motionPose !in 1.0f..10.0f) return false
        
        // 2. Validate Voices
        if (backup.dsp.customVoices.size > 20) return false // Prevent storage spam
        backup.dsp.customVoices.forEach { 
            if (it.label.length > 50) return false
            if (it.pitch !in 0.1f..4.0f) return false
        }

        // 3. Validate Matrix Data & Keys
        for ((key, value) in backup.matrixData) {
            if (key.length > MAX_KEY_LENGTH) return false
            if (!SAFE_KEY_PATTERN.matches(key)) {
                Log.e("ACK_IMPORT", "Invalid Key Detected: $key")
                return false 
            }
            if (value.length > MAX_PHRASE_LENGTH) return false 
        }

        // 4. Validate Decks
        if (backup.decks.size > 20) return false
        backup.decks.forEach {
            if (it.name.length > 30) return false
            if (!SAFE_KEY_PATTERN.matches(it.id)) return false
        }
// 5. Validate root override configurations.
        if (backup.rootOverrides.size > 50) return false

        backup.rootOverrides.forEach { (category, config) ->
            if (category.length > 50) return false
            if (!SAFE_KEY_PATTERN.matches(category)) return false

            config.slots.forEach { (tag, override) ->
                if (tag !in setOf("A", "B", "C")) return false
                if (override.value.length > MAX_PHRASE_LENGTH) return false
            }
        }

// 6. Validate header shortcuts.
        if (backup.headerShortcuts.size > 3) return false

        backup.headerShortcuts.forEach { shortcut ->
            if (shortcut.label.length > 30) return false
            if (shortcut.phrase.length > MAX_PHRASE_LENGTH) return false
        }
        return true
    }

    // --- UTILITIES ---
    fun parseQrPayload(rawPayload: String): AckBackup? {
        if (rawPayload.trim().startsWith("{")) {
            return try {
                json.decodeFromString<AckBackup>(rawPayload)
            } catch (e: Exception) { null }
        }

        return try {
            val compressedBytes = Base64.getDecoder().decode(rawPayload)
            val inputStream = GZIPInputStream(ByteArrayInputStream(compressedBytes))
            val outputStream = ByteArrayOutputStream()
            val buffer = ByteArray(1024)
            var totalBytesRead = 0
            var bytesRead: Int

            while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                totalBytesRead += bytesRead
                if (totalBytesRead > MAX_DECOMPRESSED_SIZE) {
                    throw SecurityException("Payload exceeds safe size.")
                }
                outputStream.write(buffer, 0, bytesRead)
            }
            val jsonString = outputStream.toString("UTF-8")
            json.decodeFromString<AckBackup>(jsonString)
        } catch (e: Exception) {
            e.printStackTrace() 
            null
        }
    }

    private fun applyBackupToStorage(
        context: Context,
        backup: AckBackup
    ) {
        // 1. Restore DSP, physics, and custom voices.
        val dspPrefs = context.getSharedPreferences(
            PREFS_DSP,
            Context.MODE_PRIVATE
        )

        with(dspPrefs.edit()) {
            putString("USER_VOX_PROFILE", backup.dsp.userProfile)
            putString("TUT_VOX_PROFILE", backup.dsp.tutorialProfile)
            putFloat("VOX_CRUSH", backup.dsp.crush)
            putFloat("VOX_CADENCE", backup.dsp.cadence)
            putBoolean("FORCE_SPEAKER", backup.dsp.forceSpeaker)
            putInt("TONE_THEME", backup.dsp.toneTheme)
            putFloat("TONE_VOLUME", backup.dsp.toneVolume)
            putBoolean("TUTORIAL_VOX", backup.dsp.isVoxEnabled)

            putFloat("MASTER_GAIN", backup.dsp.masterGain)
            putFloat("MOT_TWIST", backup.dsp.motionTwist)
            putFloat("MOT_POSE", backup.dsp.motionPose)
            putInt("CROWN_SENS", backup.dsp.crownSens)
            putInt("AUTO_CRYO", backup.dsp.autoCryoMinutes)

            putString(
                "CUSTOM_VOICES",
                json.encodeToString(backup.dsp.customVoices)
            )

            apply()
        }

        // 2. Replace the complete matrix configuration.
        //
        // This is intentionally not additive. A restore should make the matrix
        // match the backup, including removal of old phrases, _vars entries,
        // _visual entries, root_override_* entries, old decks, and categories.
        //
        // Built-in phrases omitted by sparse export safely fall back to their
        // factory defaults after their saved override is cleared.
        val matrixPrefs = context.getSharedPreferences(
            PREFS_MATRIX,
            Context.MODE_PRIVATE
        )

        val editor = matrixPrefs.edit()

        editor.clear()

        // Restore phrase templates, live-saved local variables, visual settings,
        // root override storage, and custom deck phrase data.
        backup.matrixData.forEach { (key, value) ->
            editor.putString(key, value)
        }

        // Restore deck metadata.
        editor.putString(
            KEY_DECKS,
            json.encodeToString(backup.decks)
        )

        // Restore quick phrases.
        editor.putString(
            KEY_QUICK,
            json.encodeToString(backup.quickPhrases)
        )

        // Rebuild custom categories from the restored data only.
        //
        // Do this even when empty, so categories deleted before backup do not
        // survive from a previous local configuration.
        val customCategories = mutableSetOf<String>()

        backup.matrixData.keys.forEach { key ->
            if (key.contains("/custom/")) {
                val parts = key.split("/")
                val customIndex = parts.indexOf("custom")

                if (
                    customIndex != -1 &&
                    parts.size > customIndex + 1
                ) {
                    customCategories.add(parts[customIndex + 1])
                }
            }
        }

        editor.putStringSet(KEY_CATS, customCategories)

        editor.apply()

        // 3. Make the active audio stack reread restored DSP values immediately.
        context.startService(
            Intent(context, OutputService::class.java).apply {
                action = "UPDATE_DSP"
            }
        )
    }
    
    fun readTextFromUri(context: Context, uri: Uri): String {
        val inputStream = context.contentResolver.openInputStream(uri) ?: throw Exception("Cannot open file")
        if (inputStream.available() > MAX_DECOMPRESSED_SIZE) throw SecurityException("File too large")
        val reader = BufferedReader(InputStreamReader(inputStream))
        return reader.use { it.readText() }
    }
}
