package com.example.besu

object GifDeckHelp {
    val module = HelpModule(
        id = "deck_gif",
        category = HelpCategory.USING_DECKS,
        title = "GIF DECK",
        summary = "LOCAL GIF IMPORT, CATEGORIES, NAVIGATION, AND DISPLAY.",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "LOCAL GIF LIBRARY",
                body = "GIF decks use local files. Imported GIFs stay organized " +
                    "by category and can be displayed full-screen."
            ),
            HelpStep(
                id = "import",
                title = "IMPORT A GIF",
                body = "Choose IMPORT and select a local GIF file.",
                action = HelpAction.Interact(AckTags.GIF_IMPORT),
                targetTag = AckTags.GIF_IMPORT
            ),
            HelpStep(
                id = "commit_import",
                title = "NAME AND CATEGORIZE",
                body = "Give the GIF a title, select or create a category, and " +
                    "commit the import.",
                action = HelpAction.CommitFile(AckTags.GIF_IMPORT_COMMIT),
                targetTag = AckTags.GIF_IMPORT_COMMIT
            ),
            HelpStep(
                id = "category",
                title = "GIF CATEGORIES",
                body = "Use the category selector to filter the active GIF wheel.",
                action = HelpAction.Interact(AckTags.GIF_CATEGORY),
                targetTag = AckTags.GIF_CATEGORY
            ),
            HelpStep(
                id = "landscape",
                title = "LANDSCAPE DISPLAY",
                body = "Enable landscape display when a GIF benefits from a " +
                    "wider full-screen presentation.",
                action = HelpAction.Interact(AckTags.GIF_LANDSCAPE_TOGGLE),
                targetTag = AckTags.GIF_LANDSCAPE_TOGGLE
            )
        )
    )
}