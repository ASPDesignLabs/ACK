package com.example.besu

object HelpRegistry {
    val modules: List<HelpModule> = listOf(
        BasicsNavigationHelp.module,
        // DeckManagementHelp.module replaces what used to be an inline stub
        // module of the same id here -- it covers the same ground plus deck
        // type selection, commit, and MANAGE, once those tags were wired into
        // CreateDeckDialog.kt and MainActivity.kt's deck menu.
        DeckManagementHelp.module,
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
        QuickActionsDeckHelp.module,
        EmergencyDeckHelp.module,
        EmojiDeckHelp.module,
        GifDeckHelp.module
    ) + MatrixDeckHelp.modules + PersonalizationHelp.module + SettingsManagementHelp.module +
        TargetComputerHelp.module + FieldOpsHelp.modules
}
