// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*

/** This family's words are string resources (helpmod_<module id>_..., core/HelpWalkthroughText.kt), read where a step is drawn or spoken. */
object LogsHelp {
    val module = HelpModule(
        id = "logs",
        category = HelpCategory.CONTEXTUAL_SYSTEMS,
        title = "helpmod_logs_title",
        summary = "helpmod_logs_summary",
        destination = HelpDestination.TERMINAL,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_logs_intro_title",
                body = "helpmod_logs_intro_body"
            ),
            HelpStep(
                id = "terminal",
                title = "helpmod_logs_terminal_title",
                body = "helpmod_logs_terminal_body",
                action = HelpAction.Interact(AckTags.TERMINAL_VIEW),
                targetTag = AckTags.TERMINAL_VIEW
            )
        )
    )
}
