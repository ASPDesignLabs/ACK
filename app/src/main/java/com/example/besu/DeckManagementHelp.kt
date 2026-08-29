package com.example.besu



object DeckManagementHelp {
    val module = HelpModule(
        id = "deck_management",
        category = HelpCategory.BASICS_DECKS,
        title = "CREATING AND MANAGING DECKS",
        summary = "CREATE, NAME, RECOLOR, ORGANIZE, AND DELETE DECKS.",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "DECKS",
                body = "Decks organize different communication workflows. " +
                    "The DEFAULT MATRIX deck is permanent; custom decks can " +
                    "be created, renamed, recolored, and removed."
            ),
            HelpStep(
                id = "open_deck_menu",
                title = "OPEN DECK CONTROL",
                body = "Tap the current DECK label.",
                action = HelpAction.Interact(AckTags.DECK_SELECTOR),
                targetTag = AckTags.DECK_SELECTOR
            ),
            HelpStep(
                id = "create",
                title = "CREATE A DECK",
                body = "Choose CREATE DECK to start a new specialized deck.",
                action = HelpAction.Interact(AckTags.DECK_CREATE_BUTTON),
                targetTag = AckTags.DECK_CREATE_BUTTON
            ),
            HelpStep(
                id = "type",
                title = "CHOOSE A DECK TYPE",
                body = "Choose the deck type that fits the workflow: Quick " +
                    "Actions, Emergency, Emoji, or GIF.",
                action = HelpAction.Interact(AckTags.DECK_CREATE_TYPE),
                targetTag = AckTags.DECK_CREATE_TYPE
            ),
            HelpStep(
                id = "commit",
                title = "DEPLOY THE DECK",
                body = "Name the deck, choose its color, then create it.",
                action = HelpAction.CommitText(AckTags.DECK_CREATE_COMMIT),
                targetTag = AckTags.DECK_CREATE_COMMIT
            ),
            HelpStep(
                id = "manage",
                title = "MANAGE EXISTING DECKS",
                body = "Use MANAGE to rename, recolor, or remove a custom deck.",
                action = HelpAction.Interact(AckTags.DECK_MANAGE_BUTTON),
                targetTag = AckTags.DECK_MANAGE_BUTTON
            )
        )
    )
}