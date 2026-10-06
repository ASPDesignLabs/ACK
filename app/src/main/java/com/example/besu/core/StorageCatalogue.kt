// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale

/**
 * Everything ACK stores on this phone, grouped into the areas DELETE DATA offers, and what its confirmations say.
 * Pure data and decisions (no `android.*`) so it is tested without a phone. data/DataWipe.kt does the deleting by walking
 * this list; settings/ManageDataDialog.kt only displays it.
 *
 * The words are string resources (`area_<id>_label` / `_holds` / `_backup`, `storage_*`), in the chosen language: an [Area] names them and a
 * [TextSource] supplies them, so every decision here is still tested against the real English text. A result is reported by area **id**, never by
 * its label, so no decision depends on a translated word.
 *
 * Nothing here deletes anything by itself, and nothing is deleted that is not named here. A test scans the app's source for
 * every preference file and folder it writes and fails if one is not in an area below (or in [NOT_PERSONAL]), so a new
 * storage area cannot be added without deciding how the wipe treats it.
 *
 * Two preference files are shared between areas and are split by key, with no gap and no overlap (a test checks it):
 *  - `ack_matrix_config`: the Emergency info card key belongs to EMERGENCY INFO CARD, everything else to MESSAGES AND DECKS.
 *  - `ack_prefs`: the Terminal log key belongs to TERMINAL LOG, everything else to SETTINGS.
 */
object StorageCatalogue {

    enum class Coverage { EXPORT_JSON, OTHER_BACKUP, NOT_BACKED_UP }

    class Area(
        val id: String,
        /** Preference files cleared completely. */
        val prefsFilesCleared: Set<String> = emptySet(),
        /** Shared preference files cleared except for the keys listed (another area owns those keys). */
        val prefsFilesClearedExcept: Map<String, Set<String>> = emptyMap(),
        /** Keys removed from a shared preference file (the rest of the file belongs to another area). */
        val prefsKeysRemoved: Map<String, Set<String>> = emptyMap(),
        /** Folders under the app's private files folder. */
        val folders: Set<String> = emptySet(),
        /** Everything in the cache folder. */
        val clearsCache: Boolean = false,
        val coverage: Coverage,
        /** The resource that says what is true afterwards that the person might not expect; shown in the first confirmation. */
        val afterResource: String? = null,
        /** Memory caches (the deck list and so on) make a restart the reliable way to show a clean state. */
        val restartAfter: Boolean,
    ) {
        private val key: String get() = id.lowercase(Locale.ROOT)

        /** The area's name. */
        val labelResource: String get() = "area_${key}_label"

        /** What it holds, in plain words. */
        val holdsResource: String get() = "area_${key}_holds"

        /** The sentence that names how to save it first, or says it is not backed up. It may name EXPORT .JSON and AUDIO ARCHITECT ([BACKUP_NOTE_ARGUMENTS]). */
        val backupResource: String get() = "area_${key}_backup"
    }

    // The names a backup note can mention, as resources of the label table, so they read the same as the buttons they point to.
    const val EXPORT_JSON_LABEL = "label_export_json"
    const val AUDIO_ARCHITECT_LABEL = "label_audio_architect"
    const val EXPORT_VOICE_BACKUP_LABEL = "audio_export_voice_backup"
    const val SAVE_ALL_LABEL = "capture_save_all"
    const val RECORD_TRAINING_LABEL = "label_record_training"

    // Area ids. data/DataWipe.kt gives the areas that need more than "delete the files" their extra steps by these.
    const val ID_MESSAGES_AND_DECKS = "MESSAGES_AND_DECKS"
    const val ID_EMERGENCY_INFO_CARD = "EMERGENCY_INFO_CARD"
    const val ID_PEOPLE_AND_PLACES = "PEOPLE_AND_PLACES"
    const val ID_SAVED_LOCATIONS = "SAVED_LOCATIONS"
    const val ID_TERMINAL_LOG = "TERMINAL_LOG"
    const val ID_USAGE_SUMMARY = "USAGE_SUMMARY"
    const val ID_MESSAGE_RECORDINGS = "MESSAGE_RECORDINGS"
    const val ID_TRAINING_DATA = "TRAINING_DATA"
    const val ID_TRAINED_VOICE = "TRAINED_VOICE"
    const val ID_GIF_LIBRARY = "GIF_LIBRARY"
    const val ID_SAFETY_COPIES = "SAFETY_COPIES"
    const val ID_TEMPORARY_FILES = "TEMPORARY_FILES"
    const val ID_SETTINGS = "SETTINGS"

