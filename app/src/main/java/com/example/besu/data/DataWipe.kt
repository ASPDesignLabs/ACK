// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.compose.runtime.snapshots.SnapshotStateList
import com.example.besu.core.CustomVoiceRemoval
import com.example.besu.core.StorageCatalogue
import com.example.besu.core.StorageCatalogue.Area
import com.example.besu.geo.GeoEngineController
import com.example.besu.geo.GeoEngineMode
import com.example.besu.geo.GeoRepository
import com.example.besu.output.CustomVoiceRepository
import com.example.besu.watch.WatchSync
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

/**
 * DELETE DATA: measures and deletes the storage areas in core/StorageCatalogue.kt. The catalogue decides WHAT; this does it.
 *
 * Every step is checked afterwards (a preference file is cleared with commit(), then read back; a folder is deleted, then
 * looked at), and anything that did not work is reported by AREA NAME ONLY, never by content. Nothing here talks to the
 * network. Blocking: call it off the main thread.
 *
 * Never run against real data while testing: use a debug build with sample data.
 */
object DataWipe {
    private const val TAG = "ACK_WIPE"
    private const val GEOFENCE_REMOVAL_TIMEOUT_MS = 4000L

    class Amount(val bytes: Long, val items: Int) {
        val text: String get() = StorageCatalogue.describeAmount(bytes, items)
    }

    /** Area labels only. [failed] is empty when everything asked for was deleted. */
    class Result(val deleted: List<String>, val failed: List<String>) {
        val allOk: Boolean get() = failed.isEmpty()
    }

    // --- measuring (sizes only; content is never read or logged) ----------------------------------------------------

    fun measure(context: Context, area: Area): Amount {
        var bytes = 0L
        var items = 0
        fun count(key: String, value: Any?) { bytes += key.length + (value?.toString()?.length ?: 0); items++ }

        for (file in area.prefsFilesCleared) prefs(context, file).all.forEach { (k, v) -> count(k, v) }
        for ((file, keep) in area.prefsFilesClearedExcept) prefs(context, file).all.forEach { (k, v) -> if (k !in keep) count(k, v) }
        for ((file, keys) in area.prefsKeysRemoved) prefs(context, file).all.forEach { (k, v) -> if (k in keys) count(k, v) }
        for (folder in area.folders) {
            File(context.filesDir, folder).walkTopDown().filter { it.isFile }.forEach { bytes += it.length(); items++ }
        }
        if (area.clearsCache) {
            context.cacheDir.walkTopDown().filter { it.isFile }.forEach { bytes += it.length(); items++ }
        }
        return Amount(bytes, items)
    }

    fun measureEverything(context: Context): Amount {
        var bytes = 0L
        var items = 0
        StorageCatalogue.areas.forEach { val a = measure(context, it); bytes += a.bytes; items += a.items }
        StorageCatalogue.everythingOnlyPrefsFiles.forEach { prefs(context, it).all.forEach { (k, v) -> bytes += k.length + (v?.toString()?.length ?: 0); items++ } }
        return Amount(bytes, items)
    }

    // --- deleting ---------------------------------------------------------------------------------------------------

