package com.example.besu.decks

import com.example.besu.data.CommandRepository
import com.example.besu.data.DeckMeta
import com.example.besu.data.DeckType
import com.example.besu.ui.theme.NeonPalette
import android.content.Context
import android.net.Uri
import android.util.Log
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

// A GIF deck's images and organization scale with how built-out the deck
// is, not with how long a piece of text is (the problem the rest of the
// backup system solves) -- "plenty of images with deep categorization"
// means real binary files, potentially hundreds of megabytes, which have
// no business inside a JSON string. This is a standalone .zip export/
// import for one GIF deck at a time: real .gif files in real deck/
// category folders (openable and viewable on any OS, no app required),
// plus a manifest.json carrying the ids/ordering/toggles needed to
// restore it faithfully. Deliberately separate from TransferManager's
// EXPORT .JSON / FULL RESTORE FROM JSON, which don't know GIF decks
// exist at all.

@Serializable
data class GifBackupManifest(
    val version: Int = 1,
    val deck: GifBackupDeck,
    val categories: List<GifBackupCategory> = emptyList(),
    val entries: List<GifBackupEntry> = emptyList(),
    val showOverlayText: Boolean = true,
    val forceLandscapeOverlay: Boolean = false
)

@Serializable
data class GifBackupDeck(
    val id: String,
    val name: String,
    val colorIndex: Int
)

@Serializable
data class GifBackupCategory(
    val id: String,
    val name: String
)

@Serializable
data class GifBackupEntry(
    val id: String,
    val title: String,
    val categoryId: String,
    // The internal storage filename (GifEntry.fileName, e.g. "GIF_xxx.gif")
    // -- distinct from zipPath below, which is only for human browsing.
    val fileName: String,
    // Where this GIF's bytes live inside the archive -- "<deck>/<category>/
    // <title>.gif", sanitized and de-duplicated at export time. The
    // manifest is authoritative; this is never parsed to recover anything,
    // only looked up.
    val zipPath: String,
    val sortOrder: Long
)

object GifBackupManager {
    private const val LOG_TAG = "ACK_GIF_BACKUP"
    private const val MANIFEST_ENTRY_NAME = "manifest.json"

