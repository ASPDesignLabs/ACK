// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object PersonalizationHelp {
    val module = HelpModule(
        id = "personalization",
        category = HelpCategory.BASICS_PERSONALIZATION,
        title = "helpmod_personalization_title",
        summary = "helpmod_personalization_summary",
        destination = HelpDestination.AUDIO,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_personalization_intro_title",
                body = "helpmod_personalization_intro_body"
            ),
            HelpStep(
                id = "global_output",
                title = "helpmod_personalization_global_output_title",
                body = "helpmod_personalization_global_output_body"
            ),
            HelpStep(
                id = "master_gain",
                title = "helpmod_personalization_master_gain_title",
                body = "helpmod_personalization_master_gain_body",
                action = HelpAction.Interact(AckTags.AUDIO_MASTER_GAIN),
                targetTag = AckTags.AUDIO_MASTER_GAIN
            ),
            HelpStep(
                id = "factory_presets",
                title = "helpmod_personalization_factory_presets_title",
                body = "helpmod_personalization_factory_presets_body"
            ),
            HelpStep(
                id = "custom_profiles",
                title = "helpmod_personalization_custom_profiles_title",
                body = "helpmod_personalization_custom_profiles_body",
                action = HelpAction.Interact(AckTags.AUDIO_PROFILE_SELECT),
                targetTag = AckTags.AUDIO_PROFILE_SELECT
            ),
            HelpStep(
                id = "manage_profiles",
                title = "helpmod_personalization_manage_profiles_title",
                body = "helpmod_personalization_manage_profiles_body",
                action = HelpAction.Interact(AckTags.AUDIO_PROFILE_MANAGE),
                targetTag = AckTags.AUDIO_PROFILE_MANAGE
            ),
            HelpStep(
                id = "dsp_chain",
                title = "helpmod_personalization_dsp_chain_title",
                body = "helpmod_personalization_dsp_chain_body"
            ),
            HelpStep(
                id = "base_voice",
                title = "helpmod_personalization_base_voice_title",
                body = "helpmod_personalization_base_voice_body",
                action = HelpAction.Interact(AckTags.AUDIO_VOICE_PICKER),
                targetTag = AckTags.AUDIO_VOICE_PICKER
            ),
            HelpStep(
                id = "pitch_speed",
                title = "helpmod_personalization_pitch_speed_title",
                body = "helpmod_personalization_pitch_speed_body",
                action = HelpAction.Interact(AckTags.AUDIO_PITCH_SPEED),
                targetTag = AckTags.AUDIO_PITCH_SPEED
            ),
            HelpStep(
                id = "robotic_overlay",
                title = "helpmod_personalization_robotic_overlay_title",
                body = "helpmod_personalization_robotic_overlay_body",
                action = HelpAction.Interact(AckTags.AUDIO_ROBOTIC_OVERLAY),
                targetTag = AckTags.AUDIO_ROBOTIC_OVERLAY
            ),
            HelpStep(
                id = "bitcrush",
                title = "helpmod_personalization_bitcrush_title",
                body = "helpmod_personalization_bitcrush_body",
                action = HelpAction.Interact(AckTags.AUDIO_BITCRUSH),
                targetTag = AckTags.AUDIO_BITCRUSH
            ),
            HelpStep(
                id = "save_profile",
                title = "helpmod_personalization_save_profile_title",
                body = "helpmod_personalization_save_profile_body",
                action = HelpAction.CommitText(AckTags.AUDIO_SAVE),
                targetTag = AckTags.AUDIO_SAVE
            ),
            HelpStep(
                id = "completion",
                title = "helpmod_personalization_completion_title",
                body = "helpmod_personalization_completion_body"
            )
        )
    )
}
