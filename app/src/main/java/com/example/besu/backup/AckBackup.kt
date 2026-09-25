package com.example.besu.backup

import com.example.besu.computer.*
import com.example.besu.data.*
import com.example.besu.decks.*
import com.example.besu.geo.GeoZone
import com.example.besu.output.VisualPreset
import com.example.besu.output.VoiceRecordingBackupEntry
import kotlinx.serialization.Serializable

@Serializable
data class AckBackup(
    val version: Int = 6,
    val timestamp: Long = System.currentTimeMillis(),
    val dsp: DspConfig,
    val matrixData: Map<String, String>,
    val decks: List<DeckMeta> = emptyList(),
    val quickPhrases: List<QuickPhrase>,

    val quickActionsDecks: List<QuickActionsDeckConfig> = emptyList(),

    // Emergency deck prompts/overrides, one entry per EMERGENCY-type deck.
    val emergencyDecks: List<EmergencyDeckConfig> = emptyList(),

    // The user's own medical ID card -- not deck-scoped, so it's a single
    // entry rather than a per-deck list like the ones above.
    val emergencyInfoCard: EmergencyInfoCard = EmergencyInfoCard(),

    // Explicit root A/B/C override storage, keyed by category.
    val rootOverrides: Map<String, RootOverrideConfig> = emptyMap(),

    // Custom context layers (MANAGE CONTEXT), including each one's assigned
    // base pose and display order. Empty on backups made before this field
    // existed -- restore falls back to deriving names from matrixData keys.
    val customContextEntries: List<CustomContextEntry> = emptyList(),

    // Restores the user's current operating context after import.
    val activeDeckId: String = "DEFAULT",
    val activeDeckColorIndex: Int = 0,
    val activeProfile: String = "DEFAULT",
    val activeCategoryFocus: String = "IDENTITY",

    // Existing optional systems.
    val targets: List<TargetSlot> = emptyList(),
    val syntaxRules: Map<String, String> = emptyMap(),

    // Targeting Computer category tree. Self-contained (each tree nests
    // inside its own category), unlike targets/syntaxRules above.
    val computerCategories: List<ComputerCategory> = emptyList(),

    // Header macro buttons, if your current build uses them.
    val headerShortcuts: List<CommandRepository.HeaderShortcut> = emptyList(),

    // Voice recordings bound to Quick Actions slots, audio included
    // (base64 inline -- see VoiceRecordingBackupEntry). Empty on backups
    // made before this field existed; nothing to restore, same as every
    // other field here defaulting to empty.
    val voiceRecordings: List<VoiceRecordingBackupEntry> = emptyList(),

    // PROTOCOL's recording-only playback gain (a whole percent, always a
    // multiple of 5). Defaults to 100 (unchanged) on backups made before
    // this field existed.
    val voiceRecordingGainPercent: Int = 100,

    // Autocomplete suggestion history -- what you've typed into Matrix/
    // Quick Actions variable fields and Shared Root Variables, keyed by
    // AutocompleteHistoryRepository's own opaque scope keys, each paired
    // with the AutocompleteScopeInfo a management UI needs to label it.
    // Empty on backups made before this field existed, same as every
    // other additive field here.
    val autocompleteHistory: Map<String, AutocompleteScope> = emptyMap(),

    // Geo-Protocol: geofenced zones, engine mode ("SOVEREIGN"/"OPTIMIZED"
    // as a plain string so this file doesn't need to import GeoEngineMode
    // for one field), and the master enable toggle. The two scalars are
    // nullable rather than defaulted -- a backup made before this feature
    // existed decodes them as null ("nothing to apply" on restore) rather
    // than a false-looking default that would overwrite the device's real
    // setting. Every backup made by a build that knows this field always
    // fills in a real value, never null.
    val geoZones: List<GeoZone> = emptyList(),
    val geoEngineMode: String? = null,
    val geoMasterToggle: Boolean? = null,

    // Visual prompt presets (text/outline color, outline width, font
    // size, style flags), which preset is active, and the force-device-
    // rotation overlay toggle. Same nullable-scalar convention as above.
    val visualPresets: List<VisualPreset> = emptyList(),
    val activeVisualPresetId: String? = null,
    val forceDeviceRotation: Boolean? = null,

    // Output device routing (PROTOCOL's OUTPUT DEVICE section) -- which
    // device non-forced playback goes to, and the paired Bluetooth
    // device it's pinned to, if any.
    val outputRouteMode: String? = null,
    val outputRouteBtAddress: String? = null,
    val outputRouteBtLabel: String? = null,

    // Terminal / STATUSBOX display prefs.
    val terminalRetentionDays: Int? = null,
    val terminalHideSystemMessages: Boolean? = null,
    val terminalHidePathTrace: Boolean? = null,
    val terminalMonospaceEnabled: Boolean? = null,
    val terminalStatusboxColorIndex: Int? = null,

    // Shake-to-kill sensitivity threshold (AccelerometerTapService).
    val shakeThreshold: Float? = null,

    // Whether each Shared Root Variables section is collapsed, per
    // category -- UI state, but small and cheap to carry along and merges
    // the same way rootOverrides itself does.
    val rootOverrideCollapsed: Map<String, Boolean> = emptyMap(),

    // The statement composer's saved-statement tree (folders and leaf
    // statements, mirroring computerCategories' tree shape). A leaf's
    // `template` keeps any embedded [COMPUTER:id]/{VAR:A} tokens raw
    // (see StatementRepository) so restoring one never freezes it -- it
    // keeps resolving against whatever the referenced Target Computer
    // entry or Shared Root Variable currently holds. Null on backups made
    // before this feature existed ("nothing to say about this field") or
    // before the tree replaced the original flat list -- applyBackupToStorage
    // restores it node-by-node (never wholesale), so nothing on the device
    // the backup doesn't mention is ever removed.
    val savedStatementTree: StatementNode? = null
)

@Serializable
data class DspConfig(
    val userProfile: String,
    val tutorialProfile: String,
    val crush: Float,
    val cadence: Float,
    val forceSpeaker: Boolean,
    val silentOutput: Boolean = false,
    val toneTheme: Int,
    val toneVolume: Float,
    val isVoxEnabled: Boolean,
    
    // V2 Fields
    val masterGain: Float = 1.0f,
    val motionTwist: Float = 7.0f,
    val motionPose: Float = 6.0f,
    val crownSens: Int = 2,
    val autoCryoMinutes: Int = 10,
    val fireGraceMs: Int = 500,
    val wakeWindowMs: Int = 1800,
    val customVoices: List<VoiceProfile> = emptyList()
)

@Serializable
data class TargetSlot(
    val index: Int,             // 0-7
    val label: String,          // e.g. "Commander", "Mom"
    val defaultStrategy: String // "POST" or "PRE"
)