    // The two keys that split a shared preference file. Tested against the source so a rename cannot leave them stale.
    const val KEY_EMERGENCY_INFO_CARD = "emergency_info_card"
    const val KEY_TERMINAL_LOG = "TERMINAL_LOG_ENTRIES"
    const val FILE_MATRIX_CONFIG = "ack_matrix_config"
    const val FILE_ACK_PREFS = "ack_prefs"

    /** Written by data/InstallState.kt. Only DELETE EVERYTHING removes it, so the next launch is treated as a new install. */
    const val FILE_INSTALL_STATE = "ack_install_state"

    // What is true after SETTINGS (or EVERYTHING) is deleted: the new-install defaults are seeded again (data/InstallState.kt).
    const val AFTER_DEFAULTS = "area_after_defaults"

    // The Matrix deck is given ACK's neutral starter phrases again after this area is deleted (data/StarterSeed.kt), so a wiped
    // phone does not fall back to the developer's own built-in wording.
    const val AFTER_STARTERS = "area_after_starters"

    val areas: List<Area> = listOf(
        Area(
            id = ID_MESSAGES_AND_DECKS,
            // ack_starter_seed is the starter seed's own note of which phrases it wrote (per phone, never backed up).
            prefsFilesCleared = setOf("ack_statements", "ack_autocomplete_history", StarterSets.RECORD_FILE),
            prefsFilesClearedExcept = mapOf(FILE_MATRIX_CONFIG to setOf(KEY_EMERGENCY_INFO_CARD)),
            // The learned words (data/LearnedWordsRepository.kt): derived from typed statements, so they go with them.
            folders = setOf(LearnedWordsStore.FOLDER),
            coverage = Coverage.EXPORT_JSON,
            afterResource = AFTER_STARTERS,
            restartAfter = true,
        ),
        Area(
            id = ID_EMERGENCY_INFO_CARD,
            prefsKeysRemoved = mapOf(FILE_MATRIX_CONFIG to setOf(KEY_EMERGENCY_INFO_CARD)),
            coverage = Coverage.EXPORT_JSON,
            restartAfter = true,
        ),
        Area(
            id = ID_PEOPLE_AND_PLACES,
            prefsFilesCleared = setOf("ack_targets"),
            coverage = Coverage.EXPORT_JSON,
            restartAfter = true,
        ),
        Area(
            id = ID_SAVED_LOCATIONS,
            prefsFilesCleared = setOf("ack_geo_secure"),
            folders = setOf("geo_maps"),
            coverage = Coverage.EXPORT_JSON,
            restartAfter = true,
        ),
        Area(
            id = ID_TERMINAL_LOG,
            prefsKeysRemoved = mapOf(FILE_ACK_PREFS to setOf(KEY_TERMINAL_LOG)),
            coverage = Coverage.NOT_BACKED_UP,
            restartAfter = false,
        ),
        Area(
            // The usage summary's counts (core/UsageTally.kt). Per phone and never in a backup; only the counts, never a word of a message. No restart is needed: the repository reads the file each time.
            id = ID_USAGE_SUMMARY,
            prefsFilesCleared = setOf(UsageTally.PREFS_FILE),
            coverage = Coverage.NOT_BACKED_UP,
            restartAfter = false,
        ),
        Area(
            id = ID_MESSAGE_RECORDINGS,
            prefsFilesCleared = setOf("ack_voice_recordings"),
            folders = setOf("recordings"),
            coverage = Coverage.EXPORT_JSON,
            restartAfter = true,
        ),
        Area(
            id = ID_TRAINING_DATA,
            prefsFilesCleared = setOf("ack_training_capture"),
            folders = setOf("training_capture"),
            coverage = Coverage.OTHER_BACKUP,
            restartAfter = true,
        ),
        Area(
            id = ID_TRAINED_VOICE,
            folders = setOf("custom_voice"),
            coverage = Coverage.OTHER_BACKUP,
            restartAfter = true,
        ),
        Area(
            id = ID_GIF_LIBRARY,
            prefsFilesCleared = setOf("ack_gif_library"),
            folders = setOf("gif_library"),
            coverage = Coverage.OTHER_BACKUP,
            restartAfter = true,
        ),
        Area(
            id = ID_SAFETY_COPIES,
            folders = setOf("auto_backups"),
            coverage = Coverage.NOT_BACKED_UP,
            restartAfter = false,
        ),
        Area(
            id = ID_TEMPORARY_FILES,
            clearsCache = true,
            coverage = Coverage.NOT_BACKED_UP,
            restartAfter = false,
        ),
        Area(
            id = ID_SETTINGS,
            prefsFilesCleared = setOf(
                "app_prefs", "gestures", "ack_visual_presets", "ack_deck_trainer", "ack_training_game", "ack_backup_state",
                AssistSettings.FILE,
            ),
            prefsFilesClearedExcept = mapOf(FILE_ACK_PREFS to setOf(KEY_TERMINAL_LOG)),
            coverage = Coverage.EXPORT_JSON,
            afterResource = AFTER_DEFAULTS,
            restartAfter = true,
        ),
    )

