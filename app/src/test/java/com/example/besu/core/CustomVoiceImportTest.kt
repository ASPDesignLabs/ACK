// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Test

/** How IMPORT CUSTOM VOICE decides between the two forms a voice comes in. It only routes; both landing paths check the files again. */
class CustomVoiceImportTest {

    private fun kind(vararg names: String) = CustomVoiceImport.kindOf(names.toList())

    @Test
    fun oneZipIsTheZipPath() {
        assertEquals(CustomVoiceImportKind.ONE_ZIP, kind("my_voice_backup.zip"))
        assertEquals(CustomVoiceImportKind.ONE_ZIP, kind("model.zip"))
        assertEquals(CustomVoiceImportKind.ONE_ZIP, kind("a.zip"))
    }

    @Test
    fun theSuffixIsReadWithoutRegardToCase_becausePhonesAndPickersDiffer() {
        assertEquals(CustomVoiceImportKind.ONE_ZIP, kind("VOICE.ZIP"))
        assertEquals(CustomVoiceImportKind.ONE_ZIP, kind("voice.Zip"))
    }

    @Test
    fun theTwoTrainerFilesAreTheOriginalPath_inEitherOrder() {
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("my_voice.onnx", "my_voice.onnx.json"))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("my_voice.onnx.json", "my_voice.onnx"))
    }

    @Test
    fun aZipTogetherWithAnotherFileIsNotTheZipPath_soTheOriginalPathRefusesItAsBefore() {
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("voice.zip", "voice.onnx"))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("one.zip", "two.zip"))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("one.zip", "two.zip", "three.zip"))
    }

    @Test
    fun nothingPickedOrAnUnrelatedFileFallsToTheOriginalPath() {
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, CustomVoiceImport.kindOf(emptyList()))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("voice.onnx"))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("voice.onnx.json"))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("notes.txt"))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind(""))
    }

    @Test
    fun onlyTheSuffixCounts_notAZipInTheMiddleOfTheName() {
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("voice.zip.onnx"))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("zip"))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("voice.zip "))
        assertEquals(CustomVoiceImportKind.TRAINER_FILES, kind("voicezip"))
    }

    @Test
    fun theSuffixConstantIsTheOneTheRoutingUses() {
        assertEquals(".zip", CustomVoiceImport.ZIP_SUFFIX)
    }
}
