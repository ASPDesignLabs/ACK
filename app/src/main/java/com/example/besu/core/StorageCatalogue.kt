// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale

/**
 * Everything ACK stores on this phone, grouped into the areas DELETE DATA offers, and the words its confirmations use.
 * Pure data and decisions (no `android.*`) so it is tested without a phone. data/DataWipe.kt does the deleting by walking
 * this list; settings/ManageDataDialog.kt only displays it.
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
        val label: String,
        /** What it holds, in plain words. */
        val holds: String,
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
        /** The sentence that names how to save it first, or says it is not backed up. */
        val backupNote: String,
        /** What is true afterwards that the person might not expect; shown in the first confirmation. */
        val afterNote: String? = null,
        /** Memory caches (the deck list and so on) make a restart the reliable way to show a clean state. */
        val restartAfter: Boolean,
    )

    // Area ids. data/DataWipe.kt gives the areas that need more than "delete the files" their extra steps by these.
    const val ID_MESSAGES_AND_DECKS = "MESSAGES_AND_DECKS"
    const val ID_EMERGENCY_INFO_CARD = "EMERGENCY_INFO_CARD"
    const val ID_PEOPLE_AND_PLACES = "PEOPLE_AND_PLACES"
    const val ID_SAVED_LOCATIONS = "SAVED_LOCATIONS"
    const val ID_TERMINAL_LOG = "TERMINAL_LOG"
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

    private const val DEFAULTS_AFTER =
        "AFTERWARDS ACK STARTS WITH ITS DEFAULT SETTINGS: THE ORGANIC VOICE AND THE FULL TEXT DISPLAY PRESET."

    // The Matrix deck is given ACK's neutral starter phrases again after this area is deleted (data/StarterSeed.kt), so a wiped
    // phone does not fall back to the developer's own built-in wording.
    private const val STARTERS_AFTER =
        "AFTERWARDS THE MATRIX DECK SHOWS ACK'S NEUTRAL STARTER PHRASES, NOT ITS OLD BUILT-IN WORDING."

    val areas: List<Area> = listOf(
        Area(
            id = ID_MESSAGES_AND_DECKS,
            label = "MESSAGES AND DECKS",
            holds = "YOUR DECKS, MESSAGES, STATEMENTS, SHARED VARIABLES AND TYPING HISTORY. NOT THE EMERGENCY INFO CARD.",
            // ack_starter_seed is the starter seed's own note of which phrases it wrote (per phone, never backed up).
            prefsFilesCleared = setOf("ack_statements", "ack_autocomplete_history", StarterSets.RECORD_FILE),
            prefsFilesClearedExcept = mapOf(FILE_MATRIX_CONFIG to setOf(KEY_EMERGENCY_INFO_CARD)),
            coverage = Coverage.EXPORT_JSON,
            backupNote = "IT IS IN EXPORT .JSON.",
            afterNote = STARTERS_AFTER,
            restartAfter = true,
        ),
        Area(
            id = ID_EMERGENCY_INFO_CARD,
            label = "EMERGENCY INFO CARD",
            holds = "THE MEDICAL ID CARD: NAME, DATE OF BIRTH, BLOOD TYPE, CONDITIONS, MEDICATIONS, ALLERGIES AND CONTACTS.",
            prefsKeysRemoved = mapOf(FILE_MATRIX_CONFIG to setOf(KEY_EMERGENCY_INFO_CARD)),
            coverage = Coverage.EXPORT_JSON,
            backupNote = "IT IS IN EXPORT .JSON.",
            restartAfter = true,
        ),
        Area(
            id = ID_PEOPLE_AND_PLACES,
            label = "PEOPLE AND PLACES",
            holds = "TARGET COMPUTER ENTRIES: NAMES, PHONE NUMBERS, ADDRESSES AND EMAILS.",
            prefsFilesCleared = setOf("ack_targets"),
            coverage = Coverage.EXPORT_JSON,
            backupNote = "IT IS IN EXPORT .JSON.",
            restartAfter = true,
        ),
        Area(
            id = ID_SAVED_LOCATIONS,
            label = "SAVED LOCATIONS",
            holds = "GEO-PROTOCOL ZONES (MAP COORDINATES) AND ANY MAP FILE YOU IMPORTED. LOCATION ALERTS ARE SWITCHED OFF FIRST.",
            prefsFilesCleared = setOf("ack_geo_secure"),
            folders = setOf("geo_maps"),
            coverage = Coverage.EXPORT_JSON,
            backupNote = "THE ZONES ARE IN EXPORT .JSON. THE MAP FILE IS NOT.",
            restartAfter = true,
        ),
        Area(
            id = ID_TERMINAL_LOG,
            label = "TERMINAL LOG",
            holds = "THE TERMINAL'S RECORD OF WHAT WAS SAID AND DONE.",
            prefsKeysRemoved = mapOf(FILE_ACK_PREFS to setOf(KEY_TERMINAL_LOG)),
            coverage = Coverage.NOT_BACKED_UP,
            backupNote = "IT IS NOT BACKED UP ANYWHERE.",
            restartAfter = false,
        ),
        Area(
            id = ID_MESSAGE_RECORDINGS,
            label = "MESSAGE RECORDINGS",
            holds = "VOICE RECORDINGS ATTACHED TO QUICK ACTIONS, KEYS AND MATRIX MESSAGES.",
            prefsFilesCleared = setOf("ack_voice_recordings"),
            folders = setOf("recordings"),
            coverage = Coverage.EXPORT_JSON,
            backupNote = "THE RECORDINGS ARE IN EXPORT .JSON.",
            restartAfter = true,
        ),
        Area(
            id = ID_TRAINING_DATA,
            label = "TRAINING DATA",
            holds = "RECORDINGS, NOTES AND SCRIPTS FROM RECORD TRAINING DATA.",
            prefsFilesCleared = setOf("ack_training_capture"),
            folders = setOf("training_capture"),
            coverage = Coverage.OTHER_BACKUP,
            backupNote = "THESE RECORDINGS ARE NOT IN EXPORT .JSON. SAVE THEM FIRST WITH SAVE ALL TO A FILE " +
                "(RECORD TRAINING DATA). YOUR WRITTEN SCRIPTS ARE IN EXPORT .JSON.",
            restartAfter = true,
        ),
        Area(
            id = ID_TRAINED_VOICE,
            label = "TRAINED VOICE",
            holds = "YOUR TRAINED VOICE MODEL. VOICES THAT USE IT SWITCH TO A NORMAL VOICE.",
            folders = setOf("custom_voice"),
            coverage = Coverage.OTHER_BACKUP,
            backupNote = "IT IS NOT IN EXPORT .JSON. SAVE IT FIRST WITH EXPORT VOICE BACKUP (AUDIO ARCHITECT).",
            restartAfter = true,
        ),
        Area(
            id = ID_GIF_LIBRARY,
            label = "GIF LIBRARY",
            holds = "THE GIF DECKS' PICTURES AND THEIR CATEGORIES.",
            prefsFilesCleared = setOf("ack_gif_library"),
            folders = setOf("gif_library"),
            coverage = Coverage.OTHER_BACKUP,
            backupNote = "IT IS NOT IN EXPORT .JSON. SAVE EACH GIF DECK FIRST WITH EXPORT DECK (.ZIP) IN THAT DECK.",
            restartAfter = true,
        ),
        Area(
            id = ID_SAFETY_COPIES,
            label = "SAFETY COPIES",
            holds = "THE PRIVATE COPIES ACK MADE BEFORE A DATA UPGRADE.",
            folders = setOf("auto_backups"),
            coverage = Coverage.NOT_BACKED_UP,
            backupNote = "THEY ARE NOT BACKED UP ANYWHERE.",
            restartAfter = false,
        ),
        Area(
            id = ID_TEMPORARY_FILES,
            label = "TEMPORARY FILES",
            holds = "PREVIEW AND SPEECH AUDIO AND INTERRUPTED IMPORTS. ACK MAKES THEM AGAIN WHEN NEEDED.",
            clearsCache = true,
            coverage = Coverage.NOT_BACKED_UP,
            backupNote = "THERE IS NOTHING TO BACK UP.",
            restartAfter = false,
        ),
        Area(
            id = ID_SETTINGS,
            label = "SETTINGS",
            holds = "ALL OTHER SETTINGS: VOICE PROFILES, OUTPUT DEVICE, THEME, GESTURES, VISUAL PRESETS, PRACTICE SCORES AND BACKUP REMINDER NOTES.",
            prefsFilesCleared = setOf(
                "app_prefs", "gestures", "ack_visual_presets", "ack_deck_trainer", "ack_training_game", "ack_backup_state",
                AssistSettings.FILE,
            ),
            prefsFilesClearedExcept = mapOf(FILE_ACK_PREFS to setOf(KEY_TERMINAL_LOG)),
            coverage = Coverage.EXPORT_JSON,
            backupNote = "MOST SETTINGS ARE IN EXPORT .JSON. PRACTICE SCORES AND THE LIGHT OR DARK CHOICE ARE NOT.",
            afterNote = DEFAULTS_AFTER,
            restartAfter = true,
        ),
    )

    /** DELETE EVERYTHING: every area above, plus [FILE_INSTALL_STATE]. */
    const val EVERYTHING_ID = "EVERYTHING"
    const val EVERYTHING_LABEL = "EVERYTHING"
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
    fun everythingNotInExportJson(): List<String> = areas.filter { it.coverage != Coverage.EXPORT_JSON }.map { it.label }

    // --- amount stored ----------------------------------------------------------------------------------------------

    /** "NOTHING STORED", or e.g. "3 ITEMS, 12 KB". Bytes are approximate for settings files (the size of their values). */
    fun describeAmount(bytes: Long, items: Int): String {
        if (items <= 0 && bytes <= 0L) return "NOTHING STORED"
        val noun = if (items == 1) "ITEM" else "ITEMS"
        return "$items $noun, ${describeSize(bytes)}"
    }

    /** "UNDER 1 KB", "12 KB" or "1.4 MB": one size in the words DELETE DATA and the safety-copy list share. */
    fun describeSize(bytes: Long): String = when {
        bytes < 1024L -> "UNDER 1 KB"
        bytes < 1024L * 1024L -> "${bytes / 1024L} KB"
        else -> String.format(Locale.ROOT, "%.1f MB", bytes / (1024.0 * 1024.0))
    }

    // --- the confirmations' words -----------------------------------------------------------------------------------

    const val NOT_ELSEWHERE =
        "THIS DOES NOT DELETE FILES YOU SAVED ELSEWHERE (EXPORTS, PACKAGES, BACKUPS) OR ANYTHING YOU COPIED TO ANOTHER APP."
    const val WATCH_NOTE = "A PAIRED WATCH MAY KEEP NAMES UNTIL IT NEXT CONNECTS."
    const val RESTART_NOTE = "ACK WILL RESTART WHEN IT IS DONE."
    const val CANNOT_UNDO = "THIS CANNOT BE UNDONE."

    /** Only an area that EXPORT .JSON covers can offer BACK UP FIRST; the others name the backup that does cover them. */
    fun offersBackupFirst(area: Area): Boolean = area.coverage == Coverage.EXPORT_JSON

    /** The first confirmation's paragraphs for one area: what goes, how much, how to save it first, and what stays. */
    fun firstConfirmation(area: Area, amountText: String): List<String> = buildList {
        add("THIS DELETES: ${area.holds}")
        add("STORED NOW: $amountText.")
        add(area.backupNote)
        area.afterNote?.let { add(it) }
        if (touchesWatchNames(listOf(area))) add(WATCH_NOTE)
        if (area.restartAfter) add(RESTART_NOTE)
        add(NOT_ELSEWHERE)
    }

    /** The same, for DELETE EVERYTHING. */
    fun firstConfirmationEverything(amountText: String): List<String> = buildList {
        add("THIS DELETES ALL OF THE ${areas.size} AREAS LISTED ABOVE, AND ACK'S NOTE OF WHETHER THIS PHONE IS A NEW INSTALL.")
        add("STORED NOW: $amountText.")
        add("EXPORT .JSON DOES NOT COVER: ${everythingNotInExportJson().joinToString(", ")}. SAVE THOSE FIRST IF YOU NEED THEM.")
        add(DEFAULTS_AFTER)
        add(STARTERS_AFTER)
        add(WATCH_NOTE)
        add(RESTART_NOTE)
        add(NOT_ELSEWHERE)
    }
}
