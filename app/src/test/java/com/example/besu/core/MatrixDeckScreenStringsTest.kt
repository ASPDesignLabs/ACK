// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Matrix deck screen (the group headings, ACTIVATE, the shared-value strip and its dialog, a recorded row, and the header row above every screen) now
 * reads its words from string resources, so the five translations reach it. These files cannot be compiled here, so this reads them: every string the screen
 * names exists, none is left unused, and none of the old English literals is drawn any more. Words that are app logic (deck ids, view-mode names, log text,
 * the stored pose names) are untouched and are listed where a test needs to say so.
 */
class MatrixDeckScreenStringsTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line.substringBefore(" // ")
    }
    private val english get() = StringsXml.map(StringsXml.default)

    private val groups = listOf("matrix_", "header_", "composer_")

    private fun allSources(): List<String> =
        RepoFiles.file(base).walkTopDown().filter { it.isFile && it.extension == "kt" }.map { noComments(it.readText(Charsets.UTF_8)) }.toList()

    @Test
    fun everyStringTheScreenNamesExists_andNoMatrixOrHeaderStringIsLeftUnused() {
        val used = allSources().flatMap { Regex("""R\.string\.((?:matrix|header|composer|common)_[a-z_]+)""").findAll(it).map { m -> m.groupValues[1] }.toList() }.toSet()
        val defined = english.keys.filter { name -> groups.any { name.startsWith(it) } || name.startsWith("common_") }.toSet()
        assertEquals("named but not defined: ${used - defined}", emptySet<String>(), used - defined)
        val unused = defined.filter { name -> name !in used }
        assertTrue("defined but never used: $unused", unused.isEmpty())
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawnByTheMatrixScreenOrTheHeader() {
        val design = noComments(source("ui/DesignSystem.kt"))
        val main = noComments(source("MainActivity.kt"))
        val gone = listOf(
            "\"ACTIVATE\"", "\"ACTIVE\"", "\"[EXPAND ▼]\"", "\"[COLLAPSE ▲]\"", "\"NO SHARED VALUE SET\"", "\"SHARED OVERRIDE VALUE\"",
            "\"● RECORDED\"", "\"[MANAGE CONTEXT]\"", "\"SEQUENCE :: ", "\"ROOT \$tag\"", "\"ROOT \$category",
            "Enabled tags replace matching",
        )
        for (literal in gone) assertFalse("DesignSystem.kt still draws $literal", design.contains(literal))
        for (literal in listOf("\"DECK: \"", "\"PROFILE: \"", "\"COMPUTER: \"", "ACTIVE\" else \"OFF\"")) {
            assertFalse("MainActivity.kt still draws $literal", main.contains(literal))
        }
    }

    @Test
    fun theHeaderNamesTheDeckThroughTheLabelTable_soPlainWordsShowsPage() {
        val main = noComments(source("MainActivity.kt"))
        assertTrue(main.contains("text = \"\${labelFor(LabelKey.DECK)}: \","))
        assertEquals("PAGE", english.getValue("label_deck_plain"))
    }

    @Test
    fun theStoredPoseNamesAndTheLogTextAreStillTheEnglishNamesTheAppUses() {
        val design = noComments(source("ui/DesignSystem.kt"))
        val category = design.substring(design.indexOf("fun MatrixCategory("), design.indexOf("\n}\n", design.indexOf("fun MatrixCategory(")))
        // The heading is a resource. (The MANAGE CONTEXT dialog's own "ROOT :: " row is the next screen's.)
        assertFalse(category.contains("\"ROOT :: "))
        // The focus log line and the replay source are logic, not words on the screen.
        assertTrue(category.contains("\"CONTEXT FOCUS: \$title\""))
        assertTrue(category.contains("\"MTX/\${title.uppercase()}\""))
        // The dialog is told the displayed pose name, never the stored one, for its title only.
        val dialog = design.substring(design.indexOf("fun RootOverrideValueDialog("), design.indexOf("fun MatrixNodeItem("))
        assertTrue(dialog.contains("stringResource(R.string.matrix_override_title, poseLabel(category), tag)"))
        assertTrue("the saved value still goes under the stored pose", dialog.contains("AutocompleteScopeInfo.rootOverride(category, tag)"))
    }

    @Test
    fun theFormatStringsTakeTheArgumentsTheScreenPasses() {
        assertEquals(listOf("%1\$s"), StringsXml.placeholders(english.getValue("matrix_sequence_header")))
        assertEquals(listOf("%1\$s"), StringsXml.placeholders(english.getValue("matrix_root_heading")))
        assertEquals(listOf("%1\$s"), StringsXml.placeholders(english.getValue("matrix_root_tag")))
        assertEquals(listOf("%1\$s", "%2\$s"), StringsXml.placeholders(english.getValue("matrix_override_title")))
        assertEquals(listOf("%1\$d"), StringsXml.placeholders(english.getValue("header_computer_active")))
        val design = noComments(source("ui/DesignSystem.kt"))
        assertTrue(design.contains("stringResource(R.string.matrix_sequence_header, deckName)"))
        assertTrue(noComments(source("MainActivity.kt")).contains("stringResource(R.string.header_computer_active, computerActiveCount)"))
    }

    @Test
    fun theHintKeepsItsTokens_andIsASentenceNotCapitals() {
        val hint = english.getValue("matrix_root_hint")
        assertTrue(hint.contains("{VAR:A}") && hint.contains("{VAR:B}") && hint.contains("{VAR:C}"))
        assertFalse(hint == hint.uppercase())
    }
}
