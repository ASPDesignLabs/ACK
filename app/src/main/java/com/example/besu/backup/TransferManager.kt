package com.example.besu.backup

import com.example.besu.computer.*
import com.example.besu.data.*
import com.example.besu.decks.*
import com.example.besu.geo.*
import com.example.besu.output.*
import com.example.besu.ui.theme.NeonPalette
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.BufferedReader
import java.io.InputStreamReader

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
    private const val ROOT_OVERRIDE_COLLAPSED_PREFIX = "root_override_section_collapsed_"

    // --- SECURITY CONSTANTS ---
    private const val MAX_DECOMPRESSED_SIZE = 1024 * 1024 // 1MB Limit
    private const val MAX_PHRASE_LENGTH = 300
    private const val MAX_KEY_LENGTH = 150
    // Regex: Alphanumeric, underscores, hyphens, slashes, spaces.
    private val SAFE_KEY_PATTERN = Regex("^[a-zA-Z0-9_\\-/ ]+$")

    // Targeting Computer category tree limits.
    private const val MAX_LABEL_LENGTH = 60
    private const val MAX_COMPUTER_CATEGORIES = 40
    private const val MAX_NODES_PER_CATEGORY = 500
    private const val MAX_TREE_DEPTH = 12
    private val CATEGORY_ID_PATTERN = Regex("^[A-Z0-9_]{1,$MAX_KEY_LENGTH}$")

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
            silentOutput = dspPrefs.getBoolean("SILENT_OUTPUT", false),
            toneTheme = dspPrefs.getInt("TONE_THEME", 1),
            toneVolume = dspPrefs.getFloat("TONE_VOLUME", 0.8f),
            isVoxEnabled = dspPrefs.getBoolean("TUTORIAL_VOX", true),
            // V2 Fields
            masterGain = dspPrefs.getFloat("MASTER_GAIN", 1.0f),
            motionTwist = dspPrefs.getFloat("MOT_TWIST", 7.0f),
            motionPose = dspPrefs.getFloat("MOT_POSE", 6.0f),
            crownSens = dspPrefs.getInt("CROWN_SENS", 2),
            autoCryoMinutes = dspPrefs.getInt("AUTO_CRYO", 10),
            fireGraceMs = dspPrefs.getInt("FIRE_GRACE_MS", 500),
            wakeWindowMs = dspPrefs.getInt("WAKE_WINDOW_MS", 1800),
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

// 4b. Gather Emergency configuration for Emergency decks, plus the
// user's own (non-deck-scoped) medical ID card.
        val emergencyDecks = decksList
            .filter { deck ->
                deck.type == DeckType.EMERGENCY
            }
            .map { deck ->
                CommandRepository.getEmergencyConfig(
                    context = context,
                    deckId = deck.id
                )
            }

        val emergencyInfoCard = CommandRepository.getEmergencyInfoCard(context)

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

// 6. Gather custom context layers (name, assigned base pose, and order).
        val customContextEntries = CommandRepository.getCustomContextEntries(context)

// 7. Gather current operating context.
        val activeDeckId = CommandRepository.getActiveDeckId(context)
        val activeDeckColorIndex = CommandRepository.getActiveColorIndex(context)
        val activeProfile = CommandRepository.getActiveProfile(context)
        val activeCategoryFocus = CommandRepository.getActiveCategoryFocus(context)

// 8. Gather header shortcuts.
        val headerShortcuts = CommandRepository.getHeaderShortcuts(context)

// 9. Gather Target Computer data (legacy flat slots + the new category
// tree). Both are exported unconditionally so restoring a backup never
// leaves either shape behind.
        val targets = TargetRepository.getTargets(context)
        val syntaxRules = TargetRepository.getSyntaxRules(context)
        val computerCategories = ComputerRepository.getCategories(context)

// 9b. Gather voice recordings bound to Quick Actions slots, audio
// included (base64) -- see VoiceRecordingRepository.exportForBackup.
        val voiceRecordings = VoiceRecordingRepository.exportForBackup(context)
        val voiceRecordingGainPercent = VoiceRecordingRepository.getPlaybackGainPercent(context)

// 9c. Gather autocomplete suggestion history -- its own dedicated prefs
// file, so a clean whole-file export needs no key-prefix filtering the
// way rootOverrides (sharing "ack_matrix_config" with everything else)
// does above.
        val autocompleteHistory = AutocompleteHistoryRepository.exportForBackup(context)

// 9d. Gather Geo-Protocol: zones, engine mode, master toggle.
        val geoZones = GeoRepository.getZones(context)
        val geoEngineMode = GeoRepository.getEngineMode(context).name
        val geoMasterToggle = GeoRepository.isGeoEnabled(context)

// 9e. Gather visual prompt presets, which one is active, and the
// device-rotation overlay toggle.
        val visualPresets = VisualPresetRepository.getPresets(context)
        val activeVisualPresetId = VisualPresetRepository.getActivePresetId(context)
        val forceDeviceRotation = OverlayDisplayPrefs.isDeviceRotationEnabled(context)

// 9f. Gather output device routing -- lives in the same "ack_prefs"
// file already opened above for DSP settings.
        val outputRouteMode = dspPrefs.getString("OUTPUT_ROUTE_MODE", null)
        val outputRouteBtAddress = dspPrefs.getString("OUTPUT_ROUTE_BT_ADDRESS", null)
        val outputRouteBtLabel = dspPrefs.getString("OUTPUT_ROUTE_BT_LABEL", null)

// 9g. Gather Terminal / STATUSBOX display prefs.
        val terminalRetentionDays = TerminalLogStore.getRetentionDays(context)
        val terminalHideSystemMessages = TerminalLogStore.getHideSystemMessages(context)
        val terminalHidePathTrace = TerminalLogStore.getHidePathTrace(context)
        val terminalMonospaceEnabled = TerminalLogStore.getMonospaceEnabled(context)
        val terminalStatusboxColorIndex = TerminalLogStore.getStatusboxColorIndex(context)

