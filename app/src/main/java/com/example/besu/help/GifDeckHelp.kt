// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object GifDeckHelp {
    val module = HelpModule(
        id = "deck_gif",
        category = HelpCategory.USING_DECKS,
        title = "helpmod_deck_gif_title",
        summary = "helpmod_deck_gif_summary",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_deck_gif_intro_title",
                body = "helpmod_deck_gif_intro_body"
            ),
            HelpStep(
                id = "import",
                title = "helpmod_deck_gif_import_title",
                body = "helpmod_deck_gif_import_body",
                action = HelpAction.Interact(AckTags.GIF_IMPORT),
                targetTag = AckTags.GIF_IMPORT
            ),
            HelpStep(
                id = "commit_import",
                title = "helpmod_deck_gif_commit_import_title",
                body = "helpmod_deck_gif_commit_import_body",
                action = HelpAction.CommitFile(AckTags.GIF_IMPORT_COMMIT),
                targetTag = AckTags.GIF_IMPORT_COMMIT
            ),
            HelpStep(
                id = "category",
                title = "helpmod_deck_gif_category_title",
                body = "helpmod_deck_gif_category_body",
                action = HelpAction.Interact(AckTags.GIF_CATEGORY),
                targetTag = AckTags.GIF_CATEGORY
            ),
            HelpStep(
                id = "landscape",
                title = "helpmod_deck_gif_landscape_title",
                body = "helpmod_deck_gif_landscape_body",
                action = HelpAction.Interact(AckTags.GIF_LANDSCAPE_TOGGLE),
                targetTag = AckTags.GIF_LANDSCAPE_TOGGLE
            )
        )
    )
}