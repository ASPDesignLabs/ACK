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

// Identifies which real field a scope's history belongs to, with enough
// structured detail for a management UI to build a human-readable label
// (name a deck, resolve a node's actual label, etc.) without ever parsing
// the opaque scope key string back apart -- the key stays exactly what it
// always was, a lookup-only string; this rides alongside it instead. A
// flat, non-polymorphic shape (only the fields a given fieldType actually
// uses are non-null) rather than a sealed hierarchy, so this stays
// ordinary data-class serialization rather than needing kotlinx's
// polymorphic machinery for something this small.
@Serializable
data class AutocompleteScopeInfo(
    val fieldType: String, // one of the TYPE_* constants below
    val deckId: String? = null,
    val profile: String? = null,
    val storagePath: String? = null,
    val groupIndex: Int? = null,
    val slotIndex: Int? = null,
    val tagIndex: Int? = null,
    val category: String? = null,
    val tag: String? = null
) {
    companion object {
        const val TYPE_MATRIX = "matrix"
        const val TYPE_QUICK_ACTION = "quick_action"
        const val TYPE_QUICK_ACTION_COMPUTER_FALLBACK = "quick_action_computer_fallback"
        const val TYPE_ROOT_OVERRIDE = "root_override"

        fun matrix(deckId: String, profile: String, storagePath: String, slotIndex: Int) =
            AutocompleteScopeInfo(
                fieldType = TYPE_MATRIX,
                deckId = deckId,
                profile = profile,
                storagePath = storagePath,
                slotIndex = slotIndex
            )

        fun quickAction(deckId: String, groupIndex: Int, slotIndex: Int, tagIndex: Int) =
            AutocompleteScopeInfo(
                fieldType = TYPE_QUICK_ACTION,
                deckId = deckId,
                groupIndex = groupIndex,
                slotIndex = slotIndex,
                tagIndex = tagIndex
            )

        fun quickActionComputerFallback(deckId: String, groupIndex: Int, slotIndex: Int, tagIndex: Int) =
            AutocompleteScopeInfo(
                fieldType = TYPE_QUICK_ACTION_COMPUTER_FALLBACK,
                deckId = deckId,
                groupIndex = groupIndex,
                slotIndex = slotIndex,
                tagIndex = tagIndex
            )

        fun rootOverride(category: String, tag: String) =
            AutocompleteScopeInfo(
                fieldType = TYPE_ROOT_OVERRIDE,
                category = category,
                tag = tag
            )
    }
}

// One field's stored history in full -- what field it is, and the values
// remembered for it. The unit everything in this file reads/writes as a
// whole; getSuggestions is the one exception, reading just the values.
@Serializable
data class AutocompleteScope(
    val info: AutocompleteScopeInfo,
    val entries: List<AutocompleteEntry> = emptyList()
)

