package com.example.besu.data

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID

enum class StatementNodeType { FOLDER, STATEMENT }

// A node in the statement tree -- a FOLDER (organizational, children only)
// or a STATEMENT (a leaf carrying actual composed text). Deliberately
// mirrors ComputerNode's own CATEGORY/ENTRY shape: leaf-only fields live
// directly on the node rather than nesting a separate "SavedStatement"
// object inside a generic tree wrapper, same "tree > leaf" organization
// Target Computer entries already use.
//
// template keeps [COMPUTER:id]/{VAR:A} tokens raw, never a resolved
// snapshot -- same mutability rule the whole statement composer system is
// built on (see CLAUDE.md). variableContext is which Shared Root Variables
// grouping the leaf's {VAR:A/B/C} tokens resolve against.
@Serializable
data class StatementNode(
    val id: String = UUID.randomUUID().toString(),
    val label: String = "NEW",
    val type: StatementNodeType = StatementNodeType.STATEMENT,
    val children: List<StatementNode> = emptyList(),
    val template: String = "",
    val variableContext: String = "IDENTITY",
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)

object StatementRepository {
    private const val PREFS_NAME = "ack_statements"
    private const val KEY_TREE = "statement_tree"

    // Pre-tree flat storage. Read exactly once, for migration -- never
    // written to again once a tree exists, and never deleted, so an old
    // build's data is never at risk even if migration somehow needs
    // re-reading.
    private const val KEY_LEGACY_STATEMENTS = "saved_statements"

    const val ROOT_ID = "ROOT"

    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun getRoot(context: Context): StatementNode {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_TREE, null)
        if (raw != null) {
            return try {
                json.decodeFromString(raw)
            } catch (_: Exception) {
                emptyRoot()
            }
        }

        // No tree yet -- migrate anything saved under the old flat list
        // before this system existed, once, additively. Never drops
        // statements a tester already created.
        val migrated = migrateLegacyStatements(context)
        saveRoot(context, migrated)
        return migrated
    }

    fun saveRoot(context: Context, root: StatementNode) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_TREE, json.encodeToString(root)).apply()
    }

    fun findNode(root: StatementNode, id: String): StatementNode? {
        if (root.id == id) return root
        root.children.forEach { child ->
            findNode(child, id)?.let { return it }
        }
        return null
    }

    // Merge-by-id upsert, additive per ACK's restore philosophy: an
    // existing node with this id is removed from wherever it currently
    // lives (so re-saving under a different parentId moves it) and
    // reinserted under parentId; a new id is simply added there.
    fun upsertNode(context: Context, node: StatementNode, parentId: String = ROOT_ID) {
        val withoutExisting = removeNode(getRoot(context), node.id)
        val updated = addChild(withoutExisting, parentId, node)
            ?: withoutExisting.copy(children = withoutExisting.children + node)
        saveRoot(context, updated)
    }

    fun createFolder(context: Context, label: String, parentId: String = ROOT_ID): StatementNode {
        val folder = StatementNode(label = label, type = StatementNodeType.FOLDER)
        upsertNode(context, folder, parentId)
        return folder
    }

    fun deleteNode(context: Context, id: String) {
        saveRoot(context, removeNode(getRoot(context), id))
    }

    fun renameNode(context: Context, id: String, label: String) {
        saveRoot(context, transformNode(getRoot(context), id) { it.copy(label = label) })
    }

    // Every FOLDER in the tree, root included, depth-first -- the source
    // list for any "pick a destination folder" UI (SAVE's folder picker,
    // MY STATEMENTS' new-folder parent picker).
    fun listFolders(root: StatementNode, depth: Int = 0): List<Pair<StatementNode, Int>> {
        if (root.type != StatementNodeType.FOLDER) return emptyList()
        return listOf(root to depth) + root.children.flatMap { listFolders(it, depth + 1) }
    }

    private fun emptyRoot(): StatementNode {
        return StatementNode(id = ROOT_ID, label = "STATEMENTS", type = StatementNodeType.FOLDER)
    }

    private fun migrateLegacyStatements(context: Context): StatementNode {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_LEGACY_STATEMENTS, "[]") ?: "[]"
        val legacy = try {
            json.decodeFromString<List<LegacySavedStatement>>(raw)
        } catch (_: Exception) {
            emptyList()
        }

        val children = legacy.map { statement ->
            StatementNode(
                id = statement.id,
                label = statement.label,
                type = StatementNodeType.STATEMENT,
                template = statement.template,
                variableContext = statement.variableContext,
                createdAt = statement.createdAt,
                updatedAt = statement.updatedAt
            )
        }

        return emptyRoot().copy(children = children)
    }

    private fun addChild(node: StatementNode, parentId: String, child: StatementNode): StatementNode? {
        if (node.id == parentId) {
            return node.copy(children = node.children + child)
        }
        var found = false
        val newChildren = node.children.map { existing ->
            val result = addChild(existing, parentId, child)
            if (result != null) found = true
            result ?: existing
        }
        return if (found) node.copy(children = newChildren) else null
    }

    private fun removeNode(node: StatementNode, id: String): StatementNode {
        val filtered = node.children.filterNot { it.id == id }
        return node.copy(children = filtered.map { removeNode(it, id) })
    }

    private fun transformNode(
        node: StatementNode,
        id: String,
        transform: (StatementNode) -> StatementNode
    ): StatementNode {
        if (node.id == id) return transform(node)
        return node.copy(children = node.children.map { transformNode(it, id, transform) })
    }
}

// The pre-tree shape, kept private and only for one-time migration --
// StatementRepository.getRoot() reads this exactly once per device.
@Serializable
private data class LegacySavedStatement(
    val id: String = UUID.randomUUID().toString(),
    val label: String = "NEW STATEMENT",
    val template: String = "",
    val variableContext: String = "IDENTITY",
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
    val sortOrder: Long = System.currentTimeMillis()
)
