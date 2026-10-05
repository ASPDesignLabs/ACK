// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*

/**
 * The GEO-PROTOCOL walkthrough. Its words are string resources, read where the step is drawn or spoken (core/HelpWalkthroughText.kt): a module's title and summary are
 * `helpmod_<module id>_title` / `_summary`, a step's `helpmod_<module id>_<step id>_title` / `_body`.
 */
object GeoProtocolHelp {
    val module = HelpModule(
        id = "geo_protocol",
        category = HelpCategory.CONTEXTUAL_SYSTEMS,
        title = "helpmod_geo_protocol_title",
        summary = "helpmod_geo_protocol_summary",
        destination = HelpDestination.GEO,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "helpmod_geo_protocol_intro_title",
                body = "helpmod_geo_protocol_intro_body"
            ),
            HelpStep(
                id = "geo_view",
                title = "helpmod_geo_protocol_geo_view_title",
                body = "helpmod_geo_protocol_geo_view_body",
                action = HelpAction.Interact(AckTags.GEO_VIEW),
                targetTag = AckTags.GEO_VIEW
            ),
            HelpStep(
                id = "map_data",
                title = "helpmod_geo_protocol_map_data_title",
                body = "helpmod_geo_protocol_map_data_body",
                action = HelpAction.Interact(AckTags.GEO_MAP_IMPORT),
                targetTag = AckTags.GEO_MAP_IMPORT
            )
        )
    )
}
