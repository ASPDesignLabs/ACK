// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The backup wording (EXPORT .JSON's warning, the backup reminder, the failure reasons, IMPORT MATRIX AS NEW DECK and FULL RESTORE) reads its words
 * from string resources, in the chosen language. The screens cannot be compiled here, so this reads them: the old English literals are gone, every
 * string they name exists and none is left unused, a toast reads its text through the context (it is not a composable), and the typed command the
 * Terminal asks for is still the command the Terminal accepts, in every language. The decisions themselves are in ExportContentsTest and
 * BackupReminderTextTest.
 */
class BackupWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val english get() = StringsXml.map(StringsXml.default)
    private val prefixes = listOf("export_", "backup_", "data_port_")
    private fun isBackupName(name: String) = prefixes.any { name.startsWith(it) }

    private fun allSources(): List<String> =
        RepoFiles.file(base).walkTopDown().filter { it.isFile && it.extension == "kt" }.map { noComments(it.readText(Charsets.UTF_8)) }.toList()

    @Test
    fun everyStringTheBackupScreensNameExists_andNoneIsLeftUnused() {
        val referenced = allSources().flatMap { Regex("""R\.string\.((?:export|backup|data_port)_[a-z_]+)""").findAll(it).map { m -> m.groupValues[1] }.toList() }.toSet()
        // The decisions name theirs as plain strings (resource names, read through a TextSource), and a category's is built from its key.
        val named = listOf("core/ExportContents.kt", "core/BackupReminderText.kt", "backup/BackupExporter.kt").flatMap {
            Regex(""""((?:export|backup|data_port)_[a-z_]+)"""").findAll(noComments(source(it))).map { m -> m.groupValues[1] }.toList()
        }.toSet() + ExportContents.categories.map { it.resource }
        val used = referenced + named
        val defined = english.keys.filter { isBackupName(it) }.toSet() + StringsXml.plurals(StringsXml.default).keys.filter { isBackupName(it) }
        assertEquals("named but not defined: ${used - defined}", emptySet<String>(), used - defined)
        val unused = defined - used
        assertTrue("defined but never used: $unused", unused.isEmpty())
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawnByTheBackupScreens() {
        val gone = mapOf(
            "settings/BackupWarningDialog.kt" to listOf("\"CHOOSE WHERE TO SAVE\"", "\"CANCEL\"", "category.label", "it.label"),
            "ui/BackupReminderBanner.kt" to listOf("\"BACKUP DUE\"", "\"BACK UP NOW\"", "\"NOT NOW\"", "\"CLOSE\"", "\"CANCEL\""),
            "settings/SettingsView.kt" to listOf(
                "\"IMPORT CONFIGURATION\"", "\"Import as new Deck?", "\"DECK CREATED -- RESTARTING\"", "\"PROTOCOL RESTORED -- RESTARTING\"",
                "\"INTEGRITY CHECK FAILED\"", "\"RESTORE\"", "This applies whatever the selected file contains", "One exception: this phone may have been given",
                "brings in a backup's matrix phrases", "Text(\"CANCEL\", color = Color.Red, modifier = Modifier.clickable { showImportDialog = false }",
            ),
            "backup/BackupExporter.kt" to listOf(
                "\"BACKUP EXPORTED\"", "NOTHING WAS SAVED", "\"THE FILE COULD NOT BE OPENED\"", "\"THE BACKUP COULD NOT BE PREPARED\"",
                "\"THIS LOCATION DID NOT ALLOW ACK TO SAVE THERE\"", "RAN OUT OF MEMORY",
            ),
            "core/ExportContents.kt" to listOf("THIS FILE CAN CONTAIN", "NOT ENCRYPTED", "EXPORT ACK BACKUP?", "TYPE /backup CONFIRM"),
            "core/BackupReminderText.kt" to listOf("BACKUP REMINDER: ON", "BACKUP DUE", "YOUR LAST BACKUP WAS", "NOT MADE A BACKUP YET", "\" DAYS\"", "\"1 DAY\""),
            "ui/DesignSystem.kt" to listOf("EXPORT ACK BACKUP?", "THIS FILE CAN CONTAIN"),
        )
        for ((file, literals) in gone) {
            val text = noComments(source(file))
            for (literal in literals) assertFalse("$file still holds $literal", text.contains(literal))
        }
    }

    @Test
    fun theToastsAndTheTerminalReplyReadTheirTextWhereTheyAreNotInAComposable() {
        val settings = noComments(source("settings/SettingsView.kt"))
        for (name in listOf("data_port_deck_created", "data_port_restored", "data_port_integrity_failed")) {
            assertTrue("$name: a toast reads its text through the context", settings.contains("Toast.makeText(context, context.getString(R.string.$name), Toast.LENGTH_SHORT).show()"))
        }
        assertFalse("a toast cannot call a composable", Regex("""Toast\.makeText\([^)]*stringResource""").containsMatchIn(settings))
        // The Terminal's reply and the exporter's report are not composables either: they go through the context-backed text source.
        assertTrue(noComments(source("ui/DesignSystem.kt")).contains("ExportContents.terminalText(ResourceText(context))"))
        val exporter = noComments(source("backup/BackupExporter.kt"))
        assertTrue(exporter.contains("ResourceText(context)"))
        assertFalse(exporter.contains("stringResource"))
    }

    @Test
    fun theBannerAndTheDialogResolveTheirTextOutsideTheSemanticsBlock() {
        // semantics {} is not a composable lambda: a string looked up inside it would not compile, so the icon's description is read first.
        val banner = noComments(source("ui/BackupReminderBanner.kt"))
        assertTrue(banner.contains("val iconDescription = rememberText().get(BackupReminderText.ICON_DESCRIPTION)"))
        assertTrue(banner.contains("import com.example.besu.R") || !banner.contains("R.string"))
    }

    @Test
    fun theImportNoteNamesTheTwoButtonsThroughTheLabelTable_soPlainWordsShowsTheNamesOnScreen() {
        val settings = noComments(source("settings/SettingsView.kt"))
        assertTrue(settings.contains("stringResource(R.string.data_port_import_note, labelFor(LabelKey.IMPORT_MATRIX), labelFor(LabelKey.FULL_RESTORE))"))
        assertEquals(listOf("%1\$s", "%2\$s"), StringsXml.placeholders(english.getValue("data_port_import_note")))
    }

    @Test
    fun theTypedCommandTheTerminalAsksForIsTheOneItAccepts_inEveryLanguage() {
        // The Terminal accepts "/backup confirm" (any case). If a translation changed the command, the instruction would send the person to a
        // command that does nothing. Everything around it may be translated; the command itself may not.
        val design = noComments(source("ui/DesignSystem.kt"))
        assertTrue(design.contains("""if (first == "/b" || first == "/backup") {"""))
        assertTrue(design.contains("""if (rest == "confirm") {"""))
        val all = mapOf("en" to english) + StringsXml.translations().mapValues { StringsXml.map(it.value) }
        for ((tag, map) in all) {
            // The whole command: not a prefix of a longer word ("/backup CONFIRMAR" contains "/backup CONFIRM" but the Terminal would not accept it).
            val command = Regex("""(?<![\p{L}\p{N}/])/backup CONFIRM(?![\p{L}\p{N}])""")
            assertTrue("$tag: export_terminal_confirm must contain the command /backup CONFIRM as its own words", command.containsMatchIn(map.getValue("export_terminal_confirm")))
        }
    }

    @Test
    fun aMissingResourceShowsItsNameNeverABlank_inBothLookups() {
        // data/ResourceText.kt is Android-bound, so it is read: a name with no resource must come back as itself (a visible gap, not silence),
        // for a string and for a plural, and each lookup asks for its own kind of resource.
        val text = noComments(source("data/ResourceText.kt"))
        // Three lookups: a string, a plural, and a plural that also takes arguments (a sentence with a count and a name in it).
        assertEquals(3, Regex("""if \(id == 0\) return name""").findAll(text).count())
        assertTrue(text.contains("getIdentifier(name, \"string\", context.packageName)"))
        assertTrue(text.contains("getIdentifier(name, \"plurals\", context.packageName)"))
        assertTrue(text.contains("getQuantityString(id, quantity, quantity)"))
        assertTrue("the quantity comes first, then the other arguments", text.contains("getQuantityString(id, quantity, quantity, *args)"))
    }

    @Test
    fun theExporterReportsThroughTheSharedWording_notItsOwn() {
        val exporter = noComments(source("backup/BackupExporter.kt"))
        assertTrue(exporter.contains("ExportContents.exportedText(text) to \"CMD\""))
        assertTrue(exporter.contains("ExportContents.failedText(text, result.reason) to \"CMD_ERR\""))
        assertFalse(exporter.contains("NOTHING WAS SAVED"))
    }

    @Test
    fun theWarningsThatTheFileIsNotProtectedAndWhereNotToSaveItAreKept_inEveryLanguage() {
        // The two safety sentences must never be dropped or emptied by a translation. Google Drive and OneDrive are named because a
        // person looks for those names; "ACK" because the app is named.
        val all = StringsXml.translations().mapValues { StringsXml.map(it.value) }
        for ((tag, map) in all) {
            val where = map.getValue("export_where_to_save")
            assertTrue("$tag: names Google Drive", where.contains("drive", ignoreCase = true) || where.contains("درايف") || where.contains("ड्राइव"))
            assertTrue("$tag: names OneDrive", where.contains("onedrive", ignoreCase = true) || where.contains("وان درايف") || where.contains("वनड्राइव"))
            assertTrue("$tag: says how long the reminder waits (7)", map.getValue("backup_reminder_switch_explanation").contains("7"))
        }
        assertTrue(english.getValue("export_not_protected").contains("NOT ENCRYPTED"))
        assertTrue(english.getValue("export_where_to_save").contains("GOOGLE DRIVE"))
    }

    @Test
    fun theRestoreSaysNothingIsDeletedAndTheStarterExceptionIsStillThere_inEveryLanguage() {
        for ((tag, map) in StringsXml.translations().mapValues { StringsXml.map(it.value) }) {
            assertTrue("$tag: restore body is a full paragraph", map.getValue("data_port_restore_body").length > 250)
            assertTrue("$tag: starter exception is a full paragraph", map.getValue("data_port_restore_starters").length > 150)
        }
        assertTrue(english.getValue("data_port_restore_body").contains("Nothing on this device that the file doesn't mention is touched or removed"))
    }
}
