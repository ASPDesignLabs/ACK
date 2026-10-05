// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the GEO-PROTOCOL screen, its authorization dialog and the zone notification say that is decided: in English exactly as it always was, and in every language. A zone's deck is saved as an id (DEFAULT, NONE,
 * PREVIOUS or a deck's own id) and only the word drawn for it follows the language; a zone's name and a deck's name are shown as the person saved them; the two engine names are names and are handed to the privacy
 * notice as arguments; coordinates and sizes keep Latin digits.
 */
class GeoTextTest {

    private val t = EnglishText
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val english get() = StringsXml.map(StringsXml.default)
    private val languages: List<Pair<String, TextSource>> get() = translations.keys.map { it to FileText(it) as TextSource }
    private val everyone: List<Pair<String, TextSource>> get() = listOf("en" to t as TextSource) + languages
    private fun count(text: String, part: String) = Regex(Regex.escape(part)).findAll(text).count()
    private val awkward = "100% %s %d \$1 \"q\"\nline"
    private val lrm = "‎"
    private val decks = listOf("DEFAULT" to "DEFAULT", "d-1" to "Work", "d-2" to "100% %s")

    // ---- English is exactly what the screen always said ------------------------------------------------------------------------------------

    @Test
    fun theScreenEnglishIsExactlyWhatItAlwaysSaid() {
        assertEquals("SYSTEM: ON", GeoText.systemSwitch(t, true))
        assertEquals("SYSTEM: OFF", GeoText.systemSwitch(t, false))
        assertEquals("[TRACKING: ON]", GeoText.trackingSwitch(t, true))
        assertEquals("[TRACKING: OFF]", GeoText.trackingSwitch(t, false))
        assertEquals("TARGET: 40.7128, -74.0060", GeoText.target(t, 40.7128, -74.006))
        assertEquals("TARGET: 0.0000, 0.0000", GeoText.target(t, 0.0, 0.0))
        assertEquals("TARGET: 1.2346, -2.0000", GeoText.target(t, 1.23456, -2.0))
        assertEquals("RADIUS: 100m", GeoText.radius(t, 100))
        assertEquals("RADIUS: 800m", GeoText.radius(t, 800))
        assertEquals("IMPORTED -- 3.5 MB", GeoText.mapStatus(t, 3.456f, "TACTICAL GRID"))
        assertEquals("IMPORTED -- 0.0 MB", GeoText.mapStatus(t, 0.04f, "TACTICAL GRID"))
        assertEquals("NONE -- TACTICAL GRID RENDERS COORDINATES ONLY", GeoText.mapStatus(t, null, "TACTICAL GRID"))
        assertEquals("under PLAIN WORDS the screen is called MAP", "NONE -- MAP RENDERS COORDINATES ONLY", GeoText.mapStatus(t, null, "MAP"))
        assertEquals("IMPORT FAILED: Unknown error", GeoText.importFailed(t, null))
        assertEquals("IMPORT FAILED: Cannot open selected file", GeoText.importFailed(t, "Cannot open selected file"))
        assertEquals("ENTER DECK:", GeoText.enterDeckLabel(t, "DECK"))
        assertEquals("EXIT DECK:", GeoText.exitDeckLabel(t, "DECK"))
        assertEquals("ENTER PAGE:", GeoText.enterDeckLabel(t, "PAGE"))
        assertEquals("EXIT PAGE:", GeoText.exitDeckLabel(t, "PAGE"))
    }

