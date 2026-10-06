// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object EmergencyDeckHelp {
    val module = HelpModule(
        id = "deck_emergency",
        category = HelpCategory.USING_DECKS,
        title = "helpmod_deck_emergency_title",
        summary = "helpmod_deck_emergency_summary",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_deck_emergency_intro_title",
                body = "helpmod_deck_emergency_intro_body"
            ),
            HelpStep(
                id = "slot",
                title = "helpmod_deck_emergency_slot_title",
                body = "helpmod_deck_emergency_slot_body",
                action = HelpAction.Interact(AckTags.EMERGENCY_SLOT),
                targetTag = AckTags.EMERGENCY_SLOT
            ),
            HelpStep(
                id = "save",
                title = "helpmod_deck_emergency_save_title",
                body = "helpmod_deck_emergency_save_body",
                action = HelpAction.CommitText(AckTags.EMERGENCY_SAVE),
                targetTag = AckTags.EMERGENCY_SAVE
            ),
            HelpStep(
                id = "overrides",
                title = "helpmod_deck_emergency_overrides_title",
                body = "helpmod_deck_emergency_overrides_body",
                action = HelpAction.Interact(AckTags.EMERGENCY_OVERRIDES),
                targetTag = AckTags.EMERGENCY_OVERRIDES
            ),
            HelpStep(
                id = "info",
                title = "helpmod_deck_emergency_info_title",
                body = "helpmod_deck_emergency_info_body",
                action = HelpAction.Interact(AckTags.EMERGENCY_INFO),
                targetTag = AckTags.EMERGENCY_INFO
            ),
            HelpStep(
                id = "info_save",
                title = "helpmod_deck_emergency_info_save_title",
                body = "helpmod_deck_emergency_info_save_body",
                action = HelpAction.CommitText(AckTags.EMERGENCY_INFO_SAVE),
                targetTag = AckTags.EMERGENCY_INFO_SAVE
            )
        )
    )
}