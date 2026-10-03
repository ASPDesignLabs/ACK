// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.Json
import java.security.MessageDigest

/**
 * A short fingerprint of what a backup would contain, so ACK can tell whether anything has changed since the last export
 * without a hook in every repository. Plain Kotlin (no `android.*`) so it is tested without a phone.
 *
 * The recipe, pinned by tests against hashes computed independently: parse the JSON, drop the top-level fields in
 * [IGNORED_FIELDS], sort every object's keys at every depth, write it back compactly, and take the SHA-256 of its UTF-8 bytes as
 * lower-case hex. Array order is kept (it is data). Sorting matters because `matrixData` comes from
 * `SharedPreferences.getAll()`, whose order is not guaranteed.
 *
 * Only the digest leaves this function. It is never logged in full (the caller logs a short prefix), and the JSON it reads is
 * never kept or logged.
 */
object BackupFingerprint {

    /**
     * Top-level fields that change all the time without the person adding anything: the backup's own time, which deck/profile
     * is open, the typing history, and which sections are folded. Only top-level fields are ignored: a deck or a recording that
     * has a field of the same name is real data.
     *
     * "starterPhrasesSeeded" describes where the file came from, not anything the person stored. Left in, the new field would make
     * every existing phone's fingerprint change once after the update and the backup reminder would fire for nothing.
     * "warnBeforeProfileChange" is a small on/off switch that is cheap to set again, and the same applies to the new field.
     */
    val IGNORED_FIELDS: Set<String> = setOf(
        "timestamp", "activeDeckId", "activeDeckColorIndex", "activeProfile", "activeCategoryFocus",
        "autocompleteHistory", "rootOverrideCollapsed", "starterPhrasesSeeded", "warnBeforeProfileChange",
    )

    /** @throws IllegalArgumentException if [rawJson] is JSON but not an object; a parse error if it is not JSON. */
    fun fingerprint(rawJson: String): String {
        val root = Json.parseToJsonElement(rawJson)
        require(root is JsonObject) { "a backup must be a JSON object" }
        val kept = JsonObject(root.filterKeys { it !in IGNORED_FIELDS })
        val canonical = canonicalize(kept).toString()
        val digest = MessageDigest.getInstance("SHA-256").digest(canonical.toByteArray(Charsets.UTF_8))
        return digest.joinToString("") { "%02x".format(it) }
    }

    // Objects are rebuilt with their keys in sorted order (a JsonObject keeps insertion order, and toString writes it that way).
    private fun canonicalize(element: JsonElement): JsonElement = when (element) {
        is JsonObject -> JsonObject(element.entries.sortedBy { it.key }.associate { it.key to canonicalize(it.value) })
        is JsonArray -> JsonArray(element.map { canonicalize(it) })
        else -> element
    }
}
