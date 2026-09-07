package com.example.besu

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

@Serializable
data class RootOverrideValue(
    val enabled: Boolean = false,
    val value: String = ""
)

@Serializable
data class RootOverrideConfig(
    val slots: Map<String, RootOverrideValue> = mapOf(
        "A" to RootOverrideValue(),
        "B" to RootOverrideValue(),
        "C" to RootOverrideValue()
    )
)

object RootOverrideRepository {
    private const val PREFS_NAME = "ack_matrix_config"
    private const val KEY_PREFIX = "root_override_"
    private const val KEY_COLLAPSED = "root_override_section_collapsed"

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun getConfig(context: Context, category: String): RootOverrideConfig {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val key = "$KEY_PREFIX$category"
        val raw = prefs.getString(key, null) ?: return RootOverrideConfig()

        return try {
            json.decodeFromString<RootOverrideConfig>(raw)
        } catch (_: Exception) {
            RootOverrideConfig()
        }
    }

    fun saveConfig(
        context: Context,
        category: String,
        config: RootOverrideConfig
    ) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

        prefs.edit()
            .putString(
                "$KEY_PREFIX$category",
                json.encodeToString(config)
            )
            .apply()
    }

    fun getOverrideValue(
        context: Context,
        category: String,
        tag: String
    ): RootOverrideValue {
        return getConfig(context, category).slots[tag] ?: RootOverrideValue()
    }

    /*
     * Whether the SHARED ROOT VARIABLES section is collapsed. This is a
     * single app-wide preference (not per-category) so the user sets it
     * once and every ROOT block honors it consistently. Defaults to
     * expanded -- collapsed must never be the out-of-the-box state.
     */
    fun isSectionCollapsed(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getBoolean(KEY_COLLAPSED, false)
    }

    fun setSectionCollapsed(context: Context, collapsed: Boolean) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putBoolean(KEY_COLLAPSED, collapsed).apply()
    }
}
