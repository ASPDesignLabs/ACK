// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*

// Walks through RECORD TRAINING DATA (voicecapture/*), entered from AUDIO ARCHITECT's CUSTOM VOICE section. Most steps are
// "read" steps that point at a control: the screens change as the person works (script list, editor, setup, the recording
// screen), so a highlight simply shows when its control is on screen. Only the two taps that are always possible gate a step.
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object RecordTrainingDataHelp {
    val module = HelpModule(
        id = "record_training_data",
        category = HelpCategory.BASICS_PERSONALIZATION,
        title = "helpmod_record_training_data_title",
        summary = "helpmod_record_training_data_summary",
        destination = HelpDestination.AUDIO,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_record_training_data_intro_title",
                body = "helpmod_record_training_data_intro_body"
            ),
            HelpStep(
                id = "open",
                title = "helpmod_record_training_data_open_title",
                body = "helpmod_record_training_data_open_body",
                action = HelpAction.Interact(AckTags.TRAIN_ENTRY_BTN),
                targetTag = AckTags.TRAIN_ENTRY_BTN
            ),
            HelpStep(
                id = "scripts",
                title = "helpmod_record_training_data_scripts_title",
                body = "helpmod_record_training_data_scripts_body"
            ),
            HelpStep(
                id = "new_script",
                title = "helpmod_record_training_data_new_script_title",
                body = "helpmod_record_training_data_new_script_body",
                action = HelpAction.Interact(AckTags.TRAIN_NEW_SCRIPT_BTN),
                targetTag = AckTags.TRAIN_NEW_SCRIPT_BTN
            ),
            HelpStep(
                id = "title",
                title = "helpmod_record_training_data_title_title",
                body = "helpmod_record_training_data_title_body",
                targetTag = AckTags.TRAIN_SCRIPT_TITLE,
                coachPlacement = HelpCoachPlacement.BOTTOM
            ),
            HelpStep(
                id = "text",
                title = "helpmod_record_training_data_text_title",
                body = "helpmod_record_training_data_text_body",
                targetTag = AckTags.TRAIN_SCRIPT_TEXT,
                coachPlacement = HelpCoachPlacement.BOTTOM
            ),
            HelpStep(
                id = "save",
                title = "helpmod_record_training_data_save_title",
                body = "helpmod_record_training_data_save_body",
                targetTag = AckTags.TRAIN_SCRIPT_SAVE_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "record",
                title = "helpmod_record_training_data_record_title",
                body = "helpmod_record_training_data_record_body",
                targetTag = AckTags.TRAIN_SCRIPT_RECORD_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "quiet_check",
                title = "helpmod_record_training_data_quiet_check_title",
                body = "helpmod_record_training_data_quiet_check_body",
                targetTag = AckTags.TRAIN_QUIET_CHECK_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "hands_free",
                title = "helpmod_record_training_data_hands_free_title",
                body = "helpmod_record_training_data_hands_free_body",
                targetTag = AckTags.TRAIN_CARD_TEXT,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "redo",
                title = "helpmod_record_training_data_redo_title",
                body = "helpmod_record_training_data_redo_body",
                targetTag = AckTags.TRAIN_REDO_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "end",
                title = "helpmod_record_training_data_end_title",
                body = "helpmod_record_training_data_end_body",
                targetTag = AckTags.TRAIN_END_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "free",
                title = "helpmod_record_training_data_free_title",
                body = "helpmod_record_training_data_free_body",
                targetTag = AckTags.TRAIN_FREE_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "save_file",
                title = "helpmod_record_training_data_save_file_title",
                body = "helpmod_record_training_data_save_file_body",
                targetTag = AckTags.TRAIN_SAVE_ALL_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "complete",
                title = "helpmod_record_training_data_complete_title",
                body = "helpmod_record_training_data_complete_body"
            )
        )
    )
}
