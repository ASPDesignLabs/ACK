// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*

/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object StatementComposerHelp {
    val module = HelpModule(
        id = "statement_composer",
        category = HelpCategory.BASICS_MANUAL_OVERRIDE,
        title = "helpmod_statement_composer_title",
        summary = "helpmod_statement_composer_summary",
        destination = HelpDestination.TYPE,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_statement_composer_intro_title",
                body = "helpmod_statement_composer_intro_body"
            ),
            HelpStep(
                id = "fullscreen",
                title = "helpmod_statement_composer_fullscreen_title",
                body = "helpmod_statement_composer_fullscreen_body",
                action = HelpAction.Interact(AckTags.COMPOSER_FULLSCREEN_TOGGLE),
                targetTag = AckTags.COMPOSER_FULLSCREEN_TOGGLE
            ),
            HelpStep(
                id = "variable_context",
                title = "helpmod_statement_composer_variable_context_title",
                body = "helpmod_statement_composer_variable_context_body",
                action = HelpAction.Interact(AckTags.COMPOSER_VARIABLE_CONTEXT_ROW),
                targetTag = AckTags.COMPOSER_VARIABLE_CONTEXT_ROW
            ),
            HelpStep(
                id = "compose_field",
                title = "helpmod_statement_composer_compose_field_title",
                body = "helpmod_statement_composer_compose_field_body",
                targetTag = AckTags.COMPOSER_FIELD
            ),
            HelpStep(
                id = "word_suggestions",
                title = "helpmod_statement_composer_word_suggestions_title",
                body = "helpmod_statement_composer_word_suggestions_body",
                targetTag = AckTags.COMPOSER_WORD_STRIP
            ),
            HelpStep(
                id = "insert_target_chip",
                title = "helpmod_statement_composer_insert_target_chip_title",
                body = "helpmod_statement_composer_insert_target_chip_body",
                action = HelpAction.Interact(AckTags.MANUAL_TARGET_QUICK_ROW),
                targetTag = AckTags.MANUAL_TARGET_QUICK_ROW
            ),
            HelpStep(
                id = "browse_targets",
                title = "helpmod_statement_composer_browse_targets_title",
                body = "helpmod_statement_composer_browse_targets_body",
                action = HelpAction.Interact(AckTags.COMPOSER_BROWSE_TARGETS_TOGGLE),
                targetTag = AckTags.COMPOSER_BROWSE_TARGETS_TOGGLE
            ),
            HelpStep(
                id = "insert_variable",
                title = "helpmod_statement_composer_insert_variable_title",
                body = "helpmod_statement_composer_insert_variable_body",
                action = HelpAction.Interact(AckTags.COMPOSER_VARIABLE_TOGGLE),
                targetTag = AckTags.COMPOSER_VARIABLE_TOGGLE
            ),
            HelpStep(
                id = "preview",
                title = "helpmod_statement_composer_preview_title",
                body = "helpmod_statement_composer_preview_body",
                targetTag = AckTags.COMPOSER_PREVIEW
            ),
            HelpStep(
                id = "save",
                title = "helpmod_statement_composer_save_title",
                body = "helpmod_statement_composer_save_body",
                action = HelpAction.CommitText(AckTags.COMPOSER_SAVE_BTN),
                targetTag = AckTags.COMPOSER_SAVE_BTN
            ),
            HelpStep(
                id = "copy",
                title = "helpmod_statement_composer_copy_title",
                body = "helpmod_statement_composer_copy_body",
                action = HelpAction.Interact(AckTags.COMPOSER_COPY_BTN),
                targetTag = AckTags.COMPOSER_COPY_BTN
            ),
            HelpStep(
                id = "speak",
                title = "helpmod_statement_composer_speak_title",
                body = "helpmod_statement_composer_speak_body",
                action = HelpAction.Interact(AckTags.COMPOSER_SPEAK_BTN),
                targetTag = AckTags.COMPOSER_SPEAK_BTN
            ),
            HelpStep(
                id = "statements_list",
                title = "helpmod_statement_composer_statements_list_title",
                body = "helpmod_statement_composer_statements_list_body",
                action = HelpAction.Interact(AckTags.COMPOSER_STATEMENTS_LIST_BTN),
                targetTag = AckTags.COMPOSER_STATEMENTS_LIST_BTN
            )
        )
    )
}
