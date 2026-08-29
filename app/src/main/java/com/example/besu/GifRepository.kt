package com.example.besu

import android.content.Context
import android.net.Uri
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.util.UUID

object GifRepository {
    private const val PREFS_NAME = "ack_gif_library"

    private const val CATEGORIES_KEY = "gif_categories"
    private const val ENTRIES_KEY = "gif_entries"

    private const val GIF_DIRECTORY = "gif_library"

    private const val MAX_GIF_SIZE_BYTES = 20L * 1024L * 1024L

    private const val OVERLAY_TEXT_PREFIX = "gif_overlay_text_"

    private const val LANDSCAPE_OVERLAY_PREFIX =
        "gif_force_landscape_overlay_"

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun getCategories(
        context: Context,
        deckId: String
    ): List<GifCategory> {
        return readCategories(context)
            .filter { category ->
                getEntries(context, deckId).any { entry ->
                    entry.categoryId == category.id
                }
            }
            .sortedBy { it.name }
    }

    fun getAllCategories(context: Context): List<GifCategory> {
        return readCategories(context).sortedBy { it.name }
    }

    fun getEntries(
        context: Context,
        deckId: String,
        categoryId: String? = null
    ): List<GifEntry> {
        return readEntries(context)
            .asSequence()
            .filter { entry ->
                entry.deckId == deckId
            }
            .filter { entry ->
                categoryId == null || entry.categoryId == categoryId
            }
            .filter { entry ->
                getGifFile(context, entry).exists()
            }
            .sortedBy { it.sortOrder }
            .toList()
    }

    fun shouldShowOverlayText(
        context: Context,
        deckId: String
    ): Boolean {
        return context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        ).getBoolean(
            "$OVERLAY_TEXT_PREFIX$deckId",
            true
        )
    }

    fun setShowOverlayText(
        context: Context,
        deckId: String,
        enabled: Boolean
    ) {
        context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )
            .edit()
            .putBoolean(
                "$OVERLAY_TEXT_PREFIX$deckId",
                enabled
            )
            .apply()
    }

    fun shouldForceLandscapeOverlay(
        context: Context,
        deckId: String
    ): Boolean {
        return context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        ).getBoolean(
            "$LANDSCAPE_OVERLAY_PREFIX$deckId",
            false
        )
    }

    fun setForceLandscapeOverlay(
        context: Context,
        deckId: String,
        enabled: Boolean
    ) {
        context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )
            .edit()
            .putBoolean(
                "$LANDSCAPE_OVERLAY_PREFIX$deckId",
                enabled
            )
            .apply()
    }

    fun createCategory(
        context: Context,
        name: String
    ): GifCategory {
        val cleanName = name
            .trim()
            .uppercase()
            .take(30)
            .ifBlank { "UNCATEGORIZED" }

        val existing = readCategories(context).firstOrNull { category ->
            category.name.equals(cleanName, ignoreCase = true)
        }

        if (existing != null) {
            return existing
        }

        val category = GifCategory(
            id = "GIF_CAT_${UUID.randomUUID()}",
            name = cleanName
        )

        val updated = readCategories(context).toMutableList().apply {
            add(category)
        }

        saveCategories(context, updated)

        return category
    }

    fun importGif(
        context: Context,
        deckId: String,
        sourceUri: Uri,
        title: String,
        categoryId: String
    ): Result<GifEntry> {
        return runCatching {
            val resolver = context.contentResolver
            val mimeType = resolver.getType(sourceUri)

            if (
                mimeType != null &&
                mimeType != "image/gif"
            ) {
                error("Selected file is not a GIF.")
            }

            val destinationDirectory = getGifDirectory(context)

            if (!destinationDirectory.exists()) {
                destinationDirectory.mkdirs()
            }

            val entryId = "GIF_${UUID.randomUUID()}"
            val fileName = "$entryId.gif"
            val destinationFile = File(destinationDirectory, fileName)

            resolver.openInputStream(sourceUri)?.use { input ->
                destinationFile.outputStream().use { output ->
                    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                    var copiedBytes = 0L

                    while (true) {
                        val read = input.read(buffer)

                        if (read <= 0) {
                            break
                        }

                        copiedBytes += read

                        if (copiedBytes > MAX_GIF_SIZE_BYTES) {
                            error("GIF exceeds the 20 MB safety limit.")
                        }

                        output.write(buffer, 0, read)
                    }
                }
            } ?: error("Unable to read selected file.")

            if (!isGifFile(destinationFile)) {
                destinationFile.delete()
                error("Selected file is not a valid GIF.")
            }

            val entry = GifEntry(
                id = entryId,
                deckId = deckId,
                title = title
                    .trim()
                    .take(50)
                    .ifBlank { "UNTITLED GIF" },
                categoryId = categoryId,
                fileName = fileName
            )

            val updatedEntries = readEntries(context).toMutableList().apply {
                add(entry)
            }

            saveEntries(context, updatedEntries)

            entry
        }
    }

    fun deleteGif(
        context: Context,
        entry: GifEntry
    ) {
        getGifFile(context, entry).delete()

        val updatedEntries = readEntries(context)
            .filterNot { saved ->
                saved.id == entry.id
            }

        saveEntries(context, updatedEntries)
        removeUnusedCategories(context)
    }

    fun deleteDeckGifs(
        context: Context,
        deckId: String
    ) {
        val allEntries = readEntries(context)
        val deletedEntries = allEntries.filter { entry ->
            entry.deckId == deckId
        }

        deletedEntries.forEach { entry ->
            getGifFile(context, entry).delete()
        }

        saveEntries(
            context,
            allEntries.filterNot { entry ->
                entry.deckId == deckId
            }
        )

        removeUnusedCategories(context)
        context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )
            .edit()
            .remove("$OVERLAY_TEXT_PREFIX$deckId")
            .apply()
    }

    fun getGifFile(
        context: Context,
        entry: GifEntry
    ): File {
        return File(getGifDirectory(context), entry.fileName)
    }

    private fun getGifDirectory(context: Context): File {
        return File(context.filesDir, GIF_DIRECTORY)
    }

    private fun isGifFile(file: File): Boolean {
        if (!file.exists() || file.length() < 6L) {
            return false
        }

        val header = ByteArray(6)

        file.inputStream().use { input ->
            if (input.read(header) != header.size) {
                return false
            }
        }

        val signature = header.decodeToString()

        return signature == "GIF87a" || signature == "GIF89a"
    }

    private fun removeUnusedCategories(context: Context) {
        val usedCategoryIds = readEntries(context)
            .map { entry ->
                entry.categoryId
            }
            .toSet()

        saveCategories(
            context,
            readCategories(context).filter { category ->
                category.id in usedCategoryIds
            }
        )
    }

    private fun readCategories(context: Context): List<GifCategory> {
        val prefs = context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )

        val raw = prefs.getString(CATEGORIES_KEY, "[]") ?: "[]"

        return try {
            json.decodeFromString<List<GifCategory>>(raw)
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun readEntries(context: Context): List<GifEntry> {
        val prefs = context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )

        val raw = prefs.getString(ENTRIES_KEY, "[]") ?: "[]"

        return try {
            json.decodeFromString<List<GifEntry>>(raw)
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun saveCategories(
        context: Context,
        categories: List<GifCategory>
    ) {
        context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )
            .edit()
            .putString(CATEGORIES_KEY, json.encodeToString(categories))
            .apply()
    }

    private fun saveEntries(
        context: Context,
        entries: List<GifEntry>
    ) {
        context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )
            .edit()
            .putString(ENTRIES_KEY, json.encodeToString(entries))
            .apply()
    }
}
