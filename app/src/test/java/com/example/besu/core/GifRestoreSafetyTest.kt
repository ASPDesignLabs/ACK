// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Source-reading guard for `GifRepository.restoreEntry` (an Android file, so it cannot run on a JVM; what it relies on,
 * VerifiedFileReplace, is tested by running it in VerifiedFileReplaceTest). The rule: restore is merge-by-id, so the file a
 * backup names is often one a saved entry on this phone already uses. `restoreEntry` must therefore never write to, open for
 * writing, or delete that real file itself; the only way bytes reach it is through VerifiedFileReplace, after the signature check
 * passed on a staged copy. A change that goes back to `writeBytes` on the real file fails here.
 */
class GifRestoreSafetyTest {
    private val repository = RepoFiles.read("app/src/main/java/com/example/besu/decks/GifRepository.kt")
    private val restore = RepoFiles.functionBody(repository, "fun restoreEntry(")

    @Test
    fun theBytesReachTheRealFileOnlyThroughVerifiedFileReplace() {
        assertEquals(1, Regex("VerifiedFileReplace\\.replaceIfValid\\(destinationFile, gifBytes\\)").findAll(restore).count())
        assertTrue(repository.contains("import com.example.besu.core.VerifiedFileReplace"))
    }

    @Test
    fun restoreEntryNeverWritesOpensOrDeletesAFileItself() {
        for (forbidden in listOf(
            ".writeBytes(", ".writeText(", ".outputStream(", ".appendBytes(", ".delete()", ".deleteRecursively(", ".renameTo(",
            "FileOutputStream", "RandomAccessFile", "Files.", "copyTo(",
        )) {
            assertFalse("restoreEntry must not use \"$forbidden\" (the real file may be one a saved entry uses)", restore.contains(forbidden))
        }
    }

    @Test
    fun theRealFileIsOnlyNamedForTheHelperNeverTouchedDirectly() {
        // Every line that mentions destinationFile is its declaration or the helper call.
        val lines = restore.lines().filter { it.contains("destinationFile") }
        assertEquals("expected only the declaration and the helper call, got: $lines", 2, lines.size)
        assertTrue(lines[0].contains("val destinationFile = File(destinationDirectory, entry.fileName)"))
        assertTrue(lines[1].contains("VerifiedFileReplace.replaceIfValid(destinationFile, gifBytes)"))
    }

    @Test
    fun theSignatureCheckRunsOnTheStagedCopyNotTheRealFile() {
        assertTrue(restore.contains("{ staged ->"))
        assertTrue(restore.contains("isGifFile(staged)"))
        assertFalse(restore.contains("isGifFile(destinationFile)"))
    }

    @Test
    fun aRefusedPictureIsReportedAsAnErrorSoTheEntryIsSkipped() {
        val call = restore.indexOf("VerifiedFileReplace.replaceIfValid(")
        val check = restore.indexOf("if (!replaced)", call)
        val saved = restore.indexOf("saveEntries(", call)
        assertTrue("the result of the replace must be checked", check > call)
        assertTrue("the entry must only be saved after a successful replace", saved > check)
        assertTrue(restore.indexOf("is not a valid GIF.", check) in check until saved)
    }

    @Test
    fun theExistingSafetyChecksStillRunBeforeAnythingIsWritten() {
        val call = restore.indexOf("VerifiedFileReplace.replaceIfValid(")
        val name = restore.indexOf("is not a safe file name")
        val size = restore.indexOf("MAX_GIF_SIZE_BYTES")
        assertTrue(name in 0 until call)
        assertTrue(size in 0 until call)
        assertTrue("the safe-file-name pattern must be unchanged", restore.contains("^[A-Za-z0-9_\\\\-]{1,100}\\\\.gif$"))
    }
}
