package com.example.besu


object FieldOpsHelp {
    val module = HelpModule(
        id = "field_ops_gesture_training",
        category = HelpCategory.FIELD_OPS,
        title = "GESTURE TRAINING",
        summary = "ARM, LOCK A POSE, MODIFY, AND FIRE USING THE WATCH.",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "PHYSICAL SYNC",
                body = "Gesture Training walks through a full physical command cycle: " +
                    "arm the system, lock a pose, apply a modifier, then fire. Make sure " +
                    "the watch app is open and its screen is active."
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
                id = "pose_identity",
                title = "POSE: IDENTITY",
                body = "Raise your arm straight up, like checking the time, and hold " +
                    "steady to lock the IDENTITY pose.",
                action = HelpAction.WatchEvent("POSE_ID")
            ),
            HelpStep(
                id = "pose_locked",
                title = "POSE LOCKED",
                body = "IDENTITY pose detected.\n\nWhile holding the pose, perform ONE " +
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
}
