// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context
import com.example.besu.core.SpeechLanguage

// Stubs of data/AssistPrefs.kt, data/InstallState.kt and data/LearnedWordsRepository.kt (they read preferences and files), written from their real signatures.
object AssistPrefs {
    fun speechLanguage(context: Context): SpeechLanguage = SpeechLanguage.ENGLISH_US
    fun setSpeechLanguage(context: Context, setting: SpeechLanguage) {}
    fun isWordSuggestionsOn(context: Context): Boolean = false
    fun setWordSuggestions(context: Context, on: Boolean) {}
    fun isUsageSummaryOn(context: Context): Boolean = false
    fun setUsageSummary(context: Context, on: Boolean) {}
}
object InstallState {
    fun isFreshInstall(context: Context): Boolean = false
    fun isDefaultsPromptDismissed(context: Context): Boolean = false
    fun dismissDefaultsPrompt(context: Context) {}
}
object LearnedWordsRepository {
    fun wordCount(context: Context): Int = 0
    fun listWords(context: Context): List<com.example.besu.core.ScoredWord> = emptyList()
    fun forget(context: Context, word: String): Boolean = false
    fun forgetAll(context: Context) {}
}