    /** DELETE EVERYTHING: every area above, plus [FILE_INSTALL_STATE]. */
    const val EVERYTHING_ID = "EVERYTHING"
    val everythingOnlyPrefsFiles: Set<String> = setOf(FILE_INSTALL_STATE)

    fun area(id: String): Area = areas.first { it.id == id }

    /** Items that are stored but are not the person's data, so the wipe leaves them (each with the reason). */
    val NOT_PERSONAL: Map<String, String> = mapOf(
        "espeak-ng-data" to "bundled pronunciation data copied from the app itself; identical for every voice and every user",
    )

    // --- what a wipe needs to decide -------------------------------------------------------------------------------

    /** True if any of the areas needs the app restarted afterwards (everything except the log, safety copies and temporary files). */
    fun needsRestart(selected: Collection<Area>): Boolean = selected.any { it.restartAfter }

    /** The paired watch keeps its own copy of the Target Computer names, so these wipes send it the now-empty lists. */
    fun touchesWatchNames(selected: Collection<Area>): Boolean = selected.any { it.id == ID_PEOPLE_AND_PLACES }

    /**
     * Google's geofences live outside this app's process. When Geo-Protocol is on in the Google (OPTIMIZED) mode they may
     * exist, so wiping the zones must first have them removed, and must not go on if that cannot be confirmed. Otherwise
     * (off, or the app's own SOVEREIGN mode) nothing outside the app is registered.
     */
    fun geofencesNeedConfirmedRemoval(geoEnabled: Boolean, optimizedMode: Boolean): Boolean = geoEnabled && optimizedMode

    /** Areas whose backup is not EXPORT .JSON (fully or at all). */
    fun everythingNotInExportJson(): List<Area> = areas.filter { it.coverage != Coverage.EXPORT_JSON }

    // --- the words, through a TextSource -----------------------------------------------------------------------------
    // These constants are resource names (strings.xml, in every language), not words.

    const val EVERYTHING_LABEL = "storage_everything_label"
    const val EVERYTHING_HOLDS = "storage_everything_holds"
    const val COUNTING = "storage_counting"
    const val NOT_ELSEWHERE = "storage_not_elsewhere"
    const val WATCH_NOTE = "storage_watch_note"
    const val RESTART_NOTE = "storage_restart_note"
    const val CANNOT_UNDO = "storage_cannot_undo"
    private const val THIS_DELETES = "storage_this_deletes"
    private const val STORED_NOW = "storage_stored_now"
    private const val EVERYTHING_DELETES = "storage_everything_deletes"
    private const val EVERYTHING_NOT_COVERED = "storage_everything_not_covered"
    private const val NOTHING_STORED = "storage_nothing"
    private const val AMOUNT = "storage_amount"
    private const val ITEMS = "storage_items"
    private const val SIZE_UNDER_1_KB = "storage_size_under_1kb"
    private const val SIZE_KB = "storage_size_kb"
    private const val SIZE_MB = "storage_size_mb"
    private const val DELETED_STATUS = "delete_data_deleted"
    private const val DELETED_TOAST = "delete_data_deleted_toast"
    private const val FAILED_STATUS = "delete_data_failed"
    private const val GOOGLE_NOTE = "delete_data_google_note"
    private const val NOT_RESTARTED = "delete_data_not_restarted"
    private const val LOG_DELETED = "delete_data_log_deleted"
    private const val LOG_INCOMPLETE = "delete_data_log_incomplete"
    private const val LOG_INCOMPLETE_DELETED = "delete_data_log_incomplete_deleted"

    /** The area's name. */
    fun label(text: TextSource, area: Area): String = text.get(area.labelResource)

    /** The name of an area by id, or EVERYTHING's. */
    fun labelOf(text: TextSource, id: String): String =
        if (id == EVERYTHING_ID) text.get(EVERYTHING_LABEL) else label(text, area(id))

    /** What the area holds, in plain words. */
    fun holds(text: TextSource, area: Area): String = text.get(area.holdsResource, text.get(RECORD_TRAINING_LABEL))

    /** How to save it first, or that it is not backed up. The names it mentions are the buttons' own, in the chosen language. */
    fun backupNote(text: TextSource, area: Area): String =
        text.get(area.backupResource, text.get(EXPORT_JSON_LABEL), text.get(AUDIO_ARCHITECT_LABEL), text.get(EXPORT_VOICE_BACKUP_LABEL), text.get(SAVE_ALL_LABEL), text.get(RECORD_TRAINING_LABEL))

