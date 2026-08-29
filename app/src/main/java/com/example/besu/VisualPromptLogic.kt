package com.example.besu

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

// --- DATA MODEL ---

@Serializable
data class VisualPreset(
    val id: String = java.util.UUID.randomUUID().toString(),
    val name: String = "NEW PRESET",
    val textColorArgb: Long = 0xFFFFFFFF, 
    val outlineColorArgb: Long = 0xFF00F3FF, 
    val outlineWidth: Float = 4f,
    val fontSizeSp: Float = 120f,
    val isBold: Boolean = true,
    val isItalic: Boolean = false,
    val isUnderline: Boolean = false,
    val bypassTruncation: Boolean = false // <-- NEW: Allows full phrase rendering
)

// --- REPOSITORY ---

object VisualPresetRepository {
    private const val PREFS_NAME = "ack_visual_presets"
    private const val KEY_PRESETS = "saved_presets"
    private const val KEY_ACTIVE_ID = "active_preset_id"

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    fun getPresets(context: Context): List<VisualPreset> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_PRESETS, "[]") ?: "[]"
        return try { json.decodeFromString(raw) } catch (e: Exception) { emptyList() }
    }

    fun savePreset(context: Context, preset: VisualPreset) {
        val list = getPresets(context).toMutableList()
        list.removeAll { it.id == preset.id }
        list.add(0, preset)
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_PRESETS, json.encodeToString(list)).apply()
    }

    fun deletePreset(context: Context, id: String) {
        val list = getPresets(context).toMutableList()
        list.removeAll { it.id == id }
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_PRESETS, json.encodeToString(list)).apply()
    }

    fun getActivePreset(context: Context): VisualPreset {
        val presets = getPresets(context)
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val activeId = prefs.getString(KEY_ACTIVE_ID, null)
        return presets.find { it.id == activeId } ?: presets.firstOrNull() ?: VisualPreset()
    }

    fun setActivePreset(context: Context, id: String) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit().putString(KEY_ACTIVE_ID, id).apply()
    }
}

// --- LOGIC ENGINE ---

object VisualLogicEngine {
    fun resolveDisplayPrompt(
        rawPhrase: String,
        targetName: String?,
        matrixVisualOverride: String?,
        preset: VisualPreset
    ): String {
        // RULE 1: Specific shorthand visual override (e.g. Work/Custom mapping)
        if (!matrixVisualOverride.isNullOrBlank()) {
            return matrixVisualOverride.uppercase()
        }

        // RULE 2: Target Ping overrides phrase
        if (!targetName.isNullOrBlank()) {
            return targetName.uppercase()
        }

        // RULE 3: Truncation Check
        if (preset.bypassTruncation) {
            return rawPhrase.uppercase() // Show it all, let Compose wrap the text
        }

        // Default Heuristic (Truncate if > 5 words)
        val words = rawPhrase.trim().split("\\s+".toRegex())
        return if (words.size <= 5) {
            rawPhrase.uppercase()
        } else {
            "ALERT:\n${words.take(3).joinToString(" ").uppercase()}..."
        }
    }
}
