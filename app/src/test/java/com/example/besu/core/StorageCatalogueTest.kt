// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import com.example.besu.core.StorageCatalogue.Coverage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class StorageCatalogueTest {
    private val areas = StorageCatalogue.areas

    // The words are string resources; these tests read the real English ones through EnglishText.
    private val text = EnglishText
    private fun label(a: StorageCatalogue.Area) = StorageCatalogue.label(text, a)
    private fun holds(a: StorageCatalogue.Area) = StorageCatalogue.holds(text, a)
    private fun note(a: StorageCatalogue.Area) = StorageCatalogue.backupNote(text, a)
    private fun first(a: StorageCatalogue.Area, amount: String = "X") = StorageCatalogue.firstConfirmation(text, a, amount)
    private fun firstEverything(amount: String = "X") = StorageCatalogue.firstConfirmationEverything(text, amount)
    private val notElsewhere get() = text.get(StorageCatalogue.NOT_ELSEWHERE)
    private val watchNote get() = text.get(StorageCatalogue.WATCH_NOTE)
    private val restartNote get() = text.get(StorageCatalogue.RESTART_NOTE)

    // --- the catalogue's own consistency ---------------------------------------------------------------------------

    @Test
    fun idsAndLabelsAreUnique() {
        assertEquals(areas.size, areas.map { it.id }.toSet().size)
        assertEquals(areas.size, areas.map { label(it) }.toSet().size)
    }

    @Test
    fun theThirteenApprovedAreasAreAllThere() {
        assertEquals(
            listOf(
                "MESSAGES AND DECKS", "EMERGENCY INFO CARD", "PEOPLE AND PLACES", "SAVED LOCATIONS", "TERMINAL LOG", "USAGE SUMMARY",
                "MESSAGE RECORDINGS", "TRAINING DATA", "TRAINED VOICE", "GIF LIBRARY", "SAFETY COPIES", "TEMPORARY FILES",
                "SETTINGS",
            ),
            areas.map { label(it) },
        )
    }

    @Test
    fun theLearnedWordsAreDeletedWithMessagesAndDecks_andTheConfirmationSaysSo() {
        // They are derived from what the person typed, like the typing history that area already holds.
        val area = StorageCatalogue.area(StorageCatalogue.ID_MESSAGES_AND_DECKS)
        assertTrue(LearnedWordsStore.FOLDER in area.folders)
        assertTrue(holds(area).contains("LEARNED WORDS"))
        assertEquals(Coverage.EXPORT_JSON, area.coverage)
        assertTrue(first(area).any { it.contains("LEARNED WORDS") })
        assertTrue(area.restartAfter)
    }

    @Test
    fun everyAreaHasWordsAndNamesItsBackupStatus() {
        for (a in areas) {
            assertTrue("${a.id}: label", label(a).isNotBlank() && label(a) != a.labelResource)
            assertTrue("${a.id}: holds", holds(a).isNotBlank() && holds(a) != a.holdsResource)
            assertTrue("${a.id}: backupNote", note(a).isNotBlank() && note(a) != a.backupResource)
            assertEquals("${a.id}: words are capitals like the rest of the app", holds(a).uppercase(), holds(a))
            assertEquals(note(a).uppercase(), note(a))
        }
    }

    @Test
    fun everyAreaHasSomethingToDelete() {
        for (a in areas) {
            val targets = a.prefsFilesCleared.size + a.prefsFilesClearedExcept.size + a.prefsKeysRemoved.size +
                a.folders.size + (if (a.clearsCache) 1 else 0)
            // TRAINED VOICE is deleted through CustomVoiceRepository.deleteVoice, which removes its folder.
            assertTrue("${a.id} names nothing to delete", targets > 0)
        }
    }

    @Test
    fun noAreaListsAKeyAndItsWholeFile() {
        for (a in areas) {
            val whole = a.prefsFilesCleared + a.prefsFilesClearedExcept.keys
            val both = a.prefsKeysRemoved.keys.intersect(whole)
            assertTrue("${a.id} lists both whole file(s) and key(s) of $both", both.isEmpty())
        }
    }

    @Test
    fun aSharedFileIsSplitWithNoGapAndNoOverlap() {
        val partial = areas.flatMap { it.prefsFilesClearedExcept.keys }.toSet()
        assertEquals(setOf(StorageCatalogue.FILE_MATRIX_CONFIG, StorageCatalogue.FILE_ACK_PREFS), partial)
        for (file in partial) {
            val keep = areas.filter { file in it.prefsFilesClearedExcept }.map { it.prefsFilesClearedExcept.getValue(file) }
            assertEquals("$file: exactly one area clears the rest of it", 1, keep.size)
            val ownedByOthers = areas.mapNotNull { it.prefsKeysRemoved[file] }.flatten().toSet()
            assertEquals("$file: the keys it keeps must be exactly the keys another area removes", ownedByOthers, keep.single())
            assertTrue(
                "$file is also cleared whole by another area",
                areas.none { file in it.prefsFilesCleared },
            )
        }
    }

    @Test
    fun noWholeFileOrFolderBelongsToTwoAreas() {
        val files = areas.flatMap { it.prefsFilesCleared }
        assertEquals("a preference file is cleared by two areas: ${files.groupBy { it }.filterValues { it.size > 1 }.keys}", files.size, files.toSet().size)
        val folders = areas.flatMap { it.folders }
        assertEquals("a folder belongs to two areas: ${folders.groupBy { it }.filterValues { it.size > 1 }.keys}", folders.size, folders.toSet().size)
        assertEquals("only one area empties the cache", 1, areas.count { it.clearsCache })
    }

    @Test
    fun theInstallStateFileBelongsToEverythingOnly() {
        val everywhere = areas.flatMap { it.prefsFilesCleared + it.prefsFilesClearedExcept.keys + it.prefsKeysRemoved.keys }
        assertFalse(StorageCatalogue.FILE_INSTALL_STATE in everywhere)
        assertEquals(setOf(StorageCatalogue.FILE_INSTALL_STATE), StorageCatalogue.everythingOnlyPrefsFiles)
    }

    @Test
    fun theNotPersonalListHasReasonsAndNoOverlapWithAnArea() {
        for ((name, reason) in StorageCatalogue.NOT_PERSONAL) {
            assertTrue("$name needs a reason", reason.isNotBlank())
            assertTrue("$name is also in an area", areas.none { name in it.folders })
        }
    }

    @Test
    fun theKeysThatSplitSharedFilesStillExistInTheSource() {
        val matrix = RepoFiles.read("app/src/main/java/com/example/besu/data/CommandRepository.kt")
        val terminal = RepoFiles.read("app/src/main/java/com/example/besu/data/TerminalLogStore.kt")
        assertTrue(matrix.contains("\"${StorageCatalogue.KEY_EMERGENCY_INFO_CARD}\""))
        assertTrue(terminal.contains("\"${StorageCatalogue.KEY_TERMINAL_LOG}\""))
    }

    // --- restart, watch, geofences ---------------------------------------------------------------------------------

    @Test
    fun onlyTheLogTheUsageSummarySafetyCopiesAndTemporaryFilesNeedNoRestart() {
        // The usage summary needs none because its repository reads the file each time and keeps nothing in memory that a wipe could leave stale.
        val noRestart = areas.filterNot { it.restartAfter }.map { it.id }.toSet()
        assertEquals(
            setOf(StorageCatalogue.ID_TERMINAL_LOG, StorageCatalogue.ID_USAGE_SUMMARY, StorageCatalogue.ID_SAFETY_COPIES, StorageCatalogue.ID_TEMPORARY_FILES),
            noRestart,
        )
    }

    @Test
    fun needsRestartFollowsTheAreasSelected() {
        assertFalse(StorageCatalogue.needsRestart(emptyList()))
        assertFalse(StorageCatalogue.needsRestart(listOf(StorageCatalogue.area(StorageCatalogue.ID_TERMINAL_LOG))))
        assertFalse(
            StorageCatalogue.needsRestart(
                listOf(StorageCatalogue.area(StorageCatalogue.ID_TERMINAL_LOG), StorageCatalogue.area(StorageCatalogue.ID_TEMPORARY_FILES)),
            ),
        )
        // One area that needs it is enough.
        assertTrue(
            StorageCatalogue.needsRestart(
                listOf(StorageCatalogue.area(StorageCatalogue.ID_TERMINAL_LOG), StorageCatalogue.area(StorageCatalogue.ID_SETTINGS)),
            ),
        )
        assertTrue(StorageCatalogue.needsRestart(areas))
    }

    @Test
    fun theWatchIsToldOnlyWhenPeopleAndPlacesGoes() {
        for (a in areas) {
            assertEquals(a.id, a.id == StorageCatalogue.ID_PEOPLE_AND_PLACES, StorageCatalogue.touchesWatchNames(listOf(a)))
        }
        assertTrue(StorageCatalogue.touchesWatchNames(areas))
        assertFalse(StorageCatalogue.touchesWatchNames(emptyList()))
    }

    @Test
    fun googleGeofencesNeedConfirmedRemovalOnlyWhenOnInOptimizedMode() {
        assertTrue(StorageCatalogue.geofencesNeedConfirmedRemoval(geoEnabled = true, optimizedMode = true))
        assertFalse(StorageCatalogue.geofencesNeedConfirmedRemoval(geoEnabled = true, optimizedMode = false))
        assertFalse(StorageCatalogue.geofencesNeedConfirmedRemoval(geoEnabled = false, optimizedMode = true))
        assertFalse(StorageCatalogue.geofencesNeedConfirmedRemoval(geoEnabled = false, optimizedMode = false))
    }

    // --- the words -------------------------------------------------------------------------------------------------

    @Test
    fun everyConfirmationSaysFilesSavedElsewhereAreNotDeleted() {
        for (a in areas) {
            assertTrue(a.id, notElsewhere in first(a))
        }
        assertTrue(notElsewhere in firstEverything())
        assertTrue(notElsewhere.contains("EXPORTS, PACKAGES, BACKUPS"))
        assertTrue(notElsewhere.contains("COPIED TO ANOTHER APP"))
    }

    @Test
    fun theWatchWarningAppearsForPeopleAndPlacesAndEverythingOnly() {
        for (a in areas) {
            val has = watchNote in first(a)
            assertEquals(a.id, a.id == StorageCatalogue.ID_PEOPLE_AND_PLACES, has)
        }
        assertTrue(watchNote in firstEverything())
        assertEquals("A PAIRED WATCH MAY KEEP NAMES UNTIL IT NEXT CONNECTS.", watchNote)
    }

    @Test
    fun theRestartIsAnnouncedExactlyWhereItHappens() {
        for (a in areas) {
            assertEquals(a.id, a.restartAfter, restartNote in first(a))
        }
        assertTrue(restartNote in firstEverything())
    }

    @Test
    fun backUpFirstIsOnlyOfferedWhereExportJsonCoversIt() {
        for (a in areas) assertEquals(a.id, a.coverage == Coverage.EXPORT_JSON, StorageCatalogue.offersBackupFirst(a))
        assertFalse(StorageCatalogue.offersBackupFirst(StorageCatalogue.area(StorageCatalogue.ID_TRAINING_DATA)))
        assertFalse(StorageCatalogue.offersBackupFirst(StorageCatalogue.area(StorageCatalogue.ID_TERMINAL_LOG)))
    }

    @Test
    fun anAreaNotInExportJsonNamesTheBackupThatDoesCoverIt() {
        fun note(id: String) = note(StorageCatalogue.area(id))
        assertTrue(note(StorageCatalogue.ID_TRAINING_DATA).contains("SAVE ALL TO A FILE"))
        assertTrue(note(StorageCatalogue.ID_TRAINING_DATA).contains("NOT IN EXPORT .JSON"))
        assertTrue(note(StorageCatalogue.ID_TRAINED_VOICE).contains("EXPORT VOICE BACKUP"))
        assertTrue(note(StorageCatalogue.ID_TRAINED_VOICE).contains("(AUDIO ARCHITECT)"))
        assertTrue(note(StorageCatalogue.ID_GIF_LIBRARY).contains("EXPORT DECK (.ZIP)"))
        for (id in listOf(StorageCatalogue.ID_TERMINAL_LOG, StorageCatalogue.ID_SAFETY_COPIES)) {
            assertTrue(id, note(id).contains("NOT BACKED UP"))
        }
    }

    @Test
    fun deleteEverythingNamesWhatExportJsonDoesNotCover() {
        val notIn = StorageCatalogue.everythingNotInExportJson().map { label(it) }
        for (label in listOf("TERMINAL LOG", "TRAINING DATA", "TRAINED VOICE", "GIF LIBRARY", "SAFETY COPIES", "TEMPORARY FILES")) {
            assertTrue("missing $label in $notIn", label in notIn)
        }
        for (label in listOf("MESSAGES AND DECKS", "EMERGENCY INFO CARD", "PEOPLE AND PLACES", "SETTINGS")) {
            assertFalse("$label is in EXPORT .JSON", label in notIn)
        }
        val everything = firstEverything().joinToString("\n")
        for (label in notIn) assertTrue(label, everything.contains(label))
    }

    @Test
    fun settingsSaysWhatItResetsAndWhatItKeeps() {
        val settings = StorageCatalogue.area(StorageCatalogue.ID_SETTINGS)
        assertTrue(holds(settings).contains("VOICE PROFILES"))
        assertTrue(holds(settings).contains("PRACTICE SCORES"))
        assertTrue(holds(settings).contains("OUTPUT DEVICE"))
        assertTrue(first(settings).any { it.contains("ORGANIC") && it.contains("FULL TEXT") })
        assertEquals(setOf(StorageCatalogue.KEY_TERMINAL_LOG), settings.prefsFilesClearedExcept.getValue(StorageCatalogue.FILE_ACK_PREFS))
    }

    @Test
    fun theSecondConfirmationWordsAreFixed() {
        assertEquals("THIS CANNOT BE UNDONE.", text.get(StorageCatalogue.CANNOT_UNDO))
    }

    // --- the amount stored -----------------------------------------------------------------------------------------

    @Test
    fun amountsAreDescribedAtTheirBoundaries() {
        assertEquals("NOTHING STORED", StorageCatalogue.describeAmount(text, 0, 0))
        assertEquals("1 ITEM, UNDER 1 KB", StorageCatalogue.describeAmount(text, 1, 1))
        assertEquals("2 ITEMS, UNDER 1 KB", StorageCatalogue.describeAmount(text, 1023, 2))
        assertEquals("2 ITEMS, 1 KB", StorageCatalogue.describeAmount(text, 1024, 2))
        assertEquals("3 ITEMS, 1023 KB", StorageCatalogue.describeAmount(text, 1024L * 1024L - 1, 3))
        assertEquals("3 ITEMS, 1.0 MB", StorageCatalogue.describeAmount(text, 1024L * 1024L, 3))
        assertEquals("1 ITEM, 12.5 MB", StorageCatalogue.describeAmount(text, (12.5 * 1024 * 1024).toLong(), 1))
    }

    @Test
    fun anEmptyFolderWithOneEmptyFileStillSaysSomethingIsThere() {
        // 1 item of 0 bytes is not "nothing stored": the file exists.
        assertEquals("1 ITEM, UNDER 1 KB", StorageCatalogue.describeAmount(text, 0, 1))
    }

    // --- the drift guard: every storage name the app uses must be decided here -------------------------------------

    @Test
    fun everyPreferenceFileAndFolderTheAppWritesIsInTheCatalogue() {
        val found = scanSource()
        // The guard is only worth something if the scan really sees the app's storage.
        assertTrue("scan found only ${found.prefs.keys}", found.prefs.size >= 12)
        for (known in listOf("ack_matrix_config", "ack_prefs", "ack_targets", "ack_install_state")) {
            assertTrue("scan missed the preference file $known", known in found.prefs)
        }
        for (known in listOf("recordings", "custom_voice", "auto_backups", "gif_library", "geo_maps", "training_capture")) {
            assertTrue("scan missed the folder $known", known in found.folders)
        }

        val knownPrefs = areas.flatMap { it.prefsFilesCleared + it.prefsFilesClearedExcept.keys + it.prefsKeysRemoved.keys }.toSet() +
            StorageCatalogue.everythingOnlyPrefsFiles
        val knownFolders = areas.flatMap { it.folders }.toSet() + StorageCatalogue.NOT_PERSONAL.keys

        val missingPrefs = found.prefs.filterKeys { it !in knownPrefs }
        val missingFolders = found.folders.filterKeys { it !in knownFolders }
        assertTrue(
            "The app stores data that DELETE DATA does not know about:\n" +
                missingPrefs.map { "  preference file '${it.key}'  (${it.value.joinToString()})" }.joinToString("\n") +
                (if (missingPrefs.isNotEmpty() && missingFolders.isNotEmpty()) "\n" else "") +
                missingFolders.map { "  folder '${it.key}'  (${it.value.joinToString()})" }.joinToString("\n") +
                "\nFix: add each name to an area in core/StorageCatalogue.kt -- prefsFilesCleared for a whole preference file, " +
                "prefsKeysRemoved for part of a shared one, folders for a folder under filesDir -- and decide how EXPORT .JSON or " +
                "another backup covers it. Only if it is not the person's data (a bundled asset), add it to NOT_PERSONAL with the reason.",
            missingPrefs.isEmpty() && missingFolders.isEmpty(),
        )
    }

    @Test
    fun everyPreferenceFileInstallStateOwnsIsInTheCatalogue() {
        val source = RepoFiles.read("app/src/main/java/com/example/besu/data/InstallState.kt")
        val list = Regex("OWNED_PREFS_FILES\\s*=\\s*listOf\\(([^)]*)\\)").find(source)?.groupValues?.get(1)
            ?: error("OWNED_PREFS_FILES not found in InstallState.kt")
        val owned = Regex("\"([^\"]+)\"").findAll(list).map { it.groupValues[1] }.toList()
        assertTrue("parsed only $owned", owned.size >= 10)
        val known = areas.flatMap { it.prefsFilesCleared + it.prefsFilesClearedExcept.keys + it.prefsKeysRemoved.keys }.toSet() +
            StorageCatalogue.everythingOnlyPrefsFiles
        val missing = owned.filterNot { it in known }
        assertTrue("InstallState owns preference file(s) the catalogue does not: $missing (add them to an area)", missing.isEmpty())
    }

    @Test
    fun theScannerSeesWhatItShouldAndIgnoresWhatItShould() {
        val sample = """
            val a = context.getSharedPreferences("alpha_prefs", Context.MODE_PRIVATE)
            private const val PREFS_NAME = "beta_prefs"
            private const val PREF_THEME = "not_a_file_key"
            // val c = context.getSharedPreferences("commented_out", 0)
            val d = File(context.applicationContext.filesDir, "gamma_dir")
            val e = java.io.File(context.filesDir, "delta_dir").apply { mkdirs() }
            private const val MAP_DIR_NAME = "epsilon_dir"
            private const val GIF_DIRECTORY = "zeta_dir"
            val f = File(context.cacheDir, "not_a_files_dir_folder")
        """.trimIndent()
        val found = scanText(sample, "Sample.kt", Found())
        assertEquals(setOf("alpha_prefs", "beta_prefs"), found.prefs.keys)
        assertEquals(setOf("gamma_dir", "delta_dir", "epsilon_dir", "zeta_dir"), found.folders.keys)
    }

    // --- scanning the source ---------------------------------------------------------------------------------------

    private class Found {
        val prefs = LinkedHashMap<String, MutableList<String>>()
        val folders = LinkedHashMap<String, MutableList<String>>()
    }

    private fun scanSource(): Found {
        val found = Found()
        RepoFiles.appSource.walkTopDown()
            .filter { it.isFile && it.extension == "kt" && it.name != "StorageCatalogue.kt" }
            .forEach { scanText(it.readText(Charsets.UTF_8), relative(it), found) }
        return found
    }

    private fun relative(file: File): String = file.relativeTo(RepoFiles.appSource).path.replace('\\', '/')

    private fun scanText(raw: String, where: String, into: Found): Found {
        val noBlock = raw.replace(Regex("/\\*.*?\\*/", RegexOption.DOT_MATCHES_ALL), "")
        val text = noBlock.lines().joinToString("\n") { it.substringBefore("//") }
        fun add(map: MutableMap<String, MutableList<String>>, name: String) { map.getOrPut(name) { mutableListOf() }.add(where) }
        Regex("getSharedPreferences\\(\\s*\"([^\"]+)\"").findAll(text).forEach { add(into.prefs, it.groupValues[1]) }
        Regex("\\bPREFS\\w*\\s*=\\s*\"([^\"]+)\"").findAll(text).forEach { add(into.prefs, it.groupValues[1]) }
        Regex("File\\(\\s*[\\w.]*filesDir\\s*,\\s*\"([^\"]+)\"").findAll(text).forEach { add(into.folders, it.groupValues[1]) }
        Regex("\\b\\w*_(?:DIR|DIRECTORY|DIR_NAME)\\s*=\\s*\"([^\"]+)\"").findAll(text).forEach { add(into.folders, it.groupValues[1]) }
        return into
    }
}