    /**
     * Deletes [selected] (all of the catalogue's areas when [everything] is true). One area failing never stops the rest;
     * the result says which did. [logs] is the Terminal's live log, cleared with the TERMINAL LOG area.
     */
    fun wipe(context: Context, selected: List<Area>, everything: Boolean, logs: SnapshotStateList<LogEntry>): Result {
        val deleted = ArrayList<String>()
        val failed = ArrayList<String>()
        val ids = selected.map { it.id }.toSet()

        // Before any zone is cleared: location alerts off, and Google's geofences (which live outside this app's process
        // and survive a restart) removed. If that cannot be confirmed where it matters, the zones are left alone.
        val savedLocationsBlocked = StorageCatalogue.ID_SAVED_LOCATIONS in ids && !switchOffLocationAlerts(context)

        for (area in selected) {
            val ok = try {
                if (area.id == StorageCatalogue.ID_SAVED_LOCATIONS && savedLocationsBlocked) false
                else wipeArea(context, area, logs)
            } catch (e: Exception) {
                Log.e(TAG, "wipe failed for ${area.id}", e)
                false
            }
            (if (ok) deleted else failed).add(area.label)
            Log.i(TAG, "area ${area.id}: ${if (ok) "deleted" else "FAILED"}")
        }

        val deletedIds = selected.filter { it.label in deleted }.map { it.id }.toSet()

        // DELETE EVERYTHING also forgets that this install was ever recorded, so the next launch seeds as a new install.
        if (everything && failed.isEmpty()) {
            try { prefs(context, StorageCatalogue.FILE_INSTALL_STATE).edit().clear().commit() } catch (e: Exception) { Log.e(TAG, "install state", e) }
        }
        // A wiped SETTINGS area would otherwise leave the robotic fallback voice and the old cut-off display.
        if (StorageCatalogue.ID_SETTINGS in deletedIds) {
            InstallState.seedDefaultsAfterWipe(context)
        }
        // A wiped MESSAGES AND DECKS area would leave every Matrix slot on the old built-in wording (the developer's own). The neutral
        // starter phrases are saved again, the same ones a new install gets. DELETE EVERYTHING is covered: this is one of its areas.
        if (StorageCatalogue.ID_MESSAGES_AND_DECKS in deletedIds) {
            StarterSeed.seedAfterWipe(context)
        }
        // The paired watch keeps its own copy of the Target Computer names. Best effort: out of reach, it keeps them until
        // it next connects (the confirmation says so).
        if (StorageCatalogue.ID_PEOPLE_AND_PLACES in deletedIds) {
            tellTheWatch(context)
        }
        return Result(deleted, failed)
    }

    /** One Terminal line: the areas by name, never their content. */
    fun logResult(context: Context, result: Result) {
        val message = if (result.allOk) {
            "DATA DELETED: ${result.deleted.joinToString(", ")}"
        } else {
            "DATA DELETE INCOMPLETE. COULD NOT DELETE: ${result.failed.joinToString(", ")}" +
                (if (result.deleted.isNotEmpty()) ". DELETED: ${result.deleted.joinToString(", ")}" else "")
        }
        context.sendBroadcast(
            Intent("ACK_LOG").apply {
                setPackage(context.packageName)
                putExtra("type", if (result.allOk) "CMD" else "CMD_ERR")
                putExtra("msg", message)
            }
        )
    }

    // --- one area ---------------------------------------------------------------------------------------------------

    private fun wipeArea(context: Context, area: Area, logs: SnapshotStateList<LogEntry>): Boolean {
        var ok = true
        if (area.id == StorageCatalogue.ID_TRAINED_VOICE) ok = wipeTrainedVoice(context) && ok
        // The live Terminal list first, so persisting it can't put the key back after it is removed below.
        if (area.id == StorageCatalogue.ID_TERMINAL_LOG) TerminalLogStore.clearAll(context, logs)

        for (file in area.prefsFilesCleared) ok = clearPrefs(context, file) && ok
        for ((file, keep) in area.prefsFilesClearedExcept) ok = clearPrefsExcept(context, file, keep) && ok
        for ((file, keys) in area.prefsKeysRemoved) ok = removeKeys(context, file, keys) && ok
        for (folder in area.folders) ok = deleteFolder(context, folder) && ok
        if (area.clearsCache) ok = clearCache(context) && ok
        return ok
    }

    private fun prefs(context: Context, name: String) = context.getSharedPreferences(name, Context.MODE_PRIVATE)

    private fun clearPrefs(context: Context, name: String): Boolean {
        val p = prefs(context, name)
        return p.edit().clear().commit() && p.all.isEmpty()
    }

    private fun clearPrefsExcept(context: Context, name: String, keep: Set<String>): Boolean {
        val p = prefs(context, name)
        val editor = p.edit()
        p.all.keys.filter { it !in keep }.forEach { editor.remove(it) }
        return editor.commit() && p.all.keys.none { it !in keep }
    }

