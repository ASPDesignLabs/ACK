package com.example.besu

object TargetComputerHelp {
    val module = HelpModule(
        id = "target_computer",
        category = HelpCategory.CONTEXTUAL_SYSTEMS,
        title = "TARGET COMPUTER",
        summary = "CATEGORY TREES, TARGET TAGS, AND GUIDED SETUP.",
        destination = HelpDestination.TARGETS,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "TARGET COMPUTER",
                body = "The Target Computer organizes reusable prompt " +
                    "content -- names, places, food, actions, and anything " +
                    "else you add -- into categories you define. Each " +
                    "category holds one active pick at a time, which can " +
                    "be dropped into outgoing phrases without retyping it."
            ),
            HelpStep(
                id = "open_category",
                title = "OPEN A CATEGORY",
                body = "Tap any category chip to view what's inside it. " +
                    "Long-press a chip to rename it, change whether its " +
                    "pick clears itself after use, or delete it.",
                action = HelpAction.Interact(AckTags.TARGET_SLOT),
                targetTag = AckTags.TARGET_SLOT
            ),
            HelpStep(
                id = "add_category",
                title = "ADD A CATEGORY",
                body = "Beyond the defaults, add as many categories as you " +
                    "want. The four shipped categories can be renamed too " +
                    "-- nothing about them is fixed.",
                action = HelpAction.Interact(AckTags.COMPUTER_ADD_CATEGORY),
                targetTag = AckTags.COMPUTER_ADD_CATEGORY
            ),
            HelpStep(
                id = "tree_navigation",
                title = "TAP TO SELECT, HOLD TO EDIT",
                body = "Inside a category: tap a subcategory to open it, " +
                    "tap an entry to make it that category's active pick " +
                    "(tap it again to clear it). Long-press anything to " +
                    "rename or delete it. \"+ CATEGORY\" and \"+ ENTRY\" " +
                    "add new items under whatever you last tapped."
            ),
            HelpStep(
                id = "display_modes",
                title = "TREE OR DROPDOWN",
                body = "Switch between a branching TREE view and a " +
                    "cascading DROPDOWN view of the same category -- " +
                    "whichever is faster for how deep you've organized it.",
                action = HelpAction.Interact(AckTags.COMPUTER_TREE_WINDOW_MODE),
                targetTag = AckTags.COMPUTER_TREE_WINDOW_MODE
            ),
            HelpStep(
                id = "guide_me",
                title = "GUIDED SETUP",
                body = "Not sure where to start? GUIDE ME walks you " +
                    "through adding categories and entries one step at a " +
                    "time, staying wherever you're building instead of " +
                    "sending you back to the start after every add.",
                action = HelpAction.Interact(AckTags.COMPUTER_GUIDE_ME),
                targetTag = AckTags.COMPUTER_GUIDE_ME
            ),
            HelpStep(
                id = "computer_tag",
                title = "USING A TARGET IN A PHRASE",
                body = "In the Matrix phrase editor, INSERT TARGET TAG " +
                    "adds a tag like [COMPUTER:PEOPLE] to your template. " +
                    "It resolves to that category's current active pick " +
                    "-- or to an authored fallback if nothing is active.",
                action = HelpAction.Interact(AckTags.MATRIX_INSERT_COMPUTER_TAG),
                targetTag = AckTags.MATRIX_INSERT_COMPUTER_TAG
            ),
            HelpStep(
                id = "status_indicator",
                title = "CHECK WHAT'S ACTIVE",
                body = "The COMPUTER status in the header shows how many " +
                    "categories currently have an active pick. Tap it to " +
                    "see every category's pick at a glance and clear any " +
                    "of them on the spot.",
                action = HelpAction.Interact(AckTags.COMPUTER_STATUS_INDICATOR),
                targetTag = AckTags.COMPUTER_STATUS_INDICATOR
            ),
            HelpStep(
                id = "completion",
                title = "TARGET COMPUTER TRAINING COMPLETE",
                body = "Target Computer training complete. You can now " +
                    "build categories, navigate and edit their trees, " +
                    "insert target tags into phrases, and check what's " +
                    "currently active."
            )
        )
    )
}