    // Generous ceilings, same "firewall, not a practical constraint"
    // philosophy TransferManager's own limits use -- a single GIF is
    // already capped at 20MB (GifRepository.MAX_GIF_SIZE_BYTES) on the
    // way in, so these bound the archive as a whole against something
    // corrupted or hostile, not against a real, if large, GIF library.
    private const val MAX_ZIP_FILE_SIZE = 500L * 1024L * 1024L // 500MB
    private const val MAX_ENTRIES = 5000
    private const val MAX_CATEGORIES = 500
    private const val MAX_LABEL_LENGTH = 120

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
        prettyPrint = true
    }

    // Ids are app-generated (DECK_<timestamp>, GIF_CAT_<uuid>, GIF_<uuid>),
    // never user-typed -- validated the same way every other backup id in
    // this app is, on principle, not because free text is expected here.
    private val SAFE_ID_PATTERN = Regex("^[A-Za-z0-9_\\-]{1,150}$")

    // No slashes, no "..", single .gif suffix -- this is the string that
    // becomes File(gifDirectory, fileName) on restore (see GifRepository.
    // restoreEntry), so this is the one field in this whole format that
    // guards against writing outside the app's own GIF storage directory.
    private val SAFE_FILENAME_PATTERN = Regex("^[A-Za-z0-9_\\-]{1,100}\\.gif$")

    private val UNSAFE_ZIP_SEGMENT_CHARS = Regex("[^A-Za-z0-9 _\\-]")

    private fun sanitizeSegment(raw: String, fallback: String): String {
        val cleaned = raw.trim().replace(UNSAFE_ZIP_SEGMENT_CHARS, "_").take(60)
        return cleaned.ifBlank { fallback }
    }

    // --- EXPORT ---

    // Writes the deck's manifest and every GIF it references to
    // destinationUri. Returns false (logging why) on any failure -- the
    // caller is responsible for telling the user.
    fun exportDeck(context: Context, deckId: String, destinationUri: Uri): Boolean {
        val deckMeta = CommandRepository.getDecks(context).find { it.id == deckId }
        if (deckMeta == null) {
            Log.e(LOG_TAG, "Export failed: no deck with id \"$deckId\"")
            return false
        }

        val categories = GifRepository.getCategories(context, deckId)
        val entries = GifRepository.getEntries(context, deckId)

        val deckFolder = sanitizeSegment(deckMeta.name, deckMeta.id)
        val usedZipPaths = mutableSetOf<String>()

        val exportPlan = entries.map { entry ->
            val categoryName = categories.find { it.id == entry.categoryId }?.name
            val categoryFolder = sanitizeSegment(categoryName ?: "UNCATEGORIZED", "UNCATEGORIZED")
            val baseTitle = sanitizeSegment(entry.title, entry.id)

            var zipPath = "$deckFolder/$categoryFolder/$baseTitle.gif"
            var suffix = 2
            while (!usedZipPaths.add(zipPath)) {
                zipPath = "$deckFolder/$categoryFolder/${baseTitle}_$suffix.gif"
                suffix++
            }

            entry to zipPath
        }

        val manifest = GifBackupManifest(
            deck = GifBackupDeck(id = deckMeta.id, name = deckMeta.name, colorIndex = deckMeta.colorIndex),
            categories = categories.map { GifBackupCategory(id = it.id, name = it.name) },
            entries = exportPlan.map { (entry, zipPath) ->
                GifBackupEntry(
                    id = entry.id,
                    title = entry.title,
                    categoryId = entry.categoryId,
                    fileName = entry.fileName,
                    zipPath = zipPath,
                    sortOrder = entry.sortOrder
                )
            },
            showOverlayText = GifRepository.shouldShowOverlayText(context, deckId),
            forceLandscapeOverlay = GifRepository.shouldForceLandscapeOverlay(context, deckId)
        )

        return try {
            context.contentResolver.openOutputStream(destinationUri)?.use { output ->
                ZipOutputStream(output).use { zip ->
                    zip.putNextEntry(ZipEntry(MANIFEST_ENTRY_NAME))
                    zip.write(json.encodeToString(manifest).toByteArray(Charsets.UTF_8))
                    zip.closeEntry()

                    exportPlan.forEach { (entry, zipPath) ->
                        val file = GifRepository.getGifFile(context, entry)
                        if (file.exists()) {
                            zip.putNextEntry(ZipEntry(zipPath))
                            file.inputStream().use { it.copyTo(zip) }
                            zip.closeEntry()
                        }
                    }
                }
            } ?: run {
                Log.e(LOG_TAG, "Export failed: could not open output stream")
                return false
            }
            true
        } catch (e: Exception) {
            Log.e(LOG_TAG, "Export failed", e)
            false
        }
    }

    // --- IMPORT ---

    data class ImportResult(
        val success: Boolean,
        val deckName: String? = null,
        val importedCount: Int = 0,
        val skippedCount: Int = 0
    )

    // Merges by id -- a category/entry the archive provides is added or
    // updated, anything already on the device that the archive doesn't
    // mention is left alone, matching how FULL RESTORE FROM JSON treats
    // the rest of the app's data. The deck itself is created if it
    // doesn't exist yet, so restoring onto a device with no GIF decks
    // works end to end.
    fun importBackup(context: Context, sourceUri: Uri): ImportResult {
        val tempFile = File.createTempFile("gif_import_", ".zip", context.cacheDir)

        try {
            val copiedBytes = context.contentResolver.openInputStream(sourceUri)?.use { input ->
                tempFile.outputStream().use { output -> input.copyTo(output) }
            }

            if (copiedBytes == null) {
                Log.e(LOG_TAG, "Import failed: could not open selected file")
                return ImportResult(success = false)
            }
            if (copiedBytes > MAX_ZIP_FILE_SIZE) {
                Log.e(LOG_TAG, "Import failed: file exceeds $MAX_ZIP_FILE_SIZE bytes ($copiedBytes)")
                return ImportResult(success = false)
            }

            ZipFile(tempFile).use { zipFile ->
                val manifestEntry = zipFile.getEntry(MANIFEST_ENTRY_NAME)
                if (manifestEntry == null) {
                    Log.e(LOG_TAG, "Import failed: no $MANIFEST_ENTRY_NAME in archive")
                    return ImportResult(success = false)
                }

                val manifest = try {
                    json.decodeFromString<GifBackupManifest>(
                        zipFile.getInputStream(manifestEntry).use { it.readBytes() }.toString(Charsets.UTF_8)
                    )
                } catch (e: Exception) {
                    Log.e(LOG_TAG, "Import failed: manifest.json did not parse", e)
                    return ImportResult(success = false)
                }

                if (!validateManifest(manifest)) {
                    return ImportResult(success = false)
                }

                val existingDeck = CommandRepository.getDecks(context).find { it.id == manifest.deck.id }
                if (existingDeck != null && existingDeck.type != DeckType.GIF) {
                    // Refuses to let an imported GIF backup silently retype
                    // an existing non-GIF deck (including DEFAULT, whose
                    // type is always MATRIX) -- a manifest ever claiming
                    // that id is corrupted or not from this feature.
                    Log.e(
                        LOG_TAG,
                        "Import failed: deck \"${manifest.deck.id}\" already exists as ${existingDeck.type}, not GIF"
                    )
                    return ImportResult(success = false)
                }

                CommandRepository.upsertDeck(
                    context,
                    DeckMeta(
                        id = manifest.deck.id,
                        name = manifest.deck.name,
                        colorIndex = manifest.deck.colorIndex,
                        type = DeckType.GIF
                    )
                )

                manifest.categories.forEach { category ->
                    GifRepository.upsertCategory(
                        context,
                        GifCategory(id = category.id, name = category.name)
                    )
                }

                var importedCount = 0
                var skippedCount = 0

                manifest.entries.forEach { backupEntry ->
                    val zipEntry = zipFile.getEntry(backupEntry.zipPath)
                    if (zipEntry == null) {
                        Log.e(LOG_TAG, "Skipping \"${backupEntry.title}\": manifest references missing zip entry \"${backupEntry.zipPath}\"")
                        skippedCount++
                        return@forEach
                    }

                    val gifBytes = zipFile.getInputStream(zipEntry).use { it.readBytes() }
                    val entry = GifEntry(
                        id = backupEntry.id,
                        deckId = manifest.deck.id,
                        title = backupEntry.title,
                        categoryId = backupEntry.categoryId,
                        fileName = backupEntry.fileName,
                        sortOrder = backupEntry.sortOrder
                    )

                    GifRepository.restoreEntry(context, entry, gifBytes)
                        .onSuccess { importedCount++ }
                        .onFailure {
                            Log.e(LOG_TAG, "Skipping \"${backupEntry.title}\": ${it.message}")
                            skippedCount++
                        }
                }

                GifRepository.setShowOverlayText(context, manifest.deck.id, manifest.showOverlayText)
                GifRepository.setForceLandscapeOverlay(context, manifest.deck.id, manifest.forceLandscapeOverlay)

                return ImportResult(
                    success = true,
                    deckName = manifest.deck.name,
                    importedCount = importedCount,
                    skippedCount = skippedCount
                )
            }
        } catch (e: Exception) {
            Log.e(LOG_TAG, "Import failed", e)
            return ImportResult(success = false)
        } finally {
            tempFile.delete()
        }
    }

    private fun validateManifest(manifest: GifBackupManifest): Boolean {
        if (!SAFE_ID_PATTERN.matches(manifest.deck.id)) {
            Log.e(LOG_TAG, "deck.id fails SAFE_ID_PATTERN: \"${manifest.deck.id}\"")
            return false
        }
        if (manifest.deck.name.isBlank() || manifest.deck.name.length > MAX_LABEL_LENGTH) {
            Log.e(LOG_TAG, "deck.name invalid length: ${manifest.deck.name.length}")
            return false
        }
        if (manifest.deck.colorIndex !in NeonPalette.SWATCHES.indices) {
            Log.e(LOG_TAG, "deck.colorIndex out of range: ${manifest.deck.colorIndex}")
            return false
        }

        if (manifest.categories.size > MAX_CATEGORIES) {
            Log.e(LOG_TAG, "categories.size exceeds $MAX_CATEGORIES: ${manifest.categories.size}")
            return false
        }
        manifest.categories.forEach { category ->
            if (!SAFE_ID_PATTERN.matches(category.id)) {
                Log.e(LOG_TAG, "category.id fails SAFE_ID_PATTERN: \"${category.id}\"")
                return false
            }
            if (category.name.isBlank() || category.name.length > MAX_LABEL_LENGTH) {
                Log.e(LOG_TAG, "category \"${category.id}\" name invalid length: ${category.name.length}")
                return false
            }
        }
        if (manifest.categories.map { it.id }.distinct().size != manifest.categories.size) {
            Log.e(LOG_TAG, "categories has duplicate ids")
            return false
        }

        if (manifest.entries.size > MAX_ENTRIES) {
            Log.e(LOG_TAG, "entries.size exceeds $MAX_ENTRIES: ${manifest.entries.size}")
            return false
        }

        val categoryIds = manifest.categories.map { it.id }.toSet()

        manifest.entries.forEach { entry ->
            if (!SAFE_ID_PATTERN.matches(entry.id)) {
                Log.e(LOG_TAG, "entry.id fails SAFE_ID_PATTERN: \"${entry.id}\"")
                return false
            }
            if (entry.title.length > MAX_LABEL_LENGTH) {
                Log.e(LOG_TAG, "entry \"${entry.id}\" title exceeds $MAX_LABEL_LENGTH chars")
                return false
            }
            if (entry.categoryId !in categoryIds) {
                Log.e(LOG_TAG, "entry \"${entry.id}\" categoryId not in categories: \"${entry.categoryId}\"")
                return false
            }
            if (!SAFE_FILENAME_PATTERN.matches(entry.fileName)) {
                Log.e(LOG_TAG, "entry \"${entry.id}\" fileName fails SAFE_FILENAME_PATTERN: \"${entry.fileName}\"")
                return false
            }
            if (entry.zipPath.isBlank() || entry.zipPath.contains("..")) {
                Log.e(LOG_TAG, "entry \"${entry.id}\" zipPath invalid: \"${entry.zipPath}\"")
                return false
            }
        }
        if (manifest.entries.map { it.id }.distinct().size != manifest.entries.size) {
            Log.e(LOG_TAG, "entries has duplicate ids")
            return false
        }

        return true
    }
}
