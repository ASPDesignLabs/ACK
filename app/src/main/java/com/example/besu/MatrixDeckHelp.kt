package com.example.besu

object MatrixDeckHelpCopy {
    const val HEADER_INTRO =
        "The ACK Command Bar is your always-available control surface. " +
                "It shows your active deck, active profile, quick phrases, " +
                "watch connection state, system settings, and Help access."

    const val HEADER_DECK =
        "DECK selects the communication system currently loaded in ACK. " +
                "A deck can be a Matrix, emergency board, quick-action board, " +
                "emoji board, GIF board, or another custom workflow."

    const val HEADER_PROFILE =
        "PROFILE selects the active communication profile inside a Matrix " +
                "deck. Profiles let the same gesture structure use different " +
                "phrasing for different situations."

    const val HEADER_SHORTCUTS =
        "The compact buttons beside ACK are header shortcuts. Tap one to " +
                "immediately transmit its saved phrase without opening a deck."

    const val HEADER_PROTOCOL =
        "PROTOCOL opens system configuration: watch behavior, sensor " +
                "settings, shortcuts, data controls, and output preferences."

    const val HEADER_HELP =
        "HELP opens this training system. Modules guide you through live " +
                "controls instead of making you memorize the whole machine."

    const val HEADER_LINK =
        "The pulsing square is the watch link indicator. Its color and the " +
                "nearby status label show whether the watch is offline, armed, " +
                "locked, or actively communicating with ACK."

    const val HEADER_COMPLETE =
        "Command Bar training complete! The ACK Command Bar remains present " +
                "at all times, making access to shortcuts and status " +
                "effortless when using the app."

    const val DECK_PROFILE_START =
        "Start by selecting a Matrix deck. Matrix decks support profiles, " +
                "gesture mapping, local variables, and shared root values."

    const val DECK_PROFILE_PROFILE =
        "Now select a profile. Profiles let one gesture system adapt to " +
                "different communication contexts without rebuilding the Matrix."

    const val DECK_PROFILE_COMPLETE =
        "Deck and profile selection complete. You can now switch between " +
                "communication environments before transmitting a phrase."

    const val MATRIX_INTRO =
        "The ACK Matrix maps watch poses and twists to communication " +
                "phrases. Each category is a gesture context, and each row is " +
                "a phrase node that can be edited or played manually."

    const val MATRIX_IDENTITY =
        "ROOT :: IDENTITY is the primary status-reporting context. Its " +
                "gesture rows are commonly used for direct personal output. " +
                "Each row can hold a phrase and local fallback values."

    const val MATRIX_EDIT_FIRST =
        "Your first prompt lives in Twist 0. Tap the highlighted Twist 0 " +
                "row to open its Live Save Editor."

    const val MATRIX_EDITOR =
        "This is the Live Save Editor. Use MACRO TEMPLATE to type the phrase " +
                "you want ACK to transmit. Changes are saved while you work. " +
                "Variables are powerful and useful, but they get their own " +
                "training module so we do not summon the complexity goblins yet."

    const val MATRIX_COMMIT =
        "Destructive Controls can clear local values, the prompt, or both. " +
                "They are intentionally dramatic. Your prompt is already " +
                "live-saved, but tap COMMIT now to confirm this editing pass and " +
                "return to the Matrix."

    const val MATRIX_PLAYBACK =
        "Your prompt is now ready for manual playback. Tap the highlighted " +
                "play control beside Twist 0 to transmit the phrase you created."

    const val MATRIX_COMPLETE =
        "Prompt creation complete. You edited a Matrix node, saved its " +
                "template, and played it back from the Matrix."
}

object MatrixDeckHelp {
    const val HEADER_MODULE_ID = "ack_command_bar"
    const val DECK_PROFILE_MODULE_ID = "deck_profile_selection"
    const val PROMPTS_MODULE_ID = "matrix_prompt_creation"

