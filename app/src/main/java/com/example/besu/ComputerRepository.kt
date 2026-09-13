package com.example.besu

import android.content.Context
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID

object ComputerRepository {
    private const val PREFS_NAME = "ack_targets"
    private const val KEY_CATEGORIES = "computer_categories"

    private val DEFAULT_CATEGORY_LABELS = listOf("PEOPLE", "PLACES", "FOOD/DRINK", "ACTIONS")

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }

    // --- STORAGE (CRUD) ---

    fun getCategories(context: Context): List<ComputerCategory> {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val raw = prefs.getString(KEY_CATEGORIES, "[]") ?: "[]"
        return try { json.decodeFromString(raw) } catch (e: Exception) { emptyList() }
    }

    fun saveCategory(context: Context, category: ComputerCategory) {
        val categories = getCategories(context).toMutableList()
        categories.removeAll { it.id == category.id }
        categories.add(category)
        categories.sortBy { it.order }
        saveCategories(context, categories)
    }

    fun createCategory(context: Context, label: String): ComputerCategory {
        val existing = getCategories(context)
        val id = uniqueCategoryId(slugify(label), existing)

        val category = ComputerCategory(
            id = id,
            label = label,
            order = (existing.maxOfOrNull { it.order } ?: -1) + 1,
            root = ComputerNode(id = newNodeId(), label = label, type = ComputerNodeType.CATEGORY)
        )

        saveCategory(context, category)
        return category
    }

    fun deleteCategory(context: Context, categoryId: String) {
        val categories = getCategories(context).toMutableList()
        categories.removeAll { it.id == categoryId }
        saveCategories(context, categories)
    }

    // Restore-only: replaces the entire category list wholesale, matching
    // this app's "a restore mirrors the backup exactly" convention (see
    // TransferManager.applyBackupToStorage).
    fun replaceCategories(context: Context, categories: List<ComputerCategory>) {
        saveCategories(context, categories)
    }

    private fun saveCategories(context: Context, categories: List<ComputerCategory>) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_CATEGORIES, json.encodeToString(categories)).apply()
    }

    private fun updateCategory(
        context: Context,
        categoryId: String,
        transform: (ComputerCategory) -> ComputerCategory
    ) {
        val categories = getCategories(context).map {
            if (it.id == categoryId) transform(it) else it
        }
        saveCategories(context, categories)
    }

    // --- TREE MUTATION (scoped to one category's root node) ---

    fun addNode(
        context: Context,
        categoryId: String,
        parentNodeId: String,
        label: String,
        type: ComputerNodeType
    ): ComputerNode {
        val newNode = ComputerNode(id = newNodeId(), label = label, type = type)

        updateCategory(context, categoryId) { category ->
            category.copy(root = mapNode(category.root, parentNodeId) { parent ->
                parent.copy(children = parent.children + newNode)
            })
        }

        return newNode
    }

    fun renameNode(context: Context, categoryId: String, nodeId: String, newLabel: String) {
        updateCategory(context, categoryId) { category ->
            category.copy(root = mapNode(category.root, nodeId) { it.copy(label = newLabel) })
        }
    }

    fun deleteNode(context: Context, categoryId: String, nodeId: String) {
        updateCategory(context, categoryId) { category ->
            val prunedRoot = pruneNode(category.root, nodeId)
            val activeStillPresent = category.activeNodeId?.let { activeId ->
                findNode(prunedRoot, activeId) != null
            } ?: true

            category.copy(
                root = prunedRoot,
                activeNodeId = if (activeStillPresent) category.activeNodeId else null
            )
        }
    }

    fun findNode(category: ComputerCategory, nodeId: String): ComputerNode? =
        findNode(category.root, nodeId)

    fun findPath(category: ComputerCategory, nodeId: String): List<ComputerNode> {
        val path = mutableListOf<ComputerNode>()

        fun walk(node: ComputerNode): Boolean {
            path.add(node)
            if (node.id == nodeId) return true
            for (child in node.children) {
                if (walk(child)) return true
            }
            path.removeAt(path.lastIndex)
            return false
        }

        walk(category.root)
        return path
    }

    private fun findNode(node: ComputerNode, nodeId: String): ComputerNode? {
        if (node.id == nodeId) return node
        for (child in node.children) {
            findNode(child, nodeId)?.let { return it }
        }
        return null
    }

    private fun mapNode(
        node: ComputerNode,
        targetId: String,
        transform: (ComputerNode) -> ComputerNode
    ): ComputerNode {
        if (node.id == targetId) return transform(node)
        if (node.children.isEmpty()) return node
        return node.copy(children = node.children.map { mapNode(it, targetId, transform) })
    }

    private fun pruneNode(node: ComputerNode, targetId: String): ComputerNode {
        val remaining = node.children.filter { it.id != targetId }
        return node.copy(children = remaining.map { pruneNode(it, targetId) })
    }

    // --- ACTIVE SELECTION ---

    fun setActiveEntry(context: Context, categoryId: String, leafNodeId: String) {
        updateCategory(context, categoryId) { category ->
            val node = findNode(category, leafNodeId)
            if (node != null && node.type == ComputerNodeType.ENTRY) {
                category.copy(activeNodeId = leafNodeId)
            } else {
                category
            }
        }
    }

    fun clearActiveEntry(context: Context, categoryId: String) {
        updateCategory(context, categoryId) { it.copy(activeNodeId = null) }
    }

    fun getActiveEntry(context: Context, categoryId: String): ComputerNode? {
        val category = getCategories(context).find { it.id == categoryId } ?: return null
        val activeId = category.activeNodeId ?: return null
        return findNode(category, activeId)
    }

    // --- [COMPUTER:CATEGORY] RESOLUTION ---
    // resolveTag is a pure read with no side effects. Single-use consumption
    // is a separate, explicit step -- see consumeIfSingleUse below for why.

    fun resolveTag(context: Context, categoryId: String): String {
        return getActiveEntry(context, categoryId)?.label.orEmpty()
    }

    // Call this exactly once, only from a path that has actually committed a
    // phrase to output (e.g. OutputService dispatch, WearListenerService's
    // triggerVoice) -- never from a preview/debug resolution. This app's
    // matrix "PLAY" flow already resolves a phrase twice per tap (once for
    // an on-screen debug log, once for the real spoken output); wiring
    // consumption into resolveTag itself would consume a single-use pick on
    // the debug pass before the real one ever runs.
    fun consumeIfSingleUse(context: Context, categoryId: String) {
        val category = getCategories(context).find { it.id == categoryId } ?: return
        if (!category.persistUntilCleared) {
            clearActiveEntry(context, categoryId)
        }
    }

    // --- INITIALIZATION & MIGRATION ---

    // didMigrate tells the caller whether the legacy 8-slot data just moved,
    // so the UI can surface a one-time "here's what happened" notice instead
    // of silently transforming data -- see migrateLegacyTargetsIfNeeded.
    data class InitResult(val categories: List<ComputerCategory>, val didMigrate: Boolean)

    // Call from wherever the Targeting Computer UI first needs data (not
    // wired into app startup itself -- see migrateLegacyTargetsIfNeeded).
    fun ensureInitialized(context: Context): InitResult {
        val existing = getCategories(context)
        if (existing.isNotEmpty()) return InitResult(existing, didMigrate = false)

        if (migrateLegacyTargetsIfNeeded(context)) {
            return InitResult(getCategories(context), didMigrate = true)
        }

        val seeded = DEFAULT_CATEGORY_LABELS.mapIndexed { index, label ->
            ComputerCategory(
                id = slugify(label),
                label = label,
                order = index,
                root = ComputerNode(id = newNodeId(), label = label, type = ComputerNodeType.CATEGORY)
            )
        }

        saveCategories(context, seeded)
        return InitResult(seeded, didMigrate = false)
    }

    // Idempotent: a category tree already existing on this device means
    // migration already ran (or the user built one from scratch), so this
    // is a no-op. Takes an automatic local backup before touching anything,
    // and never deletes the legacy TargetSlot data it reads from -- it's
    // left inert as a rollback path, matching "edits need to be confirmed."
    fun migrateLegacyTargetsIfNeeded(context: Context): Boolean {
        if (getCategories(context).isNotEmpty()) return false

        val legacyTargets = TargetRepository.getTargets(context)
        if (legacyTargets.isEmpty()) return false

        if (!TransferManager.writeInternalSnapshot(context, "pre_migration")) {
            // Backup-first is non-negotiable: don't transform data we
            // couldn't safety-net. The old 8-slot screen keeps working.
            return false
        }

        val peopleChildren = legacyTargets.sortedBy { it.index }.map { slot ->
            ComputerNode(
                id = newNodeId(),
                label = slot.label,
                type = ComputerNodeType.ENTRY,
                legacyStrategy = slot.defaultStrategy
            )
        }

        val peopleCategory = ComputerCategory(
            id = "PEOPLE",
            label = "PEOPLE",
            order = 0,
            root = ComputerNode(
                id = newNodeId(),
                label = "PEOPLE",
                type = ComputerNodeType.CATEGORY,
                children = peopleChildren
            )
        )

        saveCategories(context, listOf(peopleCategory))
        return true
    }

    // --- ID GENERATION ---

    private fun newNodeId(): String = UUID.randomUUID().toString()

    private fun slugify(label: String): String {
        val upper = label.trim().uppercase().replace(Regex("[^A-Z0-9]+"), "_").trim('_')
        return upper.ifEmpty { "CATEGORY" }.take(24)
    }

    private fun uniqueCategoryId(base: String, existing: List<ComputerCategory>): String {
        if (existing.none { it.id == base }) return base

        var suffix = 2
        while (existing.any { it.id == "${base}_$suffix" }) {
            suffix++
        }
        return "${base}_$suffix"
    }
}
