package com.example.besu


object LogsHelp {
    val module = HelpModule(
        id = "logs",
        category = HelpCategory.CONTEXTUAL_SYSTEMS,
        title = "SYSTEM LOGS",
        summary = "READ OUTPUT, WATCH, AND SYSTEM EVENT HISTORY.",
        destination = HelpDestination.TERMINAL,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "TERMINAL LOGS",
                body = "The Terminal records ACK system activity, output events, " +
                    "and watch-linked status messages."
            ),
            HelpStep(
                id = "terminal",
                title = "READING EVENTS",
                body = "Use logs to confirm what ACK received, resolved, and sent.",
                action = HelpAction.Interact(AckTags.TERMINAL_VIEW),
                targetTag = AckTags.TERMINAL_VIEW
            )
        )
    )
}
