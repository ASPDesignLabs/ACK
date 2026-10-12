// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the person picked when importing a trained voice, judged by the picked files' names alone (plain Kotlin: no android.*, tested on a JVM).
 *
 * A voice reaches the phone in one of two forms: the two files a trainer writes (`<name>.onnx` and `<name>.onnx.json`), or the one `.zip` ACK Voice Studio
 * (and ACK's own EXPORT VOICE BACKUP) makes, which holds them under the fixed names `model.onnx` and `model.onnx.json`. IMPORT CUSTOM VOICE takes either, so a
 * phone with no voice yet can start from the zip; the restore button next to EXPORT (shown only once a voice exists) keeps taking only the zip.
 *
 * This only routes. Both landing paths check the files again themselves (sizes, the config's keys, the zip's two entry names), so a wrong guess here
 * can never install anything that would not have been accepted.
 */
enum class CustomVoiceImportKind {
    /** One file whose name ends in `.zip`: a voice backup / Voice Studio zip. */
    ONE_ZIP,

    /** Anything else, including two files: the original path, which says plainly if it is not a `.onnx` and a `.onnx.json`. */
    TRAINER_FILES
}

object CustomVoiceImport {
    const val ZIP_SUFFIX = ".zip"

    fun kindOf(names: List<String>): CustomVoiceImportKind =
        if (names.size == 1 && names[0].endsWith(ZIP_SUFFIX, ignoreCase = true)) CustomVoiceImportKind.ONE_ZIP else CustomVoiceImportKind.TRAINER_FILES
}
