package com.example.besu

object QuickActionsDeckHelp {
    val module = HelpModule(
        id = "deck_quick_actions",
        category = HelpCategory.USING_DECKS,
        title = "QUICK ACTIONS DECK",
        summary = "THREE POSES, FOUR ACTIONS EACH -- FAST, FIXED OUTPUT.",
        destination = HelpDestination.MATRIX,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "QUICK ACTIONS",
                body = "Quick Actions is a simpler, fixed alternative to the Matrix " +
                    "deck: three groups of four phrases, meant for your most common " +
                    "lines rather than live remapping.\n\n" +
                    "While a Quick Actions deck is active, it takes over completely -- " +
                    "the watch's pose and twist choose a phrase from THIS deck instead " +
                    "of running the usual Matrix categories."
            ),
            HelpStep(
                id = "groups_intro",
                title = "THREE GROUPS, THREE POSES",
                body = "Each of the three groups is bound to one root pose -- " +
                    "IDENTITY, DEFEND, or CONNECT. Each group tab shows its " +
                    "bound pose underneath (e.g. \"G1\" over \"IDE\")."
            ),
            HelpStep(
                id = "select_group",
                title = "SELECT A GROUP",
                body = "Tap a group tab to view its four actions.",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_GROUP),
                targetTag = AckTags.QUICK_ACTION_GROUP
            ),
            HelpStep(
                id = "edit_group",
                title = "REBIND THE POSE",
                body = "Tap EDIT to rename the group or change which pose fires " +
                    "it. Picking a pose another group already uses swaps the two " +
                    "-- every pose always belongs to exactly one group.\n\n" +
                    "ROOT OVERRIDE SOURCE is a separate setting: it picks which " +
                    "A/B/C variable bank fills any {{tags}} in this group's " +
                    "phrases, and has no effect on which gesture triggers it.",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_GROUP_EDIT),
                targetTag = AckTags.QUICK_ACTION_GROUP_EDIT
            ),
            HelpStep(
                id = "mods",
                title = "FOUR ACTIONS PER GROUP",
                body = "Within a bound pose, the four actions line up with the " +
                    "watch's modifier twists: hold the pose and fire immediately " +
                    "for action 1, or twist 1-3 times first to reach the others."
            ),
            HelpStep(
                id = "edit_slot",
                title = "EDIT AN ACTION",
                body = "Hold an action to edit its label, phrase, and any local " +
                    "variable values.",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_SLOT),
                targetTag = AckTags.QUICK_ACTION_SLOT
            ),
            HelpStep(
                id = "save_slot",
                title = "SAVE AND PLAY BACK",
                body = "Commit the action, then tap it normally -- it speaks the " +
                    "resolved phrase immediately, so you can check it sounds right.",
                action = HelpAction.CommitText(AckTags.QUICK_ACTION_SAVE),
                targetTag = AckTags.QUICK_ACTION_SAVE
            ),
            HelpStep(
                id = "complete",
                title = "READY TO GO",
                body = "That's the whole deck: pick a pose per group, four " +
                    "phrases per pose, edited and played back right here."
            )
        )
    )
}
