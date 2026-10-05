// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*

/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object DeckManagementHelp {
    val module = HelpModule(
        id = "deck_management",
        category = HelpCategory.BASICS_DECKS,
        title = "helpmod_deck_management_title",
        summary = "helpmod_deck_management_summary",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_deck_management_intro_title",
                body = "helpmod_deck_management_intro_body"
            ),
            HelpStep(
                id = "open_deck_menu",
                title = "helpmod_deck_management_open_deck_menu_title",
                body = "helpmod_deck_management_open_deck_menu_body",
                action = HelpAction.Interact(AckTags.DECK_SELECTOR),
                targetTag = AckTags.DECK_SELECTOR
            ),
            HelpStep(
                id = "create",
                title = "helpmod_deck_management_create_title",
                body = "helpmod_deck_management_create_body",
                action = HelpAction.Interact(AckTags.DECK_CREATE_BUTTON),
                targetTag = AckTags.DECK_CREATE_BUTTON
            ),
            HelpStep(
                id = "type",
                title = "helpmod_deck_management_type_title",
                body = "helpmod_deck_management_type_body",
                action = HelpAction.Interact(AckTags.DECK_CREATE_TYPE),
                targetTag = AckTags.DECK_CREATE_TYPE
            ),
            HelpStep(
                id = "commit",
                title = "helpmod_deck_management_commit_title",
                body = "helpmod_deck_management_commit_body",
                action = HelpAction.CommitText(AckTags.DECK_CREATE_COMMIT),
                targetTag = AckTags.DECK_CREATE_COMMIT
            ),
            HelpStep(
                id = "manage",
                title = "helpmod_deck_management_manage_title",
                body = "helpmod_deck_management_manage_body",
                action = HelpAction.Interact(AckTags.DECK_MANAGE_BUTTON),
                targetTag = AckTags.DECK_MANAGE_BUTTON
            )
        )
    )
}