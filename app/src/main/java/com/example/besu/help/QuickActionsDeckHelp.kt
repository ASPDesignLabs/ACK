// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object QuickActionsDeckHelp {
    val module = HelpModule(
        id = "deck_quick_actions",
        category = HelpCategory.USING_DECKS,
        title = "helpmod_deck_quick_actions_title",
        summary = "helpmod_deck_quick_actions_summary",
        destination = HelpDestination.MATRIX,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_deck_quick_actions_intro_title",
                body = "helpmod_deck_quick_actions_intro_body"
            ),
            HelpStep(
                id = "groups_intro",
                title = "helpmod_deck_quick_actions_groups_intro_title",
                body = "helpmod_deck_quick_actions_groups_intro_body"
            ),
            HelpStep(
                id = "select_group",
                title = "helpmod_deck_quick_actions_select_group_title",
                body = "helpmod_deck_quick_actions_select_group_body",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_GROUP),
                targetTag = AckTags.QUICK_ACTION_GROUP
            ),
            HelpStep(
                id = "edit_group",
                title = "helpmod_deck_quick_actions_edit_group_title",
                body = "helpmod_deck_quick_actions_edit_group_body",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_GROUP_EDIT),
                targetTag = AckTags.QUICK_ACTION_GROUP_EDIT
            ),
            HelpStep(
                id = "mods",
                title = "helpmod_deck_quick_actions_mods_title",
                body = "helpmod_deck_quick_actions_mods_body"
            ),
            HelpStep(
                id = "edit_slot",
                title = "helpmod_deck_quick_actions_edit_slot_title",
                body = "helpmod_deck_quick_actions_edit_slot_body",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_SLOT),
                targetTag = AckTags.QUICK_ACTION_SLOT
            ),
            HelpStep(
                id = "save_slot",
                title = "helpmod_deck_quick_actions_save_slot_title",
                body = "helpmod_deck_quick_actions_save_slot_body",
                action = HelpAction.CommitText(AckTags.QUICK_ACTION_SAVE),
                targetTag = AckTags.QUICK_ACTION_SAVE
            ),
            HelpStep(
                id = "complete",
                title = "helpmod_deck_quick_actions_complete_title",
                body = "helpmod_deck_quick_actions_complete_body"
            )
        )
    )
}
