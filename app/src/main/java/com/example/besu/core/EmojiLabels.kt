// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the EMOJI deck says that is decided, not just drawn: the hint under the title, the name a page is shown with, and the title of a related panel. Plain Kotlin (no
 * `android.*`) so it is tested without a phone; the words are string resources (`emoji_*`, in the chosen language) read through a [TextSource].
 *
 * **A saved name is never rewritten.** A page is created named `PAGE 1`, `PAGE 2`.. (decks/EmojiDeck.kt). That is saved text: a page still carrying its saved default name is
 * *shown* in the chosen language; any other name (one from a backup, say) is shown exactly as saved. What the person typed into a tile (its emoji, label and overlay text) is theirs
 * and is never touched.
 */
object EmojiLabels {
    /** What a page is saved with until it is named. Must equal what `EmojiDeckConfig` and the deck configuration dialog create (a test reads the source). */
    fun storedDefaultPageName(pageIndex: Int): String = "PAGE ${pageIndex + 1}"

    /** The name to show for the page at [pageIndex]: the default in the chosen language, anything else exactly as saved. */
    fun shownPageName(text: TextSource, stored: String, pageIndex: Int): String =
        if (stored == storedDefaultPageName(pageIndex)) text.get("emoji_page_default", pageIndex + 1) else stored

    /** "TAP: DISPLAY  //  HOLD: CONFIGURE": two parts in the chosen language, joined by the app's own separator (a resource would collapse the double spaces). */
    fun hint(text: TextSource): String = text.get("emoji_hint_tap") + "  //  " + text.get("emoji_hint_hold")

    /** "RELATED // <name>": the tile's label, else its emoji, else the word for a panel. The label and the emoji are the person's own and are shown as typed. */
    fun relatedTitle(text: TextSource, label: String, emoji: String): String =
        text.get("emoji_related_title", label.ifBlank { emoji.ifBlank { text.get("emoji_panel_default") } })
}
