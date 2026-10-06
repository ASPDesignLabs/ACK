// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The GEO-PROTOCOL screen, its authorization dialog and the zone notification (`geo/GeoProtocolView.kt`, `PermissionModal.kt`, `GeoBroadcastReceiver.kt`) read their words from string resources, in the chosen
 * language. They use the SDK, Mapsforge and Google Play Services and cannot be compiled here (they are syntax-checked), so this reads them: the old English literals are gone, every string they name exists in every
 * language and none is unused, each word sits on the control that does what it says, what a zone saves is still an id, the two engine names are still names, the notification is worded in the chosen language while the
 * engine's own log lines stay English, and nothing that deletes or imports got easier. GeoTextTest holds the decisions.
 */
class GeoWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val view get() = noComments(RepoFiles.read("$base/geo/GeoProtocolView.kt"))
    private val modal get() = noComments(RepoFiles.read("$base/geo/PermissionModal.kt"))
    private val receiver get() = noComments(RepoFiles.read("$base/geo/GeoBroadcastReceiver.kt"))
    private val repository get() = noComments(RepoFiles.read("$base/geo/GeoRepository.kt"))
    private val controller get() = noComments(RepoFiles.read("$base/geo/GeoEngineController.kt"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringTheGeoScreensNameExists_inEveryLanguage_andNoneIsLeftUnused() {
        val sources = listOf(view, modal, receiver, noComments(RepoFiles.read("$base/core/GeoText.kt")))
        val referenced = sources.flatMap { Regex("""R\.string\.(geo_[a-z0-9_]+)""").findAll(it).map { m -> m.groupValues[1] }.toList() }.toSet() +
            // A name read through the text source (the notification's channel id "geo_protocol_alerts" is an id, not a string).
            sources.flatMap { Regex("""(?:words|text)\.get\("(geo_[a-z0-9_]+)"""").findAll(it).map { m -> m.groupValues[1] }.toList() }.toSet() +
            sources.flatMap { Regex("""if \(\w+\) "(geo_[a-z0-9_]+)" else "(geo_[a-z0-9_]+)"""").findAll(it).flatMap { m -> listOf(m.groupValues[1], m.groupValues[2]) }.toList() }.toSet() +
            Regex("""-> "(geo_[a-z0-9_]+)"""").findAll(sources.last()).map { it.groupValues[1] }.toSet()
        val defined = english.keys.filter { it.startsWith("geo_") }.toSet()
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = referenced.filter { it !in map }
            assertEquals("$tag: named but not defined: $missing", emptyList<String>(), missing)
        }
        assertEquals("defined but never used: ${defined - referenced}", emptySet<String>(), defined - referenced)
        // The shared strings these screens borrow exist too.
        for ((tag, map) in listOf("en" to english) + translations.toList()) for (name in listOf("common_cancel", "common_abort", "label_geo_grid", "label_geo_protocol", "label_deck")) assertTrue("$tag/$name", map.containsKey(name))
    }

    @Test
    fun theOldEnglishLiteralsAreGoneFromTheScreen() {
        val v = view
        for (literal in listOf(
            "NO MAP DATA IMPORTED", "[TRACKING", "\"[ABORT]\"", "\"TARGET: ", "\"PURGE\"", "LOCK COORDINATE", "\"SYSTEM: ", "\"MAP DATA\"", "IMPORTED -- ", "NONE -- TACTICAL GRID", "IMPORT FAILED",
            "IMPORT MAP FILE", "\"REMOVE\"", "A REGION MAP IS NOT REQUIRED", "REPLACE MAP DATA?", "IMPORT MAP DATA?", "REMOVE MAP DATA?", "This replaces the currently", "This copies the selected file",
            "Tactical Grid will fall back", "\"IMPORT\"", "\"CANCEL\"", "\"Unknown error\"", "\" [EDIT]\"", "\" [PURGE]\"", "\"RADIUS: ", "\"ENTER DECK:\"", "\"EXIT DECK:\"", "\"SYSTEM DEFAULT\"", "\"DO NOTHING\"",
            "\"REVERT TO PREVIOUS\"", "String.format", ".format(",
        )) assertFalse("GeoProtocolView still holds $literal", v.contains(literal))
        val m = modal
        for (literal in listOf("GEO-PROTOCOL // AUTHORIZATION", "To switch decks automatically", "PRIVACY NOTICE", "STEP 2:", "\"PROCEED\"", "\"ABORT\"")) assertFalse("PermissionModal still holds $literal", m.contains(literal))
        val r = receiver
        for (literal in listOf("\"GEO-NODE: ", "Switch layout to", "\"ENGAGE\"", "\"ABORT\"", "\"Geo-Protocol Alerts\"", "\"SYSTEM DEFAULT\"", "\"PREVIOUS DECK\"", "\"UNKNOWN\"")) {
            // "UNKNOWN" is still written once for the Terminal log line in handleEngage (English, like every log line); the other four are gone.
            if (literal == "\"UNKNOWN\"") assertEquals("only the log line keeps UNKNOWN", 1, Regex(Regex.escape(literal)).findAll(r).count())
            else assertFalse("GeoBroadcastReceiver still holds $literal", r.contains(literal))
        }
    }

    // ---- each word sits on the control that does what it says -------------------------------------------------------------------------------

    @Test
    fun theControlsDoWhatTheirWordsSay() {
        val v = view
        assertTrue(Regex("""R\.string\.geo_purge\), Modifier\.weight\(1f\), mainColor = Color\.Red\) \{\s*GeoRepository\.deleteZone\(context, editingZoneId!!\)""").containsMatchIn(v))
        assertTrue(Regex("""R\.string\.geo_lock_coordinate\)[\s\S]{0,700}?GeoRepository\.saveZone""").containsMatchIn(v))
        assertTrue(Regex("""GeoText\.systemSwitch\(words, isMasterEnabled\)[\s\S]{0,300}?GeoRepository\.setGeoEnabled\(context, !isMasterEnabled\)""").containsMatchIn(v))
        assertTrue(Regex("""ThemeOption\(index, mode\.name, if \(currentEngine == mode\) index else -1, primaryColor\) \{\s*GeoRepository\.setEngineMode\(context, mode\)""").containsMatchIn(v))
        assertTrue(Regex("""GeoText\.trackingSwitch\(words, isTracking\)[\s\S]{0,300}?isTracking = !isTracking""").containsMatchIn(v))
        assertTrue(Regex("""R\.string\.geo_abort_tag\)[\s\S]{0,300}?isMapFullscreen = false; editingZoneId = null""").containsMatchIn(v))
        assertTrue(Regex("""R\.string\.geo_import_map\)[\s\S]{0,700}?mapImportLauncher\.launch""").containsMatchIn(v))
        assertTrue(Regex("""R\.string\.geo_remove\), mainColor = Color\.Red\) \{\s*showMapRemoveConfirm = true""").containsMatchIn(v))
        assertTrue(Regex("""R\.string\.geo_edit_tag\)[\s\S]{0,300}?onEdit\(\)""").containsMatchIn(v))
        assertTrue(Regex("""R\.string\.geo_purge_tag\)[\s\S]{0,300}?onDelete\(\)""").containsMatchIn(v))
        assertTrue(Regex("""R\.string\.common_cancel\)[\s\S]{0,200}?onDismiss\(\)""").containsMatchIn(v))
        for (tag in listOf("GEO_MAP_IMPORT")) assertTrue(tag, v.contains("helpTarget(AckTags.$tag"))
        val m = modal
        assertTrue(Regex("""R\.string\.geo_proceed\)[\s\S]{0,900}?permissionLauncher\.launch""").containsMatchIn(m))
        assertTrue(Regex("""R\.string\.common_abort\), isActive = false, mainColor = primaryColor\) \{ onDismiss\(\) \}""").containsMatchIn(m))
    }

    @Test
    fun importingAndRemovingAMapStillAsksFirst_andOnlyTheAnswerActs() {
        val v = view
        assertEquals("one import call", 1, Regex("""GeoRepository\.importUserMapFile\(""").findAll(v).count())
        assertEquals("one remove call", 1, Regex("""GeoRepository\.clearUserMapFile\(""").findAll(v).count())
        assertTrue(Regex("""GeoText\.mapActionTitle\(words, GeoText\.importAction\(userMapFile != null\)\)[\s\S]{0,700}?onConfirm = \{\s*val result = GeoRepository\.importUserMapFile\(context, uri\)""").containsMatchIn(v))
        assertTrue(Regex("""GeoText\.mapActionTitle\(words, GeoText\.MapAction\.REMOVE\)[\s\S]{0,700}?onConfirm = \{\s*GeoRepository\.clearUserMapFile\(context\)""").containsMatchIn(v))
        assertTrue("the file picker only stages the file", Regex("""\{ uri ->\s*if \(uri != null\) \{\s*mapImportError = null\s*pendingMapImportUri = uri""").containsMatchIn(v))
        assertTrue("the failure reason is the file layer's own text, or the screen's translated fallback", v.contains("""result.exceptionOrNull()?.message ?: words.get("geo_unknown_error")"""))
        assertTrue("the dialog's two choices are CANCEL (first) and the action", Regex("""R\.string\.common_cancel\)[\s\S]{0,200}?onDismiss\(\)[\s\S]{0,200}?text = confirmLabel[\s\S]{0,100}?onConfirm\(\)""").containsMatchIn(v))
    }

    // ---- a zone saves ids, never words ------------------------------------------------------------------------------------------------------

    @Test
    fun aZoneStillSavesDeckIdsAndTheEnginesStillSaveTheirNames() {
        val v = view
        // The options are (id, label) pairs; choosing one saves the id.
        assertTrue(v.contains("onUpdate(zone.copy(enterDeckId = id))") && v.contains("onUpdate(zone.copy(exitDeckId = id))"))
        assertTrue(v.contains("GeoText.optionLabel(enterOptions, zone.enterDeckId)") && v.contains("GeoText.optionLabel(exitOptions, zone.exitDeckId)"))
        assertTrue("a new zone's saved default name is still the English NODE n", v.contains("\"NODE \${zones.size + 1}\""))
        assertTrue("a typed name is saved in capitals as it always was", v.contains("onUpdate(zone.copy(name = it.uppercase()))"))
        // The deck ids are the repository's own defaults and what the receiver compares.
        assertTrue(repository.contains("var enterDeckId: String = \"DEFAULT\"") && repository.contains("var exitDeckId: String = \"NONE\""))
        assertTrue(receiver.contains("targetDeckId == \"NONE\"") && receiver.contains("deckId == \"PREVIOUS\"") && receiver.contains("if (deckId == \"DEFAULT\")"))
        // The engine names: stored as the enum's name, drawn as it, and handed to the privacy notice as arguments.
        assertTrue(repository.contains("enum class GeoEngineMode {\n    SOVEREIGN,") && repository.contains("OPTIMIZED"))
        assertTrue(modal.contains("GeoText.privacyNotice(words, GeoEngineMode.SOVEREIGN.name, GeoEngineMode.OPTIMIZED.name)"))
        assertFalse("the chips are not a translated word", view.contains("stringResource(R.string.geo_sovereign"))
    }

    @Test
    fun coordinatesAreWrittenByTheDecisionWithLatinDigits() {
        assertTrue(view.contains("GeoText.target(words, crosshairLat, crosshairLng)"))
        assertFalse(view.contains("%.4f"))
        assertTrue(noComments(RepoFiles.read("$base/core/GeoText.kt")).contains("String.format(Locale.ROOT, \"%.4f\", value)"))
        assertTrue("the size is divided as a Float, as it always was", view.contains("GeoText.mapStatus(words, userMapFile?.let { it.length() / 1_048_576f }, labelFor(LabelKey.GEO_GRID))"))
    }

    // ---- the notification -------------------------------------------------------------------------------------------------------------------

    @Test
    fun theNotificationIsWordedInTheChosenLanguage_andTheEnginesLogLinesStayEnglish() {
        val r = receiver
        assertEquals("one wrap of the context", 1, Regex("""InterfaceLocale\.wrap\(context\)""").findAll(r).count())
        assertTrue(r.contains("val words = ResourceText(InterfaceLocale.wrap(context))"))
        assertTrue(r.contains("GeoText.notificationDeckName(words, targetDeckId, CommandRepository.getDecks(context).find { it.id == targetDeckId }?.name)"))
        assertTrue(r.contains("channelId, words.get(\"geo_notif_channel\"), NotificationManager.IMPORTANCE_HIGH"))
        assertTrue(r.contains(".setContentTitle(GeoText.notificationTitle(words, zone.name))") && r.contains(".setContentText(GeoText.notificationText(words, deckName))"))
        assertTrue(r.contains(".addAction(0, words.get(\"geo_notif_engage\"), engagePending)") && r.contains(".addAction(0, words.get(\"common_abort\"), abortPending)"))
        // What the notification's two buttons do is unchanged: ENGAGE sends the engage action, ABORT the abort action.
        assertTrue(Regex("""engagePending[\s\S]{0,60}?ACTION_GEO_ENGAGE|ACTION_GEO_ENGAGE[\s\S]{0,400}?engagePending""").containsMatchIn(r))
        assertTrue(Regex("""ACTION_GEO_ABORT[\s\S]{0,400}?abortPending""").containsMatchIn(r))
        // The lines the geo code writes into the Terminal are English text through ACK_LOG, like every line other parts of ACK write there.
        for (line in listOf("Awaiting User Ack.", "PROTOCOL ENGAGED: ", "PROTOCOL ABORTED: ", "\"Entering\"", "\"Exiting\"")) assertTrue("the log line $line is still English", r.contains(line))
        for (line in listOf("SOVEREIGN ENGINE: ONLINE", "OPTIMIZED ENGINE: ONLINE", "GEO ERR: No Location Providers Enabled")) assertTrue("the engine's log line $line is still English", controller.contains(line))
        assertFalse("the engine controller reads no string resources", controller.contains("R.string") || controller.contains("context.getString("))
    }

    @Test
    fun theNotificationVibratesAsBeforeAndNothingElseAboutItChanged() {
        val r = receiver
        assertTrue(r.contains(".setVibrate(longArrayOf(0, 250, 250, 250))"))
        assertTrue(r.contains("NotificationCompat.PRIORITY_HIGH") && r.contains("NotificationManager.IMPORTANCE_HIGH"))
        assertTrue(r.contains("val notifId = zone.id.hashCode()"))
    }

    @Test
    fun eachMapDialogIsWiredToItsOwnTitleBodyAndButton_andTheFailureShowsItsReason() {
        val v = view
        assertTrue(
            "import: its own title, body and IMPORT button, then the import",
            Regex(
                """title = GeoText\.mapActionTitle\(words, GeoText\.importAction\(userMapFile != null\)\),\s*""" +
                    """body = GeoText\.mapActionBody\(words, GeoText\.importAction\(userMapFile != null\)\),\s*""" +
                    """confirmLabel = stringResource\(R\.string\.geo_import\),\s*""" +
                    """onDismiss = \{ pendingMapImportUri = null \},\s*onConfirm = \{\s*val result = GeoRepository\.importUserMapFile"""
            ).containsMatchIn(v)
        )
        assertTrue(
            "remove: its own title, body and REMOVE button, then the removal",
            Regex(
                """title = GeoText\.mapActionTitle\(words, GeoText\.MapAction\.REMOVE\),\s*""" +
                    """body = GeoText\.mapActionBody\(words, GeoText\.MapAction\.REMOVE\),\s*""" +
                    """confirmLabel = stringResource\(R\.string\.geo_remove\),\s*""" +
                    """onDismiss = \{ showMapRemoveConfirm = false \},\s*onConfirm = \{\s*GeoRepository\.clearUserMapFile"""
            ).containsMatchIn(v)
        )
        assertTrue(
            "the reason an import failed is drawn under the status, only when there is one",
            Regex("""if \(mapImportError != null\) \{[\s\S]{0,200}?Text\(GeoText\.importFailed\(words, mapImportError\), color = Color\.Red""").containsMatchIn(v)
        )
    }

    @Test
    fun eachZoneCardColumnShowsItsOwnLabelAndItsOwnChoices_andTheRadiusIsTheZonesRadius() {
        val v = view
        assertTrue("one enter list and one exit list, each from its own function",
            v.contains("val enterOptions = GeoText.enterOptions(words, availableDecks.map { it.id to it.name })") &&
                v.contains("val exitOptions = GeoText.exitOptions(words, availableDecks.map { it.id to it.name })"))
        assertTrue(
            "ENTER column: its heading, then the word for the saved enter id, and a menu of the enter choices that saves the enter id",
            Regex(
                """enterExpanded = true \}\) \{ Text\(GeoText\.enterDeckLabel\(words, labelFor\(LabelKey\.DECK\)\)[^;]*;\s*Text\(enterLabel,""" +
                    """[\s\S]{0,400}?DropdownMenu\(expanded = enterExpanded[\s\S]{0,200}?enterOptions\.forEach[\s\S]{0,300}?onUpdate\(zone\.copy\(enterDeckId = id\)\)"""
            ).containsMatchIn(v)
        )
        assertTrue(
            "EXIT column: its heading, then the word for the saved exit id, and a menu of the exit choices that saves the exit id",
            Regex(
                """exitExpanded = true \}\) \{ Text\(GeoText\.exitDeckLabel\(words, labelFor\(LabelKey\.DECK\)\)[^;]*;\s*Text\(exitLabel,""" +
                    """[\s\S]{0,400}?DropdownMenu\(expanded = exitExpanded[\s\S]{0,200}?exitOptions\.forEach[\s\S]{0,300}?onUpdate\(zone\.copy\(exitDeckId = id\)\)"""
            ).containsMatchIn(v)
        )
        assertTrue("the card shows the zone's own radius, as the slider sets it", v.contains("Text(GeoText.radius(words, zone.radiusMeters.toInt()), "))
        assertTrue("the engine chips are in the enum's order", v.contains("GeoEngineMode.entries.forEachIndexed { index, mode ->"))
        assertFalse("nothing reverses or re-sorts the chips", v.contains("GeoEngineMode.entries.reversed") || v.contains("GeoEngineMode.entries.sorted"))
    }

    @Test
    fun theLogLineSaysEnteringWhenEnteringAndExitingWhenExiting() {
        val r = receiver
        assertTrue(r.contains("val actionText = if (isEntering) \"Entering\" else \"Exiting\""))
        assertTrue(r.contains("broadcastLog(context, \"\$actionText \${zone.name}. Awaiting User Ack.\", \"GEO\")"))
        assertTrue("the deck a transition names is the one for entering or for exiting", r.contains("val targetDeckId = if (isEntering) zone.enterDeckId else zone.exitDeckId"))
    }
}
