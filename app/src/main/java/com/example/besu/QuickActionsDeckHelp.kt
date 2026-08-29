package com.example.besu

object QuickActionsDeckHelp {
    val module = HelpModule(
        id = "deck_quick_actions",
        category = HelpCategory.USING_DECKS,
        title = "QUICK ACTIONS DECK",
        summary = "GROUPED PHRASES, ROOT OVERRIDES, AND FAST OUTPUT.",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "QUICK ACTIONS",
                body = "Quick Actions provides grouped, touch-first phrase " +
                    "controls with optional root-variable integration."
            ),
            HelpStep(
                id = "group",
                title = "SELECT A GROUP",
                body = "Groups separate related actions and can use different " +
                    "root override categories.",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_GROUP),
                targetTag = AckTags.QUICK_ACTION_GROUP
            ),
            HelpStep(
                id = "slot",
                title = "CONFIGURE AN ACTION",
                body = "Hold an action to edit its label, phrase template, " +
                    "and local variable values.",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_SLOT),
                targetTag = AckTags.QUICK_ACTION_SLOT
            ),
            HelpStep(
                id = "save",
                title = "SAVE THE ACTION",
                body = "Commit the action configuration, then tap it normally " +
                    "to execute its resolved phrase.",
                action = HelpAction.CommitText(AckTags.QUICK_ACTION_SAVE),
                targetTag = AckTags.QUICK_ACTION_SAVE
            )
        )
    )
}