package com.example.besu.data

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

// One remembered value for a given field, plus how often and how recently
// it's been used -- getSuggestions ranks by count first, lastUsedAt as the
// tiebreaker, so a value used many times stays ahead of one used just once
// a moment ago.
@Serializable
data class AutocompleteEntry(
    val value: String,
    val count: Int = 1,
    val lastUsedAt: Long = System.currentTimeMillis()
)

// Local-only "you've typed this here before" suggestions for three field
// types: a Matrix node's local variable values, a Quick Actions slot's
// local variable values, and Shared Root Variables' A/B/C values. Each
// field type builds its own scope key (see the three *ScopeKey functions
// below) at the precision that field's own editor UI calls for -- Matrix
// and Quick Actions per node/slot, Root Override globally per category,
// matching how Root Override's actual values are already shared globally
// today. Deliberately its own SharedPreferences file rather than folded
// into CommandRepository's "ack_matrix_config" -- keeps this feature's
// storage (and its backup export, which reads this whole file) cleanly
// separate from everything else living in that shared file.
object AutocompleteHistoryRepository {
    private const val PREFS_NAME = "ack_autocomplete_history"

    // Per scope, the oldest/least-used entries are trimmed past this many
    // distinct remembered values -- keeps a field that's seen years of
    // varied input from growing its history (and backup size) without
    // bound, while comfortably exceeding MAX_SUGGESTIONS so trimming never
    // affects what's actually shown.
    private const val MAX_ENTRIES_PER_SCOPE = 20

    // Chips shown per field -- the top this-many entries by count.
    const val MAX_SUGGESTIONS = 5

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    // --- SCOPE KEYS ---
    // Opaque, never parsed back apart -- only ever used for exact-match
    // storage/lookup, so the exact separator or field order doesn't matter
    // beyond being internally consistent. "/" rather than a character like
    // "|" specifically so these keys stay within TransferManager's existing
    // SAFE_KEY_PATTERN (letters/digits/underscore/hyphen/slash/space) and
    // can be validated on import the same way every other backup key is,
    // without needing a bespoke pattern just for this field.
    // Matrix local variable value -- per node (deckId+profile+storagePath,
    // matching CommandRepository's own node scoping), per variable slot (a
    // node can have more than one {VAR}/{VAR:tag} token, each tracked
    // separately since they usually hold different kinds of values).
    fun matrixVariableScopeKey(
        deckId: String,
        profile: String,
        storagePath: String,
        slotIndex: Int
    ): String = "matrix/$deckId/$profile/$storagePath/$slotIndex"

    // Quick Actions local variable value -- per slot (deckId+groupIndex+
    // slotIndex), per variable tag position within that slot's template.
    fun quickActionVariableScopeKey(
        deckId: String,
        groupIndex: Int,
        slotIndex: Int,
        tagIndex: Int
    ): String = "qa/$deckId/$groupIndex/$slotIndex/$tagIndex"

    // Shared Root Variable value -- global per category (pose name or
    // custom context layer) and tag (A/B/C), with no deck/profile in the
    // key at all. This intentionally matches RootOverrideRepository's own
    // scoping: the value itself is already shared across every deck and
    // profile that touches this category, so its usage history is too.
    fun rootOverrideScopeKey(category: String, tag: String): String =
        "root/$category/$tag"

    // --- READ/WRITE ---

    fun getSuggestions(context: Context, scopeKey: String): List<String> {
        return loadEntries(context, scopeKey)
            .sortedWith(compareByDescending<AutocompleteEntry> { it.count }.thenByDescending { it.lastUsedAt })
            .take(MAX_SUGGESTIONS)
            .map { it.value }
    }

    // Blank values are never recorded -- there's nothing useful to suggest
    // back. Safe to call unconditionally from a field's commit point
    // (focus-loss, a dialog's save button) without the caller needing to
    // check emptiness itself first.
    fun recordUsage(context: Context, scopeKey: String, value: String) {
        val trimmed = value.trim()
        if (trimmed.isEmpty()) {
            return
        }

        val entries = loadEntries(context, scopeKey).toMutableList()
        val existingIndex = entries.indexOfFirst { it.value == trimmed }

        if (existingIndex != -1) {
            val existing = entries[existingIndex]
            entries[existingIndex] = existing.copy(
                count = existing.count + 1,
                lastUsedAt = System.currentTimeMillis()
            )
        } else {
            entries.add(AutocompleteEntry(value = trimmed))
        }

        val trimmedToCap = if (entries.size > MAX_ENTRIES_PER_SCOPE) {
            entries
                .sortedWith(compareByDescending<AutocompleteEntry> { it.count }.thenByDescending { it.lastUsedAt })
                .take(MAX_ENTRIES_PER_SCOPE)
        } else {
            entries
        }

        saveEntries(context, scopeKey, trimmedToCap)
    }

    // The single broad "CLEAR AUTOCOMPLETE HISTORY" action in PROTOCOL --
    // wipes every scope's history at once. Per-scope/per-value removal is
    // intentionally not part of this pass; a more granular management UI
    // is planned as a later PROTOCOL addition.
    fun clearAll(context: Context) {
        prefs(context).edit().clear().apply()
    }

    private fun loadEntries(context: Context, scopeKey: String): List<AutocompleteEntry> {
        val raw = prefs(context).getString(scopeKey, null) ?: return emptyList()
        return try {
            json.decodeFromString(raw)
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun saveEntries(context: Context, scopeKey: String, entries: List<AutocompleteEntry>) {
        prefs(context).edit().putString(scopeKey, json.encodeToString(entries)).apply()
    }

    // --- BACKUP ---
    // An explicit, fully-typed export/restore pair (rather than riding
    // CommandRepository's sparse matrixData dump) -- this repository's
    // dedicated prefs file makes a clean whole-file read/replace safe with
    // no exclusion list needed, since nothing else lives in it.

    fun exportForBackup(context: Context): Map<String, List<AutocompleteEntry>> {
        return prefs(context).all.mapNotNull { (key, rawValue) ->
            val raw = rawValue as? String ?: return@mapNotNull null
            val entries = try {
                json.decodeFromString<List<AutocompleteEntry>>(raw)
            } catch (_: Exception) {
                return@mapNotNull null
            }
            key to entries
        }.toMap()
    }

    // Restore-only: wipes whatever's already stored and replaces it
    // wholesale, same convention as ComputerRepository.replaceCategories
    // and VoiceRecordingRepository.replaceFromBackup.
    fun restoreFromBackup(context: Context, data: Map<String, List<AutocompleteEntry>>) {
        val editor = prefs(context).edit().clear()
        data.forEach { (scopeKey, entries) ->
            editor.putString(scopeKey, json.encodeToString(entries))
        }
        editor.apply()
    }
}
