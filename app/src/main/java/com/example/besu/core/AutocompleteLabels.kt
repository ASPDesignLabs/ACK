// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words the MANAGE AUTOCOMPLETE tree shows for a field: which kind of field a branch holds, a variable's number, a default slot name, a pose name. Read through a
 * [TextSource] so they are in the chosen language; plain Kotlin so they are tested. The tree is built outside any composable, so it is handed the text source rather
 * than calling a composable. A name the person gave (a deck, a profile, a layer, a group or a slot) is never passed through here: it is shown exactly as typed.
 */
object AutocompleteLabels {
    enum class Kind(val labelResource: String) {
        MATRIX("label_deck_type_matrix"),
        QUICK_ACTIONS("label_deck_type_quick"),
        SHARED_ROOT("label_shared_variables"),
    }

    /**
     * Stands in for a pose or layer the field's own node could not be found for. It cannot be the name of a layer a person made (those are capitals, digits, spaces, underscores
     * and hyphens only), so it is never shown as if it were one; it is only ever a grouping key, and its label is [unknown].
     */
    const val UNKNOWN_KEY = "?"

    private const val KIND_COUNT = "autocomplete_kind_count"
    private const val VARIABLE = "autocomplete_variable"
    private const val VARIABLE_ROOT = "autocomplete_variable_root"
    private const val VAR_N = "autocomplete_var_n"
    private const val TAG = "autocomplete_tag"
    private const val SLOT_N = "autocomplete_slot_n"
    private const val UNKNOWN = "autocomplete_unknown"
    private const val UNKNOWN_NODE = "autocomplete_unknown_node"

    /** "MATRIX (3)": the kind in the same words the deck types and the shared variables are called elsewhere, and how many fields it holds. */
    fun kindHeading(text: TextSource, kind: Kind, count: Int): String = text.get(KIND_COUNT, text.get(kind.labelResource), count)

    /** A Matrix field: its number among the node's variables, and the shared root tag it is tied to if there is one. */
    fun variable(text: TextSource, slotIndex: Int, tag: String?): String =
        if (tag == null) text.get(VARIABLE, slotIndex + 1) else text.get(VARIABLE_ROOT, slotIndex + 1, tag)

    /** A Quick Actions field: `VAR:A` when the template names its tag (that is token syntax, not a word, so it is not translated), otherwise its number. */
    fun quickActionField(text: TextSource, tagIndex: Int, tag: String?): String = if (tag != null) "VAR:$tag" else text.get(VAR_N, tagIndex + 1)

    /** A Shared Root Variables field: its tag letter. */
    fun rootTag(text: TextSource, tag: String): String = text.get(TAG, tag)

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
