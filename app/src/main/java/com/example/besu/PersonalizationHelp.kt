package com.example.besu

object PersonalizationHelp {
    val module = HelpModule(
        id = "personalization",
        category = HelpCategory.BASICS_PERSONALIZATION,
        title = "AUDIO ARCHITECT",
        summary = "VOICE PROFILES, DSP, OUTPUT ROUTING, AND CUSTOM SLOTS.",
        destination = HelpDestination.AUDIO,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "AUDIO ARCHITECT",
                body = "Audio Architect controls how ACK sounds when it speaks. " +
                    "It lets you configure output volume, routing behavior, " +
                    "voice profiles, and custom signal processing."
            ),
            HelpStep(
                id = "global_output",
                title = "GLOBAL OUTPUT",
                body = "Global Output settings affect ACK's overall speech " +
                    "behavior. Master Gain controls output level. Global Cadence " +
                    "adjusts pacing. Force Speaker changes routing behavior, and " +
                    "Guide Vox controls whether spoken tutorial feedback is used."
            ),
            HelpStep(
                id = "master_gain",
                title = "MASTER GAIN AND CADENCE",
                body = "Adjust Master Gain to set overall speech volume. Adjust " +
                    "Global Cadence to change the timing and spacing of ACK's " +
                    "voice output. Choose values that remain comfortable and " +
                    "understandable in your common environments.",
                action = HelpAction.Interact(AckTags.AUDIO_MASTER_GAIN),
                targetTag = AckTags.AUDIO_MASTER_GAIN
            ),
            HelpStep(
                id = "output_routing",
                title = "SPEAKER AND GUIDE VOX",
                body = "Force Speaker can direct speech toward the device speaker " +
                    "when that is appropriate for your setup. Guide Vox controls " +
                    "spoken tutorial and system guidance. These settings let you " +
                    "shape how much audible feedback ACK provides.",
                action = HelpAction.Interact(AckTags.AUDIO_OUTPUT_ROUTING),
                targetTag = AckTags.AUDIO_OUTPUT_ROUTING
            ),
            HelpStep(
                id = "factory_presets",
                title = "FACTORY VOICE PRESETS",
                body = "Factory presets provide ready-to-use voice styles. They " +
                    "are useful when you want a consistent voice without editing " +
                    "a full DSP chain. Select a factory preset to use it as the " +
                    "active speech profile."
            ),
            HelpStep(
                id = "custom_profiles",
                title = "CUSTOM PROFILE SLOTS",
                body = "Custom profile slots can store your own voice designs. " +
                    "Select one of the custom placeholder slots below to open " +
                    "its editable DSP Chain configuration.",
                action = HelpAction.Interact(AckTags.AUDIO_PROFILE_SELECT),
                targetTag = AckTags.AUDIO_PROFILE_SELECT
            ),
            HelpStep(
                id = "dsp_chain",
                title = "DSP CHAIN",
                body = "The DSP Chain is available when a custom profile is " +
                    "selected. It controls the source voice and signal treatment " +
                    "stored inside that custom slot."
            ),
            HelpStep(
                id = "base_voice",
                title = "SELECT A BASE VOICE",
                body = "Select a Base Voice to choose from on-device Android TTS " +
                    "voices. This is the human-readable source signal before " +
                    "pitch, speed, robotic processing, or texture effects are " +
                    "applied.",
                action = HelpAction.Interact(AckTags.AUDIO_VOICE_PICKER),
                targetTag = AckTags.AUDIO_VOICE_PICKER
            ),
            HelpStep(
                id = "pitch_speed",
                title = "PITCH AND SPEED",
                body = "Pitch Shift changes the perceived height of the voice. " +
                    "Speed changes how quickly it speaks. Small adjustments can " +
                    "make a profile clearer, calmer, more expressive, or more " +
                    "recognizably yours.",
                // action = HelpAction.Interact(AckTags.AUDIO_PITCH_SPEED),
                // targetTag = AckTags.AUDIO_PITCH_SPEED
            ),
            HelpStep(
                id = "robotic_overlay",
                title = "ROBOTIC OVERLAY",
                body = "The Robotic Overlay adds modulation to the selected voice. " +
                    "Enable it to reveal frequency and depth controls. Frequency " +
                    "changes the character of the effect, while depth controls " +
                    "how strongly the processed signal replaces the base voice.",
                // action = HelpAction.Interact(AckTags.AUDIO_ROBOTIC_OVERLAY),
                // targetTag = AckTags.AUDIO_ROBOTIC_OVERLAY
            ),
            HelpStep(
                id = "bitcrush",
                title = "BITCRUSH TEXTURE",
                body = "Bitcrush adds a deliberately digital texture to the voice. " +
                    "Use subtle values for a lightly synthesized edge, or higher " +
                    "values for a more aggressively processed communication style.",
                // action = HelpAction.Interact(AckTags.AUDIO_BITCRUSH),
                // targetTag = AckTags.AUDIO_BITCRUSH
            ),
            HelpStep(
                id = "save_profile",
                title = "COMMIT CUSTOM PROFILE",
                body = "When the profile sounds right, use COMMIT to save the DSP " +
                    "Chain into the selected custom slot. That profile can then " +
                    "be selected as ACK's active output voice.",
                action = HelpAction.CommitText(AckTags.AUDIO_SAVE),
                targetTag = AckTags.AUDIO_SAVE
            ),
            HelpStep(
                id = "completion",
                title = "AUDIO ARCHITECT COMPLETE",
                body = "Audio Architect training complete. You can now configure " +
                    "global output, select voice profiles, build a custom DSP " +
                    "Chain, and save it to a reusable custom slot."
            )
        )
    )
}
