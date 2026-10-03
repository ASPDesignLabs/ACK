// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * docs/STARTER_PHRASES.md is what the developer and an SLP read to review the sets, so it must say exactly what the app will
 * seed. The tables in it sit between two marker lines and are compared, character for character, with what
 * StarterSets.documentTables() produces from the data the app uses.
 */
class StarterPhrasesDocTest {

    private val begin = "<!-- STARTER-TABLES:BEGIN (checked against core/StarterSets.kt; edit the code, not this block) -->"
    private val end = "<!-- STARTER-TABLES:END -->"

    private fun docTables(): String {
        val doc = RepoFiles.read("docs/STARTER_PHRASES.md")
        val from = doc.indexOf(begin)
        val to = doc.indexOf(end)
        assertTrue("docs/STARTER_PHRASES.md has lost its begin marker line", from >= 0)
        assertTrue("docs/STARTER_PHRASES.md has lost its end marker line", to > from)
        return doc.substring(from + begin.length, to).trim()
    }

    @Test
    fun theDocumentShowsExactlyWhatTheAppWillSeed() {
        assertEquals(StarterSets.documentTables().trim(), docTables())
    }

    @Test
    fun everyPhraseInTheDocumentIsInTheCode_andNothingIsLeftOut() {
        val table = docTables()
        val phrases = StarterSets.matrixPhrases.map { it.phrase } + StarterSets.quickActionsGroups.flatMap { g -> g.slots.map { it.phrase } }
        for (p in phrases) assertTrue("'$p' is missing from the document", table.contains("| $p |"))
    }

    @Test
    fun theTablesCannotBeBrokenByATableCharacterInAPhrase() {
        val cells = StarterSets.matrixPhrases.flatMap { listOf(it.phrase, it.gesture) } +
            StarterSets.quickActionsGroups.flatMap { g -> listOf(g.label) + g.slots.flatMap { listOf(it.label, it.phrase) } }
        for (c in cells) {
            assertFalse("'$c' has a | in it", c.contains('|'))
            assertFalse("'$c' has a line break in it", c.contains('\n'))
        }
    }

    @Test
    fun everyKindOfMessageHasAPlainNameAndTheNamesAreDistinct() {
        val names = StarterFunction.values().map { it.plain }
        assertTrue(names.all { it.isNotBlank() })
        assertEquals(names.size, names.toSet().size)
    }

    @Test
    fun theDocumentSaysItIsADraftAndNamesWhoIsToReviewIt() {
        val doc = RepoFiles.read("docs/STARTER_PHRASES.md")
        assertTrue(doc.contains("DRAFT"))
        assertTrue(doc.contains("new install", ignoreCase = true))
    }
}
