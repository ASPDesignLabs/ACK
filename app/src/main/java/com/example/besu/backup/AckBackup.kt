package com.example.besu.backup

import com.example.besu.computer.*
import com.example.besu.data.*
import com.example.besu.decks.*
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
    val voiceRecordingGainPercent: Int = 100
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
