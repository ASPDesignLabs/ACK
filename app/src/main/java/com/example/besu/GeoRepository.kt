package com.example.besu

import android.content.Context
import android.net.Uri
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

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

    // 3. USER-SUPPLIED MAP DATA
    //
    // No region map ships inside the APK. Instead, a user can import their own
    // Mapsforge-compatible .map file at runtime (see GEO_MAP_IMPORT in
    // GeoProtocolView) and it's copied into app-private storage here. This
    // keeps the release build small while still letting Tactical Grid render
    // real basemap tiles for whoever supplies their own regional extract.
    private const val MAP_DIR_NAME = "geo_maps"
    private const val USER_MAP_FILE_NAME = "user_region.map"

    private fun mapDir(context: Context): File {
        return File(context.filesDir, MAP_DIR_NAME).apply { mkdirs() }
    }

    /** The imported map file, or null if the user hasn't supplied one. */
    fun getUserMapFile(context: Context): File? {
        val file = File(mapDir(context), USER_MAP_FILE_NAME)
        return if (file.exists() && file.length() > 0) file else null
    }

    /**
     * Streams [uri] into app-private storage as the active region map.
     * Writes to a temp file first and only swaps it in on full success, so a
     * failed/interrupted import can never corrupt or half-overwrite an
     * existing map.
     */
    fun importUserMapFile(context: Context, uri: Uri): Result<File> {
        return try {
            val dir = mapDir(context)
            val tempFile = File(dir, "$USER_MAP_FILE_NAME.tmp")
            val destFile = File(dir, USER_MAP_FILE_NAME)

            val input = context.contentResolver.openInputStream(uri)
                ?: return Result.failure(Exception("Cannot open selected file"))

            input.use { streamIn ->
                tempFile.outputStream().use { streamOut ->
                    streamIn.copyTo(streamOut)
                }
            }

            if (tempFile.length() == 0L) {
                tempFile.delete()
                return Result.failure(Exception("Selected file is empty"))
            }

            destFile.delete()
            tempFile.renameTo(destFile)

            Result.success(destFile)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /** Removes the imported map, if any. Tactical Grid falls back to no basemap tiles. */
    fun clearUserMapFile(context: Context) {
        getUserMapFile(context)?.delete()
    }
}
