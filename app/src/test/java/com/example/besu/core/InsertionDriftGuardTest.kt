// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Every insert button must behave the same way, and that only stays true if no screen goes back to splicing text into a field
 * itself. These tests read the app's source and fail if one does, and if any insert surface stops using the shared rule
 * (core/TextInsertion.kt, plus core/TokenSlots.kt where per-occurrence values are kept by position). The screens cannot be
 * compiled or run without the Android SDK, so this is what holds them in line.
 */
class InsertionDriftGuardTest {

    /** Files allowed to splice text themselves, each with the reason. Empty on purpose: add to it only with a real reason. */
    private val allowed: Map<String, String> = emptyMap()

    private class Hit(val file: String, val line: Int, val text: String)

    // `.replaceRange(` is how the old code spliced; `"$name {VAR}"` / `"$name [COMPUTER:..]"` is how the editors appended a token.
    private val replaceRange = Regex("""\.replaceRange\(""")
    private val appendedToken = Regex(""""[^"\n]*\$\{?\w+\}?\s+(\{VAR|\[COMPUTER:)""")

    private fun scanText(source: String, file: String): List<Hit> = source.lines().mapIndexedNotNull { i, raw ->
        val trimmed = raw.trim()
        if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*")) return@mapIndexedNotNull null
        val code = raw.substringBefore(" // ")
        if (replaceRange.containsMatchIn(code) || appendedToken.containsMatchIn(code)) Hit(file, i + 1, trimmed) else null
    }

    private fun scanSource(): List<Hit> {
        val root = RepoFiles.appSource
        return root.walkTopDown()
            .filter { it.isFile && it.extension == "kt" }
            .map { it to it.relativeTo(root).path.replace('\\', '/') }
            .filter { (_, rel) -> rel != "com/example/besu/core/TextInsertion.kt" && rel !in allowed }
            .flatMap { (f, rel) -> scanText(f.readText(Charsets.UTF_8), rel).asSequence() }
            .toList()
    }

    @Test
    fun noScreenSplicesTextIntoAFieldItself() {
        val hits = scanSource()
        assertTrue(
            "Text is being spliced into a field outside core/TextInsertion.kt:\n" +
                hits.joinToString("\n") { "  ${it.file}:${it.line}  ${it.text}" } +
                "\nFix: call TextInsertion.insert (and TokenSlots.realign where the phrase keeps values by position). " +
                "Only if there is a real reason, add the file to `allowed` in this test with that reason.",
            hits.isEmpty()
        )
    }

    @Test
    fun theScannerSeesWhatItShouldAndIgnoresWhatItShould() {
        val sample = """
            val a = text.replaceRange(1, 2, "x")
            updateTemplate("${'$'}tempText {VAR}")
            updateTemplate("${'$'}{template} [COMPUTER:HOME]")
            // val c = text.replaceRange(1, 2, "commented out")
            * text.replaceRange(1, 2, "in a doc comment")
            val d = "${'$'}name has a {VAR} later but not right after"
            val e = "plain [COMPUTER:HOME] text with no dollar before it"
            val f = text.substring(0, 1) + "x"
        """.trimIndent()
        val hits = scanText(sample, "Sample.kt")
        assertEquals(listOf(1, 2, 3), hits.map { it.line })
    }

    @Test
    fun theScannerReallyReadsTheAppsSource() {
        val files = RepoFiles.appSource.walkTopDown().count { it.isFile && it.extension == "kt" }
        assertTrue("scan found only $files Kotlin files", files > 100)
    }

    // ---- each surface really uses the shared rule ----------------------------------------------------------------------

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

