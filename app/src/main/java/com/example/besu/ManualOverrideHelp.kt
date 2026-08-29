package com.example.besu

object ManualOverrideHelp {
    val module = HelpModule(
        id = "manual_override",
        category = HelpCategory.BASICS_MANUAL_OVERRIDE,
        title = "MANUAL OVERRIDE",
        summary = "MEMORY BANKS, SAVED PHRASES, AND DIRECT TEXT OUTPUT.",
        destination = HelpDestination.TYPE,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "MANUAL OVERRIDE",
                body = "Manual Override provides direct communication when " +
                    "watch interaction is unavailable, inconvenient, or unwanted."
            ),
            HelpStep(
                id = "memory_banks",
                title = "MEMORY BANKS",
                body = "Use memory banks to keep useful phrases available for " +
                    "quick manual recall.",
                action = HelpAction.Interact(AckTags.MANUAL_MEMORY_BANKS),
                targetTag = AckTags.MANUAL_MEMORY_BANKS
            ),
            HelpStep(
                id = "input",
                title = "DIRECT INPUT",
                body = "Enter a phrase manually when it is not already stored " +
                    "in a deck or memory bank.",
                action = HelpAction.Interact(AckTags.MANUAL_TEXT_FIELD),
                targetTag = AckTags.MANUAL_TEXT_FIELD
            ),
            HelpStep(
                id = "send",
                title = "SEND MANUAL OUTPUT",
                body = "Commit the phrase to send it through ACK output.",
                action = HelpAction.CommitText(AckTags.MANUAL_SEND),
                targetTag = AckTags.MANUAL_SEND
            )
        )
    )
}