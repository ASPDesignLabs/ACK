// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.util.Log
import com.example.besu.core.LearnedWordsStore
import com.example.besu.core.Prediction
import com.example.besu.core.ScoredWord
import com.example.besu.core.WordModelData
import java.io.File

/**
 * The thin Android edge over the learned words (core/LearnedWordsStore.kt holds the rules and is tested on a computer): one shared store
 * for the whole process, so its lock covers every screen, in `filesDir/learned_words`.
 *
 * Rules that live here because only this file knows the switch:
 *  - **Learning and suggesting are off unless the person turned WORD SUGGESTIONS on** (AssistPrefs). The check is inside [learn] and
 *    [predict], so no screen can forget it.
 *  - **Listing, forgetting and the backup work with the switch off.** The words are the person's data whether or not the feature is on:
 *    they can always see them, remove them, and have them in EXPORT .JSON.
 *  - **Nothing typed is ever logged,** not even in an error. A failure says only that it failed. A learning failure never reaches the
 *    screen: the composer must keep working.
 *
 * The words are plain text in a private file (no network, nothing leaves the phone unless an export is saved), cleared by DELETE DATA >
 * MESSAGES AND DECKS and by FORGET ALL WORDS.
 */
object LearnedWordsRepository {
    private const val TAG = "ACK_LEARNED_WORDS"

    @Volatile private var shared: LearnedWordsStore? = null

    // Literal folder name on purpose: the storage scan (StorageCatalogueTest) finds folders by it, and LearnedWordsWiringTest checks it
    // equals LearnedWordsStore.FOLDER.
    private fun store(context: Context): LearnedWordsStore =
        shared ?: synchronized(this) {
            shared ?: LearnedWordsStore(File(context.filesDir, "learned_words")).also { shared = it }
        }

    /** Learns committed text (a statement saved, spoken or copied). Does nothing with the switch off. Never throws. */
    fun learn(context: Context, text: String) {
        if (!AssistPrefs.isWordSuggestionsOn(context)) return
        try {
            store(context).learn(text)
        } catch (e: Exception) {
            Log.e(TAG, "learning failed (details withheld: they could contain what was typed)")
        }
    }

    /** What to offer for [text] with the cursor at [cursor]. Nothing with the switch off. Never throws. */
    fun predict(context: Context, extraWords: List<String>, text: String, cursor: Int, limit: Int = 3): Prediction {
        if (!AssistPrefs.isWordSuggestionsOn(context)) return Prediction.NONE
        return try {
            store(context).predict(extraWords, text, cursor, limit)
        } catch (e: Exception) {
            Log.e(TAG, "suggesting failed (details withheld: they could contain what was typed)")
            Prediction.NONE
        }
    }

    fun wordCount(context: Context): Int = try { store(context).wordCount() } catch (e: Exception) { 0 }

    /** Every learned word, most used first, for FORGET WORDS. */
    fun listWords(context: Context): List<ScoredWord> = try { store(context).listWords() } catch (e: Exception) { emptyList() }

    /** Removes one word and every pair it is in. True if it was there. */
    fun forget(context: Context, word: String): Boolean = try { store(context).forget(word) } catch (e: Exception) { false }

    /** Removes every learned word and any damaged copy set aside. */
    fun forgetAll(context: Context) {
        try {
            store(context).forgetAll()
        } catch (e: Exception) {
            Log.e(TAG, "forgetting all words failed")
        }
    }

    /** The words as EXPORT .JSON carries them: null when nothing was learned. Not gated on the switch. */
    fun exportForBackup(context: Context): WordModelData? = try { store(context).exportForBackup() } catch (e: Exception) { null }

    /** Adds a restored backup's words to what is here (never lowers a count, never removes a word). */
    fun mergeFromBackup(context: Context, data: WordModelData) {
        try {
            store(context).mergeFromBackup(data)
        } catch (e: Exception) {
            Log.e(TAG, "restoring the learned words failed")
        }
    }
}