    @Test
    fun theDialogsEnglishIsExactlyWhatTheyAlwaysSaid() {
        assertEquals("REPLACE MAP DATA?", GeoText.mapActionTitle(t, GeoText.MapAction.REPLACE))
        assertEquals("IMPORT MAP DATA?", GeoText.mapActionTitle(t, GeoText.MapAction.IMPORT))
        assertEquals("REMOVE MAP DATA?", GeoText.mapActionTitle(t, GeoText.MapAction.REMOVE))
        assertEquals(
            "This replaces the currently imported map file. The old file cannot be recovered unless you still have the original on your device to import again.",
            GeoText.mapActionBody(t, GeoText.MapAction.REPLACE),
        )
        assertEquals(
            "This copies the selected file into ACK's private storage. It stays on this device only and is never bundled into or read from any backup you export.",
            GeoText.mapActionBody(t, GeoText.MapAction.IMPORT),
        )
        assertEquals("Tactical Grid will fall back to coordinates only until a new map file is imported.", GeoText.mapActionBody(t, GeoText.MapAction.REMOVE))
        assertEquals("a map that is there is replaced, the first one is imported", GeoText.MapAction.REPLACE, GeoText.importAction(true))
        assertEquals(GeoText.MapAction.IMPORT, GeoText.importAction(false))
        assertEquals("GEO-PROTOCOL // AUTHORIZATION", GeoText.authTitle(t, "GEO-PROTOCOL"))
        assertEquals("LOCATION ALERTS // AUTHORIZATION", GeoText.authTitle(t, "LOCATION ALERTS"))
        assertEquals(
            "PRIVACY NOTICE: Your coordinates are kept strictly on-device only when using the SOVEREIGN model as processing is handled on device. Using the OPTIMIZED model enables Google Play Services support. " +
                "Your location information will be transmitted to Google services if you use this method.",
            GeoText.privacyNotice(t, "SOVEREIGN", "OPTIMIZED"),
        )
        assertEquals("To switch decks automatically, ACK requires 'Always On' location access to detect boundaries while in your pocket.", english.getValue("geo_auth_body"))
        assertEquals("STEP 2: Please select 'Allow all the time' in the following Android settings screen.", english.getValue("geo_auth_step2"))
    }

    @Test
    fun theNotificationEnglishIsExactlyWhatItAlwaysSaid() {
        assertEquals("SYSTEM DEFAULT", GeoText.notificationDeckName(t, "DEFAULT", "DEFAULT"))
        assertEquals("PREVIOUS DECK", GeoText.notificationDeckName(t, "PREVIOUS", null))
        assertEquals("Work", GeoText.notificationDeckName(t, "d-1", "Work"))
        assertEquals("a deck that no longer exists", "UNKNOWN", GeoText.notificationDeckName(t, "d-gone", null))
        assertEquals("GEO-NODE: HOME", GeoText.notificationTitle(t, "HOME"))
        assertEquals("Switch layout to [Work]?", GeoText.notificationText(t, "Work"))
        assertEquals("Geo-Protocol Alerts", english.getValue("geo_notif_channel"))
        assertEquals("ENGAGE", english.getValue("geo_notif_engage"))
        assertEquals("ABORT", english.getValue("common_abort"))
    }

