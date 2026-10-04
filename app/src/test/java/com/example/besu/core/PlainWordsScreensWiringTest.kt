// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The screens that show a label (docs/PLAIN_LANGUAGE.md) cannot be compiled here, so this reads them and holds them to the promises that keep PLAIN
 * WORDS safe: a label is display text only (never an id, a storage key, a tag or an event), nothing forces capitals on a translated word, every
 * key in the table is either drawn by a screen or on a short, stated list of ones not yet wired, and a wired label is not also drawn as its English
 * literal. The words themselves are checked in PlainLabelsTest; the switch in PlainWordsWiringTest.
 */
class PlainWordsScreensWiringTest {

    private val base = "app/src/main/java/com/example/besu"
    private val labelCall = Regex("""\b(labelFor|stringFormatLabel|slotLabel|poseLabel)\(""")

    private class Source(val path: String, val text: String)

    private fun sources(): List<Source> {
        val root = RepoFiles.file(base)
        return root.walkTopDown().filter { it.isFile && it.extension == "kt" }
            .map { Source(it.relativeTo(root).path.replace(File.separatorChar, '/'), it.readText(Charsets.UTF_8)) }
            .toList()
    }

    /** Comment text removed line by line (a block-comment regex would trip over a "*" + "/" inside a string literal). */
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line.substringBefore(" // ")
    }

    private fun usedKeys(): Set<String> = sources()
        .filter { it.path != "core/PlainLabels.kt" }
        .flatMap { Regex("""LabelKey\.([A-Z0-9_]+)""").findAll(noComments(it.text)).map { m -> m.groupValues[1] }.toList() }
        .toSet()

    // ---- the keys screens name are real ---------------------------------------------------------------------------------------------

    @Test
    fun everyKeyAScreenNamesIsInTheTable() {
        val real = LabelKey.values().map { it.name }.toSet()
        val unknown = usedKeys() - real
        assertTrue("screens name keys that are not in LabelKey: $unknown", unknown.isEmpty())
    }

    /** Keys not drawn by any screen yet. A key leaves this list the day a screen draws it, and the test says so. */
    private val notYetWired = setOf(
        "DECK",              // the word on its own; screens use DECK NAME / MANAGE DECKS / the type names
        "DECKS",
        "POSE",              // the group heading is drawn through poseLabel(); the bare word has no screen of its own yet
        "TARGET_ENTRY",      // ENTRY rows are named by the person
        "TARGET_CATEGORY",
        "GEO_GRID",          // the screen uses GEO_OPEN_GRID
        "TERMINAL"           // the Terminal's own plain-mode pass is a separate step
    )

    /** Slot names and pose names are drawn through slotLabel()/poseLabel(), which pick these keys by the stored name (PlainLabelsTest). */
    private val reachedByHelpers = LabelKey.values().map { it.name }.filter { it.startsWith("TWIST_") && it != "TWIST_SENS" || it.startsWith("POSE_") }.toSet()

    @Test
    fun everyKeyIsDrawnByAScreenOrIsOnTheShortListOfKeysNotYetWired() {
        val all = LabelKey.values().map { it.name }.toSet()
        val unwired = all - usedKeys() - reachedByHelpers
        assertEquals("keys no screen draws (wire them, or add them to notYetWired with a reason)", notYetWired, unwired)
    }

    @Test
    fun theHelpersThatReachSlotAndPoseKeysAreCalledByTheMatrixScreen() {
        val design = sources().first { it.path == "ui/DesignSystem.kt" }.text
        assertTrue(design.contains("slotLabel(node.label)"))
        assertTrue(design.contains("poseLabel(title)"))
    }

    // ---- a label is display text only ----------------------------------------------------------------------------------------------

    @Test
    fun labelsAreOnlyUsedByScreens_neverByStorageBackupSpeechOrTheRules() {
        val screens = listOf("data/", "backup/", "output/", "core/", "capture/", "training/", "wear/")
        val offenders = sources()
            .filter { s -> screens.any { s.path.startsWith(it) } && s.path != "core/PlainLabels.kt" }
            .filter { labelCall.containsMatchIn(noComments(it.text)) || it.text.contains("LocalPlainWords") || it.text.contains("PlainWordsState") }
            .map { it.path }
        assertTrue("these files must not read labels: $offenders", offenders.isEmpty())
    }

    @Test
    fun aLabelIsNeverAnArgumentOfAnIdStorageEventOrLogCall() {
        // The label call must not sit inside the parentheses of one of these. (A call that merely shares a line with one, such as a testTag on the
        // same button, is fine: only a label *inside* the call is a problem.)
        val intoLogic = Regex("""(putExtra|putString|onEvent|Interacted|TextCommitted|WatchInput|setActive\w*|setPhrase|savePhrase|upsert\w*|Log\.[a-z])\([^\n)]*\b(labelFor|stringFormatLabel|slotLabel|poseLabel)\(""")
        val offenders = sources().filter { it.path != "core/PlainLabels.kt" }.flatMap { s ->
            noComments(s.text).lines().withIndex().filter { intoLogic.containsMatchIn(it.value) }.map { "${s.path}:${it.index + 1}" }
        }
        assertTrue("a label reaches logic or storage: $offenders", offenders.isEmpty())
    }

    @Test
    fun aStoredPoseOrSlotNameIsNeverReplacedByItsLabelWhereItIsUsedAsAKey() {
        // MatrixCategory keeps `title` (the stored pose) for focus, logging and the override strip, and shows only poseLabel(title).
        val design = sources().first { it.path == "ui/DesignSystem.kt" }.text
        val at = design.indexOf("fun MatrixCategory(")
        assertTrue(at >= 0)
        val end = design.indexOf("\n}\n", at)
        val body = design.substring(at, end)
        assertTrue(body.contains("CommandRepository.setActiveCategoryFocus(\n                                context,\n                                title\n"))
        assertTrue(body.contains("category = title,"))
        assertTrue(body.contains("\"CONTEXT FOCUS: \$title\""))
        assertEquals("the pose label is shown once, in the heading", 1, Regex("""poseLabel\(""").findAll(body).count())
    }

    @Test
    fun noCapitalIsForcedOnALabel_theScriptsOfTheOtherLanguagesHaveNone() {
        val forcing = Regex("""\b(labelFor|stringFormatLabel|slotLabel|poseLabel)\([^\n]*\)\s*\.\s*(uppercase|lowercase|toUpperCase|toLowerCase|capitalize)\(""")
        val offenders = sources().flatMap { s ->
            noComments(s.text).lines().withIndex().filter { forcing.containsMatchIn(it.value) }.map { "${s.path}:${it.index + 1}" }
        }
        assertTrue("a label has its case forced: $offenders", offenders.isEmpty())
    }

    // ---- a wired label is not also drawn as its English literal -------------------------------------------------------------------------

    /**
     * Where an English label text may still appear as a whole string literal, because it is *logic* there and not a word on a screen: the default
     * name a new deck is saved with, the view-mode and log-type names, and the trigger mode. A label text found anywhere else means a screen still
     * draws it raw, and a person on PLAIN WORDS (or another language) would still see the jargon.
     */
    private val stillLogic: Map<String, Set<String>> = mapOf(
        "MATRIX" to setOf("MainActivity.kt", "decks/CreateDeckDialog.kt", "data/CommandRepository.kt"),
        "QUICK ACTIONS" to setOf("decks/CreateDeckDialog.kt", "data/CommandRepository.kt"),
        "EMERGENCY" to setOf("ui/DesignSystem.kt", "decks/CreateDeckDialog.kt", "decks/EmergencyDeck.kt", "data/CommandRepository.kt", "output/OutputService.kt"),
        "EMOJI" to setOf("decks/CreateDeckDialog.kt", "data/CommandRepository.kt"),
        "GIF" to setOf("decks/CreateDeckDialog.kt", "data/CommandRepository.kt"),
        "VARIABLE" to setOf("ui/DesignSystem.kt"),
        // The DELETE DATA confirmations use fixed, tested words (core/StorageCatalogue.kt); that surface is not part of this pass.
        "SAFETY COPIES" to setOf("core/StorageCatalogue.kt"),
        "TERMINAL LOG" to setOf("core/StorageCatalogue.kt")
    )

    @Test
    fun aWiredLabelIsNotAlsoDrawnAsItsEnglishLiteral() {
        val english = StringsXml.map(StringsXml.default)
        val offenders = mutableListOf<String>()
        for (name in usedKeys().sorted()) {
            val text = english["label_${name.lowercase()}"] ?: continue
            if (text.contains('%')) continue
            val literal = "\"$text\""
            for (s in sources()) {
                if (s.path.startsWith("help/") || s.path == "core/PlainLabels.kt") continue
                if (stillLogic[text]?.contains(s.path) == true) continue
                val hits = noComments(s.text).lines().withIndex().filter { it.value.contains(literal) }
                hits.forEach { offenders += "${s.path}:${it.index + 1}  $literal" }
            }
        }
        assertTrue("a wired label is still drawn as a literal (use labelFor, or list it as logic): $offenders", offenders.isEmpty())
    }

    @Test
    fun theLogicLiteralsThatAreAllowedStillExist_soThisListCannotGoStale() {
        val all = sources().associate { it.path to noComments(it.text) }
        for ((text, files) in stillLogic) {
            for (path in files) {
                assertTrue("$path no longer holds \"$text\": remove it from stillLogic", all.getValue(path).contains("\"$text\""))
            }
        }
    }
}
