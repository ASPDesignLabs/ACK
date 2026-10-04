// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The MANAGE CONTEXT dialogs (ui/ManageContextDialog.kt: the list, ADD, RENAME, REASSIGN and the delete question) read their words from string resources, in the chosen
 * language. They cannot be compiled or run here, so this reads them: the old English literals are gone, every string named exists and none is unused, a pose is drawn through
 * poseLabel() but what is saved and compared is still the stored name, a layer's own name is shown as the person typed it, each word sits on the control that does what it
 * says, and a layer is only deleted from the confirmation.
 */
class ManageContextWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val dialog get() = file("ui/ManageContextDialog.kt")
    private val design get() = file("ui/DesignSystem.kt")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val contextNames get() = english.keys.filter { it.startsWith("context_") }

    @Test
    fun everyStringTheDialogsNameExists_andNoneIsLeftUnused() {
        val referenced = Regex("""R\.string\.((?:context_|common_|matrix_root_heading)[a-z_]*)""").findAll(dialog).map { it.groupValues[1] }.toSet()
        val missing = referenced.filter { it !in english.keys }
        assertEquals("named but not defined: $missing", emptyList<String>(), missing)
        val unused = contextNames.toSet() - referenced
        assertTrue("defined but never used: $unused", unused.isEmpty())
        for (name in listOf("common_done", "common_abort", "common_cancel", "common_create", "common_delete", "common_confirm", "common_confirm_delete", "common_rename", "matrix_root_heading")) {
            assertTrue("$name is not used by the dialogs", name in referenced)
        }
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawn() {
        val gone = listOf(
            "\"MANAGE CONTEXT\"", "\"DONE\"", "The three base poses are permanent", "\"+ ADD CONTEXT\"", "\"CONFIRM DELETE\"", "\"ABORT\"", "Permanently remove context layer", "\"DELETE PERMANENTLY\"",
            "\"CANCEL\"", "\"ROOT :: ", "\"[IMMUTABLE]\"", "\"BASED ON: ", "\"REASSIGN\"", "\"RENAME\"", "\"DELETE\"", "\"ADD CONTEXT\"", "\"CONTEXT NAME\"", "\"E.G. SCHOOL, WORK, PLAY\"",
            "\"ASSIGN TO POSE\"", "The physical gesture that activates", "\"CREATE\"", "\"RENAME CONTEXT\"", "Every saved phrase, variable, and override", "\"CONFIRM RENAME\"", "\"REASSIGN POSE // ",
            "Choose which pose's physical gesture", "\"CONFIRM\"", "text = pose,",
        )
        for (literal in gone) assertFalse("ManageContextDialog.kt still holds $literal", dialog.contains(literal))
        assertTrue("an explicit R import outside the base package", dialog.contains("import com.example.besu.R"))
        assertTrue(dialog.contains("import androidx.compose.ui.res.stringResource"))
        // The dialogs left DesignSystem.kt whole: only the call remains there.
        for (moved in listOf("fun ManageContextDialog(", "fun PosePicker(", "fun AddContextDialog(", "fun RenameContextDialog(", "fun ReassignPoseDialog(")) assertFalse("$moved is still in DesignSystem.kt", design.contains(moved))
        assertTrue(design.contains("ManageContextDialog(\n            context = context,"))
    }

    // ---- poses: shown through poseLabel(), saved and compared by their stored names --------------------------------------------------

    @Test
    fun aPoseIsDrawnThroughPoseLabel_butWhatIsSavedAndComparedIsTheStoredName() {
        assertTrue(dialog.contains("stringResource(R.string.matrix_root_heading, poseLabel(pose))"))
        assertTrue(dialog.contains("stringResource(R.string.context_based_on, poseLabel(entry.basePose))"))
        assertTrue(dialog.contains("text = poseLabel(pose),"))
        // The picker still selects, and the dialogs still save and validate, the stored pose names.
        assertTrue(dialog.contains(".clickable { onSelect(pose) }"))
        assertTrue(dialog.contains("val isSelected = pose == selected"))
        assertTrue(dialog.contains("var basePose by remember { mutableStateOf(POSE_CATEGORIES[0]) }"))
        assertTrue(dialog.contains("onCreate(cleanName, basePose)"))
        assertTrue(dialog.contains("onConfirm(basePose)"))
        assertTrue(dialog.contains("cleanName !in POSE_CATEGORIES"))
    }

    @Test
    fun aLayersOwnNameIsShownAsTheTypedName_andTypedNamesAreStillUppercasedAndCapped() {
        assertTrue(dialog.contains("text = entry.name,"))
        assertTrue(dialog.contains("stringResource(R.string.context_reassign_title, entry.name)"))
        assertTrue(dialog.contains("stringResource(R.string.context_delete_body, deleting.name)"))
        assertEquals("two text fields", 2, Regex("""onValueChange = \{ name = it\.uppercase\(\)\.take\(24\) \}""").findAll(dialog).count())
        assertFalse("a layer's name is not a label", Regex("""poseLabel\((?:entry\.name|deleting\.name|name)\)""").containsMatchIn(dialog))
    }

    // ---- each word sits on the control that does what it says ----------------------------------------------------------------------------

    private fun wordThenAction(word: String, action: String, within: Int = 300) =
        Regex("""R\.string\.${Regex.escape(word)}[\s\S]{0,$within}?${Regex.escape(action)}""").containsMatchIn(dialog)

    @Test
    fun everyButtonWordIsOnTheControlThatDoesWhatItSays() {
        // The tap is on the box and the word is drawn inside it, so here the action comes first.
        assertTrue("+ ADD CONTEXT opens the add dialog", Regex("""showAddDialog = true[\s\S]{0,500}?R\.string\.context_add\)""").containsMatchIn(dialog))
        assertTrue("REASSIGN", wordThenAction("context_reassign)", "onClick = onReassign"))
        assertTrue("RENAME", wordThenAction("common_rename)", "onClick = onRename"))
        assertTrue("DELETE in a row only asks", wordThenAction("common_delete)", "onClick = onDelete"))
        assertTrue("DELETE PERMANENTLY removes", wordThenAction("context_delete_permanently)", "CommandRepository.removeCustomContextEntry(context, deleting.name)", 400))
        assertTrue("CANCEL in the question closes it", wordThenAction("common_cancel)", "deletingEntry = null", 400))
        assertTrue("CREATE creates", wordThenAction("common_create)", "onCreate(cleanName, basePose)", 400))
        assertTrue("CONFIRM RENAME renames", wordThenAction("context_confirm_rename)", "onConfirm(cleanName)", 400))
        assertTrue("CONFIRM reassigns", wordThenAction("common_confirm)", "onConfirm(basePose)", 300))
        assertTrue("the list closes with DONE", dialog.contains("dismissLabel = stringResource(R.string.common_done)"))
        assertTrue("the delete question's header closes with ABORT", dialog.contains("dismissLabel = stringResource(R.string.common_abort)"))
        assertTrue("the delete question's title", dialog.contains("title = stringResource(R.string.common_confirm_delete),"))
    }

    @Test
    fun theTwoArrowsMoveALayerUpAndDownAndAreGreyedAtTheEnds() {
        // Glyphs are not words, but a swapped arrow would move a layer the wrong way, so they are held too.
        assertTrue(dialog.contains("text = \"▲\",\n                    enabled = canMoveUp,"))
        assertTrue(dialog.contains("text = \"▼\",\n                    enabled = canMoveDown,"))
        assertTrue(Regex("""onMoveUp = \{\s*CommandRepository\.moveCustomContextEntry\(\s*context, entry\.name, -1""").containsMatchIn(dialog))
        assertTrue(Regex("""onMoveDown = \{\s*CommandRepository\.moveCustomContextEntry\(\s*context, entry\.name, 1""").containsMatchIn(dialog))
        assertTrue(dialog.contains("canMoveUp = index > 0,"))
        assertTrue(dialog.contains("canMoveDown = index < entries.lastIndex,"))
    }

    @Test
    fun aLayerIsOnlyDeletedFromTheConfirmation_andTheValidationIsAsItWas() {
        assertEquals("one call that removes a layer", 1, Regex("""removeCustomContextEntry\(""").findAll(dialog).count())
        assertTrue(dialog.contains("onDelete = { deletingEntry = entry }"))
        // CREATE and CONFIRM RENAME stay greyed until the name is valid, exactly as before.
        assertTrue(dialog.contains("val isValid = cleanName.isNotEmpty() &&\n            cleanName !in POSE_CATEGORIES &&\n            cleanName !in existingNames"))
        assertTrue(dialog.contains("(cleanName == entry.name ||\n                    (cleanName !in POSE_CATEGORIES && cleanName !in existingNames))"))
        assertEquals("both dialogs act only when valid", 2, Regex("""if \(isValid\) \{""").findAll(dialog).count())
        assertEquals(2, Regex("""isActive = isValid""").findAll(dialog).count())
    }

    // ---- every language -----------------------------------------------------------------------------------------------------------------

    @Test
    fun wordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "context_add" to "context_add_title", "context_reassign" to "common_rename", "context_confirm_rename" to "common_confirm", "context_delete_permanently" to "common_delete",
            "context_rename_title" to "context_add_title", "context_manage_title" to "context_add_title", "context_name_label" to "context_assign_label",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for ((a, b) in pairs) {
                if (tag == "en" && (a to b) == ("context_add" to "context_add_title")) continue // "+ ADD CONTEXT" and "ADD CONTEXT": the plus is the difference
                assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
            }
            assertNotEquals("$tag: DELETE PERMANENTLY must not read like CANCEL", map.getValue("context_delete_permanently"), map.getValue("common_cancel"))
            assertNotEquals("$tag: CONFIRM must not read like CANCEL", map.getValue("common_confirm"), map.getValue("common_cancel"))
        }
    }

    @Test
    fun theDeleteQuestionNamesTheLayerAndKeepsBothSentences_inEveryLanguage() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val body = map.getValue("context_delete_body")
            assertTrue("$tag: names the layer", body.contains("%1\$s"))
            assertTrue("$tag: says what is lost and the advice, as two parts", body.contains("--"))
        }
        for ((tag, map) in translations) {
            assertNotEquals("$tag: the question is still English", english.getValue("context_delete_body"), map.getValue("context_delete_body"))
            assertNotEquals("$tag: the title is still English", english.getValue("context_manage_title"), map.getValue("context_manage_title"))
        }
        // The two titles that carry a name take it as %1$s.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertEquals("$tag/context_reassign_title", listOf("%1\$s"), StringsXml.placeholders(map.getValue("context_reassign_title")))
            assertEquals("$tag/context_based_on", listOf("%1\$s"), StringsXml.placeholders(map.getValue("context_based_on")))
        }
    }

    @Test
    fun theWordPoseReadsAsTheScreensOwnWordForIt_inEveryLanguage() {
        // "POSE" has no screen of its own yet (PlainWordsScreensWiringTest), so each sentence that says it uses the label table's word for it.
        for ((tag, map) in translations) {
            val pose = map.getValue("label_pose")
            for (name in listOf("context_assign_label", "context_reassign_title", "context_reassign_help")) {
                assertTrue("$tag/$name says POSE as \"$pose\"", map.getValue(name).contains(pose.removeSuffix("ة").removeSuffix("ـ")))
            }
        }
    }

    @Test
    fun theDialogsKeepTheirEnglishExactly() {
        assertEquals("MANAGE CONTEXT", english.getValue("context_manage_title"))
        assertEquals("ROOT :: %1\$s", english.getValue("matrix_root_heading"))
        assertEquals("[IMMUTABLE]", english.getValue("context_immutable"))
        assertEquals("REASSIGN POSE // %1\$s", english.getValue("context_reassign_title"))
        assertEquals("BASED ON: %1\$s", english.getValue("context_based_on"))
        assertEquals(
            "Permanently remove context layer \"%1\$s\"? Every phrase, variable, and shared override saved under it will be deleted across every deck and profile. " +
                "This cannot be undone -- consider exporting a backup first.",
            english.getValue("context_delete_body")
        )
        assertEquals("RENAME", english.getValue("common_rename"))
    }
}
