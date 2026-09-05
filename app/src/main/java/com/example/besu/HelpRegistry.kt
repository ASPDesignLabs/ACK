package com.example.besu

object HelpRegistry {
    val modules: List<HelpModule> = listOf(
        BasicsNavigationHelp.module,
        HelpModule(
            id = "deck_management",
            category = HelpCategory.BASICS_DECKS,
            title = "DECK MANAGEMENT",
            summary = "CREATE, ORGANIZE, RECOLOR, AND REMOVE DECKS.",
            destination = HelpDestination.MATRIX,
            steps = listOf(
                HelpStep(
                    id = "intro",
                    title = "WELCOME TO DECK MANAGEMENT",
                    body = "Using colors and names to assist with organization helps with accessing " +
                            "what you need quickly. Deck Management makes this easy. To manage decks " +
                            "we interact with the Deck Selector in the ACK Command Bar on top. "
                ),
                HelpStep(
                    id = "deck_selector",
                    title = "CUSTOMIZING DECKS",
                    body = "Tapping the highlighted Deck Selector opens our Deck Selection menu, which " +
                            "gives you access to deck management tools. CREATE DECK and MANAGE.",
                    action = HelpAction.Interact(AckTags.DECK_SELECTOR),
                    targetTag = AckTags.DECK_SELECTOR
                ),
                HelpStep(
                    id = "create",
                    title = "CREATE A DECK",
                    body = "Choose CREATE DECK to make a specialized deck.",
                    action = HelpAction.Interact(AckTags.DECK_CREATE_BUTTON),
                    targetTag = AckTags.DECK_CREATE_BUTTON
                )
            )
        ),
        HelpModule(
            id = "manual_override",
            category = HelpCategory.BASICS_MANUAL_OVERRIDE,
            title = "MANUAL OVERRIDE",
            summary = "MEMORY BANKS, SAVED PHRASES, AND DIRECT TEXT OUTPUT.",
            destination = HelpDestination.TYPE,
            steps = listOf(
                HelpStep(
                    id = "intro",
                    title = "MANUAL OVERRIDE",
                    body = "Manual Override provides direct text communication " +
                        "when watch input is unavailable or inconvenient."
                ),
                HelpStep(
                    id = "open_manual",
                    title = "OPEN MANUAL INPUT",
                    body = "Tap the keyboard navigation control.",
                    action = HelpAction.Interact(AckTags.MANUAL_INPUT_BTN),
                    targetTag = AckTags.MANUAL_INPUT_BTN
                )
            )
        ),
        GeoProtocolHelp.module,
        LogsHelp.module,
        QuickActionsDeckHelp.module
    ) + MatrixDeckHelp.modules + PersonalizationHelp.module + SettingsManagementHelp.module +
        TargetComputerHelp.module + FieldOpsHelp.modules
}
