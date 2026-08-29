package com.example.besu

object TargetComputerHelp {
    val module = HelpModule(
        id = "target_computer",
        category = HelpCategory.CONTEXTUAL_SYSTEMS,
        title = "TARGET COMPUTER",
        summary = "TARGET SLOTS, PROMPT INSERTION, AND MESSAGE ROUTING.",
        destination = HelpDestination.TARGETS,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "TARGET COMPUTER",
                body = "The Target Computer stores names, labels, places, and " +
                    "other reusable prompt context. A selected target can be " +
                    "inserted into outgoing ACK phrases without rewriting the " +
                    "same context every time."
            ),
            HelpStep(
                id = "prompt_injection",
                title = "TARGETS AND PROMPTS",
                body = "When a target is active, ACK can inject its label into a " +
                    "generated or manually issued prompt. For example, a target " +
                    "placeholder such as [TARGET_NAME] can become part of a " +
                    "message such as [TARGET_NAME], I NEED A MOMENT."
            ),
            HelpStep(
                id = "open_slot",
                title = "CONFIGURE A TARGET SLOT",
                body = "Each slot stores one target entry. Select any slot to " +
                    "open its configuration panel. Empty slots can be deployed " +
                    "as new targets, while configured slots can be revised or " +
                    "cleared.",
                action = HelpAction.Interact(AckTags.TARGET_SLOT),
                targetTag = AckTags.TARGET_SLOT
            ),
            HelpStep(
                id = "placement_strategy",
                title = "PREPEND OR APPEND",
                body = "Choose where ACK inserts this target in a phrase. PREPEND " +
                    "places the target before the message, such as [TARGET_NAME], " +
                    "[MESSAGE]. APPEND places the target after the message, such " +
                    "as [MESSAGE], [TARGET_NAME].",
                action = HelpAction.Interact(AckTags.TARGET_STRATEGY),
                targetTag = AckTags.TARGET_STRATEGY
            ),
            HelpStep(
                id = "save_slot",
                title = "SAVE THE TARGET",
                body = "Enter a descriptive placeholder or target label, then " +
                    "save the slot. You can use any naming scheme that makes " +
                    "sense to you, such as [PERSON], [PLACE], [TEAM], or " +
                    "[CONTEXT_LABEL].",
                action = HelpAction.CommitText(AckTags.TARGET_SLOT_SAVE),
                targetTag = AckTags.TARGET_SLOT_SAVE
            ),
            HelpStep(
                id = "using_target",
                title = "USING A TARGET",
                body = "Once selected through your chosen ACK target workflow, " +
                    "the active target modifies compatible outgoing prompts. " +
                    "Use this when you need to address a person, identify a " +
                    "place, or add repeated context with less typing."
            ),
            HelpStep(
                id = "completion",
                title = "TARGET COMPUTER TRAINING COMPLETE",
                body = "Target Computer training complete. You can now create " +
                    "target slots, choose message placement, save target labels, " +
                    "and use active context with compatible prompts."
            )
        )
    )
}
