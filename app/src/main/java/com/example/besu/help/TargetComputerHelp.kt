// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object TargetComputerHelp {
    val module = HelpModule(
        id = "target_computer",
        category = HelpCategory.CONTEXTUAL_SYSTEMS,
        title = "helpmod_target_computer_title",
        summary = "helpmod_target_computer_summary",
        destination = HelpDestination.TARGETS,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_target_computer_intro_title",
                body = "helpmod_target_computer_intro_body"
            ),
            HelpStep(
                id = "open_category",
                title = "helpmod_target_computer_open_category_title",
                body = "helpmod_target_computer_open_category_body",
                action = HelpAction.Interact(AckTags.TARGET_SLOT),
                targetTag = AckTags.TARGET_SLOT
            ),
            HelpStep(
                id = "add_category",
                title = "helpmod_target_computer_add_category_title",
                body = "helpmod_target_computer_add_category_body",
                action = HelpAction.Interact(AckTags.COMPUTER_ADD_CATEGORY),
                targetTag = AckTags.COMPUTER_ADD_CATEGORY
            ),
            HelpStep(
                id = "tree_navigation",
                title = "helpmod_target_computer_tree_navigation_title",
                body = "helpmod_target_computer_tree_navigation_body"
            ),
            HelpStep(
                id = "display_modes",
                title = "helpmod_target_computer_display_modes_title",
                body = "helpmod_target_computer_display_modes_body",
                action = HelpAction.Interact(AckTags.COMPUTER_TREE_WINDOW_MODE),
                targetTag = AckTags.COMPUTER_TREE_WINDOW_MODE
            ),
            HelpStep(
                id = "guide_me",
                title = "helpmod_target_computer_guide_me_title",
                body = "helpmod_target_computer_guide_me_body",
                action = HelpAction.Interact(AckTags.COMPUTER_GUIDE_ME),
                targetTag = AckTags.COMPUTER_GUIDE_ME
            ),
            HelpStep(
                id = "computer_tag",
                title = "helpmod_target_computer_computer_tag_title",
                body = "helpmod_target_computer_computer_tag_body",
                action = HelpAction.Interact(AckTags.MATRIX_INSERT_COMPUTER_TAG),
                targetTag = AckTags.MATRIX_INSERT_COMPUTER_TAG
            ),
            HelpStep(
                id = "status_indicator",
                title = "helpmod_target_computer_status_indicator_title",
                body = "helpmod_target_computer_status_indicator_body",
                action = HelpAction.Interact(AckTags.COMPUTER_STATUS_INDICATOR),
                targetTag = AckTags.COMPUTER_STATUS_INDICATOR
            ),
            HelpStep(
                id = "completion",
                title = "helpmod_target_computer_completion_title",
                body = "helpmod_target_computer_completion_body"
            )
        )
    )
}
