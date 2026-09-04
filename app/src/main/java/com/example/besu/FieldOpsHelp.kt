package com.example.besu


object FieldOpsHelp {

    private const val SYNC_INTRO = "Stand by for the physical command cycle: arm the " +
        "system, lock a pose, apply a modifier, then fire. Make sure the watch app is " +
        "open and its screen is active."

    private fun poseCycleModule(
        id: String,
        poseLabel: String,
        poseInstruction: String,
        poseEventType: String
    ): HelpModule = HelpModule(
        id = id,
        category = HelpCategory.FIELD_OPS,
        title = "$poseLabel POSE",
        summary = "ARM, LOCK $poseLabel, MODIFY, AND FIRE USING THE WATCH.",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "PHYSICAL SYNC",
                body = SYNC_INTRO
            ),
            HelpStep(
                id = "wake_gesture",
                title = "THE WAKE GESTURE",
                body = "The watch is locked by default to prevent accidental commands.\n\n" +
                    "Perform a TRIPLE WRIST TWIST (rotate wrist out/in three times fast) " +
                    "to arm the system.",
                action = HelpAction.WatchEvent("ARMED")
            ),
            HelpStep(
                id = "system_armed",
                title = "SYSTEM ARMED",
                body = "The system is now ARMED. It's scanning for a dominant pose."
            ),
            HelpStep(
                id = "pose_lock",
                title = "POSE: $poseLabel",
                body = poseInstruction,
                action = HelpAction.WatchEvent(poseEventType)
            ),
            HelpStep(
                id = "pose_locked",
                title = "POSE LOCKED",
                body = "$poseLabel pose detected.\n\nWhile holding the pose, perform ONE " +
                    "TWIST to apply a modifier.",
                action = HelpAction.WatchEvent("MODIFIED")
            ),
            HelpStep(
                id = "fire_command",
                title = "FIRE COMMAND",
                body = "Hold your arm steady again to FIRE the selected command.",
                action = HelpAction.WatchEvent("FIRE")
            ),
            HelpStep(
                id = "sync_complete",
                title = "SYNC COMPLETE",
                body = "You've executed a full physical command cycle: armed, posed, " +
                    "modified, and fired."
            )
        )
    )

    // Original module id preserved for continuity (was the only gesture-training
    // entry before per-pose subcategories existed).
    val identityModule = poseCycleModule(
        id = "field_ops_gesture_training",
        poseLabel = "IDENTITY",
        poseInstruction = "Raise your arm straight up, like checking the time, and hold steady.",
        poseEventType = "POSE_ID"
    )

    val defendModule = poseCycleModule(
        id = "field_ops_pose_defend",
        poseLabel = "DEFEND",
        poseInstruction = "Hold your arm out flat, palm down, like signaling stop.",
        poseEventType = "POSE_DEF"
    )

    val connectModule = poseCycleModule(
        id = "field_ops_pose_connect",
        poseLabel = "CONNECT",
        poseInstruction = "Hold your arm out to the side, like offering a handshake.",
        poseEventType = "POSE_CON"
    )

    // Not a guided walkthrough -- MainActivity intercepts this module's id before
    // calling HelpManager.start() and opens TrainingGroundPanel instead, a live
    // telemetry readout with no steps to complete and no state-machine pacing.
    val trainingGroundModule = HelpModule(
        id = "field_ops_training_ground",
        category = HelpCategory.FIELD_OPS,
        title = "TRAINING GROUND",
        summary = "FREE-FORM PRACTICE. LIVE TELEMETRY, NORMAL PACING, NO REAL OUTPUT.",
        steps = listOf(
            HelpStep(
                id = "live",
                title = "TRAINING GROUND",
                body = "Live telemetry only. Gesture freely and watch the readout -- " +
                    "no steps to complete, no commands fire."
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
        title = "POSE TRAINING",
        summary = "PICK A POSE, THEN WALK THROUGH ARM, LOCK, MODIFY, AND FIRE.",
        steps = listOf(
            HelpStep(
                id = "select",
                title = "POSE TRAINING",
                body = "Choose a pose to train."
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

    val modules = pacedModules + trainingGroundModule + poseTrainingEntryModule
}
