// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.output

import com.example.besu.*
import com.example.besu.core.resolveDisplayText
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
    // true = show the whole message (the editor calls this SHOW FULL MESSAGE). The default stays false on
    // purpose: presets saved by older versions lack this field and must keep decoding as false, so an
    // existing install is not changed. New installs get a FULL TEXT preset with it on (data/InstallState.kt).
    val bypassTruncation: Boolean = false
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
        val activeId = getActivePresetId(context)
        return presets.find { it.id == activeId } ?: presets.firstOrNull() ?: VisualPreset()
    }

    // The raw stored active id, unresolved -- null when nothing's ever
    // been set as active. Distinct from getActivePreset, which always
    // resolves to a real, usable VisualPreset (falling back to the first
    // preset or a bare default) since most callers need something to
    // render, not the id itself.
    fun getActivePresetId(context: Context): String? {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_ACTIVE_ID, null)
    }

    fun setActivePreset(context: Context, id: String) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit().putString(KEY_ACTIVE_ID, id).apply()
    }
}

// --- OVERLAY DISPLAY MODE (PROTOCOL TOGGLE) ---

/*
 * Wide visual prompts (text/emoji/GIF) used to force the whole device into
 * landscape via WindowManager.LayoutParams.screenOrientation. That triggers a
 * real configuration change, and MainActivity -- which doesn't declare
 * android:configChanges for orientation -- gets destroyed and recreated, so
 * whatever tab the user was on is lost and they land back on TERMINAL (logs)
 * once the prompt clears. The default behavior now rotates only the prompt's
 * content in place (VisualPromptService.showOverlay) so the device orientation
 * never changes. This flag lets a user opt back into the old device-rotation
 * behavior from PROTOCOL if they prefer it.
 */
object OverlayDisplayPrefs {
    private const val PREFS_NAME = "ack_visual_presets"
    private const val KEY_FORCE_DEVICE_ROTATION = "force_device_rotation"

    fun isDeviceRotationEnabled(context: Context): Boolean {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getBoolean(KEY_FORCE_DEVICE_ROTATION, false)
    }

    fun setDeviceRotationEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_FORCE_DEVICE_ROTATION, enabled)
            .apply()
    }
}

// --- LOGIC ENGINE ---

// The rules live in core/DisplayText.kt (plain Kotlin, unit-tested). The stored field keeps its
// old name, bypassTruncation, so backups and presets saved by older versions are unaffected;
// in the editor it reads as SHOW FULL MESSAGE.
object VisualLogicEngine {
    fun resolveDisplayPrompt(
        rawPhrase: String,
        targetName: String?,
        matrixVisualOverride: String?,
        preset: VisualPreset
    ): String = resolveDisplayText(
        rawPhrase = rawPhrase,
        targetName = targetName,
        matrixVisualOverride = matrixVisualOverride,
        fullText = preset.bypassTruncation
    )
}
