package com.example.besu

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

// 1. THE DATA MODEL
@Serializable
data class GeoZone(
    val id: String,
    var name: String,
    val lat: Double,
    val lng: Double,
    var radiusMeters: Float = 100f,
    var enterDeckId: String = "DEFAULT",
    var exitDeckId: String = "NONE" // "NONE" means do nothing on exit
)

enum class GeoEngineMode {
    SOVEREIGN, // Local polling via LocationManager (Max Privacy)
    OPTIMIZED  // OS-level Geofencing via Google Play Services (Battery Saver)
}

// 2. THE ISOLATED VAULT
object GeoRepository {
    private const val PREFS_SECURE_GEO = "ack_geo_secure"
    private const val KEY_ZONES = "geo_zones_list"
    private const val KEY_ENGINE = "geo_engine_mode"
    private const val KEY_MASTER_TOGGLE = "geo_master_toggle"


    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    fun setLastPreGeoDeck(context: Context, deckId: String) {
        context.getSharedPreferences(PREFS_SECURE_GEO, Context.MODE_PRIVATE)
            .edit().putString("last_pre_geo_deck", deckId).apply()
    }

    fun getLastPreGeoDeck(context: Context): String {
        return context.getSharedPreferences(PREFS_SECURE_GEO, Context.MODE_PRIVATE)
            .getString("last_pre_geo_deck", "DEFAULT") ?: "DEFAULT"
    }

    fun getZones(context: Context): List<GeoZone> {
        val prefs = context.getSharedPreferences(PREFS_SECURE_GEO, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_ZONES, "[]") ?: "[]"
        return try { json.decodeFromString(raw) } catch (e: Exception) { emptyList() }
    }

    fun saveZone(context: Context, zone: GeoZone) {
        val list = getZones(context).toMutableList()
        list.removeAll { it.id == zone.id }
        list.add(0, zone) // Add new zones to the top
        val prefs = context.getSharedPreferences(PREFS_SECURE_GEO, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_ZONES, json.encodeToString(list)).apply()
    }

    fun deleteZone(context: Context, zoneId: String) {
        val list = getZones(context).toMutableList()
        list.removeAll { it.id == zoneId }
        val prefs = context.getSharedPreferences(PREFS_SECURE_GEO, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_ZONES, json.encodeToString(list)).apply()
    }

    fun getEngineMode(context: Context): GeoEngineMode {
        val prefs = context.getSharedPreferences(PREFS_SECURE_GEO, Context.MODE_PRIVATE)
        val modeStr = prefs.getString(KEY_ENGINE, GeoEngineMode.SOVEREIGN.name)
        return try { GeoEngineMode.valueOf(modeStr!!) } catch (e: Exception) { GeoEngineMode.SOVEREIGN }
    }

    fun setEngineMode(context: Context, mode: GeoEngineMode) {
        val prefs = context.getSharedPreferences(PREFS_SECURE_GEO, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_ENGINE, mode.name).apply()
    }

    fun isGeoEnabled(context: Context): Boolean {
        return context.getSharedPreferences(PREFS_SECURE_GEO, Context.MODE_PRIVATE)
            .getBoolean(KEY_MASTER_TOGGLE, false)
    }

    fun setGeoEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS_SECURE_GEO, Context.MODE_PRIVATE)
            .edit().putBoolean(KEY_MASTER_TOGGLE, enabled).apply()
    }
}
