package com.example.besu.data

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID

// A composed, savable statement for the (planned) statement composer screen.
// `template` stores the raw text as typed, including any embedded
// TemplateEngine tokens ([COMPUTER:id], {VAR}/{VAR:A}/{VAR:B}/{VAR:C}) --
// never a resolved snapshot. This is what keeps a saved statement mutable:
// resolving it (for COPY or SPEAK) always re-reads whichever Target
// Computer entry or Shared Root Variable the tokens point at, the same way
// Matrix/Quick Actions phrases already do via TemplateEngine.resolve().
@Serializable
data class SavedStatement(
    val id: String = UUID.randomUUID().toString(),
    val label: String = "NEW STATEMENT",
    val template: String = "",
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
    val sortOrder: Long = System.currentTimeMillis()
)

object StatementRepository {
    private const val PREFS_NAME = "ack_statements"
    private const val KEY_STATEMENTS = "saved_statements"

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun getStatements(context: Context): List<SavedStatement> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_STATEMENTS, "[]") ?: "[]"
        return try {
            json.decodeFromString(raw)
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun getStatement(context: Context, id: String): SavedStatement? {
        return getStatements(context).firstOrNull { it.id == id }
    }

    // Merge-by-id: overwrites an existing statement in place, or inserts a
    // new one at the front. Never wipes the rest of the list first, per
    // ACK's additive-restore philosophy (see CLAUDE.md) -- this is also
    // what backup restore calls per-entry.
    fun upsertStatement(context: Context, statement: SavedStatement) {
        val list = getStatements(context).toMutableList()
        list.removeAll { it.id == statement.id }
        list.add(0, statement)
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_STATEMENTS, json.encodeToString(list)).apply()
    }

    fun deleteStatement(context: Context, id: String) {
        val list = getStatements(context).toMutableList()
        list.removeAll { it.id == id }
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_STATEMENTS, json.encodeToString(list)).apply()
    }
}
