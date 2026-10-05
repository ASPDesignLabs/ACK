// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
import com.example.besu.training.*

/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object FieldOpsHelp {

    // Original module id preserved for continuity (was the only gesture-training
    // entry before per-pose subcategories existed).
    val identityModule = HelpModule(
        id = "field_ops_gesture_training",
        category = HelpCategory.FIELD_OPS,
        title = "helpmod_field_ops_gesture_training_title",
        summary = "helpmod_field_ops_gesture_training_summary",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_field_ops_gesture_training_intro_title",
                body = "helpmod_field_ops_gesture_training_intro_body"
            ),
            HelpStep(
                id = "wake_gesture",
                title = "helpmod_field_ops_gesture_training_wake_gesture_title",
                body = "helpmod_field_ops_gesture_training_wake_gesture_body",
                action = HelpAction.WatchEvent("ARMED")
            ),
            HelpStep(
                id = "system_armed",
                title = "helpmod_field_ops_gesture_training_system_armed_title",
                body = "helpmod_field_ops_gesture_training_system_armed_body"
            ),
            HelpStep(
                id = "pose_lock",
                title = "helpmod_field_ops_gesture_training_pose_lock_title",
                body = "helpmod_field_ops_gesture_training_pose_lock_body",
                action = HelpAction.WatchEvent("POSE_ID")
            ),
            HelpStep(
                id = "pose_locked",
                title = "helpmod_field_ops_gesture_training_pose_locked_title",
                body = "helpmod_field_ops_gesture_training_pose_locked_body",
                action = HelpAction.WatchEvent("MODIFIED")
            ),
            HelpStep(
                id = "fire_command",
                title = "helpmod_field_ops_gesture_training_fire_command_title",
                body = "helpmod_field_ops_gesture_training_fire_command_body",
                action = HelpAction.WatchEvent("FIRE")
            ),
            HelpStep(
                id = "sync_complete",
                title = "helpmod_field_ops_gesture_training_sync_complete_title",
                body = "helpmod_field_ops_gesture_training_sync_complete_body"
            )
        )
    )

    val defendModule = HelpModule(
        id = "field_ops_pose_defend",
        category = HelpCategory.FIELD_OPS,
        title = "helpmod_field_ops_pose_defend_title",
        summary = "helpmod_field_ops_pose_defend_summary",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_field_ops_pose_defend_intro_title",
                body = "helpmod_field_ops_pose_defend_intro_body"
            ),
            HelpStep(
                id = "wake_gesture",
                title = "helpmod_field_ops_pose_defend_wake_gesture_title",
                body = "helpmod_field_ops_pose_defend_wake_gesture_body",
                action = HelpAction.WatchEvent("ARMED")
            ),
            HelpStep(
                id = "system_armed",
                title = "helpmod_field_ops_pose_defend_system_armed_title",
                body = "helpmod_field_ops_pose_defend_system_armed_body"
            ),
            HelpStep(
                id = "pose_lock",
                title = "helpmod_field_ops_pose_defend_pose_lock_title",
                body = "helpmod_field_ops_pose_defend_pose_lock_body",
                action = HelpAction.WatchEvent("POSE_DEF")
            ),
            HelpStep(
                id = "pose_locked",
                title = "helpmod_field_ops_pose_defend_pose_locked_title",
                body = "helpmod_field_ops_pose_defend_pose_locked_body",
                action = HelpAction.WatchEvent("MODIFIED")
            ),
            HelpStep(
                id = "fire_command",
                title = "helpmod_field_ops_pose_defend_fire_command_title",
                body = "helpmod_field_ops_pose_defend_fire_command_body",
                action = HelpAction.WatchEvent("FIRE")
            ),
            HelpStep(
                id = "sync_complete",
                title = "helpmod_field_ops_pose_defend_sync_complete_title",
                body = "helpmod_field_ops_pose_defend_sync_complete_body"
            )
        )
    )

    val connectModule = HelpModule(
        id = "field_ops_pose_connect",
        category = HelpCategory.FIELD_OPS,
        title = "helpmod_field_ops_pose_connect_title",
        summary = "helpmod_field_ops_pose_connect_summary",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_field_ops_pose_connect_intro_title",
                body = "helpmod_field_ops_pose_connect_intro_body"
            ),
            HelpStep(
                id = "wake_gesture",
                title = "helpmod_field_ops_pose_connect_wake_gesture_title",
                body = "helpmod_field_ops_pose_connect_wake_gesture_body",
                action = HelpAction.WatchEvent("ARMED")
            ),
            HelpStep(
                id = "system_armed",
                title = "helpmod_field_ops_pose_connect_system_armed_title",
                body = "helpmod_field_ops_pose_connect_system_armed_body"
            ),
            HelpStep(
                id = "pose_lock",
                title = "helpmod_field_ops_pose_connect_pose_lock_title",
                body = "helpmod_field_ops_pose_connect_pose_lock_body",
                action = HelpAction.WatchEvent("POSE_CON")
            ),
            HelpStep(
                id = "pose_locked",
                title = "helpmod_field_ops_pose_connect_pose_locked_title",
                body = "helpmod_field_ops_pose_connect_pose_locked_body",
                action = HelpAction.WatchEvent("MODIFIED")
            ),
            HelpStep(
                id = "fire_command",
                title = "helpmod_field_ops_pose_connect_fire_command_title",
                body = "helpmod_field_ops_pose_connect_fire_command_body",
                action = HelpAction.WatchEvent("FIRE")
            ),
            HelpStep(
                id = "sync_complete",
                title = "helpmod_field_ops_pose_connect_sync_complete_title",
                body = "helpmod_field_ops_pose_connect_sync_complete_body"
            )
        )
    )

    // Not a guided walkthrough -- MainActivity intercepts this module's id before
    // calling HelpManager.start() and opens TrainingGroundPanel instead, a live
    // telemetry readout with no steps to complete and no state-machine pacing.
    val trainingGroundModule = HelpModule(
        id = "field_ops_training_ground",
        category = HelpCategory.FIELD_OPS,
        title = "helpmod_field_ops_training_ground_title",
        summary = "helpmod_field_ops_training_ground_summary",
        steps = listOf(
            HelpStep(
                id = "live",
                title = "helpmod_field_ops_training_ground_live_title",
                body = "helpmod_field_ops_training_ground_live_body"
            )
        )
    )

    // Not a guided walkthrough -- MainActivity intercepts this module's id
    // before calling HelpManager.start() and opens DeckTrainerPanel instead:
    // a scored drill like Training Ground, but the prompt it shows is a real
    // statement resolved from the deck (and Matrix profile) the user picks,
    // rather than a bare pose/mod label.
    val deckTrainerModule = HelpModule(
        id = "field_ops_deck_trainer",
        category = HelpCategory.FIELD_OPS,
        title = "helpmod_field_ops_deck_trainer_title",
        summary = "helpmod_field_ops_deck_trainer_summary",
        steps = listOf(
            HelpStep(
                id = "live",
                title = "helpmod_field_ops_deck_trainer_live_title",
                body = "helpmod_field_ops_deck_trainer_live_body"
            )
        )
    )

    data class PoseOption(
        val moduleId: String,
        val label: String,
        val hint: String
    )

    val poseOptions = listOf(
        PoseOption(identityModule.id, "IDENTITY", "Arm raised straight up, like checking the time."),
        PoseOption(defendModule.id, "DEFEND", "Arm out flat, palm down, like signaling stop."),
        PoseOption(connectModule.id, "CONNECT", "Arm out to the side, like offering a handshake.")
    )

    // Also not a guided walkthrough by itself -- MainActivity intercepts this
    // module's id before calling HelpManager.start() and opens PoseSelectorDialog
    // instead. Picking an option there starts the matching real module below.
    val poseTrainingEntryModule = HelpModule(
        id = "field_ops_pose_training",
        category = HelpCategory.FIELD_OPS,
        title = "helpmod_field_ops_pose_training_title",
        summary = "helpmod_field_ops_pose_training_summary",
        steps = listOf(
            HelpStep(
                id = "select",
                title = "helpmod_field_ops_pose_training_select_title",
                body = "helpmod_field_ops_pose_training_select_body"
            )
        )
    )

    // Guided, paced walkthroughs, one per pose. Kept registered for HelpManager
    // lookup but hidden from the menu list in favor of poseTrainingEntryModule --
    // see MainActivity's filtered HelpMenuDialog modules list. Distinct from
    // trainingGroundModule, which runs live-paced instead of paced -- see
    // MainActivity's training-mode sync effect.
    val pacedModules = listOf(identityModule, defendModule, connectModule)
    val pacedModuleIds: Set<String> = pacedModules.map { it.id }.toSet()

    val modules = pacedModules + trainingGroundModule + deckTrainerModule + poseTrainingEntryModule
}