    private fun removeKeys(context: Context, name: String, keys: Set<String>): Boolean {
        val p = prefs(context, name)
        val editor = p.edit()
        keys.forEach { editor.remove(it) }
        return editor.commit() && keys.none { p.contains(it) }
    }

    private fun deleteFolder(context: Context, name: String): Boolean {
        val dir = File(context.filesDir, name)
        if (!dir.exists()) return true
        dir.deleteRecursively()
        return !dir.exists() || dir.list().isNullOrEmpty()
    }

    private fun clearCache(context: Context): Boolean {
        fun attempt() = context.cacheDir.listFiles()?.forEach { it.deleteRecursively() }
        attempt()
        // A file ACK is using this very moment (speech audio being played) can survive the first pass.
        if (!context.cacheDir.list().isNullOrEmpty()) { Thread.sleep(300); attempt() }
        return context.cacheDir.list().isNullOrEmpty()
    }

    // --- the areas that need more than "delete the files" -----------------------------------------------------------

    /**
     * Location alerts off, then Google's geofences removed, before anything is cleared. Returns false only when the zones
     * must NOT be cleared: Geo-Protocol is on in the Google (OPTIMIZED) mode and Google's service did not confirm the
     * removal. In that case the master switch is put back as it was, so nothing is left half done.
     */
    private fun switchOffLocationAlerts(context: Context): Boolean {
        val wasEnabled = GeoRepository.isGeoEnabled(context)
        val optimized = GeoRepository.getEngineMode(context) == GeoEngineMode.OPTIMIZED
        val mustConfirm = StorageCatalogue.geofencesNeedConfirmedRemoval(wasEnabled, optimized)

        GeoRepository.setGeoEnabled(context, false)
        GeoEngineController.syncEngineState(context)
        val confirmed = GeoEngineController.stopAllAndAwaitGeofenceRemoval(context, GEOFENCE_REMOVAL_TIMEOUT_MS)

        if (mustConfirm && !confirmed) {
            Log.e(TAG, "geofence removal not confirmed; leaving the saved locations alone")
            GeoRepository.setGeoEnabled(context, wasEnabled)
            GeoEngineController.syncEngineState(context)
            return false
        }
        return true
    }

    /** The model, its config and tokens.txt (CustomVoiceRepository.deleteVoice), then any voice profile that used it. */
    private fun wipeTrainedVoice(context: Context): Boolean {
        val allGone = CustomVoiceRepository.deleteVoice(context)
        try {
            val p = prefs(context, StorageCatalogue.FILE_ACK_PREFS)
            val profiles = try {
                Json.decodeFromString<List<VoiceProfile>>(p.getString("CUSTOM_VOICES", "[]") ?: "[]")
            } catch (e: Exception) {
                emptyList()
            }
            val active = p.getString("USER_VOX_PROFILE", "CYBER") ?: "CYBER"
            val impact = CustomVoiceRemoval.impact(active, profiles.map { CustomVoiceRemoval.Profile(it.id, it.label, it.useCustomVoice) })
            if (impact.anyAffected) {
                val updated = profiles.map { if (it.id in impact.profileIdsToClear) it.copy(useCustomVoice = false) else it }
                p.edit()
                    .putString("USER_VOX_PROFILE", impact.newActiveProfileId)
                    .putString("CUSTOM_VOICES", Json.encodeToString(updated))
                    .commit()
            }
        } catch (e: Exception) {
            Log.e(TAG, "could not move voice profiles off the deleted voice", e)
        }
        return allGone
    }

    private fun tellTheWatch(context: Context) {
        try {
            WatchSync.sendComputerCategoriesForDeck(context, CommandRepository.getActiveDeckId(context))
            WatchSync.sendAllComputerCategories(context)
            WatchSync.sendTargetList(context)
        } catch (e: Exception) {
            Log.e(TAG, "could not send the empty lists to the watch", e)
        }
    }
}
