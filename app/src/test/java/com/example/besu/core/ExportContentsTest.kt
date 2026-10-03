// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ExportContentsTest {

    // --- the drift guard -------------------------------------------------------------------------------------------

    @Test
    fun everyAckBackupFieldIsDescribedByTheWarning() {
        val fields = ackBackupFieldNames(RepoFiles.read("app/src/main/java/com/example/besu/backup/AckBackup.kt"))
        val unmapped = fields.filterNot { it in ExportContents.mappedFields }
        assertTrue(
            "AckBackup has field(s) the export warning does not describe: $unmapped\n" +
                "Fix: add each name to the right category's `fields` in core/ExportContents.kt (or to `formatFields` if it only " +
                "describes the file itself). If it holds something personal that none of the labels covers, add a category.",
            unmapped.isEmpty(),
        )
    }

    @Test
    fun theWarningNamesNoFieldThatNoLongerExists() {
        val fields = ackBackupFieldNames(RepoFiles.read("app/src/main/java/com/example/besu/backup/AckBackup.kt")).toSet()
        val stale = ExportContents.mappedFields.filterNot { it in fields }
        assertTrue(
            "core/ExportContents.kt names field(s) AckBackup does not have: $stale\n" +
                "Fix: remove or rename them (a renamed field would otherwise leave its data undescribed).",
            stale.isEmpty(),
        )
    }

    @Test
    fun aFieldIsInExactlyOneCategory() {
        val all = ExportContents.categories.flatMap { it.fields } + ExportContents.formatFields
        val twice = all.groupBy { it }.filterValues { it.size > 1 }.keys
        assertTrue("field(s) listed more than once: $twice", twice.isEmpty())
    }

    // The guard above is only worth something if the parser really sees AckBackup's fields.
    @Test
    fun theParserSeesTheRealFields() {
        val fields = ackBackupFieldNames(RepoFiles.read("app/src/main/java/com/example/besu/backup/AckBackup.kt"))
        assertTrue("found only ${fields.size}: $fields", fields.size >= 35)
        for (known in listOf("dsp", "emergencyInfoCard", "voiceRecordings", "trainingScripts", "savedStatementTree")) {
            assertTrue("parser missed $known in $fields", known in fields)
        }
        assertFalse("parser leaked a field of another class: $fields", "userProfile" in fields)
    }

    @Test
    fun theParserIgnoresCommentsAndNestedDefaults() {
        val source = """
            package x
            @Serializable
            data class AckBackup(
                // val commentedOut: Int = 1
                val one: Int = 6, // trailing (val notAField: String)
                /* val blockCommented: String */
                val two: Map<String, String>,
                val three: Thing = Thing(),
                val four: List<Thing> = emptyList(),
                val five: String? = null
            )
            data class Other(val six: Int)
        """.trimIndent()
        assertEquals(listOf("one", "two", "three", "four", "five"), ackBackupFieldNames(source))
    }

    // --- the wording -----------------------------------------------------------------------------------------------

    @Test
    fun theCategoryLabelsAreTheApprovedWording() {
        assertEquals(
            listOf(
                "EMERGENCY INFO CARD",
                "PEOPLE AND PLACES, WITH PHONE NUMBERS AND ADDRESSES",
                "SAVED LOCATIONS (MAP COORDINATES)",
                "YOUR VOICE RECORDINGS (THE AUDIO ITSELF)",
                "MESSAGES, STATEMENTS AND DECKS",
                "SETTINGS AND HISTORY",
            ),
            ExportContents.categories.map { it.label },
        )
    }

    @Test
    fun everyCategoryHasALabelAndFields() {
        for (c in ExportContents.categories) {
            assertTrue("blank label", c.label.isNotBlank())
            assertTrue("${c.label} has no fields", c.fields.isNotEmpty())
        }
        val labels = ExportContents.categories.map { it.label }
        assertEquals("labels must be unique", labels.size, labels.toSet().size)
    }

    @Test
    fun theDialogTextNamesEveryCategoryAndSaysItIsNotEncrypted() {
        val text = ExportContents.dialogText()
        for (c in ExportContents.categories) assertTrue("missing ${c.label}", c.label in text)
        assertTrue(text.contains("NOT ENCRYPTED"))
        assertTrue(text.contains("NO PASSWORD"))
        assertTrue(text.contains("GOOGLE DRIVE, ONEDRIVE"))
    }

    @Test
    fun theTerminalTextHasTheSameFactsAndTheConfirmLineLast() {
        val text = ExportContents.terminalText()
        for (c in ExportContents.categories) assertTrue("missing ${c.label}", c.label in text)
        assertTrue(text.contains("NOT ENCRYPTED"))
        assertTrue(text.contains("ONLINE FOLDERS"))
        assertTrue("the confirm line must still be the last line", text.lines().last() == "TYPE /backup CONFIRM TO PROCEED.")
        assertTrue("the question comes first", text.lines().first() == "EXPORT ACK BACKUP?")
    }

    @Test
    fun theWordingIsCapitalsLikeTheRestOfTheApp() {
        // The confirm line keeps the lower-case command name the person must type.
        val shown = ExportContents.dialogText() + "\n" + ExportContents.terminalText().replace("/backup", "/BACKUP")
        assertEquals(shown.uppercase(), shown)
    }

    @Test
    fun itNeverMentionsAnAppLockOrAPasswordOption() {
        val text = (ExportContents.dialogText() + ExportContents.terminalText()).uppercase()
        for (banned in listOf("APP LOCK", "SET A PASSWORD", "PASSWORD-PROTECT", "ENCRYPT IT", "PASSCODE")) {
            assertFalse("must not mention: $banned", text.contains(banned))
        }
    }

    // --- parsing AckBackup.kt --------------------------------------------------------------------------------------

    /**
     * The property names declared in `data class AckBackup( ... )`. Comments are removed first (they contain brackets and the
     * word `val`), then the constructor's brackets are matched, so a default such as `Thing()` cannot end it early.
     */
    private fun ackBackupFieldNames(source: String): List<String> {
        val noBlock = source.replace(Regex("/\\*.*?\\*/", RegexOption.DOT_MATCHES_ALL), "")
        val clean = noBlock.lines().joinToString("\n") { it.substringBefore("//") }
        val start = clean.indexOf("data class AckBackup(")
        check(start >= 0) { "data class AckBackup( not found" }
        val open = clean.indexOf('(', start)
        var depth = 0
        var end = -1
        for (i in open until clean.length) {
            when (clean[i]) {
                '(' -> depth++
                ')' -> { depth--; if (depth == 0) { end = i; break } }
            }
        }
        check(end > open) { "the end of AckBackup's constructor was not found" }
        val body = clean.substring(open + 1, end)
        return Regex("\\bval\\s+(\\w+)\\s*:").findAll(body).map { it.groupValues[1] }.toList()
    }
}
