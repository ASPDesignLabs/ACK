package com.example.besu.help

import com.example.besu.*
object SettingsManagementHelp {
    val module = HelpModule(
        id = "settings_management",
        category = HelpCategory.BASICS_SETTINGS,
        title = "SETTINGS MANAGEMENT",
        summary = "AUDIO ROUTING, WATCH AUDIO, HARDWARE, SENSORS, SHORTCUTS, AND DATA.",
        destination = HelpDestination.SETTINGS,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "PROTOCOL OVERVIEW",
                body = "PROTOCOL contains ACK's system-wide configuration. " +
                        "These controls affect the application independently of " +
                        "the currently active deck."
            ),
            HelpStep(
                id = "audio_output_routing",
                title = "AUDIO OUTPUT ROUTING",
                body = "Force Speaker can direct speech toward the device speaker " +
                        "when that is appropriate for your setup. Guide Vox controls " +
                        "whether tutorial and guide narration is spoken aloud. Silent " +
                        "Mode shows prompts as normal but never speaks them out loud.",
                action = HelpAction.Interact(AckTags.SETTINGS_AUDIO_ROUTING),
                targetTag = AckTags.SETTINGS_AUDIO_ROUTING
            ),
            HelpStep(
                id = "watch_audio",
                title = "WATCH AUDIO FEEDBACK",
                body = "This section controls audio feedback played by the watch " +
                        "when issuing pose commands. Select a texture preset and adjust the " +
                        "watch feedback volume to fit your needs.",
                action = HelpAction.Interact(AckTags.SETTINGS_WATCH_AUDIO),
                targetTag = AckTags.SETTINGS_WATCH_AUDIO
            ),
            HelpStep(
                id = "hardware_config",
                title = "WATCH CONFIGURATION",
                body = "Hardware Configuration controls the behavior of ACK's " +
                        "watch input system. Crown Resistance adjusts how much " +
                        "rotation is needed. Twist Sensitivity controls motion " +
                        "response. Gravity Lock controls pose stability, and " +
                        "Auto-Cryo controls automatic idle behavior.",
                action = HelpAction.Interact(AckTags.SETTINGS_WATCH_CONFIG),
                targetTag = AckTags.SETTINGS_WATCH_CONFIG
            ),
            HelpStep(
                id = "environment_sensor",
                title = "ENVIRONMENT SENSOR",
                body = "The Environment Sensor estimates local sound levels using " +
                        "the microphone in your handset. For most devices this is a " +
                        "small sensor, so the readings are not 100% accurate. Good enough " +
                        "to help judge exposure time. " +
                        "Use the scan control to begin or stop monitoring. This can " +
                        "help you judge whether speech output may need a different " +
                        "volume, cadence, route, or communication strategy.",
                action = HelpAction.Interact(AckTags.SETTINGS_ENV_SENSOR),
                targetTag = AckTags.SETTINGS_ENV_SENSOR
            ),
            HelpStep(
                id = "quick_access_keys",
                title = "QUICK-ACCESS KEYS",
                body = "Quick-Access Keys appear in the ACK Command bar. Each " +
                        "slot has a short label and a saved phrase. Configure these " +
                        "for phrases that need to be available with minimal effort.",
                // action = HelpAction.Interact(AckTags.SETTINGS_SHORTCUTS),
                // targetTag = AckTags.SETTINGS_SHORTCUTS
            ),
            HelpStep(
                id = "data_port",
                title = "DATA PORT",
                body = "The Data Port manages configuration transfer and backup. " +
                        "Export creates a JSON backup, Import Matrix As New Deck " +
                        "brings in a backup's matrix phrases as a new deck, and " +
                        "Full Restore applies everything else a backup carries -- " +
                        "overwriting or adding to your current setup, never " +
                        "deleting what it doesn't mention. " +
                        "The guide has moved upward so these controls remain visible.",
                action = HelpAction.Interact(AckTags.SETTINGS_DATA_PORT),
                targetTag = AckTags.SETTINGS_DATA_PORT,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "completion",
                title = "SETTINGS MANAGEMENT COMPLETE",
                body = "Protocol training complete. You now know where to tune " +
                        "audio output routing, watch feedback, hardware response, " +
                        "environmental scanning, header shortcuts, and configuration " +
                        "backups."
            )
        )
    )
}