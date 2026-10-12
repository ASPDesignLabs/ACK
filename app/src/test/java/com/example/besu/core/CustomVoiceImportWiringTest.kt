// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * IMPORT CUSTOM VOICE takes the voice's two trainer files or the one zip Voice Studio makes. The files that do it cannot be compiled without the Android SDK
 * (AudioView, CustomVoiceRepository, CustomVoiceBackupManager), so this reads them: the picker's result goes through the one routing function, the zip path is
 * the same restore path as before (so it validates the same way), the restore button next to EXPORT is unchanged, and the failure message names both forms
 * in every language.
 */
class CustomVoiceImportWiringTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")

    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    @Test
    fun thePickersResultGoesThroughTheRoutingFunction_andNeverStraightToTheTwoFilePath() {
        val screen = source("settings/AudioView.kt")
        assertEquals("the picked files are handed over once", 1, Regex("""CustomVoiceRepository\.importPicked\(context, uris\)""").findAll(screen).count())
        assertFalse("the screen must not call the two-file import itself", screen.contains("CustomVoiceRepository.importVoice("))
        // Any file type can be picked: neither a .onnx nor a .zip has a MIME type that can be relied on.
        assertTrue(screen.contains("importVoiceLauncher.launch(arrayOf(\"*/*\"))"))
    }

    @Test
    fun theRoutingFunctionSendsOneZipToTheBackupRestore_andEverythingElseToTheTwoFileImport() {
        val route = RepoFiles.declarationOf(source("output/CustomVoiceRepository.kt"), "importPicked")
        assertTrue(route.contains("CustomVoiceImport.kindOf(uris.map { displayName(context, it) })"))
        assertTrue(route.contains("if (kind == CustomVoiceImportKind.ONE_ZIP) CustomVoiceBackupManager.importBackup(context, uris[0]) else importVoice(context, uris)"))
        assertEquals("nothing else is installed from here", 0, Regex("""installFromValidatedFiles|copyTo""").findAll(route).count())
    }

    @Test
    fun theZipPathStillChecksTheZipAndTheFilesInsideItAndInstallsThroughTheSharedLandingPoint() {
        val manager = source("output/CustomVoiceBackupManager.kt")
        assertTrue(manager.contains("private const val MODEL_ENTRY_NAME = \"model.onnx\""))
        assertTrue(manager.contains("private const val CONFIG_ENTRY_NAME = \"model.onnx.json\""))
        assertTrue(manager.contains("CustomVoiceRepository.installFromValidatedFiles(context, tempModel!!, tempConfig!!)"))
        val install = RepoFiles.declarationOf(source("output/CustomVoiceRepository.kt"), "installFromValidatedFiles")
        assertTrue("the shared landing point re-checks the config", install.contains("looksLikePiperConfig(configSource)"))
        assertTrue("and the model's size", install.contains("modelSource.length() <= 0L || modelSource.length() > MAX_MODEL_SIZE_BYTES"))
    }

    @Test
    fun theRestoreButtonNextToExportIsAsItWas_shownOnlyOnceAVoiceExistsAndTakingOnlyAZip() {
        val screen = source("settings/AudioView.kt")
        val block = screen.substring(screen.indexOf("if (hasCustomVoice) {\n            Spacer(modifier = Modifier.height(6.dp))\n            Row("))
        assertTrue(block.contains("importVoiceBackupLauncher.launch(arrayOf(\"application/zip\"))"))
        assertTrue(screen.contains("CustomVoiceBackupManager.importBackup(context, uri)"))
        assertEquals("the restore still restarts once, as does the import", 2, Regex("""pendingCustomVoiceRestart = true""").findAll(screen).count())
    }

    @Test
    fun theFailureMessageNamesBothFormsInEveryLanguage_soAFailedZipIsNotToldToPickTwoFiles() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val text = map.getValue("audio_toast_import_failed")
            assertTrue("$tag: names .ONNX", text.contains(".ONNX"))
            assertTrue("$tag: names .ONNX.JSON", text.contains(".ONNX.JSON"))
            assertTrue("$tag: names the zip", text.contains(".ZIP"))
        }
        assertEquals("IMPORT FAILED -- PICK BOTH .ONNX AND .ONNX.JSON, OR ONE VOICE .ZIP", english.getValue("audio_toast_import_failed"))
        for ((tag, map) in translations) {
            assertTrue("$tag: translated, not English", map.getValue("audio_toast_import_failed") != english.getValue("audio_toast_import_failed"))
        }
    }
}
