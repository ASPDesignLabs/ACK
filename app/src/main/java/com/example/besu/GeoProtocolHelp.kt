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
            ),
            HelpStep(
                id = "map_data",
                title = "MAP DATA",
                body = "No region map ships with the app. Zones still work by coordinate " +
                    "with nothing imported, but you can import your own Mapsforge-compatible " +
                    ".map file here any time to see real basemap tiles on the Tactical Grid.",
                action = HelpAction.Interact(AckTags.GEO_MAP_IMPORT),
                targetTag = AckTags.GEO_MAP_IMPORT
            )
        )
    )
}