    /** The areas' names by id, in the order given, for a message. Never any content. */
    fun names(text: TextSource, ids: List<String>): String = ids.joinToString(", ") { label(text, area(it)) }

    /** "NOTHING STORED", or e.g. "3 ITEMS, 12 KB". Bytes are approximate for settings files (the size of their values). */
    fun describeAmount(text: TextSource, bytes: Long, items: Int): String {
        if (items <= 0 && bytes <= 0L) return text.get(NOTHING_STORED)
        return text.get(AMOUNT, text.count(ITEMS, items), describeSize(text, bytes))
    }

    /** "UNDER 1 KB", "12 KB" or "1.4 MB": one size in the words DELETE DATA and the safety-copy list share. */
    fun describeSize(text: TextSource, bytes: Long): String = when {
        bytes < 1024L -> text.get(SIZE_UNDER_1_KB)
        bytes < 1024L * 1024L -> text.get(SIZE_KB, bytes / 1024L)
        else -> text.get(SIZE_MB, String.format(Locale.ROOT, "%.1f", bytes / (1024.0 * 1024.0)))
    }

    /** Only an area that EXPORT .JSON covers can offer BACK UP FIRST; the others name the backup that does cover them. */
    fun offersBackupFirst(area: Area): Boolean = area.coverage == Coverage.EXPORT_JSON

    /** The first confirmation's paragraphs for one area: what goes, how much, how to save it first, and what stays. */
    fun firstConfirmation(text: TextSource, area: Area, amountText: String): List<String> = buildList {
        add(text.get(THIS_DELETES, holds(text, area)))
        add(text.get(STORED_NOW, amountText))
        add(backupNote(text, area))
        area.afterResource?.let { add(text.get(it)) }
        if (touchesWatchNames(listOf(area))) add(text.get(WATCH_NOTE))
        if (area.restartAfter) add(text.get(RESTART_NOTE))
        add(text.get(NOT_ELSEWHERE))
    }

    /** The same, for DELETE EVERYTHING. */
    fun firstConfirmationEverything(text: TextSource, amountText: String): List<String> = buildList {
        add(text.get(EVERYTHING_DELETES, areas.size))
        add(text.get(STORED_NOW, amountText))
        add(text.get(EVERYTHING_NOT_COVERED, text.get(EXPORT_JSON_LABEL), everythingNotInExportJson().joinToString(", ") { label(text, it) }))
        add(text.get(AFTER_DEFAULTS))
        add(text.get(AFTER_STARTERS))
        add(text.get(WATCH_NOTE))
        add(text.get(RESTART_NOTE))
        add(text.get(NOT_ELSEWHERE))
    }

    // --- what is said after a delete (areas by id; the words never decide anything) -----------------------------------------------

    /** Shown in the dialog after a delete that needed no restart. */
    fun successStatus(text: TextSource, deletedIds: List<String>): String = text.get(DELETED_STATUS, names(text, deletedIds))

    /** The toast for the same. */
    fun successToast(text: TextSource, deletedIds: List<String>): String = text.get(DELETED_TOAST, names(text, deletedIds))

    /**
     * Shown after a delete that did not all go through: which areas could not be deleted, which were, a note for SAVED LOCATIONS (Google's location service
     * has to confirm its alerts are removed first), and that ACK did not restart. Sentences are joined with a space here (a resource's own trailing space is
     * trimmed by Android).
     */
    fun failureStatus(text: TextSource, deletedIds: List<String>, failedIds: List<String>): String = buildList {
        add(text.get(FAILED_STATUS, names(text, failedIds)))
        if (deletedIds.isNotEmpty()) add(text.get(DELETED_STATUS, names(text, deletedIds)))
        if (ID_SAVED_LOCATIONS in failedIds) add(text.get(GOOGLE_NOTE, label(text, area(ID_SAVED_LOCATIONS))))
        add(text.get(NOT_RESTARTED))
    }.joinToString(" ")

    /** The one Terminal line after a delete: the areas by name, never their content. */
    fun logLine(text: TextSource, deletedIds: List<String>, failedIds: List<String>): String = when {
        failedIds.isEmpty() -> text.get(LOG_DELETED, names(text, deletedIds))
        deletedIds.isEmpty() -> text.get(LOG_INCOMPLETE, names(text, failedIds))
        else -> text.get(LOG_INCOMPLETE_DELETED, names(text, failedIds), names(text, deletedIds))
    }
}
