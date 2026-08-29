package com.example.besu

object BasicsNavigationHelp {
    val module = HelpModule(
        id = "basics_navigation",
        category = HelpCategory.BASICS_NAVIGATION,
        title = "UI NAVIGATION",
        summary = "DECKS, PROFILES, CONTEXT, AND SIMPLE PROMPTS.",
        destination = HelpDestination.MATRIX,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "WELCOME TO ACK",
                body = "ACK is organized around decks, views, and output " +
                        "tools. Start by learning the primary navigation controls."
            ),
            HelpStep(
                id = "deck_vs_profile",
                title = "DECKS VS PROFILES",
                body = "DECK and PROFILE control different layers of ACK. " +
                        "A deck changes the communication system you are using. " +
                        "A profile changes the phrase set used inside a Matrix deck."
            ),
            HelpStep(
                id = "deck_selector",
                title = "SWITCHING DECKS",
                body = "Tap the DECK selector to open the available deck list.",
                action = HelpAction.Interact(AckTags.DECK_SELECTOR),
                targetTag = AckTags.DECK_SELECTOR
            ),
            HelpStep(
                id = "deck_selector_detail",
                title = "UNDERSTANDING DECKS",
                body = "Decks are complete communication workspaces. " +
                        "Matrix decks use watch gestures and profiles. Other decks " +
                        "can provide quick actions, emergency phrases, emoji, or GIF " +
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
                body = "Profiles belong to Matrix decks. They let the same watch " +
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
                        "within ACK. You can select a communication deck, choose a " +
                        "Matrix profile, and move between ACK's primary tools."
            )
        )
    )
}