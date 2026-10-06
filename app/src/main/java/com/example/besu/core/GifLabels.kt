// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the GIF deck says that is decided, not just drawn: the name a category is shown with, the CATEGORY line, the ON / OFF overlay button, the toasts after an
 * import or an export and the reason an import failed. Plain Kotlin (no `android.*`) so it is tested without a phone; the words are string resources (`gif_*`, in the
 * chosen language) read through a [TextSource].
 *
 * **A saved name is never rewritten.** A category the person did not name is saved as [STORED_DEFAULT_CATEGORY] (`GifRepository.createCategory` uses this very constant). A category
 * still carrying that saved name is *shown* in the chosen language; a name the person typed is shown exactly as typed, and the stored name never changes. Every other word here is display text.
 */
object GifLabels {
    /** What `GifRepository.createCategory` saves when the person leaves the category blank. */
    const val STORED_DEFAULT_CATEGORY = "UNCATEGORIZED"

    /** The name to show for a category: the default in the chosen language, anything else exactly as saved. */
    fun shownCategoryName(text: TextSource, stored: String): String =
        if (stored == STORED_DEFAULT_CATEGORY) text.get("gif_category_default") else stored

    /** The CATEGORY button's words (without the arrow): the category's shown name, or NO GIFS when there is no category yet. */
    fun categoryLine(text: TextSource, storedCategoryName: String?): String =
        text.get("gif_category_line", if (storedCategoryName == null) text.get("gif_no_gifs") else shownCategoryName(text, storedCategoryName))

    /** The overlay-orientation button, with ON or OFF written in words (never by colour alone). */
    fun landscapeButton(text: TextSource, on: Boolean): String =
        text.get("gif_overlay_landscape", text.get(if (on) "common_on" else "common_off"))

    /**
     * The toast after a deck backup was restored: how many GIFs came in (in the language's plural form for that number), how many were skipped when any were, and that ACK is restarting.
     * Each of the two sentences is whole, so a language can put the parts where it wants them.
     */
    fun importedToast(text: TextSource, imported: Int, skipped: Int): String =
        if (skipped > 0) text.count("gif_imported_skipped_toast", imported, skipped) else text.count("gif_imported_toast", imported)

    /** The toast after an export: the deck was exported, naming it the way the rest of the screen does (the GIF label then the DECK label, which follow PLAIN WORDS), or that it failed. */
    fun exportToast(text: TextSource, succeeded: Boolean, gifLabel: String, deckLabel: String): String =
        if (succeeded) text.get("gif_exported", gifLabel, deckLabel) else text.get("gif_export_failed")

    /**
     * What the import dialog says when one GIF could not be imported. A reason this app knows ([GifImportException]) is said in the chosen language; any other failure keeps the text the system
     * gave (what it has always shown); a failure with no text says GIF IMPORT FAILED.
     */
    fun importError(text: TextSource, error: Throwable): String {
        val known = (error as? GifImportException)?.failure
        return when {
            known != null -> text.get(known.resource)
            else -> error.message ?: text.get("gif_import_failed")
        }
    }
}
