package com.example.besu

object HelpRegistry {
    val modules: List<HelpModule> = listOf(
        HelpModule(
            id = "basics_navigation",
            category = HelpCategory.BASICS_NAVIGATION,
            title = "UI NAVIGATION",
            summary = "DECKS, PROFILES, CONTEXT, AND SIMPLE PROMPTS.",
            destination = HelpDestination.MATRIX,
            steps = listOf(
                HelpStep(
                    id = "intro",
                    title = "WELCOME TO ACK",
                    body = "The Augmented Communications Link is your interface to " +
                            "a new way of accessing speech, by using the same tools you " +
                            "already have access to. " +
                            "" +
                            "ACK is built around contextual organization. From using " +
                            "a MATRIX deck to build context appropriate statements and " +
                            "responses, to Quick Actions meant for general use. Emergency " +
                            "responses to signify a greater need to hear the statement, " +
                            "along with a GIF deck, for when words are just not enough. "
                ),
                HelpStep(
                    id = "deck_vs_profile",
                    title = "DECKS VS PROFILES",
                    body = "Decks and Profiles control different layers of ACK, reshaping the " +
                            "interface around different input methods and expressions. " +
                            "Decks control how you interact with the experience. This includes watch "+
                            "interactions. " +
                            "A profile allows for greater contextual depth. Profiles store your " +
                            "custom prompts, shortcuts, established groupings, and watch pose responses. "
                ),
                HelpStep(
                    id = "deck_selector",
                    title = "SWITCHING DECKS",
                    body = "Switching a deck is easy, accessible from anywhere within ACK. Tap the highlighted " +
                            "Deck Selector in the ACK Command Bar on top to view your current list of Decks ",
                    action = HelpAction.Interact(AckTags.DECK_SELECTOR),
                    targetTag = AckTags.DECK_SELECTOR
                ),
                HelpStep(
                    id = "deck_selector_detail",
                    title = "UNDERSTANDING DECKS",
                    body = "Organization around Decks makes it easy to switch between input methods " +
                            "from anywhere within ACK. Want to switch to quick greetings instead of  " +
                            "fiddling with variables in a MATRIX deck? Need to quickly get a request for " +
                            "help out? Did your friend say something that requires an exasperated Obi Wan reaction? " +
                            "Building around Decks makes this effortless. "
                ),
                HelpStep(
                    id = "profile_selector",
                    title = "SWITCHING PROFILES",
                    body = "To access additional context relevant entries within a Deck you use the Profile Selector. " +
                            "Tap the highlighted Profile Selector above to view your available Profiles for the selected " +
                            "deck. ",
                    action = HelpAction.Interact(AckTags.PROFILE_SELECTOR),
                    targetTag = AckTags.PROFILE_SELECTOR
                ),
                HelpStep(
                    id = "profile_detail_one",
                    title = "WHY PROFILES?",
                    body = "Profiles make it easy to bind existing prompts, shortcuts, and quick actions to " +
                            "watch poses, while making it easy to access entries that are more contextually relevant. " +
                            "From creating a Work layout to establishing a general social profile without having to " +
                            "fiddle with the watch. ",
                ),
                HelpStep(
                    id = "profile_detail_two",
                    title = "PROFILES KEEP THE MAP",
                    body = "The three poses offered by the watch, IDENTIFY, DEFEND, and CONNECT, are managed " +
                            "this way. You'll learn more about watch connected features in another module. ",

                ),
                HelpStep(
                    id = "navigation_complete",
                    title = "NAVIGATION COMPLETE",
                    body = "Congratulations, you now know the basics of UI navigation " +
                            "within ACK. You can select a communication deck, choose a " +
                            "Matrix profile, and move between ACK's primary tools."
                )
            )
        ),
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
        HelpModule(
            id = "geo_protocol",
            category = HelpCategory.CONTEXTUAL_SYSTEMS,
            title = "GEO-PROTOCOL",
            summary = "LOCATION-BASED CONTEXT AND ZONE BEHAVIOR.",
            destination = HelpDestination.GEO,
            steps = listOf(
                HelpStep(
                    id = "intro",
                    title = "GEO-PROTOCOL",
                    body = "Geo-Protocol manages location-aware ACK behavior using two different methods " +
                            ", on device and assisted with Google Play Services. This allows you to automatically " +
                            "switch decks based on your location."
                ),
                HelpStep(
                    id = "geo",
                    title = "ZONE CONTROLS",
                    body = "Open the Geo-Protocol navigation screen.",
                    action = HelpAction.Interact(AckTags.GEO_VIEW),
                    targetTag = AckTags.GEO_VIEW
                )
            )
        )
    ) + MatrixDeckHelp.modules + PersonalizationHelp.module + SettingsManagementHelp.module + TargetComputerHelp.module

}