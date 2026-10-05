// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object SettingsManagementHelp {
    val module = HelpModule(
        id = "settings_management",
        category = HelpCategory.BASICS_SETTINGS,
        title = "helpmod_settings_management_title",
        summary = "helpmod_settings_management_summary",
        destination = HelpDestination.SETTINGS,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_settings_management_intro_title",
                body = "helpmod_settings_management_intro_body"
            ),
            HelpStep(
                id = "audio_output_routing",
                title = "helpmod_settings_management_audio_output_routing_title",
                body = "helpmod_settings_management_audio_output_routing_body",
                action = HelpAction.Interact(AckTags.SETTINGS_AUDIO_ROUTING),
                targetTag = AckTags.SETTINGS_AUDIO_ROUTING
            ),
            HelpStep(
                id = "watch_audio",
                title = "helpmod_settings_management_watch_audio_title",
                body = "helpmod_settings_management_watch_audio_body",
                action = HelpAction.Interact(AckTags.SETTINGS_WATCH_AUDIO),
                targetTag = AckTags.SETTINGS_WATCH_AUDIO
            ),
            HelpStep(
                id = "hardware_config",
                title = "helpmod_settings_management_hardware_config_title",
                body = "helpmod_settings_management_hardware_config_body",
                action = HelpAction.Interact(AckTags.SETTINGS_WATCH_CONFIG),
                targetTag = AckTags.SETTINGS_WATCH_CONFIG
            ),
            HelpStep(
                id = "environment_sensor",
                title = "helpmod_settings_management_environment_sensor_title",
                body = "helpmod_settings_management_environment_sensor_body",
                action = HelpAction.Interact(AckTags.SETTINGS_ENV_SENSOR),
                targetTag = AckTags.SETTINGS_ENV_SENSOR
            ),
            HelpStep(
                id = "quick_access_keys",
                title = "helpmod_settings_management_quick_access_keys_title",
                body = "helpmod_settings_management_quick_access_keys_body",
                // action = HelpAction.Interact(AckTags.SETTINGS_SHORTCUTS),
                // targetTag = AckTags.SETTINGS_SHORTCUTS
            ),
            HelpStep(
                id = "data_port",
                title = "helpmod_settings_management_data_port_title",
                body = "helpmod_settings_management_data_port_body",
                action = HelpAction.Interact(AckTags.SETTINGS_DATA_PORT),
                targetTag = AckTags.SETTINGS_DATA_PORT,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "completion",
                title = "helpmod_settings_management_completion_title",
                body = "helpmod_settings_management_completion_body"
            )
        )
    )
}