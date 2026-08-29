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
}
