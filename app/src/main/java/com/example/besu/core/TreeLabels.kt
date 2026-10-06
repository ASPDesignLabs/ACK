// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words the two browsing trees share (MANAGE AUTOCOMPLETE and MANAGE RECORDINGS): which kind of thing a branch holds and how many, the default name of a slot,
 * "unknown", and a pose or layer as a group heading. Read through a [TextSource] so they are in the chosen language; plain Kotlin so they are tested. The trees are built
 * outside any composable, so they are handed the text source rather than calling a composable. A name the person gave (a deck, a profile, a layer, a group, a slot or a key)
 * is never passed through here: it is shown exactly as typed.
 */
object TreeLabels {
    enum class Kind(val labelResource: String) {
        MATRIX("label_deck_type_matrix"),
        QUICK_ACTIONS("label_deck_type_quick"),
        QUICK_ACCESS_KEYS("label_quick_access_keys"),
        SHARED_ROOT("label_shared_variables"),
    }

    /**
     * Stands in for a pose or layer the field's own node could not be found for. It cannot be the name of a layer a person made (those are capitals, digits, spaces, underscores
     * and hyphens only), so it is never shown as if it were one; it is only ever a grouping key, and its label is [unknown].
     */
    const val UNKNOWN_KEY = "?"

    private const val KIND_COUNT = "tree_kind_count"
    private const val SLOT_N = "tree_slot_n"
    private const val UNKNOWN = "tree_unknown"
    private const val UNKNOWN_NODE = "tree_unknown_node"

    /** "MATRIX (3)": the kind in the same words the deck types, the quick-access keys and the shared variables are called elsewhere, and how many it holds. */
    fun kindHeading(text: TextSource, kind: Kind, count: Int): String = text.get(KIND_COUNT, text.get(kind.labelResource), count)

    /** The name a Quick Actions slot is shown with when its own label cannot be found. */
    fun defaultSlot(text: TextSource, slotIndex: Int): String = text.get(SLOT_N, slotIndex + 1)

    fun unknown(text: TextSource): String = text.get(UNKNOWN)

    fun unknownNode(text: TextSource): String = text.get(UNKNOWN_NODE)

    /**
     * A pose or layer name as a group heading: IDENTITY, DEFEND and CONNECT are shown the way the Matrix screen shows them (the standard name in the chosen language),
     * a layer the person made is shown exactly as typed, and [UNKNOWN_KEY] is shown as UNKNOWN. What groups and identifies the branch is still the stored name.
     */
    fun poseOrLayer(text: TextSource, stored: String): String {
        if (stored == UNKNOWN_KEY) return unknown(text)
        val key = PlainLabels.poseLabelKey(stored) ?: return stored
        return text.get(key.resourceName(false))
    }
}
