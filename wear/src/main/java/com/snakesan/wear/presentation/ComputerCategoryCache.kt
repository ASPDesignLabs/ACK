package com.example.besu.wear

import androidx.compose.runtime.mutableStateMapOf
import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json

// Mirrors app/src/main/java/com/example/besu/watch/ComputerSyncModels.kt on
// the phone side field-for-field -- kotlinx.serialization decodes by shape,
// not by shared class identity, and the two modules can't depend on each
// other's classes (separate Gradle modules, separate APKs). Keep these two
// files in sync by hand if either one's fields ever change.
@Serializable
data class SyncedComputerNode(
    val id: String,
    val label: String,
    val isCategory: Boolean,
    val parentId: String
)

@Serializable
data class SyncedComputerCategory(
    val id: String,
    val label: String,
    val nodes: List<SyncedComputerNode>,
    // Mirrors the phone's own ComputerCategory.activeNodeId (see
    // watch/ComputerSyncModels.kt's copy of this DTO) -- lets a consumer show
    // which entry is currently active without a separate round trip.
    val activeNodeId: String? = null
)

// Watch-side cache of Target Computer categories, scoped to whatever the
// currently active Quick Actions deck's slots reference -- see the phone's
// WatchSync.sendComputerCategoriesForDeck. Rebuilt wholesale on every sync
// (deck activation), never merged incrementally: the phone is always the
// source of truth, and a stale category from a previously active deck must
// not survive into the next one.
object ComputerCategoryCache {
    private val json = Json { ignoreUnknownKeys = true }

    val categories = mutableStateMapOf<String, SyncedComputerCategory>()

    fun update(raw: String) {
        categories.clear()
        if (raw.isBlank()) return

        try {
            val parsed = json.decodeFromString<List<SyncedComputerCategory>>(raw)
            parsed.forEach { category -> categories[category.id] = category }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    // Direct children of `parentId` within one category's tree ("" = the
    // category's own top level), in the original phone-side order.
    fun childrenOf(categoryId: String, parentId: String): List<SyncedComputerNode> {
        return categories[categoryId]?.nodes.orEmpty().filter { it.parentId == parentId }
    }

    fun categoryLabel(categoryId: String): String = categories[categoryId]?.label ?: categoryId
}
