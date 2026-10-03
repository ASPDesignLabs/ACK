// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What can be checked from here about the older-backup rule's Android side (backup/TransferManager.kt, backup/AckBackup.kt,
 * data/StarterSeed.kt, settings/SettingsView.kt), none of which can be compiled without the Android SDK.
 */
class StarterRestoreWiringTest {

    private fun source(name: String) = RepoFiles.read("app/src/main/java/com/example/besu/$name")

    private fun bodyOf(text: String, name: String): String {
        val at = text.indexOf("fun $name(")
        assertTrue("fun $name( not found", at >= 0)
        val open = text.indexOf('{', text.indexOf(')', at))
        var depth = 0
        var i = open
        while (i < text.length) {
            if (text[i] == '{') depth++
            if (text[i] == '}') { depth--; if (depth == 0) return text.substring(open + 1, i) }
            i++
        }
        error("unbalanced braces in $name")
    }

    private val marker = "starterPhrasesSeeded"

    @Test
    fun theBackupFormatHasANullableMarker_soAnOlderFileReadsAsNull() {
        assertTrue(
            "AckBackup must declare `val $marker: Boolean? = null` (null means the file predates the starter phrases)",
            Regex("""val $marker: Boolean\? = null""").containsMatchIn(source("backup/AckBackup.kt"))
        )
    }

    @Test
    fun everyNewBackupSaysWhetherItsPhoneWasSeeded() {
        val body = bodyOf(source("backup/TransferManager.kt"), "buildBackup")
        assertTrue(
            "buildBackup must set $marker from StarterSeed.wasSeeded(context)",
            body.contains("$marker = StarterSeed.wasSeeded(context)")
        )
    }

    @Test
    fun aRestoreTakesBackUntouchedStarters_beforeItWritesTheFilesPhrases() {
        val body = bodyOf(source("backup/TransferManager.kt"), "applyBackupToStorage")
        val call = "StarterSeed.takeBackUntouchedStarters(context, backup.matrixData.keys, backup.$marker)"
        val callAt = body.indexOf(call)
        val writeAt = body.indexOf("matrixPrefs.edit()")
        assertTrue("applyBackupToStorage must call $call", callAt >= 0)
        assertTrue("the starters must be taken back BEFORE the file's own phrases are written", callAt < writeAt)
    }

    @Test
    fun theEdgeAsksTheTestedRuleWhatToTakeBack_andForgetsTheNoteForEach() {
        val body = bodyOf(source("data/StarterSeed.kt"), "takeBackUntouchedStarters")
        assertTrue(body.contains("StarterRestore.seededPhrases("))
        assertTrue(body.contains("StarterRestore.toTakeBack("))
        assertTrue("the note of a taken-back starter must be forgotten too", body.contains(".recordKey"))
        assertTrue("it must remove only the listed keys, never clear a file", !body.contains(".clear()"))
    }

    @Test
    fun theMarkerIsNotThePersonsData_soItIsOutOfTheFingerprintAndTheExportWarning() {
        // A new top-level field would otherwise make every existing phone's fingerprint change once after the update, and the
        // backup reminder would fire for no reason. The export warning lists it as a file-format field, not as stored data.
        assertTrue(marker in BackupFingerprint.IGNORED_FIELDS)
        assertTrue(marker in ExportContents.formatFields)
    }

    @Test
    fun theRestoreConfirmationSaysStartersYouNeverEditedGoBack() {
        val settings = source("settings/SettingsView.kt")
        val at = settings.indexOf("title = \"FULL RESTORE FROM JSON\"")
        assertTrue(at >= 0)
        val dialog = settings.substring(at, at + 3500)
        assertTrue("the FULL RESTORE confirmation must mention starter phrases", dialog.contains("starter phrases", ignoreCase = true))
        assertTrue("and that edited ones are never touched", dialog.contains("never touched", ignoreCase = true))
    }

    @Test
    fun aMarkerOfFalseOrNull_bothMeanTheFilesPhoneHadNoStarters() {
        // Pinned here too because the whole rule hangs on it: only an explicit true keeps the starters.
        val seeded = StarterRestore.seededPhrases(mapOf(StarterSets.recordKey("/std/id/0") to "Yes."))
        val current = mapOf("/std/id/0" to "Yes.")
        assertEquals(1, StarterRestore.toTakeBack(seeded, current, emptySet(), null).size)
        assertEquals(1, StarterRestore.toTakeBack(seeded, current, emptySet(), false).size)
        assertEquals(0, StarterRestore.toTakeBack(seeded, current, emptySet(), true).size)
    }
}
