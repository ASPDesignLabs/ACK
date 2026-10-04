// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context
import com.example.besu.core.SpeechLanguage

// Stubs of data/AssistPrefs.kt and data/InstallState.kt (they read preferences), written from their real signatures.
object AssistPrefs {
    fun speechLanguage(context: Context): SpeechLanguage = SpeechLanguage.ENGLISH_US
    fun setSpeechLanguage(context: Context, setting: SpeechLanguage) {}
}
object InstallState {
    fun isFreshInstall(context: Context): Boolean = false
    fun isDefaultsPromptDismissed(context: Context): Boolean = false
    fun dismissDefaultsPrompt(context: Context) {}
}
