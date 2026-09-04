package com.example.besu.wear

object PoseActions {
    const val ACTION_ENABLE_POSE_LISTENING =
        "com.example.besu.wear.ACTION_ENABLE_POSE_LISTENING"

    const val ACTION_DISABLE_POSE_LISTENING =
        "com.example.besu.wear.ACTION_DISABLE_POSE_LISTENING"

    const val ACTION_ENTER_CRYO =
        "com.example.besu.wear.ACTION_ENTER_CRYO"

    const val ACTION_SET_TRAINING_MODE =
        "com.example.besu.wear.ACTION_SET_TRAINING_MODE"

    // Sent when the phone's coach panel actually reaches its FIRE step during
    // paced training -- the only permission BackgroundSensorService needs to
    // complete a held pose while paced. No timer substitutes for this.
    const val ACTION_TRAINING_FIRE_READY =
        "com.example.besu.wear.ACTION_TRAINING_FIRE_READY"

    const val EXTRA_DURATION_MS = "duration_ms"

    // String extra, one of "OFF" / "PACED" / "LIVE" -- matches
    // BackgroundSensorService.TrainingMode.
    const val EXTRA_TRAINING_MODE = "training_mode"

    const val DEFAULT_LISTENING_DURATION_MS = 60_000L
}
