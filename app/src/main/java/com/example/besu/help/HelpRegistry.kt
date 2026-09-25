package com.example.besu.help

import com.example.besu.*
import com.example.besu.decks.*
object HelpRegistry {
    val modules: List<HelpModule> = listOf(
        BasicsNavigationHelp.module,
        // DeckManagementHelp.module replaces what used to be an inline stub
        // module of the same id here -- it covers the same ground plus deck
        // type selection, commit, and MANAGE, once those tags were wired into
        // CreateDeckDialog.kt and MainActivity.kt's deck menu.
        DeckManagementHelp.module,
        // TYPE now shows the statement composer -- StatementComposerHelp.module
        // below covers it. This module is specifically about MEMORY BANKS/
        // saved phrases/direct text output, the classic screen's own
        // features, so it routes to TERMINAL instead and walks the user
        // through /m rather than the TYPE tab. See MainActivity's
        // onShowManualOverride, which dispatches this module's WatchEvent
        // once /m actually opens the overlay.
        HelpModule(
            id = "manual_override",
            category = HelpCategory.BASICS_MANUAL_OVERRIDE,
            title = "MANUAL OVERRIDE",
            summary = "MEMORY BANKS, SAVED PHRASES, AND DIRECT TEXT OUTPUT.",
            destination = HelpDestination.TERMINAL,
            steps = listOf(
                HelpStep(
                    id = "intro",
                    title = "MANUAL OVERRIDE",
                    body = "Manual Override provides direct text communication " +
                        "when watch input is unavailable or inconvenient. It's " +
                        "reached from TERMINAL now that TYPE is the statement " +
                        "composer."
                ),
                HelpStep(
                    id = "open_manual",
                    title = "OPEN MANUAL INPUT",
                    body = "Type /m at the TERMINAL prompt and send it.",
                    action = HelpAction.WatchEvent("MANUAL_OVERRIDE_OPENED")
                )
            )
        ),
        StatementComposerHelp.module,
        GeoProtocolHelp.module,
        LogsHelp.module,
        QuickActionsDeckHelp.module,
        EmergencyDeckHelp.module,
        EmojiDeckHelp.module,
        GifDeckHelp.module
    ) + MatrixDeckHelp.modules + PersonalizationHelp.module + SettingsManagementHelp.module +
        TargetComputerHelp.module + FieldOpsHelp.modules + VoiceRecordingsHelp.modules
}
