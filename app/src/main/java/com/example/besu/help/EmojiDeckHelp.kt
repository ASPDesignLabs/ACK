// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object EmojiDeckHelp {
    val module = HelpModule(
        id = "deck_emoji",
        category = HelpCategory.USING_DECKS,
        title = "helpmod_deck_emoji_title",
        summary = "helpmod_deck_emoji_summary",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_deck_emoji_intro_title",
                body = "helpmod_deck_emoji_intro_body"
            ),
            HelpStep(
                id = "slot",
                title = "helpmod_deck_emoji_slot_title",
                body = "helpmod_deck_emoji_slot_body",
                action = HelpAction.Interact(AckTags.EMOJI_SLOT),
                targetTag = AckTags.EMOJI_SLOT
            ),
            HelpStep(
                id = "library",
                title = "helpmod_deck_emoji_library_title",
                body = "helpmod_deck_emoji_library_body",
                action = HelpAction.Interact(AckTags.EMOJI_LIBRARY),
                targetTag = AckTags.EMOJI_LIBRARY
            ),
            HelpStep(
                id = "related",
                title = "helpmod_deck_emoji_related_title",
                body = "helpmod_deck_emoji_related_body",
                action = HelpAction.Interact(AckTags.EMOJI_RELATED_PANEL),
                targetTag = AckTags.EMOJI_RELATED_PANEL
            ),
            HelpStep(
                id = "clear",
                title = "helpmod_deck_emoji_clear_title",
                body = "helpmod_deck_emoji_clear_body",
                action = HelpAction.OverlayCleared(AckTags.EMOJI_SLOT),
                targetTag = AckTags.EMOJI_SLOT
            )
        )
    )
}