// Local-only "you've typed this here before" suggestions for four field
// types: a Matrix node's local variable values, a Quick Actions slot's
// local variable values, a Quick Actions slot's [COMPUTER:X] tag fallback
// values, and Shared Root Variables' A/B/C values. Each field type builds
// its own scope key (see the *ScopeKey functions below) at the precision
// that field's own editor UI calls for -- Matrix and Quick Actions per
// node/slot (and, for computer fallbacks, per tag occurrence within that
// slot -- see quickActionComputerFallbackScopeKey for why that can't
// reuse quickActionVariableScopeKey's shape), Root Override globally per
// category, matching how Root Override's actual values are already shared
// globally today. Deliberately its own SharedPreferences file rather than
// folded into CommandRepository's "ack_matrix_config" -- keeps this
// feature's storage (and its backup export, which reads this whole file)
// cleanly separate from everything else living in that shared file.
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

    // Quick Actions [COMPUTER:X] tag fallback value -- same addressing as
    // quickActionVariableScopeKey above (per slot, per tag occurrence) but
    // deliberately a different key shape ("qa_computer/..." vs "qa/..."):
    // {VAR} and [COMPUTER:X] tags are counted/indexed independently within
    // the same template, so a slot's first {VAR} and first [COMPUTER:X]
    // would otherwise collide on the exact same key and corrupt each
    // other's history.
    fun quickActionComputerFallbackScopeKey(
        deckId: String,
        groupIndex: Int,
        slotIndex: Int,
        tagIndex: Int
    ): String = "qa_computer/$deckId/$groupIndex/$slotIndex/$tagIndex"

    // Shared Root Variable value -- global per category (pose name or
    // custom context layer) and tag (A/B/C), with no deck/profile in the
    // key at all. This intentionally matches RootOverrideRepository's own
    // scoping: the value itself is already shared across every deck and
    // profile that touches this category, so its usage history is too.
    fun rootOverrideScopeKey(category: String, tag: String): String =
        "root/$category/$tag"

    // --- READ/WRITE ---

    fun getSuggestions(context: Context, scopeKey: String): List<String> {
        return loadScope(context, scopeKey)?.entries.orEmpty()
            .sortedWith(compareByDescending<AutocompleteEntry> { it.count }.thenByDescending { it.lastUsedAt })
            .take(MAX_SUGGESTIONS)
            .map { it.value }
    }

    // Blank values are never recorded -- there's nothing useful to suggest
    // back. Safe to call unconditionally from a field's commit point
    // (focus-loss, a dialog's save/commit button) without the caller
    // needing to check emptiness itself first. info is only actually
    // written the first time a scope is recorded (or if it somehow
    // changed) -- cheap to pass on every call regardless, callers already
    // have every piece of it in hand from building the scope key itself.
    fun recordUsage(
        context: Context,
        scopeKey: String,
        info: AutocompleteScopeInfo,
        value: String
    ) {
        val trimmed = value.trim()
        if (trimmed.isEmpty()) {
            return
        }

        val entries = loadScope(context, scopeKey)?.entries.orEmpty().toMutableList()
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

        saveScope(context, scopeKey, AutocompleteScope(info = info, entries = trimmedToCap))
    }

    // Every stored scope, key alongside its full record -- backs the
    // MANAGE AUTOCOMPLETE tree browser. A scope whose stored JSON somehow
    // fails to decode is silently skipped rather than crashing the browser
    // over one corrupt entry.
    fun listAllScopes(context: Context): List<Pair<String, AutocompleteScope>> {
        return prefs(context).all.mapNotNull { (key, rawValue) ->
            val raw = rawValue as? String ?: return@mapNotNull null
            val scope = try {
                json.decodeFromString<AutocompleteScope>(raw)
            } catch (_: Exception) {
                return@mapNotNull null
            }
            key to scope
        }
    }

    // Removes just one remembered value from one scope's history, leaving
    // the rest of that scope (and every other scope) untouched. Drops the
    // scope's key entirely once its last value is removed, rather than
    // leaving an empty-but-present entry behind.
    fun removeValue(context: Context, scopeKey: String, value: String) {
        val scope = loadScope(context, scopeKey) ?: return
        val updatedEntries = scope.entries.filterNot { it.value == value }

        if (updatedEntries.isEmpty()) {
            prefs(context).edit().remove(scopeKey).apply()
        } else {
            saveScope(context, scopeKey, scope.copy(entries = updatedEntries))
        }
    }

    // Removes an entire field's history in one action -- the middle
    // ground between removeValue (one value) and clearAll (every field).
    fun clearScope(context: Context, scopeKey: String) {
        prefs(context).edit().remove(scopeKey).apply()
    }

    // The broad "CLEAR AUTOCOMPLETE HISTORY" action in PROTOCOL -- wipes
    // every scope's history at once.
    fun clearAll(context: Context) {
        prefs(context).edit().clear().apply()
    }

    private fun loadScope(context: Context, scopeKey: String): AutocompleteScope? {
        val raw = prefs(context).getString(scopeKey, null) ?: return null
        return try {
            json.decodeFromString(raw)
        } catch (_: Exception) {
            null
        }
    }

    private fun saveScope(context: Context, scopeKey: String, scope: AutocompleteScope) {
        prefs(context).edit().putString(scopeKey, json.encodeToString(scope)).apply()
    }

    // --- BACKUP ---
    // An explicit, fully-typed export/restore pair (rather than riding
    // CommandRepository's sparse matrixData dump) -- this repository's
    // dedicated prefs file makes a clean whole-file read/replace safe with
    // no exclusion list needed, since nothing else lives in it.

    fun exportForBackup(context: Context): Map<String, AutocompleteScope> {
        return listAllScopes(context).toMap()
    }

    // Restore-only: upserts by scope key -- a scope in the backup
    // replaces the local one with that key (or is added), and a local
    // scope whose key isn't in the backup is left untouched.
    fun restoreFromBackup(context: Context, data: Map<String, AutocompleteScope>) {
        val editor = prefs(context).edit()
        data.forEach { (scopeKey, scope) ->
            editor.putString(scopeKey, json.encodeToString(scope))
        }
        editor.apply()
    }
}
