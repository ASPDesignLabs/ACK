// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.AckTags

// Voice recordings span three different owners (Quick Actions slots,
// Quick-Access keys, and Matrix nodes) plus a fourth, owner-agnostic
// screen (MANAGE RECORDINGS), which doesn't map cleanly onto a single
// guided walkthrough. Broken into three real modules instead -- fanned
// out from a single chooser entry point, same shape as
// FieldOpsHelp.poseTrainingEntryModule + PoseSelectorDialog.
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object VoiceRecordingsHelp {

    val recordingModule = HelpModule(
        id = "voice_rec_recording",
        category = HelpCategory.VOICE_RECORDINGS,
        title = "helpmod_voice_rec_recording_title",
        summary = "helpmod_voice_rec_recording_summary",
        destination = HelpDestination.MATRIX,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_voice_rec_recording_intro_title",
                body = "helpmod_voice_rec_recording_intro_body"
            ),
            HelpStep(
                id = "open_slot",
                title = "helpmod_voice_rec_recording_open_slot_title",
                body = "helpmod_voice_rec_recording_open_slot_body",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_SLOT),
                targetTag = AckTags.QUICK_ACTION_SLOT
            ),
            HelpStep(
                id = "find_section",
                title = "helpmod_voice_rec_recording_find_section_title",
                body = "helpmod_voice_rec_recording_find_section_body"
            ),
            HelpStep(
                id = "record",
                title = "helpmod_voice_rec_recording_record_title",
                body = "helpmod_voice_rec_recording_record_body",
                action = HelpAction.Interact(AckTags.VOICE_REC_RECORD_BTN),
                targetTag = AckTags.VOICE_REC_RECORD_BTN
            ),
            HelpStep(
                id = "stop",
                title = "helpmod_voice_rec_recording_stop_title",
                body = "helpmod_voice_rec_recording_stop_body",
                action = HelpAction.Interact(AckTags.VOICE_REC_STOP_BTN),
                targetTag = AckTags.VOICE_REC_STOP_BTN
            ),
            HelpStep(
                id = "preview",
                title = "helpmod_voice_rec_recording_preview_title",
                body = "helpmod_voice_rec_recording_preview_body",
                action = HelpAction.Interact(AckTags.VOICE_REC_PLAY_BTN),
                targetTag = AckTags.VOICE_REC_PLAY_BTN
            ),
            HelpStep(
                id = "accept",
                title = "helpmod_voice_rec_recording_accept_title",
                body = "helpmod_voice_rec_recording_accept_body",
                action = HelpAction.Interact(AckTags.VOICE_REC_ACCEPT_BTN),
                targetTag = AckTags.VOICE_REC_ACCEPT_BTN
            ),
            HelpStep(
                id = "complete",
                title = "helpmod_voice_rec_recording_complete_title",
                body = "helpmod_voice_rec_recording_complete_body"
            )
        )
    )

    val matrixModule = HelpModule(
        id = "voice_rec_matrix",
        category = HelpCategory.VOICE_RECORDINGS,
        title = "helpmod_voice_rec_matrix_title",
        summary = "helpmod_voice_rec_matrix_summary",
        destination = HelpDestination.MATRIX,
        requiresMatrixDeck = true,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_voice_rec_matrix_intro_title",
                body = "helpmod_voice_rec_matrix_intro_body"
            ),
            HelpStep(
                id = "open_node",
                title = "helpmod_voice_rec_matrix_open_node_title",
                body = "helpmod_voice_rec_matrix_open_node_body",
                action = HelpAction.Interact(AckTags.MATRIX_ROW_TARGET),
                targetTag = AckTags.MATRIX_ROW_TARGET
            ),
            HelpStep(
                id = "variables_caveat",
                title = "helpmod_voice_rec_matrix_variables_caveat_title",
                body = "helpmod_voice_rec_matrix_variables_caveat_body",
                targetTag = AckTags.VOICE_REC_MATRIX_ATTACH_BTN
            ),
            HelpStep(
                id = "record",
                title = "helpmod_voice_rec_matrix_record_title",
                body = "helpmod_voice_rec_matrix_record_body",
                action = HelpAction.Interact(AckTags.VOICE_REC_RECORD_BTN),
                targetTag = AckTags.VOICE_REC_RECORD_BTN
            ),
            HelpStep(
                id = "stop",
                title = "helpmod_voice_rec_matrix_stop_title",
                body = "helpmod_voice_rec_matrix_stop_body",
                action = HelpAction.Interact(AckTags.VOICE_REC_STOP_BTN),
                targetTag = AckTags.VOICE_REC_STOP_BTN
            ),
            HelpStep(
                id = "accept",
                title = "helpmod_voice_rec_matrix_accept_title",
                body = "helpmod_voice_rec_matrix_accept_body",
                action = HelpAction.Interact(AckTags.VOICE_REC_ACCEPT_BTN),
                targetTag = AckTags.VOICE_REC_ACCEPT_BTN
            ),
            HelpStep(
                id = "visual_override",
                title = "helpmod_voice_rec_matrix_visual_override_title",
                body = "helpmod_voice_rec_matrix_visual_override_body",
                targetTag = AckTags.VOICE_REC_MATRIX_OVERRIDE_FIELD
            ),
            HelpStep(
                id = "re_enable",
                title = "helpmod_voice_rec_matrix_re_enable_title",
                body = "helpmod_voice_rec_matrix_re_enable_body",
                targetTag = AckTags.VOICE_REC_MATRIX_REENABLE_BTN
            ),
            HelpStep(
                id = "complete",
                title = "helpmod_voice_rec_matrix_complete_title",
                body = "helpmod_voice_rec_matrix_complete_body"
            )
        )
    )

    val manageModule = HelpModule(
        id = "voice_rec_manage",
        category = HelpCategory.VOICE_RECORDINGS,
        title = "helpmod_voice_rec_manage_title",
        summary = "helpmod_voice_rec_manage_summary",
        destination = HelpDestination.SETTINGS,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_voice_rec_manage_intro_title",
                body = "helpmod_voice_rec_manage_intro_body"
            ),
            HelpStep(
                id = "open",
                title = "helpmod_voice_rec_manage_open_title",
                body = "helpmod_voice_rec_manage_open_body",
                action = HelpAction.Interact(AckTags.VOICE_REC_MANAGE_BTN),
                targetTag = AckTags.VOICE_REC_MANAGE_BTN
            ),
            HelpStep(
                id = "tree",
                title = "helpmod_voice_rec_manage_tree_title",
                body = "helpmod_voice_rec_manage_tree_body",
                targetTag = AckTags.VOICE_REC_MANAGE_TREE
            ),
            HelpStep(
                id = "leaf",
                title = "helpmod_voice_rec_manage_leaf_title",
                body = "helpmod_voice_rec_manage_leaf_body",
                targetTag = AckTags.VOICE_REC_MANAGE_LEAF
            ),
            HelpStep(
                id = "actions",
                title = "helpmod_voice_rec_manage_actions_title",
                body = "helpmod_voice_rec_manage_actions_body",
                targetTag = AckTags.VOICE_REC_MANAGE_LEAF
            ),
            HelpStep(
                id = "overlay_toggle",
                title = "helpmod_voice_rec_manage_overlay_toggle_title",
                body = "helpmod_voice_rec_manage_overlay_toggle_body",
                action = HelpAction.Interact(AckTags.VOICE_REC_MANAGE_OVERLAY_TOGGLE),
                targetTag = AckTags.VOICE_REC_MANAGE_OVERLAY_TOGGLE
            ),
            HelpStep(
                id = "complete",
                title = "helpmod_voice_rec_manage_complete_title",
                body = "helpmod_voice_rec_manage_complete_body"
            )
        )
    )

    data class VoiceRecOption(
        val moduleId: String,
        val label: String,
        val hint: String
    )

    val options = listOf(
        VoiceRecOption(
            recordingModule.id,
            "RECORDING A VOICE PROMPT",
            "The record, preview, and accept flow -- wherever it shows up."
        ),
        VoiceRecOption(
            matrixModule.id,
            "MATRIX VOICE ENTRIES",
            "Variables, the visual override, and edits after the fact."
        ),
        VoiceRecOption(
            manageModule.id,
            "MANAGING RECORDINGS",
            "Browse, play, re-record, and delete from one tree."
        )
    )

    // Not a guided walkthrough by itself -- MainActivity intercepts this
    // module's id before calling HelpManager.start() and opens
    // VoiceRecordingsHelpSelectorDialog instead. Picking an option there
    // starts the matching real module above.
    val entryModule = HelpModule(
        id = "voice_recordings_training",
        category = HelpCategory.VOICE_RECORDINGS,
        title = "helpmod_voice_recordings_training_title",
        summary = "helpmod_voice_recordings_training_summary",
        steps = listOf(
            HelpStep(
                id = "select",
                title = "helpmod_voice_recordings_training_select_title",
                body = "helpmod_voice_recordings_training_select_body"
            )
        )
    )

    // The three real modules stay registered for HelpManager lookup but
    // are hidden from the menu list in favor of entryModule -- see
    // MainActivity's filtered HelpMenuDialog modules list.
    val hiddenModuleIds: Set<String> = setOf(
        recordingModule.id,
        matrixModule.id,
        manageModule.id
    )

    val modules = listOf(recordingModule, matrixModule, manageModule, entryModule)
}
