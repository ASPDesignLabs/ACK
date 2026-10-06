// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * SAVE MESSAGE LOG TO A FILE touches files that cannot be compiled or run without the Android SDK (data/LogExporter.kt, settings/LogExportDialog.kt,
 * SettingsView). What goes in the file and what the warning says are plain Kotlin, tested in LogExportTest and LogExportContentsTest; this reads those files and
 * holds them to the promises: it warns first and writes nothing until a place is chosen, only the picker's own document is written (no share sheet, no network),
 * a failed save deletes the half-made file, nothing said is ever logged, reading the log changes nothing, it adds no storage, it is one button in SETTINGS and no
 * typed command, and nothing in it is smaller than 12 sp.
 */
class LogExportWiringTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line.substringBefore(" // ")
    }
    private val exporter get() = noComments(source("data/LogExporter.kt"))
    private val dialog get() = noComments(source("settings/LogExportDialog.kt"))

    // ---- the file is only written to the picker's own document ---------------------------------------------------------------------------

    @Test
    fun theOnlyThingWrittenIsTheDocumentThePickerMade_andAFailureDeletesIt() {
        assertEquals("one write, to the chosen document", 1, Regex("""openOutputStream\(""").findAll(exporter).count())
        assertTrue(exporter.contains("openOutputStream(uri, \"w\")"))
        assertTrue(exporter.contains("DocumentsContract.deleteDocument(resolver, uri)"))
        val failed = RepoFiles.declarationOf(exporter.replace("        fun failed", "    fun failed"), "failed")
        assertTrue("a failure deletes the half-made file", failed.contains("discard()"))
    }

    @Test
    fun everyWayTheWriteCanFailGoesThroughThatOneFailurePath() {
        val write = exporter.substring(exporter.indexOf("fun write("))
        for (kind in listOf("SecurityException", "IOException", "Exception")) {
            val at = write.indexOf("catch (e: $kind)")
            assertTrue("catch $kind", at >= 0)
            assertTrue("$kind must report through failed(...)", write.substring(at, at + 120).contains("failed("))
        }
        assertTrue("a null output stream is a failure, not a silent success", write.contains("?: return failed(BackupExporter.REASON_OPEN)"))
    }

    @Test
    fun noShareSheetNoNetworkNoOtherAppIsEverHandedTheFile() {
        for ((name, text) in listOf("data/LogExporter.kt" to exporter, "settings/LogExportDialog.kt" to dialog)) {
            for (forbidden in listOf("ACTION_SEND", "createChooser", "ShareCompat", "FileProvider", "java.net", "HttpURLConnection", "OkHttp", "WebView", "startActivity", "ACTION_VIEW", "ClipboardManager")) {
                assertFalse("$name must not use '$forbidden'", text.contains(forbidden))
            }
        }
        // The only Intent is the Terminal's own broadcast of a result line, as the backup's does.
        assertEquals(1, Regex("""Intent\(""").findAll(exporter).count())
        assertTrue(exporter.contains("Intent(\"ACK_LOG\")"))
        assertTrue(exporter.contains("setPackage(context.packageName)"))
    }

    @Test
    fun thePickerIsTheSystemsCreateDocument_forPlainText() {
        assertEquals(1, Regex("""CreateDocument\(""").findAll(dialog).count())
        assertTrue(dialog.contains("CreateDocument(\"text/plain\")"))
    }

    // ---- warns first, saves nothing until a place is chosen ---------------------------------------------------------------------------------

    @Test
    fun theFlowStartsWithTheWarning_andStartingItWritesNothingAndOpensNoPicker() {
        val start = dialog.substring(dialog.indexOf("return {"))
        assertTrue(start.contains("count = LogExporter.messagesNow(context, logs.toList()).size"))
        assertFalse(start.contains("launch("))
        assertFalse(start.contains("write("))
    }

    @Test
    fun thePickerOpensOnlyFromTheChooseButton_notFromCancelNorFromAnEmptyLog() {
        assertEquals("the picker is launched in exactly one place", 1, Regex("""launcher\.launch\(""").findAll(dialog).count())
        val choose = dialog.substring(dialog.indexOf("onChooseLocation = {"))
        assertTrue(choose.contains("launcher.launch(LogExport.fileName("))
        assertEquals("cancel only hides the warning", "onDismiss = { count = null },", Regex("""onDismiss = \{ count = null \},""").find(dialog)?.value)
        val body = dialog.substring(dialog.indexOf("fun LogExportWarningDialog("))
        assertTrue("an empty log shows a line and returns before the button", body.indexOf("if (messageCount == 0)") in 1 until body.indexOf("NeonButton("))
        assertTrue(body.substring(body.indexOf("if (messageCount == 0)")).take(200).contains("return@TightDialogSurface"))
    }

    @Test
    fun theFileIsWrittenOnlyAfterThePickerAnswers_withTheLogAsItIsThen() {
        val callback = dialog.substring(dialog.indexOf("CreateDocument(\"text/plain\")"), dialog.indexOf("val shown = count"))
        assertTrue(callback.contains("uri?.let"))
        assertTrue(callback.contains("LogExporter.write(context, it, logs.toList())"))
        assertTrue(callback.contains("LogExporter.report(context, result)"))
    }

    @Test
    fun theWarningDrawsTheWordsOfTheCoreDecision_andNothingItTypedItself() {
        assertTrue(dialog.contains("LogExportContents.countLine(text, messageCount)"))
        assertTrue(dialog.contains("LogExportContents.contains(text, logName)"))
        for (name in listOf("NOT_INCLUDED", "NOT_PROTECTED", "COPY_TOO", "WHERE_TO_SAVE", "CONTAINS_HEADING", "NONE_NOW")) assertTrue(name, dialog.contains("LogExportContents.$name"))
        assertFalse("no English typed into the screen", dialog.contains("ENCRYPTED") || dialog.contains("SCREENSHOT"))
    }

    // ---- nothing said is logged; reading changes nothing; no new storage ------------------------------------------------------------------------

    @Test
    fun noLogLineEverHoldsWhatWasSaid() {
        val calls = Regex("""Log\.[a-z]\([^\n]*""").findAll(exporter).map { it.value }.toList()
        assertTrue("the exporter should log its outcome", calls.size >= 2)
        for (call in calls) for (word in listOf(".text", ".msg", "replayText", ".from", "entries", "lines", "bytes.toString", "String(bytes")) {
            assertFalse("a Log call must not mention '$word': $call", call.contains(word))
        }
    }

    @Test
    fun readingTheLogChangesNothing() {
        for (forbidden in listOf("persist(", "pruneAndPersist", "applyRetention", "clearAll", "setRetentionDays", ".edit()", "logs.", "TerminalLogStore.load(")) {
            assertFalse("the exporter must not use '$forbidden'", exporter.contains(forbidden))
        }
        assertTrue(exporter.contains("TerminalLogStore.getRetentionDays(context)"))
    }

    @Test
    fun itAddsNoStorage_noPreferenceFileNoFolderNoKey() {
        for (text in listOf(exporter, dialog, noComments(source("core/LogExport.kt")), noComments(source("core/LogExportContents.kt")))) {
            for (forbidden in listOf("SharedPreferences", "getSharedPreferences", "filesDir", "getExternalFilesDir", "cacheDir", "File(", "openFileOutput")) {
                assertFalse("'$forbidden'", text.contains(forbidden))
            }
        }
    }

    // ---- where it is reached ----------------------------------------------------------------------------------------------------------------------

    @Test
    fun itIsOneButtonInSettings_afterTheRetentionSlider_andBeforeDataPort() {
        val settings = noComments(source("settings/SettingsView.kt"))
        assertEquals("the flow is created once", 1, Regex("""rememberLogExportFlow\(""").findAll(settings).count())
        assertEquals("one button starts it", 1, Regex("""startLogExport\(\)""").findAll(settings).count())
        val button = settings.indexOf("startLogExport()")
        assertTrue("after the retention slider", button > settings.indexOf("SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor, inactiveTrackColor = Color.DarkGray),\n                    modifier = Modifier.helpTarget(AckTags.SETTINGS_TERMINAL_LOG"))
        assertTrue("before DATA PORT", button < settings.indexOf("labelFor(LabelKey.DATA_PORT)"))
        assertTrue(settings.contains("LogExportContents.buttonDescription(words, labelFor(LabelKey.TERMINAL_LOG))"))
        assertTrue(settings.contains("rememberLogExportFlow(context, primaryColor, labelFor(LabelKey.TERMINAL_LOG), logs)"))
    }

    @Test
    fun thereIsNoTypedCommandForIt_theDeveloperChoseASettingsButtonOnly() {
        for (file in listOf("ui/DesignSystem.kt", "ui/TerminalPlainControls.kt", "core/TerminalText.kt", "MainActivity.kt")) {
            val text = noComments(source(file))
            assertFalse("$file must not start the message-log save", text.contains("LogExporter") || text.contains("LogExport.") || text.contains("rememberLogExportFlow"))
        }
        assertFalse("no new typed command", noComments(source("core/TerminalText.kt")).contains("\"/log"))
    }

    @Test
    fun theFlowIsUsedOnlyFromSettings() {
        val users = RepoFiles.appSource.walkTopDown().filter { it.isFile && it.extension == "kt" }
            .filter { it.name != "LogExportDialog.kt" && it.readText().contains("rememberLogExportFlow(") }.map { it.name }.toList()
        assertEquals(listOf("SettingsView.kt"), users)
    }

    // ---- looks --------------------------------------------------------------------------------------------------------------------------------------

    @Test
    fun nothingInTheDialogIsSmallerThanTwelveSp_andItUsesTheSharedBodyText() {
        val sizes = Regex("""fontSize\s*=\s*(\d+(?:\.\d+)?)\.sp""").findAll(dialog).map { it.groupValues[1].toDouble() }.toList()
        assertTrue(sizes.all { it >= 12.0 })
        assertTrue(dialog.contains("ConfirmBodyText("))
        val settings = noComments(source("settings/SettingsView.kt"))
        val at = settings.indexOf("LogExportContents.buttonDescription(")
        val near = settings.substring(at, at + 260)
        assertTrue("the line under the button is 12 sp", near.contains("fontSize = 12.sp"))
    }

    // ---- the strings ---------------------------------------------------------------------------------------------------------------------------------

    @Test
    fun everyStringItAddsIsUsedByTheCoreFiles_andEveryNameTheCoreUsesExists() {
        val defined = StringsXml.read(StringsXml.default).map { it.name }.filter { it.startsWith("log_export_") }.toSet()
        val core = source("core/LogExport.kt") + source("core/LogExportContents.kt")
        val used = Regex(""""(log_export_[a-z_]+)"""").findAll(core).map { it.groupValues[1] }.toSet()
        assertEquals("defined but never used: ${defined - used}; used but not defined: ${used - defined}", used, defined)
    }

    @Test
    fun theReasonsItReportsAreStringsThatExist() {
        val strings = StringsXml.map(StringsXml.default)
        val backup = source("backup/BackupExporter.kt")
        for (name in listOf("REASON_OPEN", "REASON_NOT_ALLOWED", "REASON_WRITE")) {
            val resource = Regex("""const val $name = "([^"]+)"""").find(backup)?.groupValues?.get(1)
            assertTrue("$name", resource != null && resource in strings)
        }
        assertTrue(exporter.contains("const val REASON_PREPARE = LogExportContents.FAIL_PREPARE"))
        assertTrue(LogExportContents.FAIL_PREPARE in strings)
        assertTrue("export_choose_where" in strings && "common_cancel" in strings)
    }
}
