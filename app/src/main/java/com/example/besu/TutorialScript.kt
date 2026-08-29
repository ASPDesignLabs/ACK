package com.example.besu

// --- ENUMS & DATA CLASSES ---

enum class TutAction {
    READ,       // Tap anywhere to advance
    INTERACT,   // Must click the specific UI element
    WATCH_INPUT // Must perform a gesture on the watch
}

// Used by the logic engine to define a step
data class TutorialDef(
    val stepId: Int,
    val targetTag: String?,
    val title: String,
    val body: String,
    val action: TutAction,
    val forceView: String? = null // Optional: Forces the app to switch views (e.g. "MATRIX")
)

// Used by the UI Overlay to render the state
data class TutorialState(
    val stepIndex: Int = -1,
    val isActive: Boolean = false,
    val targetTag: String? = null,
    val title: String = "",
    val body: String = "",
    val action: TutAction = TutAction.READ
)

// --- THE SCRIPT CONTENT ---

object TutorialScript {

    // MODULE 1: BOOT CAMP (The Basics)
    val MOD_BASIC = listOf(
        TutorialDef(0, AckTags.HEADER_ROW, "SYSTEM CHECK", "Welcome to ACK.\nThis terminal is your bridge between physical movement and digital speech.", TutAction.READ),
        TutorialDef(1, AckTags.LIVE_LINK, "NEURAL UPLINK", "This indicator shows the Watch status.\nGREEN = Live/Ready\nBLUE = Cryostasis (Sleep)\nGRAY = Disconnected.\n\nTap it to toggle the data stream manually.", TutAction.INTERACT),
        TutorialDef(2, AckTags.MODE_TOGGLE_BTN, "VIEWPORT CONTROL", "Use this toggle to switch between the Matrix (Configuration) and the Terminal (Logs).", TutAction.INTERACT),
        TutorialDef(3, null, "MODULE COMPLETE", "Boot Camp finished. Proceed to Field Ops to learn gesture mapping.", TutAction.READ)
    )

    // MODULE 2: FIELD OPS (Matrix Editing)
    val MOD_MATRIX = listOf(
        TutorialDef(0, AckTags.PROFILE_SELECTOR, "CONTEXT LOADING", "Tap here to open the Profile Menu.", TutAction.INTERACT, forceView = "MATRIX"),
        TutorialDef(1, AckTags.PROFILE_MENU, "SELECT BUILDER", "Load the 'BUILDER' profile. This is a sandbox for creating new mappings.", TutAction.INTERACT),
        TutorialDef(2, AckTags.MATRIX_ROW_TARGET, "NODE EDITING", "Tap the first row ('Twist 0') to edit its output phrase.", TutAction.INTERACT),
        TutorialDef(3, AckTags.EDIT_NODE_DIALOG, "DATA ENTRY", "Type a response like 'System Ready' and tap COMMIT.", TutAction.INTERACT),
        TutorialDef(4, AckTags.MATRIX_PLAY_BTN, "AUDIO TEST", "Tap the small PLAY arrow to preview your new phrase immediately.", TutAction.INTERACT),
        TutorialDef(5, null, "MODULE COMPLETE", "You can now map specific phrases to gestures.", TutAction.READ)
    )

    // MODULE 3: SENSOR SYNC (Watch Integration)
    val MOD_SENSORS = listOf(
        TutorialDef(0, null, "PHYSICAL SYNC", "Stand by for Sensor Calibration.\nEnsure the Watch app is open and screen is active.", TutAction.READ),
        TutorialDef(1, AckTags.LIVE_LINK, "THE WAKE GESTURE", "Your watch is locked by default to prevent accidents.\n\nPerform a TRIPLE WRIST TWIST to arm the system.\n(Rotate wrist out/in 3 times fast).", TutAction.WATCH_INPUT),
        TutorialDef(2, null, "SYSTEM ARMED", "Good. The system is now ARMED (Green).\nIt is scanning for a dominant axis (Pose).", TutAction.READ),
        TutorialDef(3, null, "POSE: IDENTITY", "Raise your arm straight up (like checking the time, or a thumbs up).\nHold steady.", TutAction.WATCH_INPUT), 
        TutorialDef(4, null, "POSE LOCKED", "Pose Detected: IDENTITY (Arm Up).\n\nWhile holding this pose, perform ONE TWIST to change the selection from default.", TutAction.WATCH_INPUT),
        TutorialDef(5, null, "FIRE COMMAND", "Excellent.\n\nNow, hold your arm steady again to FIRE the selected command.", TutAction.WATCH_INPUT),
        TutorialDef(6, null, "SYNC COMPLETE", "You have successfully executed a full physical command cycle.", TutAction.READ)
    )
}
