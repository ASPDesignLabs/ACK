// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data
import android.content.Context

// Stubs of the autocomplete history types and repository MANAGE AUTOCOMPLETE reads (they read preferences), written from their real signatures.
data class AutocompleteEntry(val value: String, val count: Int = 1, val lastUsedAt: Long = 0L)

data class AutocompleteScopeInfo(
    val fieldType: String,
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
    }
}

data class AutocompleteScope(val info: AutocompleteScopeInfo, val entries: List<AutocompleteEntry> = emptyList())

object AutocompleteHistoryRepository {
    fun listAllScopes(context: Context): List<Pair<String, AutocompleteScope>> = emptyList()
    fun removeValue(context: Context, scopeKey: String, value: String) {}
    fun clearScope(context: Context, scopeKey: String) {}
    fun clearAll(context: Context) {}
}