    @Test
    fun theSimpleWordsAreHeldExactly() {
        val expected = mapOf(
            "geo_no_map_overlay" to "NO MAP DATA IMPORTED -- COORDINATES ONLY", "geo_abort_tag" to "[ABORT]", "geo_purge" to "PURGE", "geo_purge_tag" to "[PURGE]", "geo_edit_tag" to "[EDIT]",
            "geo_lock_coordinate" to "LOCK COORDINATE", "geo_map_data" to "MAP DATA", "geo_import_map" to "IMPORT MAP FILE", "geo_remove" to "REMOVE", "geo_import" to "IMPORT", "geo_proceed" to "PROCEED",
            "geo_map_hint" to "A REGION MAP IS NOT REQUIRED -- ZONES STILL WORK BY COORDINATE. IMPORT A MAPSFORGE-COMPATIBLE .MAP FILE FOR VISUALS.", "geo_opt_system_default" to "SYSTEM DEFAULT",
            "geo_opt_nothing" to "DO NOTHING", "geo_opt_previous" to "REVERT TO PREVIOUS",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
    }

    // ---- what a zone saves is never what is drawn ----------------------------------------------------------------------------------------

    @Test
    fun theStoredDeckIdsAreTheOnesTheRepositoryHasAlwaysSaved() {
        assertEquals("DEFAULT", GeoText.DEFAULT)
        assertEquals("NONE", GeoText.NONE)
        assertEquals("PREVIOUS", GeoText.PREVIOUS)
        for ((tag, f) in everyone) {
            assertEquals("$tag: enter ids", listOf("DEFAULT", "DEFAULT", "d-1", "d-2"), GeoText.enterOptions(f, decks).map { it.first })
            assertEquals("$tag: exit ids", listOf("NONE", "PREVIOUS", "DEFAULT", "DEFAULT", "d-1", "d-2"), GeoText.exitOptions(f, decks).map { it.first })
            // A deck is chosen by its id and shown by its saved name, exactly as typed.
            assertEquals("$tag: deck names as saved", listOf("DEFAULT", "Work", "100% %s"), GeoText.enterOptions(f, decks).drop(1).map { it.second })
            assertEquals("$tag", "100% %s", GeoText.optionLabel(GeoText.exitOptions(f, decks), "d-2"))
            assertEquals("$tag: a deck that was deleted is shown by its id, as it always was", "d-gone", GeoText.optionLabel(GeoText.enterOptions(f, decks), "d-gone"))
        }
    }

    @Test
    fun theFirstOptionWinsAndTheAlwaysPresentDeckKeepsItsId_inEveryLanguage() {
        for ((tag, f) in everyone) {
            val enter = GeoText.enterOptions(f, decks)
            assertEquals("$tag: DEFAULT is the system default's word, not the deck called DEFAULT", f.get("geo_opt_system_default"), GeoText.optionLabel(enter, "DEFAULT"))
            val exit = GeoText.exitOptions(f, decks)
            assertEquals("$tag: NONE", f.get("geo_opt_nothing"), GeoText.optionLabel(exit, "NONE"))
            assertEquals("$tag: PREVIOUS", f.get("geo_opt_previous"), GeoText.optionLabel(exit, "PREVIOUS"))
            assertEquals("$tag: three exit words are three different words", 3, setOf(f.get("geo_opt_nothing"), f.get("geo_opt_previous"), f.get("geo_opt_system_default")).size)
        }
    }

    // ---- every language ---------------------------------------------------------------------------------------------------------------

    @Test
    fun everyDecisionReadsInTheLanguage_andNeverTheEnglish() {
        for ((tag, f) in languages) {
            val pairs = mapOf(
                "systemOn" to (GeoText.systemSwitch(f, true) to GeoText.systemSwitch(t, true)),
                "systemOff" to (GeoText.systemSwitch(f, false) to GeoText.systemSwitch(t, false)),
                "trackingOn" to (GeoText.trackingSwitch(f, true) to GeoText.trackingSwitch(t, true)),
                "trackingOff" to (GeoText.trackingSwitch(f, false) to GeoText.trackingSwitch(t, false)),
                "target" to (GeoText.target(f, 1.0, 2.0) to GeoText.target(t, 1.0, 2.0)),
                "radius" to (GeoText.radius(f, 100) to GeoText.radius(t, 100)),
                "mapImported" to (GeoText.mapStatus(f, 3.5f, "GGG") to GeoText.mapStatus(t, 3.5f, "GGG")),
                "mapNone" to (GeoText.mapStatus(f, null, "GGG") to GeoText.mapStatus(t, null, "GGG")),
                "importFailed" to (GeoText.importFailed(f, "x") to GeoText.importFailed(t, "x")),
                "unknownError" to (GeoText.importFailed(f, null) to GeoText.importFailed(t, null)),
                "enter" to (GeoText.enterDeckLabel(f, "DDD") to GeoText.enterDeckLabel(t, "DDD")),
                "exit" to (GeoText.exitDeckLabel(f, "DDD") to GeoText.exitDeckLabel(t, "DDD")),
                "replaceTitle" to (GeoText.mapActionTitle(f, GeoText.MapAction.REPLACE) to GeoText.mapActionTitle(t, GeoText.MapAction.REPLACE)),
                "importTitle" to (GeoText.mapActionTitle(f, GeoText.MapAction.IMPORT) to GeoText.mapActionTitle(t, GeoText.MapAction.IMPORT)),
                "removeTitle" to (GeoText.mapActionTitle(f, GeoText.MapAction.REMOVE) to GeoText.mapActionTitle(t, GeoText.MapAction.REMOVE)),
                "replaceBody" to (GeoText.mapActionBody(f, GeoText.MapAction.REPLACE) to GeoText.mapActionBody(t, GeoText.MapAction.REPLACE)),
                "importBody" to (GeoText.mapActionBody(f, GeoText.MapAction.IMPORT) to GeoText.mapActionBody(t, GeoText.MapAction.IMPORT)),
                "removeBody" to (GeoText.mapActionBody(f, GeoText.MapAction.REMOVE) to GeoText.mapActionBody(t, GeoText.MapAction.REMOVE)),
                "authTitle" to (GeoText.authTitle(f, "PPP") to GeoText.authTitle(t, "PPP")),
                "privacy" to (GeoText.privacyNotice(f, "AAA", "BBB") to GeoText.privacyNotice(t, "AAA", "BBB")),
                "previous" to (GeoText.notificationDeckName(f, "PREVIOUS", null) to GeoText.notificationDeckName(t, "PREVIOUS", null)),
                "system" to (GeoText.notificationDeckName(f, "DEFAULT", null) to GeoText.notificationDeckName(t, "DEFAULT", null)),
                "unknownDeck" to (GeoText.notificationDeckName(f, "gone", null) to GeoText.notificationDeckName(t, "gone", null)),
                "notifTitle" to (GeoText.notificationTitle(f, "ZZZ") to GeoText.notificationTitle(t, "ZZZ")),
                "notifText" to (GeoText.notificationText(f, "ZZZ") to GeoText.notificationText(t, "ZZZ")),
            )
            // RADIUS is how Afrikaans writes it too, so that one line is the same as the English there (allowed by name in TranslationsTest).
            for ((what, both) in pairs) if ("$tag/$what" != "af/radius") assertNotEquals("$tag/$what is still English: ${both.first}", both.second, both.first)
            for (name in listOf("geo_no_map_overlay", "geo_abort_tag", "geo_purge", "geo_purge_tag", "geo_edit_tag", "geo_lock_coordinate", "geo_map_data", "geo_import_map", "geo_remove", "geo_import", "geo_proceed",
                "geo_map_hint", "geo_auth_body", "geo_auth_step2", "geo_notif_channel", "geo_notif_engage")) assertNotEquals("$tag/$name is still English", english.getValue(name), translations.getValue(tag).getValue(name))
        }
    }

    @Test
    fun aValueThePersonOrTheFileLayerGaveIsShownExactlyAsItCame_neverUsedAsAFormat_inEveryLanguage() {
        for ((tag, f) in everyone) {
            val v = awkward
            assertEquals("$tag: zone name in the title", 1, count(GeoText.notificationTitle(f, v), v))
            assertEquals("$tag: deck name in the question", 1, count(GeoText.notificationText(f, v), v))
            assertEquals("$tag: why an import failed", 1, count(GeoText.importFailed(f, v), v))
            assertEquals("$tag: the grid's label", 1, count(GeoText.mapStatus(f, null, v), v))
            assertEquals("$tag: the deck word, enter", 1, count(GeoText.enterDeckLabel(f, v), v))
            assertEquals("$tag: the deck word, exit", 1, count(GeoText.exitDeckLabel(f, v), v))
            assertEquals("$tag: the screen's label in the title", 1, count(GeoText.authTitle(f, v), v))
            assertEquals("$tag: a deck's saved name is the notification's deck", v, GeoText.notificationDeckName(f, "d-1", v))
        }
    }

    @Test
    fun theTwoEngineNamesAreNamesHandedInAsArguments_inEveryLanguage() {
        for ((tag, f) in everyone) {
            val text = GeoText.privacyNotice(f, "AAA", "BBB")
            assertEquals("$tag: the first engine's name once in '$text'", 1, count(text, "AAA"))
            assertEquals("$tag: the second engine's name once", 1, count(text, "BBB"))
            assertFalse("$tag: a translation does not retype SOVEREIGN", text.contains("SOVEREIGN"))
            assertFalse("$tag: a translation does not retype OPTIMIZED", text.contains("OPTIMIZED"))
            assertTrue("$tag: it still says where the location may go", text.contains("Google") || text.contains("GOOGLE"))
        }
    }

    @Test
    fun theCoordinatesKeepLatinDigitsAndANegativeNumberHasALeftToRightMarkInArabicAndNowhereElse() {
        for ((tag, f) in everyone) {
            val text = GeoText.target(f, 40.7128, -74.006)
            assertEquals("$tag: latitude once", 1, count(text, "40.7128"))
            assertEquals("$tag: longitude once", 1, count(text, "-74.0060"))
            assertTrue("$tag: latitude first: $text", text.indexOf("40.7128") < text.indexOf("-74.0060"))
            val marks = count(text, lrm)
            if (tag == "ar") {
                assertEquals("$tag: a mark before each number: $text", 2, marks)
                assertTrue(text.contains(lrm + "40.7128") && text.contains(lrm + "-74.0060"))
            } else assertEquals("$tag: no mark", 0, marks)
        }
        // Nothing else in the Geo-Protocol strings has a mark in any language: only this line holds a signed number.
        for ((tag, map) in translations) {
            val withMark = map.filter { it.key.startsWith("geo_") && it.value.contains(lrm) }.keys
            assertEquals("$tag", if (tag == "ar") setOf("geo_target") else emptySet<String>(), withMark)
        }
        assertEquals("sizes use a point whatever the phone's number format", "IMPORTED -- 1.5 MB", GeoText.mapStatus(t, 1.5f, "G"))
    }

    @Test
    fun aSpanishPortugueseOrAfrikaansWordIsInCapitals_evenWhereTheEnglishSentenceIsMixedCase() {
        for (tag in listOf("es", "pt", "af")) for ((name, text) in translations.getValue(tag).filter { it.key.startsWith("geo_") }) {
            val withoutArguments = text.replace("%1\$dm", "").replace(Regex("%\\d\\$[sd]"), "")
            assertEquals("$tag/$name: $text", withoutArguments.uppercase(), withoutArguments)
        }
    }

    @Test
    fun theBracketedWordsKeepTheirBrackets_inEveryLanguage() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) for (name in listOf("geo_tracking_on", "geo_tracking_off", "geo_abort_tag", "geo_purge_tag", "geo_edit_tag")) {
            val text = map.getValue(name)
            assertTrue("$tag/$name: '$text'", text.startsWith("[") && text.endsWith("]") && text.length > 2)
        }
        for ((tag, f) in everyone) assertNotEquals("$tag: on and off differ", GeoText.trackingSwitch(f, true), GeoText.trackingSwitch(f, false))
        for ((tag, f) in everyone) assertNotEquals("$tag: system on and off differ", GeoText.systemSwitch(f, true), GeoText.systemSwitch(f, false))
    }

    @Test
    fun theTwoAndroidQuotedOptionsAreQuoted_inEveryLanguage() {
        // 'Always On' and 'Allow all the time' name options in the phone's own settings; each translation quotes them with straight single quotes, so the person can find the words.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertEquals("$tag/geo_auth_body", 2, count(map.getValue("geo_auth_body"), "'"))
            assertEquals("$tag/geo_auth_step2", 2, count(map.getValue("geo_auth_step2"), "'"))
        }
    }

    @Test
    fun theMapHintStillNamesTheFileKindAndTheFormat_inEveryLanguage() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val hint = map.getValue("geo_map_hint")
            assertTrue("$tag: Mapsforge is a name: $hint", hint.contains("MAPSFORGE", ignoreCase = true))
            assertTrue("$tag: the .MAP kind is named: $hint", hint.contains("MAP"))
        }
    }

    @Test
    fun theNotificationTitleAndQuestionKeepTheirZoneAndBrackets_inEveryLanguage() {
        for ((tag, f) in everyone) {
            assertTrue("$tag: the deck is in square brackets: ${GeoText.notificationText(f, "ZZZ")}", GeoText.notificationText(f, "ZZZ").contains("[ZZZ]"))
            assertTrue("$tag: GEO-NODE title ends with the zone: ${GeoText.notificationTitle(f, "ZZZ")}", GeoText.notificationTitle(f, "ZZZ").endsWith("ZZZ"))
        }
    }

    @Test
    fun pairsThatMustDifferDoDifferInEveryLanguage_enterFromExit_andTheThreeMapQuestionsFromEachOther() {
        for ((tag, f) in everyone) {
            assertNotEquals("$tag: enter and exit", GeoText.enterDeckLabel(f, "DDD"), GeoText.exitDeckLabel(f, "DDD"))
            val titles = GeoText.MapAction.values().map { GeoText.mapActionTitle(f, it) }
            val bodies = GeoText.MapAction.values().map { GeoText.mapActionBody(f, it) }
            assertEquals("$tag: three titles, three questions", 3, titles.toSet().size)
            assertEquals("$tag: three bodies", 3, bodies.toSet().size)
            val deckWords = setOf(
                GeoText.notificationDeckName(f, GeoText.DEFAULT, null),
                GeoText.notificationDeckName(f, GeoText.PREVIOUS, null),
                GeoText.notificationDeckName(f, "gone_deck", null),
            )
            assertEquals("$tag: the system default, the previous deck and a deleted deck read differently", 3, deckWords.size)
            assertEquals("$tag: a deck's own saved name is shown as saved", "My Deck", GeoText.notificationDeckName(f, "deck_1", "My Deck"))
        }
    }
}
