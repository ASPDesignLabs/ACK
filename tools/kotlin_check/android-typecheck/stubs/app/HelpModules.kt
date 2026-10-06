// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

// Stubs of the walkthrough modules the HELP chooser dialogs draw options from. Only the option types the dialogs read, written from the real declarations
// (help/FieldOpsHelp.kt PoseOption, help/VoiceRecordingsHelp.kt VoiceRecOption); the modules' own text is not staged.
object FieldOpsHelp {
    data class PoseOption(
        val moduleId: String,
        val label: String,
        val hint: String
    )
}

object VoiceRecordingsHelp {
    data class VoiceRecOption(
        val moduleId: String,
        val label: String,
        val hint: String
    )
}
