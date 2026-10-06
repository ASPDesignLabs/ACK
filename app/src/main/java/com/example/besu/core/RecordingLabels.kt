// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words MANAGE RECORDINGS shows around a recording that are decided, not just drawn: the overlay switch in the header, and what is shown in place of a prompt that has no text.
 * Plain Kotlin, read through a [TextSource], tested in every language.
 *
 * What the preview sends to the on-screen overlay is **not** translated: the overlay is for whoever is looking at the screen, and the visual overlay and everything spoken stay
 * as they were. So each [Missing] keeps its English [overlayText] for that, and has a translated [resource] only for the person's own list.
 */
object RecordingLabels {
    /** Why a recording has no prompt text to show. */
    enum class Missing(val overlayText: String, val resource: String) {
        EMPTY_PROMPT("(EMPTY PROMPT)", "manage_rec_empty_prompt"),
        UNKNOWN_NODE("(UNKNOWN NODE)", "manage_rec_unknown_node"),
    }

    private const val OVERLAY = "manage_rec_overlay"

    /** "[OVERLAY: ON]" or "[OVERLAY: OFF]", with ON and OFF in the same words as every other switch. */
    fun overlayToggle(text: TextSource, on: Boolean): String = text.get(OVERLAY, text.get(if (on) "common_on" else "common_off"))

    /** What the person's own list shows when there is no prompt text. */
    fun missingText(text: TextSource, missing: Missing): String = text.get(missing.resource)
}
