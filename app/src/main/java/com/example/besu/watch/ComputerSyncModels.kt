package com.example.besu.watch

import kotlinx.serialization.Serializable

// Wire shape for WatchSync.sendComputerCategoriesForDeck's "/sys/computer_categories"
// payload. Deliberately a standalone DTO rather than reusing ComputerNode/
// ComputerCategory directly (computer/ComputerModels.kt) -- those carry
// fields (contactCard, legacyStrategy, persistUntilCleared, ...) the watch
// has no use for, and the wear module can't depend on this module's classes
// anyway (separate Gradle modules, separate APKs -- everything crossing the
// wire is hand-shaped). The wear module mirrors this exact shape in its own
// ComputerCategoryCache.kt; field names must match on both sides for
// kotlinx.serialization to decode it.
//
// JSON (not this app's usual pipe/colon-delimited watch payloads) is used
// here on purpose: category/entry labels are arbitrary user text that can
// contain any character, including the delimiters those simpler payloads
// assume won't show up. A tree is also more naturally nested than flat.
@Serializable
data class SyncedComputerNode(
    val id: String,
    val label: String,
    val isCategory: Boolean,
    // "" for a node attached directly under the category (there is no
    // synced node for the category's own root -- see flattenComputerNodes).
    val parentId: String
)

@Serializable
data class SyncedComputerCategory(
    val id: String,
    val label: String,
    val nodes: List<SyncedComputerNode>,
    // Mirrors this category's own activeNodeId (computer/ComputerModels.kt) so a
    // watch-side consumer (ACK Wear, and OVERSEER relayed through it) can show
    // which entry is currently active without a separate round trip. Null/blank
    // means no active pick, same meaning as the phone-side field.
    val activeNodeId: String? = null
)
