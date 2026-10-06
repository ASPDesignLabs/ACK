// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Source-reading guards for GIF import (decks/GifRepository.kt and decks/GifDeck.kt are Android files, so they cannot be run on
 * a JVM; this reads them, like DeckScreensWordingTest, ExportContentsTest and StorageCatalogueTest do). Two promises:
 *
 *  1. An import that fails after its file was created (over 20 MB, unreadable, not a GIF, a write error) leaves no file behind
 *     in gif_library/, and the exception the caller sees is the very one that was thrown, with its [GifImportFailure].
 *  2. A failed import leaves no empty category behind either.
 *
 * "Never delete a file a saved entry points at" is why the delete is safe: the file is named after a brand-new id and is only
 * ever removed until the entry that names it has been saved. DeckScreensWordingTest pins that each failure is thrown once, as
 * its typed reason; this pins where, and what happens to the file around it.
 */
class GifImportCleanupTest {
    private val base = "app/src/main/java/com/example/besu/decks"

    // Comment lines are dropped, as DeckScreensWordingTest does, so a word in an explanatory comment is never mistaken for a call.
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }

    private val repository = noComments(RepoFiles.read("$base/GifRepository.kt"))
    private val deck = noComments(RepoFiles.read("$base/GifDeck.kt"))

    private val importGif = RepoFiles.declarationOf(repository, "importGif")

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
        for (risky in listOf("openInputStream", "outputStream", "throw ", "isGifFile", "createCategory", "saveEntries")) {
            assertFalse("\"$risky\" runs before the try, so its failure would not clean up", gap.contains(risky))
        }

        // Every step that can fail, including the size limit, the writing and the three typed reasons that follow the file, is inside the try.
        for (step in listOf(
            "openInputStream(", "outputStream()", "MAX_GIF_SIZE_BYTES",
            "GifImportFailure.TOO_BIG", "GifImportFailure.UNREADABLE", "isGifFile(", "GifImportFailure.INVALID",
            "createCategory(", "saveEntries(",
        )) {
            val at = indexAfter(importGif, step, tryAt)
            assertTrue("\"$step\" is not inside the try", at in tryAt until finallyAt)
        }
    }

    @Test
    fun theFinallyDeletesTheFileUnlessTheEntryWasSaved() {
        val finallyAt = indexAfter(importGif, "finally {", 0)
        val finallyBody = importGif.substring(finallyAt)
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
        // try/finally rethrows the very same exception, so the caller (GifLabels.importError reads its GifImportFailure) sees what
        // was thrown. A catch here could swallow it or turn it into something that has no reason attached.
        assertFalse("importGif must not catch", Regex("\\bcatch\\s*[({]").containsMatchIn(importGif))
        // The one catch is runCatching, which wraps the whole body into the Result the dialog already handles.
        assertTrue(importGif.contains("return runCatching {"))
    }

    @Test
    fun everyFailureIsStillATypedReasonNeverASentence() {
        assertFalse("importGif must not throw a sentence", importGif.contains("error(\""))
        for (reason in listOf("NOT_A_GIF", "TOO_BIG", "UNREADABLE", "INVALID")) {
            assertEquals("importGif throws $reason once", 1, Regex("""throw GifImportException\(GifImportFailure\.$reason\)""").findAll(importGif).count())
        }
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
        // GifImportDialog is a top-level function, so take its text up to the next top-level declaration.
        val at = indexAfter(deck, "private fun GifImportDialog(", 0)
        val next = Regex("\n(private fun |@Composable|fun )").find(deck, at + 1)
        val dialog = deck.substring(at, next?.range?.first ?: deck.length)
        assertFalse("GifImportDialog must not call createCategory before importGif", dialog.contains("createCategory"))
        assertTrue("the dialog must hand the typed category name to importGif", dialog.contains("categoryName = categoryName"))
        assertTrue("a failure is still shown through the typed message", dialog.contains("GifLabels.importError(words, error)"))
        assertFalse("importGif no longer takes a category id", importGif.contains("categoryId: String"))
        // Nothing else in the screen creates a category on the way to an import.
        assertEquals(0, Regex("GifRepository\\.createCategory\\(").findAll(deck).count())
    }

    @Test
    fun createCategoryKeepsItsNameRules() {
        val create = RepoFiles.declarationOf(repository, "createCategory")
        assertTrue("trimmed", create.contains(".trim()"))
        assertTrue("capitals", create.contains(".uppercase()"))
        assertTrue("30 characters at most", create.contains(".take(30)"))
        assertTrue("the saved default name, from the one constant", create.contains(".ifBlank { GifLabels.STORED_DEFAULT_CATEGORY }"))
        assertEquals("the saved default name is unchanged", "UNCATEGORIZED", GifLabels.STORED_DEFAULT_CATEGORY)
        assertTrue("dedupes by name, ignoring case", create.contains("category.name.equals(cleanName, ignoreCase = true)"))
        assertTrue("returns the existing category instead of adding a second", create.contains("return existing"))
    }
}
