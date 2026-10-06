// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Source-reading guards for GIF import (decks/GifRepository.kt and decks/GifDeck.kt are Android files, so they cannot be run on
 * a JVM; this reads them, like ExportContentsTest and StorageCatalogueTest read AckBackup.kt). Kept in core/ because that is the
 * test folder tools/kotlin_check compiles. Two promises:
 *
 *  1. An import that fails after its file was created (over 20 MB, unreadable, not a GIF, a write error) leaves no file behind
 *     in gif_library/, and the original exception is what the caller sees.
 *  2. A failed import leaves no empty category behind either.
 *
 * "Never delete a file a saved entry points at" is why the delete is safe: the file is named after a brand-new id and is only
 * ever removed until the entry that names it has been saved.
 */
class GifImportCleanupTest {
    private val repository = RepoFiles.read("app/src/main/java/com/example/besu/decks/GifRepository.kt")
    private val deck = RepoFiles.read("app/src/main/java/com/example/besu/decks/GifDeck.kt")

    private val importGif = bodyOf(repository, "fun importGif(")

    // Comments are stripped: the importGif comments name saveEntries and the finally, and must not count as calls.
    private fun bodyOf(source: String, signature: String): String = RepoFiles.functionBody(source, signature)

    private fun indexAfter(text: String, needle: String, from: Int): Int {
        val i = text.indexOf(needle, from)
        assertTrue("\"$needle\" not found after offset $from", i >= 0)
        return i
    }

    // --- 1. the file --------------------------------------------------------------------------------------------------

    @Test
    fun everythingThatCanFailAfterTheFileIsCreatedIsInsideATryWithAFinally() {
        val created = indexAfter(importGif, "val destinationFile = File(", 0)
        val tryAt = indexAfter(importGif, "try {", created)
        val finallyAt = indexAfter(importGif, "finally {", tryAt)

        // Nothing that can throw sits between creating the File object and the try.
        val gap = importGif.substring(created, tryAt)
        for (risky in listOf("openInputStream", "outputStream", "error(", "isGifFile", "createCategory", "saveEntries")) {
            assertFalse("\"$risky\" runs before the try, so its failure would not clean up", gap.contains(risky))
        }

        // Every step that can fail, including the size limit and the writing, is inside the try.
        for (step in listOf(
            "openInputStream(", "outputStream()", "MAX_GIF_SIZE_BYTES", "GIF exceeds", "isGifFile(",
            "Selected file is not a valid GIF", "createCategory(", "saveEntries(",
        )) {
            val at = indexAfter(importGif, step, tryAt)
            assertTrue("\"$step\" is not inside the try", at in tryAt until finallyAt)
        }
    }

    @Test
    fun theFinallyDeletesTheFileUnlessTheEntryWasSaved() {
        val finallyAt = indexAfter(importGif, "finally {", 0)
        val finallyBody = bodyOf(importGif.substring(finallyAt), "finally {")
        assertTrue("the finally must delete destinationFile", finallyBody.contains("destinationFile.delete()"))
        assertTrue("the delete must be skipped once the entry is saved", finallyBody.contains("if (!entrySaved)"))

        // The flag starts false, before the try, and is set exactly once, only after the entry has been written.
        val created = indexAfter(importGif, "val destinationFile = File(", 0)
        val tryAt = indexAfter(importGif, "try {", created)
        val declared = indexAfter(importGif, "var entrySaved = false", created)
        assertTrue("entrySaved must be declared before the try", declared < tryAt)

        val sets = Regex("entrySaved\\s*=\\s*true").findAll(importGif).toList()
        assertEquals("entrySaved must be set to true in exactly one place", 1, sets.size)
        val saved = indexAfter(importGif, "saveEntries(", tryAt)
        assertTrue("entrySaved is set before the entry is saved", sets.single().range.first > saved)
        assertTrue("entrySaved must be set inside the try", sets.single().range.first < finallyAt)
    }

    @Test
    fun noCatchInImportGifCanSwallowOrReplaceTheFailure() {
        // try/finally rethrows the very same exception, so the caller (the IMPORT button shows error.message) sees what was
        // thrown. A catch here could swallow it or turn it into something else.
        assertFalse("importGif must not catch", Regex("\\bcatch\\s*[({]").containsMatchIn(importGif))
        // The one catch is runCatching, which wraps the whole body into the Result the dialog already handles.
        assertTrue(importGif.contains("return runCatching {"))
    }

    @Test
    fun theFileIsNamedAfterAFreshIdSoTheDeleteCanNeverHitASavedGif() {
        assertTrue(importGif.contains("val entryId = \"GIF_\${UUID.randomUUID()}\""))
        assertTrue(importGif.contains("val fileName = \"\$entryId.gif\""))
        assertTrue(importGif.contains("val destinationFile = File(destinationDirectory, fileName)"))
        assertTrue("the entry must be saved under the same id and file name", importGif.contains("id = entryId") && importGif.contains("fileName = fileName"))
    }

    // --- 2. the category ---------------------------------------------------------------------------------------------

    @Test
    fun theCategoryIsCreatedOnlyAfterTheFileHasPassedItsChecks() {
        val checked = indexAfter(importGif, "isGifFile(destinationFile)", 0)
        val category = indexAfter(importGif, "createCategory(context, categoryName)", 0)
        val saved = indexAfter(importGif, "saveEntries(", 0)
        assertTrue("createCategory must come after the GIF check", category > checked)
        assertTrue("createCategory must come before the entry is saved", category < saved)
        assertEquals("importGif must create the category in one place", 1, Regex("createCategory\\(").findAll(importGif).count())
    }

    @Test
    fun theImportButtonNoLongerCreatesTheCategoryItself() {
        val dialog = bodyOf(deck, "private fun GifImportDialog(")
        assertFalse("GifImportDialog must not call createCategory before importGif", dialog.contains("createCategory"))
        assertTrue("the dialog must hand the typed category name to importGif", dialog.contains("categoryName = categoryName"))
        assertFalse("importGif no longer takes a category id", importGif.contains("categoryId: String"))
        // Nothing else in the app creates a category on the way to an import.
        assertEquals(0, Regex("GifRepository\\.createCategory\\(").findAll(deck).count())
    }

    @Test
    fun createCategoryKeepsItsNameRules() {
        val create = bodyOf(repository, "fun createCategory(")
        assertTrue("trimmed", create.contains(".trim()"))
        assertTrue("capitals", create.contains(".uppercase()"))
        assertTrue("30 characters at most", create.contains(".take(30)"))
        assertTrue("the saved default name", create.contains(".ifBlank { \"UNCATEGORIZED\" }"))
        assertTrue("dedupes by name, ignoring case", create.contains("category.name.equals(cleanName, ignoreCase = true)"))
        assertTrue("returns the existing category instead of adding a second", create.contains("return existing"))
    }
}
