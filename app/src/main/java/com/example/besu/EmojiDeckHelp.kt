package com.example.besu

object EmojiDeckHelp {
    val module = HelpModule(
        id = "deck_emoji",
        category = HelpCategory.USING_DECKS,
        title = "EMOJI DECK",
        summary = "VISUAL PROMPTS, TEXT, LIBRARY PICKS, AND RELATED PANELS.",
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "EMOJI EXPRESS",
                body = "The Emoji deck displays visual communication prompts. " +
                    "It can show an emoji alone or pair it with overlay text."
            ),
            HelpStep(
                id = "slot",
                title = "CONFIGURE A TILE",
                body = "Hold an emoji tile to configure its emoji, label, and " +
                    "optional display text.",
                action = HelpAction.Interact(AckTags.EMOJI_SLOT),
                targetTag = AckTags.EMOJI_SLOT
            ),
            HelpStep(
                id = "library",
                title = "EMOJI LIBRARY",
                body = "Use the library for common communication symbols, or " +
                    "enter a custom emoji directly.",
                action = HelpAction.Interact(AckTags.EMOJI_LIBRARY),
                targetTag = AckTags.EMOJI_LIBRARY
            ),
            HelpStep(
                id = "related",
                title = "RELATED PANELS",
                body = "A configured emoji can open one related panel. This is " +
                    "useful for grouping similar responses or needs.",
                action = HelpAction.Interact(AckTags.EMOJI_RELATED_PANEL),
                targetTag = AckTags.EMOJI_RELATED_PANEL
            ),
            HelpStep(
                id = "clear",
                title = "DISPLAY CLEARING",
                body = "When you display an emoji, ACK may wait for its normal " +
                    "timeout or your configured clearing behavior.",
                action = HelpAction.OverlayCleared(AckTags.EMOJI_SLOT),
                targetTag = AckTags.EMOJI_SLOT
            )
        )
    )
}