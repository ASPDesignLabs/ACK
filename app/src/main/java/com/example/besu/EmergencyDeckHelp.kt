package com.example.besu

object EmergencyDeckHelp {
    val module = HelpModule(
        id = "deck_emergency",
        category = HelpCategory.USING_DECKS,
        title = "EMERGENCY DECK",
        summary = "HIGH-PRIORITY PROMPTS, OUTPUT OVERRIDES, AND CLEARING.",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "EMERGENCY OUTPUT",
                body = "The Emergency deck is intended for immediate, " +
                    "high-priority communication with minimal interaction."
            ),
            HelpStep(
                id = "slot",
                title = "CONFIGURE A PROMPT",
                body = "Hold an emergency tile to set its label, phrase, and " +
                    "optional local variables.",
                action = HelpAction.Interact(AckTags.EMERGENCY_SLOT),
                targetTag = AckTags.EMERGENCY_SLOT
            ),
            HelpStep(
                id = "save",
                title = "COMMIT THE PROMPT",
                body = "Save the emergency prompt. A normal tap will execute it.",
                action = HelpAction.CommitText(AckTags.EMERGENCY_SAVE),
                targetTag = AckTags.EMERGENCY_SAVE
            ),
            HelpStep(
                id = "overrides",
                title = "EMERGENCY OVERRIDES",
                body = "Overrides can force device speaker output, boost audio, " +
                    "change clearing behavior, and add an alert tone.",
                action = HelpAction.Interact(AckTags.EMERGENCY_OVERRIDES),
                targetTag = AckTags.EMERGENCY_OVERRIDES
            )
        )
    )
}