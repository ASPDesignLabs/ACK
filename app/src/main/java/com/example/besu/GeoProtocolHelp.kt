package com.example.besu

object GeoProtocolHelp {
    val module = HelpModule(
        id = "geo_protocol",
        category = HelpCategory.CONTEXTUAL_SYSTEMS,
        title = "GEO-PROTOCOL",
        summary = "LOCATION-BASED CONTEXT AND ZONE BEHAVIOR.",
        destination = HelpDestination.GEO,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "GEO-PROTOCOL",
                body = "Geo-Protocol manages location-aware ACK behavior and zones."
            ),
            HelpStep(
                id = "geo_view",
                title = "ZONE CONTROLS",
                body = "Review zone controls and configure behavior appropriate " +
                    "to your environment.",
                action = HelpAction.Interact(AckTags.GEO_VIEW),
                targetTag = AckTags.GEO_VIEW
            )
        )
    )
}