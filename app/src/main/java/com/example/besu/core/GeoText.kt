// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale

/**
 * What the GEO-PROTOCOL screen, its authorization dialog and the notification a zone sends say that is decided, not just drawn. Plain Kotlin (no `android.*`) so it is tested without a phone; the words are string
 * resources (`geo_*`, in the chosen language) read through a [TextSource]. The Android edge is thin: the screen asks `rememberText()`, the notification receiver wraps its context in the chosen language first.
 *
 * **Stored values are logic and are never translated.** A zone's enter and exit deck are saved as a deck id or one of the three words [DEFAULT], [NONE] and [PREVIOUS]; the zone's own name is typed (and saved as
 * "NODE 3" when nothing was typed). Only the word *drawn* for them follows the language: [optionLabel] finds the word for an id in the options the screen offers and shows an id it does not know as it is
 * (a deleted deck's id, as it always was). A deck's own name is shown as the person saved it.
 *
 * **Names that are not words stay as they are**: the two engine names SOVEREIGN and OPTIMIZED are handed to the privacy notice as arguments (the developer's decision, like CYBER and MECH), so the chips and the
 * sentence agree in every language. Coordinates and sizes are written with Latin digits (`Locale.ROOT`) whatever the phone's number format; the Arabic coordinate line has a left-to-right mark before each number
 * because a longitude is usually negative.
 *
 * The engine's own lines in the Terminal log ("SOVEREIGN ENGINE: ONLINE", "Entering NODE 1. Awaiting User Ack.") are written by the geo engine in English and stay English like every line other parts of ACK write
 * into the Terminal.
 */
object GeoText {
    /** A zone's deck id for "the system default deck" (also the always-present deck's own id). */
    const val DEFAULT = "DEFAULT"
    /** An exit deck id for "do nothing". */
    const val NONE = "NONE"
    /** An exit deck id for "go back to the deck that was active before the zone was entered". */
    const val PREVIOUS = "PREVIOUS"

    // ---- the screen -----------------------------------------------------------------------------------------------------------------------

    fun systemSwitch(text: TextSource, on: Boolean): String = text.get(if (on) "geo_system_on" else "geo_system_off")

    fun trackingSwitch(text: TextSource, on: Boolean): String = text.get(if (on) "geo_tracking_on" else "geo_tracking_off")

    /** A coordinate to four decimals, with Latin digits and a point. */
    fun coordinate(value: Double): String = String.format(Locale.ROOT, "%.4f", value)

    /** "TARGET: 40.7128, -74.0060". */
    fun target(text: TextSource, lat: Double, lng: Double): String = text.get("geo_target", coordinate(lat), coordinate(lng))

    /** "RADIUS: 100m". */
    fun radius(text: TextSource, meters: Int): String = text.get("geo_radius", meters)

    /**
     * What MAP DATA says: the size of the imported file in megabytes (one decimal, as the screen always wrote it), or that there is none. [gridLabel] is the name of the grid screen (it follows PLAIN WORDS).
     * [megabytes] is a `Float` because the screen divides the file's length as a `Float`; the rounding stays what it was.
     */
    fun mapStatus(text: TextSource, megabytes: Float?, gridLabel: String): String =
        if (megabytes != null) text.get("geo_map_imported", String.format(Locale.ROOT, "%.1f", megabytes)) else text.get("geo_map_none", gridLabel)

    /** "IMPORT FAILED: <why>": the reason as the file layer worded it, or the screen's own words when there was none. */
    fun importFailed(text: TextSource, detail: String?): String = text.get("geo_import_failed", detail ?: text.get("geo_unknown_error"))

    /** "ENTER DECK:" with the deck word the person's mode uses (DECK, or PAGE under PLAIN WORDS). */
    fun enterDeckLabel(text: TextSource, deckWord: String): String = text.get("geo_enter_deck", deckWord)

    fun exitDeckLabel(text: TextSource, deckWord: String): String = text.get("geo_exit_deck", deckWord)

    /** The enter deck choices: the system default first (its stored id is [DEFAULT]), then each deck as (id, saved name). */
    fun enterOptions(text: TextSource, decks: List<Pair<String, String>>): List<Pair<String, String>> =
        listOf(DEFAULT to text.get("geo_opt_system_default")) + decks

    /** The exit deck choices: do nothing ([NONE]), go back ([PREVIOUS]), the system default ([DEFAULT]), then each deck as (id, saved name). */
    fun exitOptions(text: TextSource, decks: List<Pair<String, String>>): List<Pair<String, String>> =
        listOf(NONE to text.get("geo_opt_nothing"), PREVIOUS to text.get("geo_opt_previous"), DEFAULT to text.get("geo_opt_system_default")) + decks

    /** The word for [id] among [options], or the id itself when it is not there (a deck that no longer exists). The first match wins, as it always did. */
    fun optionLabel(options: List<Pair<String, String>>, id: String): String = options.find { it.first == id }?.second ?: id

    /** The three things the two map dialogs can ask about. */
    enum class MapAction { REPLACE, IMPORT, REMOVE }

    fun mapActionTitle(text: TextSource, action: MapAction): String = text.get(
        when (action) {
            MapAction.REPLACE -> "geo_replace_title"
            MapAction.IMPORT -> "geo_import_title"
            MapAction.REMOVE -> "geo_remove_title"
        }
    )

    fun mapActionBody(text: TextSource, action: MapAction): String = text.get(
        when (action) {
            MapAction.REPLACE -> "geo_replace_body"
            MapAction.IMPORT -> "geo_import_body"
            MapAction.REMOVE -> "geo_remove_body"
        }
    )

    /** What importing asks: replace the map that is there, or import the first one. */
    fun importAction(hasMap: Boolean): MapAction = if (hasMap) MapAction.REPLACE else MapAction.IMPORT

    // ---- the authorization dialog ----------------------------------------------------------------------------------------------------

    /** "GEO-PROTOCOL // AUTHORIZATION" with the screen's own label (it follows PLAIN WORDS). */
    fun authTitle(text: TextSource, protocolLabel: String): String = text.get("geo_auth_title", protocolLabel)

    /** The privacy notice; the two engine names go in as they are saved and shown on the chips. */
    fun privacyNotice(text: TextSource, sovereign: String, optimized: String): String = text.get("geo_privacy", sovereign, optimized)

    // ---- the notification a zone sends -----------------------------------------------------------------------------------------------

    /** The deck named in the notification: the system default, the previous deck, the deck's own saved name, or UNKNOWN when it no longer exists. */
    fun notificationDeckName(text: TextSource, targetDeckId: String, deckName: String?): String = when (targetDeckId) {
        DEFAULT -> text.get("geo_opt_system_default")
        PREVIOUS -> text.get("geo_notif_previous")
        else -> deckName ?: text.get("geo_notif_unknown")
    }

    /** "GEO-NODE: HOME": the zone's name as saved. */
    fun notificationTitle(text: TextSource, zoneName: String): String = text.get("geo_notif_title", zoneName)

    /** "Switch layout to [DECK]?". */
    fun notificationText(text: TextSource, deckName: String): String = text.get("geo_notif_text", deckName)
}
