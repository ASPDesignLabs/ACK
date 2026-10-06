// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words of the one-time offer of the newer defaults (AUDIO ARCHITECT), read through a [TextSource] so they are in the chosen language. The banner says which of
 * the two defaults are on offer, so the choice of sentence is a decision and lives here, in plain Kotlin, where it is tested. Nothing in this file changes a setting.
 */
object DefaultsText {
    const val BANNER_VOICE = "defaults_banner_voice"
    const val BANNER_FULL = "defaults_banner_full"
    const val BANNER_BOTH = "defaults_banner_both"

    /**
     * The names of the two built-in voices the review sentences mention. They are names, not words to translate (the same in every language, like the chips that show
     * them), so a sentence takes them as arguments and never retypes them.
     */
    const val ORGANIC = "ORGANIC"
    const val CYBER = "CYBER"

    /** The sentence for what is on offer: the voice, the full message, or both. Empty when nothing is (the banner is not shown then). */
    fun banner(text: TextSource, offer: DefaultsOffer): String = when {
        offer.unprocessedVoice && offer.fullMessage -> text.get(BANNER_BOTH)
        offer.unprocessedVoice -> text.get(BANNER_VOICE)
        offer.fullMessage -> text.get(BANNER_FULL)
        else -> ""
    }
}
