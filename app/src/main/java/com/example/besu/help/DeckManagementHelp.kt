// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*

object DeckManagementHelp {
    val module = HelpModule(
        id = "deck_management",
        category = HelpCategory.BASICS_DECKS,
        title = "CREATING AND MANAGING {{DECKS:DECKS}}",
        summary = "CREATE, NAME, RECOLOR, ORGANIZE, AND DELETE {{DECKS:DECKS}}.",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "DECKS",
                body = "{{DECKS:Decks}} organize different communication workflows. " +
                    "The DEFAULT MATRIX {{DECK:deck}} is permanent; custom {{DECKS:decks}} can " +
                    "be created, renamed, recolored, and removed."
            ),
            HelpStep(
                id = "open_deck_menu",
                title = "OPEN {{DECK:DECK}} CONTROL",
                body = "Tap the current {{DECK:DECK}} label.",
                action = HelpAction.Interact(AckTags.DECK_SELECTOR),
                targetTag = AckTags.DECK_SELECTOR
            ),
            HelpStep(
                id = "create",
                title = "CREATE A {{DECK:DECK}}",
                body = "Choose {{DECK_CREATE:CREATE DECK}} to start a new specialized {{DECK:deck}}.",
                action = HelpAction.Interact(AckTags.DECK_CREATE_BUTTON),
                targetTag = AckTags.DECK_CREATE_BUTTON
            ),
            HelpStep(
                id = "type",
                title = "CHOOSE A {{DECK:DECK}} TYPE",
                body = "Choose the {{DECK:deck}} type that fits the workflow: Quick " +
                    "Actions, Emergency, Emoji, or GIF.",
                action = HelpAction.Interact(AckTags.DECK_CREATE_TYPE),
                targetTag = AckTags.DECK_CREATE_TYPE
            ),
            HelpStep(
                id = "commit",
                title = "DEPLOY THE {{DECK:DECK}}",
                body = "Name the {{DECK:deck}}, choose its color, then create it.",
                action = HelpAction.CommitText(AckTags.DECK_CREATE_COMMIT),
                targetTag = AckTags.DECK_CREATE_COMMIT
            ),
            HelpStep(
                id = "manage",
                title = "MANAGE EXISTING {{DECKS:DECKS}}",
                body = "Use MANAGE to rename, recolor, or remove a custom {{DECK:deck}}.",
                action = HelpAction.Interact(AckTags.DECK_MANAGE_BUTTON),
                targetTag = AckTags.DECK_MANAGE_BUTTON
            )
        )
    )
}