package com.example.besu.wear

object PoseActions {
    const val ACTION_ENABLE_POSE_LISTENING =
        "com.example.besu.wear.ACTION_ENABLE_POSE_LISTENING"

    const val ACTION_DISABLE_POSE_LISTENING =
        "com.example.besu.wear.ACTION_DISABLE_POSE_LISTENING"

    const val ACTION_ENTER_CRYO =
        "com.example.besu.wear.ACTION_ENTER_CRYO"

    // Sent when the wearer taps the watch face while a pose is locked --
    // aborts the pending fire and returns to ARMED instead of speaking
    // whatever got locked in.
    const val ACTION_CANCEL_POSE =
        "com.example.besu.wear.ACTION_CANCEL_POSE"

    // Sent on a long press of the watch face -- flips shaky-hands mode,
    // which widens pose-hold, wake-twist, and fire-grace timing for
    // moments motor control is worse than usual. Replaces the old
    // long-press CRYO setup menu.
    const val ACTION_TOGGLE_SHAKY_HANDS =
        "com.example.besu.wear.ACTION_TOGGLE_SHAKY_HANDS"

    const val ACTION_SET_TRAINING_MODE =
        "com.example.besu.wear.ACTION_SET_TRAINING_MODE"

    // Sent when the phone's coach panel actually reaches its FIRE step during
    // paced training -- the only permission BackgroundSensorService needs to
    // complete a held pose while paced. No timer substitutes for this.
    const val ACTION_TRAINING_FIRE_READY =
        "com.example.besu.wear.ACTION_TRAINING_FIRE_READY"

    // Sent when the coach panel reaches a step needing a fresh, deliberate
    // gesture (pose entry or the modifier twist), so a reading picked up
    // incidentally during the previous transition can't silently consume it.
    const val ACTION_TRAINING_RESET_LISTEN =
        "com.example.besu.wear.ACTION_TRAINING_RESET_LISTEN"

    // String extra for ACTION_TRAINING_RESET_LISTEN: "POSE" or "MODIFIER".
    const val EXTRA_RESET_TARGET = "reset_target"

    const val EXTRA_DURATION_MS = "duration_ms"

    // String extra, one of "OFF" / "PACED" / "LIVE" -- matches
    // BackgroundSensorService.TrainingMode.
    const val EXTRA_TRAINING_MODE = "training_mode"

    const val DEFAULT_LISTENING_DURATION_MS = 60_000L
}