    val modules: List<HelpModule> = listOf(
        HelpModule(
            id = HEADER_MODULE_ID,
            category = HelpCategory.BASICS_NAVIGATION,
            title = "ACK COMMAND BAR",
            summary = "HEADER CONTROLS, SHORTCUTS, WATCH LINK, AND HELP.",
            destination = HelpDestination.MATRIX,
            requiresMatrixDeck = true,
            steps = listOf(
                HelpStep(
                    id = "header_intro",
                    title = "ACK COMMAND BAR",
                    body = MatrixDeckHelpCopy.HEADER_INTRO
                ),
                HelpStep(
                    id = "header_deck",
                    title = "DECK SELECTOR",
                    body = MatrixDeckHelpCopy.HEADER_DECK,
                    targetTag = AckTags.DECK_SELECTOR
                ),
                HelpStep(
                    id = "header_profile",
                    title = "PROFILE SELECTOR",
                    body = MatrixDeckHelpCopy.HEADER_PROFILE,
                    targetTag = AckTags.PROFILE_SELECTOR
                ),
                HelpStep(
                    id = "header_shortcuts",
                    title = "SHORTCUT ROW",
                    body = MatrixDeckHelpCopy.HEADER_SHORTCUTS,
                    targetTag = AckTags.HEADER_SHORTCUTS
                ),
                HelpStep(
                    id = "header_protocol",
                    title = "PROTOCOL",
                    body = MatrixDeckHelpCopy.HEADER_PROTOCOL,
                    targetTag = AckTags.CONFIG_BUTTON
                ),
                HelpStep(
                    id = "header_help",
                    title = "HELP SYSTEM",
                    body = MatrixDeckHelpCopy.HEADER_HELP,
                    targetTag = AckTags.HELP_BUTTON
                ),
                HelpStep(
                    id = "header_watch_link",
                    title = "WATCH LINK",
                    body = MatrixDeckHelpCopy.HEADER_LINK,
                    targetTag = AckTags.LIVE_LINK
                ),
                HelpStep(
                    id = "header_complete",
                    title = "COMMAND BAR COMPLETE",
                    body = MatrixDeckHelpCopy.HEADER_COMPLETE
                )
            )
        ),
        HelpModule(
            id = DECK_PROFILE_MODULE_ID,
            category = HelpCategory.BASICS_NAVIGATION,
            title = "DECK AND PROFILE SELECTION",
            summary = "LOAD A MATRIX DECK, THEN SWITCH ITS ACTIVE PROFILE.",
            destination = HelpDestination.MATRIX,
            requiresMatrixDeck = true,
            steps = listOf(
                HelpStep(
                    id = "select_deck",
                    title = "SELECT A MATRIX DECK",
                    body = MatrixDeckHelpCopy.DECK_PROFILE_START,
                    action = HelpAction.DeckSelected(AckTags.DECK_SELECTOR),
                    targetTag = AckTags.DECK_SELECTOR
                ),
                HelpStep(
                    id = "select_profile",
                    title = "SELECT A PROFILE",
                    body = MatrixDeckHelpCopy.DECK_PROFILE_PROFILE,
                    action = HelpAction.ProfileSelected(
                        AckTags.PROFILE_SELECTOR
                    ),
                    targetTag = AckTags.PROFILE_SELECTOR
                ),
                HelpStep(
                    id = "deck_profile_complete",
                    title = "SELECTION COMPLETE",
                    body = MatrixDeckHelpCopy.DECK_PROFILE_COMPLETE
                )
            )
        ),
        HelpModule(
            id = PROMPTS_MODULE_ID,
            category = HelpCategory.BASICS_NAVIGATION,
            title = "CREATING AND USING PROMPTS",
            summary = "EDIT A MATRIX NODE, SAVE ITS TEMPLATE, AND PLAY IT.",
            destination = HelpDestination.MATRIX,
            requiresMatrixDeck = true,
            steps = listOf(
                HelpStep(
                    id = "matrix_intro",
                    title = "THE ACK MATRIX",
                    body = MatrixDeckHelpCopy.MATRIX_INTRO
                ),
                HelpStep(
                    id = "identity_root",
                    title = "ROOT :: IDENTITY",
                    body = MatrixDeckHelpCopy.MATRIX_IDENTITY,
                    targetTag = AckTags.MATRIX_ROOT_IDENTITY
                ),
                HelpStep(
                    id = "edit_twist_zero",
                    title = "EDIT YOUR FIRST PROMPT",
                    body = MatrixDeckHelpCopy.MATRIX_EDIT_FIRST,
                    action = HelpAction.Interact(
                        AckTags.MATRIX_ROW_TARGET
                    ),
                    targetTag = AckTags.MATRIX_ROW_TARGET
                ),
                HelpStep(
                    id = "macro_template",
                    title = "LIVE SAVE EDITOR",
                    body = MatrixDeckHelpCopy.MATRIX_EDITOR,
                    action = HelpAction.KeyboardDismissed(
                        AckTags.MACRO_TEMPLATE_INPUT
                    ),
                    targetTag = AckTags.MACRO_TEMPLATE_INPUT
                ),
                HelpStep(
                    id = "commit_prompt",
                    title = "SAVE YOUR PROMPT",
                    body = MatrixDeckHelpCopy.MATRIX_COMMIT,
                    action = HelpAction.Interact(
                        AckTags.MATRIX_COMMIT_BUTTON
                    ),
                    targetTag = AckTags.MATRIX_COMMIT_BUTTON
                ),
                HelpStep(
                    id = "play_prompt",
                    title = "PLAY BACK YOUR PROMPT",
                    body = MatrixDeckHelpCopy.MATRIX_PLAYBACK,
                    action = HelpAction.Interact(
                        AckTags.MATRIX_PLAY_BUTTON
                    ),
                    targetTag = AckTags.MATRIX_PLAY_BUTTON
                ),
                HelpStep(
                    id = "prompt_complete",
                    title = "PROMPT COMPLETE",
                    body = MatrixDeckHelpCopy.MATRIX_COMPLETE
                )
            )
        )
    )
}