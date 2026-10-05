// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object BasicsNavigationHelp {
    val module = HelpModule(
        id = "basics_navigation",
        category = HelpCategory.BASICS_NAVIGATION,
        title = "helpmod_basics_navigation_title",
        summary = "helpmod_basics_navigation_summary",
        destination = HelpDestination.MATRIX,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_basics_navigation_intro_title",
                body = "helpmod_basics_navigation_intro_body"
            ),
            HelpStep(
                id = "deck_vs_profile",
                title = "helpmod_basics_navigation_deck_vs_profile_title",
                body = "helpmod_basics_navigation_deck_vs_profile_body"
            ),
            HelpStep(
                id = "deck_selector",
                title = "helpmod_basics_navigation_deck_selector_title",
                body = "helpmod_basics_navigation_deck_selector_body",
                action = HelpAction.Interact(AckTags.DECK_SELECTOR),
                targetTag = AckTags.DECK_SELECTOR
            ),
            HelpStep(
                id = "deck_selector_detail",
                title = "helpmod_basics_navigation_deck_selector_detail_title",
                body = "helpmod_basics_navigation_deck_selector_detail_body"
            ),
            HelpStep(
                id = "profile_selector",
                title = "helpmod_basics_navigation_profile_selector_title",
                body = "helpmod_basics_navigation_profile_selector_body",
                action = HelpAction.Interact(AckTags.PROFILE_SELECTOR),
                targetTag = AckTags.PROFILE_SELECTOR
            ),
            HelpStep(
                id = "profile_detail_one",
                title = "helpmod_basics_navigation_profile_detail_one_title",
                body = "helpmod_basics_navigation_profile_detail_one_body"
            ),
            HelpStep(
                id = "profile_detail_two",
                title = "helpmod_basics_navigation_profile_detail_two_title",
                body = "helpmod_basics_navigation_profile_detail_two_body"
            ),
            HelpStep(
                id = "navigation_complete",
                title = "helpmod_basics_navigation_navigation_complete_title",
                body = "helpmod_basics_navigation_navigation_complete_body"
            )
        )
    )
}