// 9h. Gather shake-to-kill sensitivity -- also lives in "ack_prefs".
        val shakeThreshold = dspPrefs.getFloat(
            "SHAKE_THRESHOLD",
            AccelerometerTapService.DEFAULT_SHAKE_THRESHOLD
        )

// 9i. Gather Shared Root Variables' per-category collapsed/expanded UI
// state -- same matrixPrefs file rootOverrides itself reads above,
// filtered to the collapsed-state keys (Boolean-valued) instead of the
// config keys (String-valued), so the two extractions never overlap.
        val rootOverrideCollapsed = matrixPrefs.all
            .filter { (key, value) -> key.startsWith(ROOT_OVERRIDE_COLLAPSED_PREFIX) && value is Boolean }
            .mapNotNull { (key, value) ->
                val category = key.removePrefix(ROOT_OVERRIDE_COLLAPSED_PREFIX)
                val collapsed = value as? Boolean ?: return@mapNotNull null
                category to collapsed
            }
            .toMap()

// 10. Wrap and encode.
        val backup = AckBackup(
            dsp = dspConfig,
            matrixData = matrixMap,
            decks = decksList,
            quickPhrases = quickPhrases,
            rootOverrides = rootOverrides,
            customContextEntries = customContextEntries,
            activeDeckId = activeDeckId,
            activeDeckColorIndex = activeDeckColorIndex,
            activeProfile = activeProfile,
            activeCategoryFocus = activeCategoryFocus,
            headerShortcuts = headerShortcuts,
            quickActionsDecks = quickActionsDecks,
            emergencyDecks = emergencyDecks,
            emergencyInfoCard = emergencyInfoCard,
            targets = targets,
            syntaxRules = syntaxRules,
            computerCategories = computerCategories,
            voiceRecordings = voiceRecordings,
            voiceRecordingGainPercent = voiceRecordingGainPercent,
            autocompleteHistory = autocompleteHistory,
            geoZones = geoZones,
            geoEngineMode = geoEngineMode,
            geoMasterToggle = geoMasterToggle,
            visualPresets = visualPresets,
            activeVisualPresetId = activeVisualPresetId,
            forceDeviceRotation = forceDeviceRotation,
            outputRouteMode = outputRouteMode,
            outputRouteBtAddress = outputRouteBtAddress,
            outputRouteBtLabel = outputRouteBtLabel,
            terminalRetentionDays = terminalRetentionDays,
            terminalHideSystemMessages = terminalHideSystemMessages,
            terminalHidePathTrace = terminalHidePathTrace,
            terminalMonospaceEnabled = terminalMonospaceEnabled,
            terminalStatusboxColorIndex = terminalStatusboxColorIndex,
            shakeThreshold = shakeThreshold,
            rootOverrideCollapsed = rootOverrideCollapsed,
        )

        return json.encodeToString(backup)
    }

    // Writes a backup snapshot to app-internal storage (not a user-facing
    // export) as a safety net before a one-time, non-reversible-feeling data
    // transform such as the Target Computer's legacy-slot migration. Returns
    // false if the snapshot couldn't be written, so the caller can decline
    // to proceed rather than transform data with no rollback copy.
    fun writeInternalSnapshot(context: Context, label: String): Boolean {
        return try {
            val dir = java.io.File(context.filesDir, "auto_backups").apply { mkdirs() }
            val file = java.io.File(dir, "${label}_${System.currentTimeMillis()}.json")
            file.writeText(generateBackupJson(context))
            true
        } catch (e: Exception) {
            Log.e("ACK_BACKUP", "Automatic snapshot failed: $label", e)
            false
        }
    }

    // --- RESTORE (SECURE) ---
    // Whole-protocol restore -- validates then wholesale-overwrites DSP,
    // decks, quick actions, emergency, root overrides, target computer,
    // voice recordings, and autocomplete history, all at once (see
    // applyBackupToStorage). Used by PROTOCOL's FULL RESTORE FROM JSON;
    // deliberately not what the narrower IMPORT .JSON button calls, since
    // that one imports just matrix phrases into a new deck rather than
    // overwriting the whole configuration.
    fun restoreBackup(context: Context, rawJson: String): Boolean {
        return try {
            // STEP 1: PARSE
            val backup = parseBackupJson(rawJson) ?: return false

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
    // Every rejection logs the specific check and value that failed under
    // the ACK_IMPORT tag before returning false -- restoreBackup's own
    // "Data integrity check failed" line only ever said that *something*
    // failed, never what, which made a real failure undiagnosable without
    // reading this function by hand. Logging here is deliberately the
    // last line of defense, not the first: every field's real input
    // constraint (a TextField's own length cap, if it has one) is the
    // actual source of truth, and this function's limits are meant to be
    // generous enough to accept anything the app itself can produce.
    private fun validateDataIntegrity(backup: AckBackup): Boolean {
        // 1. Validate DSP Limits
        if (backup.dsp.crush !in 0.0f..1.0f) {
            Log.e("ACK_IMPORT", "dsp.crush out of range: ${backup.dsp.crush}")
            return false
        }
        if (backup.dsp.cadence !in 0.0f..1.0f) {
            Log.e("ACK_IMPORT", "dsp.cadence out of range: ${backup.dsp.cadence}")
            return false
        }
        if (backup.dsp.masterGain !in 0.0f..5.0f) {
            Log.e("ACK_IMPORT", "dsp.masterGain out of range: ${backup.dsp.masterGain}")
            return false
        }

        // Physics Sanity
        if (backup.dsp.motionTwist !in 1.0f..20.0f) {
            Log.e("ACK_IMPORT", "dsp.motionTwist out of range: ${backup.dsp.motionTwist}")
            return false
        }
        if (backup.dsp.motionPose !in 1.0f..10.0f) {
            Log.e("ACK_IMPORT", "dsp.motionPose out of range: ${backup.dsp.motionPose}")
            return false
        }

        // 2. Validate Voices
        if (backup.dsp.customVoices.size > 20) {
            Log.e("ACK_IMPORT", "customVoices.size exceeds 20: ${backup.dsp.customVoices.size}")
            return false // Prevent storage spam
        }
        backup.dsp.customVoices.forEach {
            if (it.label.length > 50) {
                Log.e("ACK_IMPORT", "customVoice label exceeds 50 chars: \"${it.label}\" (${it.label.length})")
                return false
            }
            if (it.pitch !in 0.1f..4.0f) {
                Log.e("ACK_IMPORT", "customVoice \"${it.label}\" pitch out of range: ${it.pitch}")
                return false
            }
        }

        // 3. Validate Matrix Data & Keys
        for ((key, value) in backup.matrixData) {
            if (key.length > MAX_KEY_LENGTH) {
                Log.e("ACK_IMPORT", "matrixData key exceeds $MAX_KEY_LENGTH chars: \"$key\" (${key.length})")
                return false
            }
            if (!SAFE_KEY_PATTERN.matches(key)) {
                Log.e("ACK_IMPORT", "Invalid Key Detected: $key")
                return false
            }
            if (value.length > MAX_PHRASE_LENGTH) {
                Log.e("ACK_IMPORT", "matrixData[\"$key\"] value exceeds $MAX_PHRASE_LENGTH chars: ${value.length}")
                return false
            }
        }

        // 4. Validate Decks
        if (backup.decks.size > 20) {
            Log.e("ACK_IMPORT", "decks.size exceeds 20: ${backup.decks.size}")
            return false
        }
        backup.decks.forEach {
            // 40, not 30 -- matches the cap CommandRepository.createDeck
            // (and every deck-rename flow) has always actually enforced.
            if (it.name.length > 40) {
                Log.e("ACK_IMPORT", "deck name exceeds 40 chars: \"${it.name}\" (${it.name.length})")
                return false
            }
            if (!SAFE_KEY_PATTERN.matches(it.id)) {
                Log.e("ACK_IMPORT", "deck id fails SAFE_KEY_PATTERN: \"${it.id}\"")
                return false
            }
        }
// 5. Validate root override configurations.
        if (backup.rootOverrides.size > 50) {
            Log.e("ACK_IMPORT", "rootOverrides.size exceeds 50: ${backup.rootOverrides.size}")
            return false
        }

        backup.rootOverrides.forEach { (category, config) ->
            if (category.length > 50) {
                Log.e("ACK_IMPORT", "rootOverrides category exceeds 50 chars: \"$category\"")
                return false
            }
            if (!SAFE_KEY_PATTERN.matches(category)) {
                Log.e("ACK_IMPORT", "rootOverrides category fails SAFE_KEY_PATTERN: \"$category\"")
                return false
            }

            config.slots.forEach { (tag, override) ->
                if (tag !in setOf("A", "B", "C")) {
                    Log.e("ACK_IMPORT", "rootOverrides[\"$category\"] has invalid tag: \"$tag\"")
                    return false
                }
                if (override.value.length > MAX_PHRASE_LENGTH) {
                    Log.e("ACK_IMPORT", "rootOverrides[\"$category\"][\"$tag\"] value exceeds $MAX_PHRASE_LENGTH chars: ${override.value.length}")
                    return false
                }
            }
        }

// 6. Validate custom context layers.
        if (backup.customContextEntries.size > 20) {
            Log.e("ACK_IMPORT", "customContextEntries.size exceeds 20: ${backup.customContextEntries.size}")
            return false
        }

        val contextNamePattern = Regex("^[A-Z0-9 _-]{1,24}$")

        backup.customContextEntries.forEach { entry ->
            if (!contextNamePattern.matches(entry.name)) {
                Log.e("ACK_IMPORT", "customContextEntry name fails pattern: \"${entry.name}\"")
                return false
            }
            if (entry.name in POSE_CATEGORIES) {
                Log.e("ACK_IMPORT", "customContextEntry name collides with a built-in pose: \"${entry.name}\"")
                return false
            }
            if (entry.basePose !in POSE_CATEGORIES) {
                Log.e("ACK_IMPORT", "customContextEntry \"${entry.name}\" has invalid basePose: \"${entry.basePose}\"")
                return false
            }
        }

        if (
            backup.customContextEntries.map { it.name }.distinct().size !=
            backup.customContextEntries.size
        ) {
            Log.e("ACK_IMPORT", "customContextEntries has duplicate names")
            return false
        }

// 7. Validate header shortcuts.
        if (backup.headerShortcuts.size > 3) {
            Log.e("ACK_IMPORT", "headerShortcuts.size exceeds 3: ${backup.headerShortcuts.size}")
            return false
        }

        backup.headerShortcuts.forEach { shortcut ->
            if (shortcut.label.length > 30) {
                Log.e("ACK_IMPORT", "headerShortcut label exceeds 30 chars: \"${shortcut.label}\"")
                return false
            }
            if (shortcut.phrase.length > MAX_PHRASE_LENGTH) {
                Log.e("ACK_IMPORT", "headerShortcut \"${shortcut.label}\" phrase exceeds $MAX_PHRASE_LENGTH chars: ${shortcut.phrase.length}")
                return false
            }
        }

// 8. Validate emergency deck configs.
        if (backup.emergencyDecks.size > 20) {
            Log.e("ACK_IMPORT", "emergencyDecks.size exceeds 20: ${backup.emergencyDecks.size}")
            return false
        }

        backup.emergencyDecks.forEach { config ->
            if (!SAFE_KEY_PATTERN.matches(config.deckId)) {
                Log.e("ACK_IMPORT", "emergencyDeck id fails SAFE_KEY_PATTERN: \"${config.deckId}\"")
                return false
            }
            if (config.slots.size > 20) {
                Log.e("ACK_IMPORT", "emergencyDeck \"${config.deckId}\" slots.size exceeds 20: ${config.slots.size}")
                return false
            }

            config.slots.forEach { slot ->
                if (slot.label.length > 60) {
                    Log.e("ACK_IMPORT", "emergencyDeck \"${config.deckId}\" slot label exceeds 60 chars: \"${slot.label}\"")
                    return false
                }
                if (slot.template.length > MAX_PHRASE_LENGTH) {
                    Log.e("ACK_IMPORT", "emergencyDeck \"${config.deckId}\" slot \"${slot.label}\" template exceeds $MAX_PHRASE_LENGTH chars: ${slot.template.length}")
                    return false
                }
                if (slot.localValues.size > 20) {
                    Log.e("ACK_IMPORT", "emergencyDeck \"${config.deckId}\" slot \"${slot.label}\" localValues.size exceeds 20: ${slot.localValues.size}")
                    return false
                }
                slot.localValues.forEach {
                    if (it.length > MAX_PHRASE_LENGTH) {
                        Log.e("ACK_IMPORT", "emergencyDeck \"${config.deckId}\" slot \"${slot.label}\" localValue exceeds $MAX_PHRASE_LENGTH chars: ${it.length}")
                        return false
                    }
                }
            }
        }

// 9. Validate the medical ID card.
        val card = backup.emergencyInfoCard
        if (card.fullName.length > 100) {
            Log.e("ACK_IMPORT", "emergencyInfoCard.fullName exceeds 100 chars: ${card.fullName.length}")
            return false
        }
        if (card.dateOfBirth.length > 40) {
            Log.e("ACK_IMPORT", "emergencyInfoCard.dateOfBirth exceeds 40 chars: ${card.dateOfBirth.length}")
            return false
        }
        if (card.bloodType.length > 20) {
            Log.e("ACK_IMPORT", "emergencyInfoCard.bloodType exceeds 20 chars: ${card.bloodType.length}")
            return false
        }
        if (card.communicationNote.length > MAX_PHRASE_LENGTH) {
            Log.e("ACK_IMPORT", "emergencyInfoCard.communicationNote exceeds $MAX_PHRASE_LENGTH chars: ${card.communicationNote.length}")
            return false
        }
        if (card.conditions.length > MAX_PHRASE_LENGTH) {
            Log.e("ACK_IMPORT", "emergencyInfoCard.conditions exceeds $MAX_PHRASE_LENGTH chars: ${card.conditions.length}")
            return false
        }
        if (card.allergies.length > MAX_PHRASE_LENGTH) {
            Log.e("ACK_IMPORT", "emergencyInfoCard.allergies exceeds $MAX_PHRASE_LENGTH chars: ${card.allergies.length}")
            return false
        }
        if (card.medications.length > MAX_PHRASE_LENGTH) {
            Log.e("ACK_IMPORT", "emergencyInfoCard.medications exceeds $MAX_PHRASE_LENGTH chars: ${card.medications.length}")
            return false
        }
        if (card.notes.length > MAX_PHRASE_LENGTH) {
            Log.e("ACK_IMPORT", "emergencyInfoCard.notes exceeds $MAX_PHRASE_LENGTH chars: ${card.notes.length}")
            return false
        }
        if (card.contacts.size > 5) {
            Log.e("ACK_IMPORT", "emergencyInfoCard.contacts.size exceeds 5: ${card.contacts.size}")
            return false
        }
        card.contacts.forEach { contact ->
            if (contact.name.length > 100) {
                Log.e("ACK_IMPORT", "emergencyInfoCard contact name exceeds 100 chars: \"${contact.name}\"")
                return false
            }
            if (contact.relationship.length > 60) {
                Log.e("ACK_IMPORT", "emergencyInfoCard contact \"${contact.name}\" relationship exceeds 60 chars")
                return false
            }
            if (contact.phone.length > 40) {
                Log.e("ACK_IMPORT", "emergencyInfoCard contact \"${contact.name}\" phone exceeds 40 chars")
                return false
            }
        }

// 10. Validate legacy target slots and their syntax rules.
        if (backup.targets.size > 50) {
            Log.e("ACK_IMPORT", "targets.size exceeds 50: ${backup.targets.size}")
            return false
        }
        backup.targets.forEach { slot ->
            if (slot.label.length > MAX_LABEL_LENGTH) {
                Log.e("ACK_IMPORT", "target label exceeds $MAX_LABEL_LENGTH chars: \"${slot.label}\"")
                return false
            }
            if (slot.defaultStrategy !in setOf("PRE", "POST")) {
                Log.e("ACK_IMPORT", "target \"${slot.label}\" has invalid defaultStrategy: \"${slot.defaultStrategy}\"")
                return false
            }
        }

        if (backup.syntaxRules.size > 200) {
            Log.e("ACK_IMPORT", "syntaxRules.size exceeds 200: ${backup.syntaxRules.size}")
            return false
        }
        backup.syntaxRules.forEach { (key, value) ->
            if (key.length > MAX_KEY_LENGTH) {
                Log.e("ACK_IMPORT", "syntaxRules key exceeds $MAX_KEY_LENGTH chars: \"$key\"")
                return false
            }
            if (!SAFE_KEY_PATTERN.matches(key)) {
                Log.e("ACK_IMPORT", "syntaxRules key fails SAFE_KEY_PATTERN: \"$key\"")
                return false
            }
            if (value !in setOf("PRE", "POST")) {
                Log.e("ACK_IMPORT", "syntaxRules[\"$key\"] has invalid value: \"$value\"")
                return false
            }
        }

// 11. Validate the Targeting Computer category tree.
        if (backup.computerCategories.size > MAX_COMPUTER_CATEGORIES) {
            Log.e("ACK_IMPORT", "computerCategories.size exceeds $MAX_COMPUTER_CATEGORIES: ${backup.computerCategories.size}")
            return false
        }

        backup.computerCategories.forEach { category ->
            if (!CATEGORY_ID_PATTERN.matches(category.id)) {
                Log.e("ACK_IMPORT", "computerCategory id fails CATEGORY_ID_PATTERN: \"${category.id}\"")
                return false
            }
            if (category.label.length > MAX_LABEL_LENGTH) {
                Log.e("ACK_IMPORT", "computerCategory \"${category.id}\" label exceeds $MAX_LABEL_LENGTH chars: \"${category.label}\" (${category.label.length})")
                return false
            }
            if (!isComputerNodeValid(category.id, category.root)) return false

            val (nodeCount, depth) = countComputerNodes(category.root)
            if (nodeCount > MAX_NODES_PER_CATEGORY) {
                Log.e("ACK_IMPORT", "computerCategory \"${category.id}\" node count exceeds $MAX_NODES_PER_CATEGORY: $nodeCount")
                return false
            }
            if (depth > MAX_TREE_DEPTH) {
                Log.e("ACK_IMPORT", "computerCategory \"${category.id}\" tree depth exceeds $MAX_TREE_DEPTH: $depth")
                return false
            }
        }

        if (
            backup.computerCategories.map { it.id }.distinct().size !=
            backup.computerCategories.size
        ) {
            Log.e("ACK_IMPORT", "computerCategories has duplicate ids")
            return false
        }

// 12. Validate autocomplete suggestion history. Scope keys are generated
// internally (see AutocompleteHistoryRepository's *ScopeKey functions),
// not user-typed, but still validated on the way in like every other
// backup key -- a corrupted or hand-edited backup shouldn't be trusted
// just because this field's keys aren't normally free text. The scope's
// info rides alongside the key rather than being derived from it, so it
// gets the same treatment -- its string fields with the identifier
// pattern every other deckId/storagePath-shaped field in this file uses.
        if (backup.autocompleteHistory.size > 2000) {
            Log.e("ACK_IMPORT", "autocompleteHistory.size exceeds 2000: ${backup.autocompleteHistory.size}")
            return false
        }

        val validAutocompleteFieldTypes = setOf(
            AutocompleteScopeInfo.TYPE_MATRIX,
            AutocompleteScopeInfo.TYPE_QUICK_ACTION,
            AutocompleteScopeInfo.TYPE_ROOT_OVERRIDE
        )

        backup.autocompleteHistory.forEach { (scopeKey, scope) ->
            if (scopeKey.length > MAX_KEY_LENGTH) {
                Log.e("ACK_IMPORT", "autocompleteHistory scope key exceeds $MAX_KEY_LENGTH chars: \"$scopeKey\"")
                return false
            }
            if (!SAFE_KEY_PATTERN.matches(scopeKey)) {
                Log.e("ACK_IMPORT", "autocompleteHistory scope key fails SAFE_KEY_PATTERN: \"$scopeKey\"")
                return false
            }
            if (scope.entries.size > 20) {
                Log.e("ACK_IMPORT", "autocompleteHistory[\"$scopeKey\"] entries.size exceeds 20: ${scope.entries.size}")
                return false
            }

            if (scope.info.fieldType !in validAutocompleteFieldTypes) {
                Log.e("ACK_IMPORT", "autocompleteHistory[\"$scopeKey\"] has invalid fieldType: \"${scope.info.fieldType}\"")
                return false
            }
            listOfNotNull(
                scope.info.deckId,
                scope.info.profile,
                scope.info.storagePath,
                scope.info.category,
                scope.info.tag
            ).forEach {
                if (it.length > MAX_KEY_LENGTH) {
                    Log.e("ACK_IMPORT", "autocompleteHistory[\"$scopeKey\"] info field exceeds $MAX_KEY_LENGTH chars: \"$it\"")
                    return false
                }
                if (!SAFE_KEY_PATTERN.matches(it)) {
                    Log.e("ACK_IMPORT", "autocompleteHistory[\"$scopeKey\"] info field fails SAFE_KEY_PATTERN: \"$it\"")
                    return false
                }
            }
            listOfNotNull(scope.info.groupIndex, scope.info.slotIndex, scope.info.tagIndex).forEach {
                if (it !in 0..10_000) {
                    Log.e("ACK_IMPORT", "autocompleteHistory[\"$scopeKey\"] index field out of range: $it")
                    return false
                }
            }

            scope.entries.forEach { entry ->
                if (entry.value.length > MAX_PHRASE_LENGTH) {
                    Log.e("ACK_IMPORT", "autocompleteHistory[\"$scopeKey\"] entry value exceeds $MAX_PHRASE_LENGTH chars: ${entry.value.length}")
                    return false
                }
                if (entry.count !in 1..100_000) {
                    Log.e("ACK_IMPORT", "autocompleteHistory[\"$scopeKey\"] entry count out of range: ${entry.count}")
                    return false
                }
            }
        }

// 13. Validate Geo-Protocol zones and settings.
        if (backup.geoZones.size > 100) {
            Log.e("ACK_IMPORT", "geoZones.size exceeds 100: ${backup.geoZones.size}")
            return false
        }

        backup.geoZones.forEach { zone ->
            if (zone.id.length > MAX_KEY_LENGTH) {
                Log.e("ACK_IMPORT", "geoZone id exceeds $MAX_KEY_LENGTH chars: \"${zone.id}\"")
                return false
            }
            if (zone.name.length > MAX_LABEL_LENGTH) {
                Log.e("ACK_IMPORT", "geoZone \"${zone.id}\" name exceeds $MAX_LABEL_LENGTH chars: \"${zone.name}\" (${zone.name.length})")
                return false
            }
            if (zone.lat !in -90.0..90.0) {
                Log.e("ACK_IMPORT", "geoZone \"${zone.id}\" lat out of range: ${zone.lat}")
                return false
            }
            if (zone.lng !in -180.0..180.0) {
                Log.e("ACK_IMPORT", "geoZone \"${zone.id}\" lng out of range: ${zone.lng}")
                return false
            }
            if (zone.radiusMeters !in 1f..100_000f) {
                Log.e("ACK_IMPORT", "geoZone \"${zone.id}\" radiusMeters out of range: ${zone.radiusMeters}")
                return false
            }
            if (!SAFE_KEY_PATTERN.matches(zone.enterDeckId)) {
                Log.e("ACK_IMPORT", "geoZone \"${zone.id}\" enterDeckId fails SAFE_KEY_PATTERN: \"${zone.enterDeckId}\"")
                return false
            }
            if (!SAFE_KEY_PATTERN.matches(zone.exitDeckId)) {
                Log.e("ACK_IMPORT", "geoZone \"${zone.id}\" exitDeckId fails SAFE_KEY_PATTERN: \"${zone.exitDeckId}\"")
                return false
            }
        }

        if (backup.geoZones.map { it.id }.distinct().size != backup.geoZones.size) {
            Log.e("ACK_IMPORT", "geoZones has duplicate ids")
            return false
        }

        if (backup.geoEngineMode != null && backup.geoEngineMode !in setOf("SOVEREIGN", "OPTIMIZED")) {
            Log.e("ACK_IMPORT", "geoEngineMode is invalid: \"${backup.geoEngineMode}\"")
            return false
        }

// 14. Validate visual prompt presets.
        if (backup.visualPresets.size > 50) {
            Log.e("ACK_IMPORT", "visualPresets.size exceeds 50: ${backup.visualPresets.size}")
            return false
        }

        backup.visualPresets.forEach { preset ->
            if (preset.id.length > MAX_KEY_LENGTH) {
                Log.e("ACK_IMPORT", "visualPreset id exceeds $MAX_KEY_LENGTH chars: \"${preset.id}\"")
                return false
            }
            if (preset.name.length > MAX_LABEL_LENGTH) {
                Log.e("ACK_IMPORT", "visualPreset \"${preset.id}\" name exceeds $MAX_LABEL_LENGTH chars: \"${preset.name}\" (${preset.name.length})")
                return false
            }
            if (preset.outlineWidth !in 0f..50f) {
                Log.e("ACK_IMPORT", "visualPreset \"${preset.id}\" outlineWidth out of range: ${preset.outlineWidth}")
                return false
            }
            if (preset.fontSizeSp !in 10f..400f) {
                Log.e("ACK_IMPORT", "visualPreset \"${preset.id}\" fontSizeSp out of range: ${preset.fontSizeSp}")
                return false
            }
        }

        if (backup.visualPresets.map { it.id }.distinct().size != backup.visualPresets.size) {
            Log.e("ACK_IMPORT", "visualPresets has duplicate ids")
            return false
        }
        if (backup.activeVisualPresetId != null && backup.activeVisualPresetId.length > MAX_KEY_LENGTH) {
            Log.e("ACK_IMPORT", "activeVisualPresetId exceeds $MAX_KEY_LENGTH chars")
            return false
        }

// 15. Validate output device routing.
        if (backup.outputRouteMode != null && backup.outputRouteMode !in setOf("AUTO", "BLUETOOTH", "WATCH")) {
            Log.e("ACK_IMPORT", "outputRouteMode is invalid: \"${backup.outputRouteMode}\"")
            return false
        }
        if (backup.outputRouteBtAddress != null && backup.outputRouteBtAddress.length > MAX_KEY_LENGTH) {
            Log.e("ACK_IMPORT", "outputRouteBtAddress exceeds $MAX_KEY_LENGTH chars")
            return false
        }
        if (backup.outputRouteBtLabel != null && backup.outputRouteBtLabel.length > MAX_LABEL_LENGTH) {
            Log.e("ACK_IMPORT", "outputRouteBtLabel exceeds $MAX_LABEL_LENGTH chars")
            return false
        }

// 16. Validate Terminal / STATUSBOX prefs.
        backup.terminalRetentionDays?.let {
            if (it !in TerminalLogStore.MIN_RETENTION_DAYS..TerminalLogStore.MAX_RETENTION_DAYS) {
                Log.e("ACK_IMPORT", "terminalRetentionDays out of range: $it")
                return false
            }
        }
        backup.terminalStatusboxColorIndex?.let {
            if (it !in NeonPalette.SWATCHES.indices) {
                Log.e("ACK_IMPORT", "terminalStatusboxColorIndex out of range: $it")
                return false
            }
        }

// 17. Validate shake-to-kill sensitivity -- generous headroom over the
// 8f..25f slider range, matching how the DSP physics fields above are
// validated a bit looser than their own sliders.
        backup.shakeThreshold?.let {
            if (it !in 1f..50f) {
                Log.e("ACK_IMPORT", "shakeThreshold out of range: $it")
                return false
            }
        }

// 18. Validate Shared Root Variables' collapsed-state map.
        if (backup.rootOverrideCollapsed.size > 50) {
            Log.e("ACK_IMPORT", "rootOverrideCollapsed.size exceeds 50: ${backup.rootOverrideCollapsed.size}")
            return false
        }
        backup.rootOverrideCollapsed.forEach { (category, _) ->
            if (category.length > 50) {
                Log.e("ACK_IMPORT", "rootOverrideCollapsed category exceeds 50 chars: \"$category\"")
                return false
            }
            if (!SAFE_KEY_PATTERN.matches(category)) {
                Log.e("ACK_IMPORT", "rootOverrideCollapsed category fails SAFE_KEY_PATTERN: \"$category\"")
                return false
            }
        }

        return true
    }

    private fun isComputerNodeValid(categoryId: String, node: ComputerNode): Boolean {
        if (node.id.length > MAX_KEY_LENGTH) {
            Log.e("ACK_IMPORT", "computerCategory \"$categoryId\" node id exceeds $MAX_KEY_LENGTH chars: \"${node.id}\"")
            return false
        }
        if (node.label.length > MAX_LABEL_LENGTH) {
            Log.e("ACK_IMPORT", "computerCategory \"$categoryId\" node label exceeds $MAX_LABEL_LENGTH chars: \"${node.label}\" (${node.label.length})")
            return false
        }
        if (node.legacyStrategy != null && node.legacyStrategy !in setOf("PRE", "POST")) {
            Log.e("ACK_IMPORT", "computerCategory \"$categoryId\" node \"${node.label}\" has invalid legacyStrategy: \"${node.legacyStrategy}\"")
            return false
        }
        return node.children.all { isComputerNodeValid(categoryId, it) }
    }

    // Returns (total node count, max depth) for the subtree rooted at node.
    private fun countComputerNodes(node: ComputerNode, depth: Int = 1): Pair<Int, Int> {
        var count = 1
        var maxDepth = depth

        for (child in node.children) {
            val (childCount, childDepth) = countComputerNodes(child, depth + 1)
            count += childCount
            maxDepth = maxOf(maxDepth, childDepth)
        }

        return count to maxDepth
    }

    // --- UTILITIES ---
    fun parseBackupJson(rawJson: String): AckBackup? {
        return try {
            json.decodeFromString<AckBackup>(rawJson)
        } catch (e: Exception) {
            null
        }
    }

    private fun applyBackupToStorage(
        context: Context,
        backup: AckBackup
    ) {
        // 1. Restore DSP, physics, and custom voices -- dsp is
        // non-optional, so any valid backup always fully specifies it,
        // and it's always fully overwritten. Output device routing and
        // shake-to-kill sensitivity share this same "ack_prefs" file, so
        // they're folded into the same transaction; both are nullable
        // and only written when the backup actually specifies them,
        // leaving the device's current value alone otherwise.
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
            putBoolean("SILENT_OUTPUT", backup.dsp.silentOutput)
            putInt("TONE_THEME", backup.dsp.toneTheme)
            putFloat("TONE_VOLUME", backup.dsp.toneVolume)
            putBoolean("TUTORIAL_VOX", backup.dsp.isVoxEnabled)

            putFloat("MASTER_GAIN", backup.dsp.masterGain)
            putFloat("MOT_TWIST", backup.dsp.motionTwist)
            putFloat("MOT_POSE", backup.dsp.motionPose)
            putInt("CROWN_SENS", backup.dsp.crownSens)
            putInt("AUTO_CRYO", backup.dsp.autoCryoMinutes)
            putInt("FIRE_GRACE_MS", backup.dsp.fireGraceMs)
            putInt("WAKE_WINDOW_MS", backup.dsp.wakeWindowMs)

            putString(
                "CUSTOM_VOICES",
                json.encodeToString(backup.dsp.customVoices)
            )

            if (backup.outputRouteMode != null) {
                putString("OUTPUT_ROUTE_MODE", backup.outputRouteMode)
                putString("OUTPUT_ROUTE_BT_ADDRESS", backup.outputRouteBtAddress)
                putString("OUTPUT_ROUTE_BT_LABEL", backup.outputRouteBtLabel)
            }

            if (backup.shakeThreshold != null) {
                putFloat("SHAKE_THRESHOLD", backup.shakeThreshold)
            }

            apply()
        }

        // 1b. Terminal / STATUSBOX prefs -- also "ack_prefs", but routed
        // through TerminalLogStore's own setters rather than raw keys
        // here, matching how every other named repository below gets
        // its own restore call instead of TransferManager reaching into
        // its storage directly.
        if (backup.terminalRetentionDays != null) {
            TerminalLogStore.setRetentionDays(context, backup.terminalRetentionDays)
        }
        if (backup.terminalHideSystemMessages != null) {
            TerminalLogStore.setHideSystemMessages(context, backup.terminalHideSystemMessages)
        }
        if (backup.terminalHidePathTrace != null) {
            TerminalLogStore.setHidePathTrace(context, backup.terminalHidePathTrace)
        }
        if (backup.terminalMonospaceEnabled != null) {
            TerminalLogStore.setMonospaceEnabled(context, backup.terminalMonospaceEnabled)
        }
        if (backup.terminalStatusboxColorIndex != null) {
            TerminalLogStore.setStatusboxColorIndex(context, backup.terminalStatusboxColorIndex)
        }

        // 2. Merge the matrix configuration. Unlike a mirror restore,
        // this never clears the prefs file first -- every key the
        // backup provides overwrites the device's value (or is added);
        // a key the backup doesn't mention -- an existing phrase, local
        // variable, visual override, or custom deck's data -- is left
        // exactly as it is.
        val matrixPrefs = context.getSharedPreferences(
            PREFS_MATRIX,
            Context.MODE_PRIVATE
        )

        val editor = matrixPrefs.edit()

        backup.matrixData.forEach { (key, value) ->
            editor.putString(key, value)
        }

        // Decks, Quick Phrases, and custom context layers each live
        // under their own single key in this same file as one encoded
        // list -- merge each by its natural id rather than overwriting
        // the whole list, so a deck/phrase/layer created since the
        // backup was made survives.
        val mergedDecks = CommandRepository.getDecks(context).associateBy { it.id }.toMutableMap()
        backup.decks.forEach { mergedDecks[it.id] = it }
        editor.putString(KEY_DECKS, json.encodeToString(mergedDecks.values.toList()))

        val mergedQuickPhrases = CommandRepository.getQuickPhrases(context).associateBy { it.id }.toMutableMap()
        backup.quickPhrases.forEach { mergedQuickPhrases[it.id] = it }
        editor.putString(KEY_QUICK, json.encodeToString(mergedQuickPhrases.values.toList()))

        val mergedCustomContext = CommandRepository.getCustomContextEntries(context)
            .associateBy { it.name }.toMutableMap()
        backup.customContextEntries.forEach { mergedCustomContext[it.name] = it }
        editor.putString(KEY_CATS, json.encodeToString(mergedCustomContext.values.toList()))

        editor.apply()

        // 2b. Header shortcuts are fixed slots by array index, with no
        // id field to merge by -- merge by index instead, skipping a
        // backup index whose shortcut is blank so it can't clobber a
        // real local shortcut with an empty placeholder.
        val mergedShortcuts = CommandRepository.getHeaderShortcuts(context).toMutableList()
        backup.headerShortcuts.forEachIndexed { index, shortcut ->
            if (shortcut.label.isNotBlank() || shortcut.phrase.isNotBlank()) {
                while (mergedShortcuts.size <= index) {
                    mergedShortcuts.add(CommandRepository.HeaderShortcut("", ""))
                }
                mergedShortcuts[index] = shortcut
            }
        }
        CommandRepository.saveHeaderShortcuts(context, mergedShortcuts)

        // 2c. Restore structured data that lives outside the sparse
        // matrix dump above. Root overrides, per-deck configs, Geo
        // zones, visual presets, and Target Computer categories are
        // each upserted by their own repository's save function -- an
        // entry this device already has that the backup doesn't mention
        // is left untouched.
        backup.rootOverrides.forEach { (category, config) ->
            RootOverrideRepository.saveConfig(context, category, config)
        }

        backup.rootOverrideCollapsed.forEach { (category, collapsed) ->
            RootOverrideRepository.setSectionCollapsed(context, category, collapsed)
        }

        backup.quickActionsDecks.forEach { config ->
            CommandRepository.saveQuickActionsConfig(context, config)
        }

        backup.emergencyDecks.forEach { config ->
            CommandRepository.saveEmergencyConfig(context, config)
        }

        // The medical ID card is a single object, not a per-id
        // collection -- merge field by field, only overwriting a string
        // field when the backup's value is non-blank, and merging
        // contacts by name so an existing contact not in the backup
        // survives.
        val existingCard = CommandRepository.getEmergencyInfoCard(context)
        val backupCard = backup.emergencyInfoCard
        val mergedContacts = existingCard.contacts.associateBy { it.name }.toMutableMap()
        backupCard.contacts.forEach { contact ->
            if (!contact.isBlank) mergedContacts[contact.name] = contact
        }
        CommandRepository.saveEmergencyInfoCard(
            context,
            existingCard.copy(
                fullName = backupCard.fullName.ifBlank { existingCard.fullName },
                dateOfBirth = backupCard.dateOfBirth.ifBlank { existingCard.dateOfBirth },
                bloodType = backupCard.bloodType.ifBlank { existingCard.bloodType },
                communicationNote = backupCard.communicationNote.ifBlank { existingCard.communicationNote },
                conditions = backupCard.conditions.ifBlank { existingCard.conditions },
                allergies = backupCard.allergies.ifBlank { existingCard.allergies },
                medications = backupCard.medications.ifBlank { existingCard.medications },
                notes = backupCard.notes.ifBlank { existingCard.notes },
                contacts = mergedContacts.values.toList()
            )
        )

        // Target Computer: legacy targets/syntax rules and the category
        // tree both merge internally now (see TargetRepository.
        // restoreTargets and ComputerRepository.mergeCategories) --
        // there's no longer a separate legacy-to-tree migration branch
        // here, since an empty/absent backup section is simply nothing
        // to merge in, not a signal to synthesize anything.
        TargetRepository.restoreTargets(context, backup.targets, backup.syntaxRules)
        ComputerRepository.mergeCategories(context, backup.computerCategories)

        // The quickActionsDecks restore above already brought back each
        // slot's recordingId reference -- this brings back the actual
        // audio those ids point to, so they resolve to real files again
        // instead of a slot with a recordingId pointing at nothing.
        VoiceRecordingRepository.mergeFromBackup(context, backup.voiceRecordings)
        VoiceRecordingRepository.setPlaybackGainPercent(context, backup.voiceRecordingGainPercent)

        AutocompleteHistoryRepository.restoreFromBackup(context, backup.autocompleteHistory)

        // Geo-Protocol: zones merge by id; engine mode and the master
        // toggle are nullable scalars, applied only when specified.
        backup.geoZones.forEach { zone ->
            GeoRepository.saveZone(context, zone)
        }
        if (backup.geoEngineMode != null) {
            GeoRepository.setEngineMode(context, GeoEngineMode.valueOf(backup.geoEngineMode))
        }
        if (backup.geoMasterToggle != null) {
            GeoRepository.setGeoEnabled(context, backup.geoMasterToggle)
        }

        // Visual prompt presets: merge by id; active preset id and the
        // device-rotation toggle are nullable scalars.
        backup.visualPresets.forEach { preset ->
            VisualPresetRepository.savePreset(context, preset)
        }
        if (backup.activeVisualPresetId != null) {
            VisualPresetRepository.setActivePreset(context, backup.activeVisualPresetId)
        }
        if (backup.forceDeviceRotation != null) {
            OverlayDisplayPrefs.setDeviceRotationEnabled(context, backup.forceDeviceRotation)
        }

        // Restoring adopts the backup's active deck/profile/category
        // focus -- unchanged from every prior version of this restore
        // path.
        CommandRepository.activateDeck(
            context = context,
            deckId = backup.activeDeckId,
            colorIndex = backup.activeDeckColorIndex
        )
        CommandRepository.setActiveProfile(context, backup.activeProfile)
        CommandRepository.setActiveCategoryFocus(context, backup.activeCategoryFocus)

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
