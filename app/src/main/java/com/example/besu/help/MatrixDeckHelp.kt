// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*

/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object MatrixDeckHelp {

    val modules: List<HelpModule> = listOf(
        HelpModule(
            id = "ack_command_bar",
            category = HelpCategory.BASICS_NAVIGATION,
            title = "helpmod_ack_command_bar_title",
            summary = "helpmod_ack_command_bar_summary",
            destination = HelpDestination.MATRIX,
            requiresMatrixDeck = true,
            steps = listOf(
                HelpStep(
                    id = "header_intro",
                    title = "helpmod_ack_command_bar_header_intro_title",
                    body = "helpmod_ack_command_bar_header_intro_body"
                ),
                HelpStep(
                    id = "header_deck",
                    title = "helpmod_ack_command_bar_header_deck_title",
                    body = "helpmod_ack_command_bar_header_deck_body",
                    targetTag = AckTags.DECK_SELECTOR
                ),
                HelpStep(
                    id = "header_profile",
                    title = "helpmod_ack_command_bar_header_profile_title",
                    body = "helpmod_ack_command_bar_header_profile_body",
                    targetTag = AckTags.PROFILE_SELECTOR
                ),
                HelpStep(
                    id = "header_shortcuts",
                    title = "helpmod_ack_command_bar_header_shortcuts_title",
                    body = "helpmod_ack_command_bar_header_shortcuts_body",
                    targetTag = AckTags.HEADER_SHORTCUTS
                ),
                HelpStep(
                    id = "header_protocol",
                    title = "helpmod_ack_command_bar_header_protocol_title",
                    body = "helpmod_ack_command_bar_header_protocol_body",
                    targetTag = AckTags.CONFIG_BUTTON
                ),
                HelpStep(
                    id = "header_help",
                    title = "helpmod_ack_command_bar_header_help_title",
                    body = "helpmod_ack_command_bar_header_help_body",
                    targetTag = AckTags.HELP_BUTTON
                ),
                HelpStep(
                    id = "header_watch_link",
                    title = "helpmod_ack_command_bar_header_watch_link_title",
                    body = "helpmod_ack_command_bar_header_watch_link_body",
                    targetTag = AckTags.LIVE_LINK
                ),
                HelpStep(
                    id = "header_complete",
                    title = "helpmod_ack_command_bar_header_complete_title",
                    body = "helpmod_ack_command_bar_header_complete_body"
                )
            )
        ),
        HelpModule(
            id = "deck_profile_selection",
            category = HelpCategory.BASICS_NAVIGATION,
            title = "helpmod_deck_profile_selection_title",
            summary = "helpmod_deck_profile_selection_summary",
            destination = HelpDestination.MATRIX,
            requiresMatrixDeck = true,
            steps = listOf(
                HelpStep(
                    id = "select_deck",
                    title = "helpmod_deck_profile_selection_select_deck_title",
                    body = "helpmod_deck_profile_selection_select_deck_body",
                    action = HelpAction.DeckSelected(AckTags.DECK_SELECTOR),
                    targetTag = AckTags.DECK_SELECTOR
                ),
                HelpStep(
                    id = "select_profile",
                    title = "helpmod_deck_profile_selection_select_profile_title",
                    body = "helpmod_deck_profile_selection_select_profile_body",
                    action = HelpAction.ProfileSelected(
                        AckTags.PROFILE_SELECTOR
                    ),
                    targetTag = AckTags.PROFILE_SELECTOR
                ),
                HelpStep(
                    id = "deck_profile_complete",
                    title = "helpmod_deck_profile_selection_deck_profile_complete_title",
                    body = "helpmod_deck_profile_selection_deck_profile_complete_body"
                )
            )
        ),
        HelpModule(
            id = "matrix_prompt_creation",
            category = HelpCategory.BASICS_NAVIGATION,
            title = "helpmod_matrix_prompt_creation_title",
            summary = "helpmod_matrix_prompt_creation_summary",
            destination = HelpDestination.MATRIX,
            requiresMatrixDeck = true,
            steps = listOf(
                HelpStep(
                    id = "matrix_intro",
                    title = "helpmod_matrix_prompt_creation_matrix_intro_title",
                    body = "helpmod_matrix_prompt_creation_matrix_intro_body"
                ),
                HelpStep(
                    id = "identity_root",
                    title = "helpmod_matrix_prompt_creation_identity_root_title",
                    body = "helpmod_matrix_prompt_creation_identity_root_body",
                    targetTag = AckTags.MATRIX_ROOT_IDENTITY
                ),
                HelpStep(
                    id = "edit_twist_zero",
                    title = "helpmod_matrix_prompt_creation_edit_twist_zero_title",
                    body = "helpmod_matrix_prompt_creation_edit_twist_zero_body",
                    action = HelpAction.Interact(
                        AckTags.MATRIX_ROW_TARGET
                    ),
                    targetTag = AckTags.MATRIX_ROW_TARGET
                ),
                HelpStep(
                    id = "macro_template",
                    title = "helpmod_matrix_prompt_creation_macro_template_title",
                    body = "helpmod_matrix_prompt_creation_macro_template_body",
                    action = HelpAction.KeyboardDismissed(
                        AckTags.MACRO_TEMPLATE_INPUT
                    ),
                    targetTag = AckTags.MACRO_TEMPLATE_INPUT
                ),
                HelpStep(
                    id = "commit_prompt",
                    title = "helpmod_matrix_prompt_creation_commit_prompt_title",
                    body = "helpmod_matrix_prompt_creation_commit_prompt_body",
                    action = HelpAction.Interact(
                        AckTags.MATRIX_COMMIT_BUTTON
                    ),
                    targetTag = AckTags.MATRIX_COMMIT_BUTTON
                ),
                HelpStep(
                    id = "play_prompt",
                    title = "helpmod_matrix_prompt_creation_play_prompt_title",
                    body = "helpmod_matrix_prompt_creation_play_prompt_body",
                    action = HelpAction.Interact(
                        AckTags.MATRIX_PLAY_BUTTON
                    ),
                    targetTag = AckTags.MATRIX_PLAY_BUTTON
                ),
                HelpStep(
                    id = "prompt_complete",
                    title = "helpmod_matrix_prompt_creation_prompt_complete_title",
                    body = "helpmod_matrix_prompt_creation_prompt_complete_body"
                )
            )
        )
    )
}