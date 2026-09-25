package com.example.besu.help

import com.example.besu.*

object StatementComposerHelp {
    val module = HelpModule(
        id = "statement_composer",
        category = HelpCategory.BASICS_MANUAL_OVERRIDE,
        title = "STATEMENT COMPOSER",
        summary = "BUILD, SAVE, COPY, OR SPEAK MULTI-SENTENCE STATEMENTS.",
        destination = HelpDestination.TYPE,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "STATEMENT COMPOSER",
                body = "Build longer, structured statements from Target Computer " +
                    "entries and Shared Root Variables, then save, copy, or speak " +
                    "them. Saved statements stay mutable -- they always resolve " +
                    "against whatever those entries currently hold, not a frozen " +
                    "snapshot."
            ),
            HelpStep(
                id = "fullscreen",
                title = "FULL SCREEN",
                body = "Tap FULL SCREEN to hide the header and bottom navigation " +
                    "and give the composer the whole screen -- useful for longer " +
                    "statements. The toggle stays pinned at the top so you can " +
                    "always tap back out.",
                action = HelpAction.Interact(AckTags.COMPOSER_FULLSCREEN_TOGGLE),
                targetTag = AckTags.COMPOSER_FULLSCREEN_TOGGLE
            ),
            HelpStep(
                id = "variable_context",
                title = "VARIABLE CONTEXT",
                body = "Pick which Shared Root Variables grouping this statement's " +
                    "variables use. A/B/C slots are only unique within one " +
                    "grouping, same as a Matrix phrase resolving against its own " +
                    "node's pose.",
                action = HelpAction.Interact(AckTags.COMPOSER_VARIABLE_CONTEXT_ROW),
                targetTag = AckTags.COMPOSER_VARIABLE_CONTEXT_ROW
            ),
            HelpStep(
                id = "compose_field",
                title = "COMPOSE",
                body = "Type freely here -- full sentences and paragraphs, not " +
                    "just a single phrase.",
                targetTag = AckTags.COMPOSER_FIELD
            ),
            HelpStep(
                id = "insert_target_chip",
                title = "INSERT A LIVE REFERENCE",
                body = "Tap a Target Computer chip to insert a live reference -- " +
                    "it always resolves to whatever's currently active in that " +
                    "category. Long-press a chip to retarget which entry is " +
                    "active, for real, across the whole app.",
                action = HelpAction.Interact(AckTags.MANUAL_TARGET_QUICK_ROW),
                targetTag = AckTags.MANUAL_TARGET_QUICK_ROW
            ),
            HelpStep(
                id = "browse_targets",
                title = "BROWSE FOR A SPECIFIC ENTRY",
                body = "BROWSE TARGETS opens the full Target Computer tree. " +
                    "Entries picked here insert as plain text, not a live " +
                    "reference -- a browsed entry might not be the active one, " +
                    "so it can't be represented as a token.",
                action = HelpAction.Interact(AckTags.COMPOSER_BROWSE_TARGETS_TOGGLE),
                targetTag = AckTags.COMPOSER_BROWSE_TARGETS_TOGGLE
            ),
            HelpStep(
                id = "insert_variable",
                title = "INSERT A VARIABLE",
                body = "INSERT VARIABLE browses the current grouping's A/B/C " +
                    "Shared Root Variable slots and inserts a live reference to " +
                    "whichever one you tap.",
                action = HelpAction.Interact(AckTags.COMPOSER_VARIABLE_TOGGLE),
                targetTag = AckTags.COMPOSER_VARIABLE_TOGGLE
            ),
            HelpStep(
                id = "preview",
                title = "LIVE PREVIEW",
                body = "This shows exactly what the statement will say or copy " +
                    "as right now, with every reference resolved.",
                targetTag = AckTags.COMPOSER_PREVIEW
            ),
            HelpStep(
                id = "save",
                title = "SAVE",
                body = "SAVE stores the statement as typed, references intact -- " +
                    "it keeps resolving live every time it's reused, even if " +
                    "the entries it points at change later.",
                action = HelpAction.CommitText(AckTags.COMPOSER_SAVE_BTN),
                targetTag = AckTags.COMPOSER_SAVE_BTN
            ),
            HelpStep(
                id = "copy",
                title = "COPY",
                body = "COPY resolves the statement and places the result on the " +
                    "clipboard, ready to paste into Messages, chat apps, or " +
                    "anywhere else.",
                action = HelpAction.Interact(AckTags.COMPOSER_COPY_BTN),
                targetTag = AckTags.COMPOSER_COPY_BTN
            ),
            HelpStep(
                id = "speak",
                title = "SPEAK",
                body = "SPEAK resolves the statement and sends it straight to " +
                    "output.",
                action = HelpAction.Interact(AckTags.COMPOSER_SPEAK_BTN),
                targetTag = AckTags.COMPOSER_SPEAK_BTN
            ),
            HelpStep(
                id = "statements_list",
                title = "MY STATEMENTS",
                body = "MY STATEMENTS organizes everything you've saved into " +
                    "folders, tree-and-leaf, the same shape as Target Computer " +
                    "entries. Tap a folder to expand it, or a statement to " +
                    "reload it for editing, copy, speak, or delete it right " +
                    "from the list.",
                action = HelpAction.Interact(AckTags.COMPOSER_STATEMENTS_LIST_BTN),
                targetTag = AckTags.COMPOSER_STATEMENTS_LIST_BTN
            )
        )
    )
}
