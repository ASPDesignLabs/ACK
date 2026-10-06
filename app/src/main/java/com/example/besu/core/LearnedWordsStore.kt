// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/**
 * The learned words as a file in [dir] (data/LearnedWordsRepository.kt gives it `filesDir/learned_words`). Plain Kotlin (no `android.*`,
 * only `java.io`) so saving, damage and forgetting are tested on a computer, like `capture/TrainingStore`.
 *
 * What it promises:
 *  - **A save is all or nothing.** The model is written to a temporary file, forced to disk, and moved into place in one step, so a crash
 *    leaves the old words or the new ones, never half.
 *  - **A damaged file is never overwritten.** One that is not JSON, fails the checks, or is far too large is treated as empty and **moved
 *    aside** (`model.json.damaged-<time>`) before anything new is saved; nothing is deleted because it looked wrong.
 *  - **A change made behind its back is noticed.** DELETE DATA removes the file and a restore may rewrite it; the file's size and time are
 *    compared on every use, so the old words are never saved back over a wipe.
 *  - **Forgetting forgets.** FORGET ALL removes every file this store made, the set-aside copies included, and leaves anything else alone.
 *  - **Reading writes nothing**, and learning only text that holds a word writes anything at all.
 *  - **Typed text is never logged.** This class has no logging.
 *
 * One lock serialises every call, so two threads cannot lose each other's learning.
 */
class LearnedWordsStore(private val dir: File, private val clock: () -> Long = { System.currentTimeMillis() }) {

    companion object {
        /** The folder under the app's private files folder (a test keeps this equal to the one data/LearnedWordsRepository.kt names). */
        const val FOLDER = "learned_words"
        const val FILE_NAME = "model.json"
        const val TEMP_NAME = "model.json.tmp"
        const val DAMAGED_PREFIX = "model.json.damaged"

        /** A model at its caps is about 2 MB; anything over this is not one. */
        const val MAX_FILE_BYTES = 8L * 1024L * 1024L

        private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    }

    private data class Stamp(val length: Long, val modified: Long)

    private val lock = Any()
    private var model = WordModel()
    private var loaded = false
    private var stamp: Stamp? = null

    private val file get() = File(dir, FILE_NAME)

    private fun currentStamp(): Stamp? = file.takeIf { it.isFile }?.let { Stamp(it.length(), it.lastModified()) }

    /** Reloads if the file is not the one the model came from. Never creates anything. */
    private fun ensureFresh() {
        if (loaded && currentStamp() == stamp) return
        model = load()
        stamp = currentStamp()
        loaded = true
    }

    private fun load(): WordModel {
        val f = file
        if (!f.isFile) return WordModel()
        val data = try {
            if (f.length() > MAX_FILE_BYTES) null
            else json.decodeFromString<WordModelData>(f.readText(Charsets.UTF_8)).takeIf { it.validate() == null }
        } catch (e: Exception) {
            null
        }
        if (data == null) {
            setAside(f)
            return WordModel()
        }
        return WordModel.fromData(data)
    }

    private fun setAside(damaged: File) {
        var n = 0
        var target: File
        do {
            target = File(dir, "$DAMAGED_PREFIX-${clock()}${if (n == 0) "" else "-$n"}")
            n++
        } while (target.exists())
        try {
            Files.move(damaged.toPath(), target.toPath())
        } catch (e: IOException) {
            // Could not move it: leave it where it is. The next save would replace it, so refuse to save until it can be moved.
            blockedByDamage = true
        }
    }

    private var blockedByDamage = false

    /** Writes the model (or removes the file if it is empty). False if it could not be saved; the words stay in memory until then. */
    private fun save(): Boolean {
        if (blockedByDamage && file.isFile) return false
        blockedByDamage = false
        if (model.wordCount == 0) {
            file.delete()
            File(dir, TEMP_NAME).delete()
            stamp = null
            return !file.exists()
        }
        val temp = File(dir, TEMP_NAME)
        return try {
            dir.mkdirs()
            val bytes = json.encodeToString(model.toData()).toByteArray(Charsets.UTF_8)
            FileOutputStream(temp).use { out ->
                out.write(bytes)
                out.fd.sync()
            }
            Files.move(temp.toPath(), file.toPath(), StandardCopyOption.ATOMIC_MOVE)
            stamp = currentStamp()
            true
        } catch (e: IOException) {
            temp.delete()
            false
        }
    }

    /** Learns [text] (committed text) and saves. Text with no word in it is not even looked at twice. */
    fun learn(text: String): Unit = synchronized(lock) {
        if (WordTokens.words(text).isEmpty()) return
        ensureFresh()
        model.learn(text, clock())
        save()
    }

    /** What to offer for [text] with the cursor at [cursor]; [extraWords] are names kept elsewhere, offered but never saved. */
    fun predict(extraWords: List<String>, text: String, cursor: Int, limit: Int = 3): Prediction = synchronized(lock) {
        ensureFresh()
        WordPrediction.predict(model, extraWords, text, cursor, limit)
    }

    fun wordCount(): Int = synchronized(lock) { ensureFresh(); model.wordCount }

    /** Every learned word, most used first, for the FORGET WORDS list. */
    fun listWords(): List<ScoredWord> = synchronized(lock) { ensureFresh(); model.listWords() }

    /** Removes one word and every pair it is in. True if it was there. */
    fun forget(word: String): Boolean = synchronized(lock) {
        ensureFresh()
        val removed = model.forget(word)
        if (removed) save()
        removed
    }

    /** Removes every file this store made, including damaged copies it set aside. Files that are not its own are left alone. */
    fun forgetAll(): Unit = synchronized(lock) {
        model = WordModel()
        stamp = null
        loaded = false
        blockedByDamage = false
        dir.listFiles()?.filter { it.isFile && it.name.startsWith(FILE_NAME) }?.forEach { it.delete() }
        if (dir.list().isNullOrEmpty()) dir.delete()
    }

    /** What EXPORT .JSON holds: the model, or null when nothing was learned (so an unused feature adds nothing to a backup). */
    fun exportForBackup(): WordModelData? = synchronized(lock) {
        ensureFresh()
        if (model.wordCount == 0) null else model.toData()
    }

    /** Folds a restored backup in: never lowers a count, never removes a word, drops anything broken. True if it was saved. */
    fun mergeFromBackup(data: WordModelData): Boolean = synchronized(lock) {
        ensureFresh()
        model.merge(data)
        save()
    }
}
