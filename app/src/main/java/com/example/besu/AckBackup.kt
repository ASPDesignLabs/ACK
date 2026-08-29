package com.example.besu

import kotlinx.serialization.Serializable

@Serializable
data class AckBackup(
    val version: Int = 4,
    val timestamp: Long = System.currentTimeMillis(),
    val dsp: DspConfig,
    val matrixData: Map<String, String>,
    val decks: List<DeckMeta> = emptyList(),
    val quickPhrases: List<QuickPhrase>,

    val quickActionsDecks: List<QuickActionsDeckConfig> = emptyList(),

    // Explicit root A/B/C override storage, keyed by category.
    val rootOverrides: Map<String, RootOverrideConfig> = emptyMap(),

    // Restores the user's current operating context after import.
    val activeDeckId: String = "DEFAULT",
    val activeDeckColorIndex: Int = 0,
    val activeProfile: String = "DEFAULT",
    val activeCategoryFocus: String = "IDENTITY",

    // Existing optional systems.
    val targets: List<TargetSlot> = emptyList(),
    val syntaxRules: Map<String, String> = emptyMap(),

    // Header macro buttons, if your current build uses them.
    val headerShortcuts: List<CommandRepository.HeaderShortcut> = emptyList()
)

@Serializable
data class DspConfig(
    val userProfile: String,
    val tutorialProfile: String,
    val crush: Float,
    val cadence: Float,
    val forceSpeaker: Boolean,
    val toneTheme: Int,
    val toneVolume: Float,
    val isVoxEnabled: Boolean,
    
    // V2 Fields
    val masterGain: Float = 1.0f,
    val motionTwist: Float = 7.0f,
    val motionPose: Float = 6.0f,
    val crownSens: Int = 2,
    val autoCryoMinutes: Int = 10,
    val customVoices: List<VoiceProfile> = emptyList()
)

@Serializable
data class TargetSlot(
    val index: Int,             // 0-7
    val label: String,          // e.g. "Commander", "Mom"
    val defaultStrategy: String // "POST" or "PRE"
)
