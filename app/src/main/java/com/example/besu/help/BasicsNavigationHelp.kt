// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
object BasicsNavigationHelp {
    val module = HelpModule(
        id = "basics_navigation",
        category = HelpCategory.BASICS_NAVIGATION,
        title = "UI NAVIGATION",
        summary = "{{DECKS:DECKS}}, PROFILES, CONTEXT, AND SIMPLE PROMPTS.",
        destination = HelpDestination.MATRIX,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "WELCOME TO ACK",
                body = "ACK is organized around {{DECKS:decks}}, views, and output " +
                        "tools. Start by learning the primary navigation controls."
            ),
            HelpStep(
                id = "deck_vs_profile",
                title = "{{DECKS:DECKS}} VS PROFILES",
                body = "{{DECK:DECK}} and PROFILE control different layers of ACK. " +
                        "A {{DECK:deck}} changes the communication system you are using. " +
                        "A profile changes the phrase set used inside a Matrix {{DECK:deck}}."
            ),
            HelpStep(
                id = "deck_selector",
                title = "SWITCHING {{DECKS:DECKS}}",
                body = "Tap the {{DECK:DECK}} selector to open the available {{DECK:deck}} list.",
                action = HelpAction.Interact(AckTags.DECK_SELECTOR),
                targetTag = AckTags.DECK_SELECTOR
            ),
            HelpStep(
                id = "deck_selector_detail",
                title = "UNDERSTANDING {{DECKS:DECKS}}",
                body = "{{DECKS:Decks}} are complete communication workspaces. " +
                        "Matrix {{DECKS:decks}} use watch gestures and profiles. Other {{DECKS:decks}} " +
                        "can provide {{DECK_TYPE_QUICK:quick actions}}, emergency phrases, emoji, or GIF " +
                        "output for specific situations."
            ),
            HelpStep(
                id = "profile_selector",
                title = "MATRIX PROFILES",
                body = "Tap PROFILE to select a Matrix communication profile.",
                action = HelpAction.Interact(AckTags.PROFILE_SELECTOR),
                targetTag = AckTags.PROFILE_SELECTOR
            ),
            HelpStep(
                id = "profile_detail_one",
                title = "WHAT PROFILES CHANGE",
                body = "Profiles belong to Matrix {{DECKS:decks}}. They let the same watch " +
                        "poses and twists produce wording appropriate for different " +
                        "people, places, routines, or communication contexts."
            ),
            HelpStep(
                id = "profile_detail_two",
                title = "PROFILES KEEP THE MAP",
                body = "Switching profiles does not change how the gesture map is " +
                        "laid out. It changes the phrases assigned within that map, " +
                        "so your muscle memory can remain consistent."
            ),
            HelpStep(
                id = "navigation_complete",
                title = "NAVIGATION COMPLETE",
                body = "Congratulations, you now know the basics of UI navigation " +
                        "within ACK. You can select a communication {{DECK:deck}}, choose a " +
                        "Matrix profile, and move between ACK's primary tools."
            )
        )
    )
}