    @Test
    fun everyInsertSurfaceCallsTheSharedRule() {
        val surfaces = listOf(
            "composer/StatementComposerView.kt" to "insertTextAtCursor",
            "ui/DesignSystem.kt" to "insertAtTrigger",
            "MainActivity.kt" to "insertIntoManualOverride",
            "ui/DesignSystem.kt" to "insertTokenAtCursor",
            "decks/QuickActionsDeck.kt" to "insertComputerTagAtCursor",
        )
        for ((file, fn) in surfaces) {
            assertTrue("$fn in $file must call TextInsertion.insert(", bodyOf(source(file), fn).contains("TextInsertion.insert("))
        }
    }

    @Test
    fun theTerminalPassesTheTriggerAsTheReplaceRange() {
        val body = bodyOf(source("ui/DesignSystem.kt"), "insertAtTrigger")
        assertTrue(body.contains("InsertMode.WORD, span)"))
    }

    @Test
    fun theEditorsShiftTheirPositionBasedValuesBeforeSaving() {
        val matrix = bodyOf(source("ui/DesignSystem.kt"), "insertTokenAtCursor")
        assertTrue(matrix.contains("SlotFamily.VARIABLE"))
        assertTrue(matrix.contains("SlotFamily.COMPUTER"))
        assertTrue(matrix.indexOf("TokenSlots.realign(") < matrix.indexOf("updateTemplate(result.text)"))
        val quick = bodyOf(source("decks/QuickActionsDeck.kt"), "insertComputerTagAtCursor")
        assertTrue(quick.contains("SlotFamily.COMPUTER"))
        assertTrue(quick.indexOf("TokenSlots.realign(") < quick.indexOf("updateTemplate(result.text)"))
    }

    @Test
    fun aFreshlyOpenedEditorHasItsCursorAtTheEnd_soTheFirstInsertionStillLandsLast() {
        assertTrue(source("ui/DesignSystem.kt").contains("TextFieldValue(rawPhrase, TextRange(rawPhrase.length))"))
        assertTrue(source("decks/QuickActionsDeck.kt").contains("TextFieldValue(slot.template, TextRange(slot.template.length))"))
    }

    @Test
    fun theEditorsStillFireTheirHelpEventsAndKeepTheirTags() {
        val design = source("ui/DesignSystem.kt")
        val at = design.indexOf("insertTokenAtCursor(\"[COMPUTER:\${computerCategory.id}]\")")
        assertTrue(at >= 0)
        assertTrue(
            "the MATRIX_INSERT_COMPUTER_TAG event must still fire right after the insertion",
            design.substring(at, at + 400).contains("HelpEvent.Interacted(") &&
                design.substring(at, at + 400).contains("AckTags.MATRIX_INSERT_COMPUTER_TAG")
        )
        assertTrue(design.contains(".testTag(AckTags.MATRIX_INSERT_COMPUTER_TAG)"))
        assertTrue(design.contains(".helpTarget(AckTags.MATRIX_INSERT_COMPUTER_TAG, primaryColor)"))
        val quick = source("decks/QuickActionsDeck.kt")
        assertTrue(quick.contains(".testTag(AckTags.QUICK_ACTION_INSERT_COMPUTER_TAG)"))
        assertTrue(quick.contains(".helpTarget(AckTags.QUICK_ACTION_INSERT_COMPUTER_TAG, primaryColor)"))
    }

    @Test
    fun aCursorOnlyChangeIsNotATemplateEdit() {
        // Moving the cursor makes onValueChange fire with the same text. Treating that as an edit would re-save the phrase (and could
        // wrongly flag a recording as out of date) every time the cursor moved.
        assertTrue(source("ui/DesignSystem.kt").contains("if (newValue.text != tempText) {"))
        assertTrue(source("decks/QuickActionsDeck.kt").contains("if (newValue.text != template) {"))
    }

    @Test
    fun theMatrixEditorsClearFlows_resetTheCursorFieldToo() {
        // tempText is reset directly by the clear flows; the cursor-aware field must follow or it would show the old text.
        val resets = Regex("""tempText = ""\s*templateValue = TextFieldValue\(""\)""").findAll(source("ui/DesignSystem.kt")).count()
        assertEquals(2, resets)
    }
}
