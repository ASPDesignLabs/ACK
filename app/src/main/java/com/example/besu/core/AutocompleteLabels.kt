// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words only the MANAGE AUTOCOMPLETE tree needs: how a field is named in it. The words both trees share (the kinds, a default slot, unknown, a pose) are in [TreeLabels].
 * Read through a [TextSource]; a name the person gave is never passed through here.
 */
object AutocompleteLabels {
    private const val VARIABLE = "autocomplete_variable"
    private const val VARIABLE_ROOT = "autocomplete_variable_root"
    private const val VAR_N = "autocomplete_var_n"
    private const val TAG = "autocomplete_tag"

    /** A Matrix field: its number among the node's variables, and the shared root tag it is tied to if there is one. */
    fun variable(text: TextSource, slotIndex: Int, tag: String?): String =
        if (tag == null) text.get(VARIABLE, slotIndex + 1) else text.get(VARIABLE_ROOT, slotIndex + 1, tag)

    /** A Quick Actions field: `VAR:A` when the template names its tag (that is token syntax, not a word, so it is not translated), otherwise its number. */
    fun quickActionField(text: TextSource, tagIndex: Int, tag: String?): String = if (tag != null) "VAR:$tag" else text.get(VAR_N, tagIndex + 1)

    /** A Shared Root Variables field: its tag letter. */
    fun rootTag(text: TextSource, tag: String): String = text.get(TAG, tag)
}
