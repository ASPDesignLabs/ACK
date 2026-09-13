package com.example.besu

import kotlinx.serialization.Serializable

// CATEGORY nodes can hold children; ENTRY nodes are the selectable leaves.
// This is stored explicitly rather than inferred from children.isEmpty()
// because a freshly-created, still-empty category must not be mistaken for
// a selectable entry.
@Serializable
enum class ComputerNodeType { CATEGORY, ENTRY }

@Serializable
data class ComputerNode(
    val id: String,
    val label: String,
    val type: ComputerNodeType,
    val children: List<ComputerNode> = emptyList(),

    // PRE/POST hint carried over from a migrated TargetSlot, so the legacy
    // auto-inject behavior (TargetRepository.processPhrase) can keep working
    // unchanged after migration. Unused by anything else.
    val legacyStrategy: String? = null
)

@Serializable
data class ComputerCategory(
    // Stable identity a [COMPUTER:id] tag binds to. Never changes after
    // creation -- renaming a category only ever changes `label`, so saved
    // phrase templates never go stale.
    val id: String,
    val label: String,
    val persistUntilCleared: Boolean = true,
    val order: Int = 0,

    // The single active pick for this root category, or null for none.
    // One category has exactly one active entry at a time.
    val activeNodeId: String? = null,

    // root.type is always CATEGORY; root.label is unused (category.label is
    // what's shown -- root exists purely to hold top-level children).
    val root: ComputerNode
)
