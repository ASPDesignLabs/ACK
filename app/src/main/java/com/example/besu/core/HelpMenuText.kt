// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words HELP's own screens show that are decided rather than just drawn: a module family's three names, and each card's "N STEPS // VIEW" line. Plain Kotlin, read through a
 * [TextSource], tested in every language.
 *
 * Only HELP's chrome is here. A walkthrough's own title, summary, step titles and step text are still English (the per-feature files in help/), and a family's name may hold a label
 * placeholder (written with double braces) that `helpText()` fills in for PLAIN WORDS, so these functions return the raw resource text and the screen passes it through `helpText()`.
 */
object HelpMenuText {
    /** The module family's full name, "SECTION // SUBSECTION" in the house style. [categoryName] is the `HelpCategory` constant's name (BASICS_NAVIGATION). */
    fun categoryTitle(text: TextSource, categoryName: String): String = text.get(categoryKey(categoryName, "title"))

    /** The short name on the family's chip: the part after the section, or the whole name when it has no section. Its own string, so a translation never has to keep a separator. */
    fun categoryChip(text: TextSource, categoryName: String): String = text.get(categoryKey(categoryName, "chip"))

    fun categorySubtitle(text: TextSource, categoryName: String): String = text.get(categoryKey(categoryName, "subtitle"))

    /** The resource name for one of a family's three texts. Public so a test can hold every family to it. */
    fun categoryKey(categoryName: String, part: String): String = "help_cat_${categoryName.lowercase()}_$part"

    /**
     * Each screen a walkthrough can send the person to (`HelpDestination.viewMode`, which is logic and never changes) and the words that name it on a card. A mode that is not here
     * reads as itself rather than as something wrong; HelpMenuTextTest fails if a destination is missing.
     */
    val viewNameResources: Map<String, String> = mapOf(
        "MATRIX" to "help_view_matrix",
        "TERMINAL" to "help_view_terminal",
        "SETTINGS" to "help_view_settings",
        "TYPE" to "help_view_type",
        "AUDIO" to "help_view_audio",
        "TARGETS" to "help_view_targets",
        "GEO" to "help_view_geo",
    )

    /** Where a walkthrough starts: the screen it goes to, or "CURRENT VIEW" when it stays wherever the person is. */
    fun viewName(text: TextSource, viewMode: String?): String {
        if (viewMode == null) return text.get("help_menu_current_view")
        val resource = viewNameResources[viewMode] ?: return viewMode
        return text.get(resource)
    }

    /** "3 STEPS // MATRIX": the count in the word form that fits it (1 STEP), then where it starts. */
    fun stepsLine(text: TextSource, stepCount: Int, viewMode: String?): String =
        text.get("help_menu_steps_line", text.count("help_menu_steps", stepCount), viewName(text, viewMode))
}
