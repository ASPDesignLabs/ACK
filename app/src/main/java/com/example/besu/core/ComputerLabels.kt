// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The names the People and places (Target Computer) screens show that are decided, not just drawn. Plain Kotlin (no `android.*`), tested without a phone; the
 * words are string resources (`people_*`) read through a [TextSource].
 *
 * **A saved name is never rewritten.** A fresh install is given four categories named PEOPLE, PLACES, FOOD/DRINK and ACTIONS (data/ComputerRepository.kt). Those
 * names are saved text and the ids made from them are what `[COMPUTER:id]` tokens refer to, so neither is ever changed to a translation. A category still carrying
 * its saved default name is *shown* in the chosen language; a category the person renamed, or made themselves, is shown exactly as typed. Opening a category's
 * options and saving without touching the name saves what was stored ([nameToSave]). The same rule the Emergency deck uses for its buttons.
 */
object ComputerLabels {
    /** The four seeded categories: id, then the name they are saved with. Must equal `ComputerRepository.DEFAULT_CATEGORY_LABELS` (a test reads the source; an id is the name's slug). */
    val DEFAULT_CATEGORIES: List<Pair<String, String>> = listOf(
        "PEOPLE" to "PEOPLE",
        "PLACES" to "PLACES",
        "FOOD_DRINK" to "FOOD/DRINK",
        "ACTIONS" to "ACTIONS",
    )

    /** The resource that names a default category (`people_category_<id>`). */
    fun defaultResource(id: String): String = "people_category_${id.lowercase()}"

    /** The default category [id]'s name in the chosen language, or the id itself if it is not one of the four. */
    fun defaultName(text: TextSource, id: String): String =
        if (DEFAULT_CATEGORIES.any { it.first == id }) text.get(defaultResource(id)) else id

    /** A category's name as shown: the default in the chosen language while it still has its saved default name, otherwise exactly what is saved. */
    fun shownCategoryLabel(text: TextSource, id: String, stored: String): String {
        val default = DEFAULT_CATEGORIES.firstOrNull { it.first == id }
        return if (default != null && stored == default.second) text.get(defaultResource(id)) else stored
    }

    /** What to save from an editor: the name as it was stored if the field was left as shown, otherwise what was typed. */
    fun nameToSave(typed: String, shownAtStart: String, storedAtStart: String): String =
        if (typed.trim() == shownAtStart.trim()) storedAtStart else typed
}
