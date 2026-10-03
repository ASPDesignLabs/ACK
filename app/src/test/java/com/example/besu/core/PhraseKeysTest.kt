// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Where a Matrix phrase is stored. One function now serves both the repository (which reads and writes phrases) and the
 * starter seed (which must write to exactly the same keys), so the two can never disagree about a key.
 */
class PhraseKeysTest {

    @Test
    fun theDefaultDeckAndProfile_useThePathItself() {
        assertEquals("/std/id/0", PhraseKeys.storageKey("DEFAULT", "DEFAULT", "/std/id/0"))
    }

    @Test
    fun anotherDeck_isPrefixedWithItsId() {
        assertEquals("DECK_1_/std/id/0", PhraseKeys.storageKey("DECK_1", "DEFAULT", "/std/id/0"))
    }

    @Test
    fun anotherProfile_isPrefixedWithItsName() {
        assertEquals("WORK_/std/id/0", PhraseKeys.storageKey("DEFAULT", "WORK", "/std/id/0"))
    }

    @Test
    fun anotherDeckAndProfile_putTheDeckFirst() {
        assertEquals("DECK_1_WORK_/std/id/0", PhraseKeys.storageKey("DECK_1", "WORK", "/std/id/0"))
    }

    @Test
    fun aCustomContextPath_isKeptAsIs() {
        assertEquals("DECK_1_/custom/MY LAYER/2", PhraseKeys.storageKey("DECK_1", "DEFAULT", "/custom/MY LAYER/2"))
    }

    // The repository must USE this function, not keep a private copy that could drift from it.
    private val repository = RepoFiles.read("app/src/main/java/com/example/besu/data/CommandRepository.kt")

    @Test
    fun theRepositoryBuildsItsKeysWithThisFunction() {
        assertTrue(
            "CommandRepository.generateStorageKey must delegate to PhraseKeys.storageKey",
            Regex("""fun generateStorageKey\([^)]*\)\s*:\s*String\s*=\s*PhraseKeys\.storageKey\(""").containsMatchIn(repository)
        )
        assertTrue(
            "CommandRepository.kt must import com.example.besu.core.PhraseKeys",
            repository.contains("import com.example.besu.core.PhraseKeys")
        )
    }

    @Test
    fun theRepositoryNoLongerBuildsKeysItself() {
        // The two halves of the old key recipe, now only in PhraseKeys.
        assertTrue(!repository.contains("""val deckPrefix = if (deckId == "DEFAULT")"""))
        assertTrue(!repository.contains("""val profilePrefix = if (profile == "DEFAULT")"""))
    }
}
