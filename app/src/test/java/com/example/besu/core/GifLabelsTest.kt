// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the GIF deck says that is decided, in English exactly as it always was and in every language: the category's shown name (a saved name is never rewritten), the CATEGORY line,
 * the ON / OFF overlay button, the toasts after an import or an export (with the language's plural form) and the reason an import failed (carried by id, never by a sentence).
 */
class GifLabelsTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    // ---- English is exactly what it always said -------------------------------------------------------------------------------------

    @Test
    fun theEnglishWordsAreExactlyWhatTheDeckAlwaysSaid() {
        assertEquals("CATEGORY: REACTIONS", GifLabels.categoryLine(t, "REACTIONS"))
        assertEquals("CATEGORY: NO GIFS", GifLabels.categoryLine(t, null))
        assertEquals("CATEGORY: UNCATEGORIZED", GifLabels.categoryLine(t, "UNCATEGORIZED"))
        assertEquals("OVERLAY: LANDSCAPE [ON]", GifLabels.landscapeButton(t, true))
        assertEquals("OVERLAY: LANDSCAPE [OFF]", GifLabels.landscapeButton(t, false))
        assertEquals("GIF DECK EXPORTED", GifLabels.exportToast(t, true, "GIF", "DECK"))
        assertEquals("EXPORT FAILED", GifLabels.exportToast(t, false, "GIF", "DECK"))
        assertEquals("IMPORT FAILED -- INTEGRITY CHECK", english.getValue("gif_import_failed_check"))
        assertEquals("GIF IMPORT FAILED", GifLabels.importError(t, RuntimeException()))
    }

    @Test
    fun theImportedToastIsExactlyTheSentenceTheScreenAlwaysBuilt() {
        assertEquals("IMPORTED 1 GIF -- RESTARTING", GifLabels.importedToast(t, 1, 0))
        assertEquals("IMPORTED 3 GIFS -- RESTARTING", GifLabels.importedToast(t, 3, 0))
        assertEquals("IMPORTED 0 GIFS -- RESTARTING", GifLabels.importedToast(t, 0, 0))
        assertEquals("IMPORTED 3 GIFS, 2 SKIPPED -- RESTARTING", GifLabels.importedToast(t, 3, 2))
        assertEquals("IMPORTED 1 GIF, 1 SKIPPED -- RESTARTING", GifLabels.importedToast(t, 1, 1))
        // Nothing skipped says nothing about skipping (the old code added the part only when the count was above zero).
        assertFalse(GifLabels.importedToast(t, 5, 0).contains("SKIPPED"))
        assertTrue(GifLabels.importedToast(t, 5, 1).contains("SKIPPED"))
    }

    @Test
    fun aCategoryStillNamedByItsSavedDefaultIsShownInTheLanguage_inEnglishItReadsAsItAlwaysDid() {
        assertEquals("UNCATEGORIZED", GifLabels.STORED_DEFAULT_CATEGORY)
        assertEquals("UNCATEGORIZED", GifLabels.shownCategoryName(t, "UNCATEGORIZED"))
        assertEquals("REACTIONS", GifLabels.shownCategoryName(t, "REACTIONS"))
        assertEquals("", GifLabels.shownCategoryName(t, ""))
    }

    // ---- why an import failed is carried by id --------------------------------------------------------------------------------------

    @Test
    fun eachFailureCarriesTheTextItAlwaysHad_andItsResourceSaysTheSameInEnglish() {
        val expected = mapOf(
            GifImportFailure.NOT_A_GIF to "Selected file is not a GIF.", GifImportFailure.TOO_BIG to "GIF exceeds the 20 MB safety limit.",
            GifImportFailure.UNREADABLE to "Unable to read selected file.", GifImportFailure.INVALID to "Selected file is not a valid GIF.",
        )
        assertEquals(expected.keys, GifImportFailure.values().toSet())
        for ((failure, text) in expected) {
            assertEquals(text, failure.englishMessage)
            assertEquals(text, GifImportException(failure).message)
            assertEquals("${failure.resource} says what the repository's failure always said", text, english.getValue(failure.resource))
            assertEquals(text, GifLabels.importError(t, GifImportException(failure)))
            assertTrue("it is still an IllegalStateException, what error(...) threw", GifImportException(failure) is IllegalStateException)
        }
        assertEquals("four different resources", 4, GifImportFailure.values().map { it.resource }.toSet().size)
    }

    @Test
    fun aFailureThisAppDoesNotKnowKeepsTheTextTheSystemGave_andOneWithNoTextSaysGifImportFailed() {
        assertEquals("open failed: EACCES (Permission denied)", GifLabels.importError(t, java.io.IOException("open failed: EACCES (Permission denied)")))
        assertEquals("GIF IMPORT FAILED", GifLabels.importError(t, java.io.IOException()))
        for ((tag, map) in translations) {
            val f = FileText(tag)
            // What the system said is passed through untouched, in every language: it is the phone's own text, not ours.
            assertEquals("$tag", "open failed: EACCES", GifLabels.importError(f, java.io.IOException("open failed: EACCES")))
            assertEquals("$tag: no text reads as the language's own sentence", map.getValue("gif_import_failed"), GifLabels.importError(f, java.io.IOException()))
            assertNotEquals("$tag: still English", "GIF IMPORT FAILED", GifLabels.importError(f, java.io.IOException()))
        }
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------

    @Test
    fun eachKnownFailureIsSaidInTheLanguage_andOnlyTheTooBigOneNamesTheLimit() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val said = GifImportFailure.values().map { it to GifLabels.importError(f, GifImportException(it)) }
            for ((failure, text) in said) {
                assertEquals("$tag/$failure", map.getValue(failure.resource), text)
                assertNotEquals("$tag/$failure: still English", failure.englishMessage, text)
                assertFalse("$tag/$failure: a placeholder leaked: $text", text.contains("%"))
                assertEquals("$tag/$failure: only the size limit holds a number", failure == GifImportFailure.TOO_BIG, text.any { it.isDigit() })
            }
            assertTrue("$tag: 20 MB stays as a symbol", said.single { it.first == GifImportFailure.TOO_BIG }.second.contains("20 MB"))
            assertEquals("$tag: four different sentences", 4, said.map { it.second }.toSet().size)
        }
    }

    @Test
    fun aSavedDefaultCategoryIsShownInTheLanguage_anyOtherNameExactlyAsSaved() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val shown = GifLabels.shownCategoryName(f, "UNCATEGORIZED")
            assertEquals("$tag", map.getValue("gif_category_default"), shown)
            assertNotEquals("$tag: still English", "UNCATEGORIZED", shown)
            // A typed name, a name that reads like the language's own default, and a near miss of the saved one are all shown as saved.
            assertEquals("$tag: typed", "MEMES", GifLabels.shownCategoryName(f, "MEMES"))
            assertEquals("$tag: reads like ours", shown, GifLabels.shownCategoryName(f, shown))
            assertEquals("$tag: near miss (lower case)", "uncategorized", GifLabels.shownCategoryName(f, "uncategorized"))
            assertEquals("$tag: near miss (space)", "UNCATEGORIZED ", GifLabels.shownCategoryName(f, "UNCATEGORIZED "))
            assertEquals("$tag: empty", "", GifLabels.shownCategoryName(f, ""))
        }
    }

    @Test
    fun theCategoryLineHoldsTheCategoryTheDefaultInTheLanguageOrTheNoGifsWord() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            assertTrue("$tag: typed", GifLabels.categoryLine(f, "MEMES").contains("MEMES"))
            assertTrue("$tag: default", GifLabels.categoryLine(f, "UNCATEGORIZED").contains(map.getValue("gif_category_default")))
            assertFalse("$tag: the saved English default must not show", GifLabels.categoryLine(f, "UNCATEGORIZED").contains("UNCATEGORIZED"))
            assertTrue("$tag: no category", GifLabels.categoryLine(f, null).contains(map.getValue("gif_no_gifs")))
            assertNotEquals("$tag: three different lines", GifLabels.categoryLine(f, null), GifLabels.categoryLine(f, "UNCATEGORIZED"))
            assertFalse("$tag: a placeholder leaked", GifLabels.categoryLine(f, null).contains("%"))
        }
    }

    @Test
    fun theOverlayButtonSaysOnOrOffInWords_inEveryLanguage() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            assertTrue("$tag: ON", GifLabels.landscapeButton(f, true).contains(map.getValue("common_on")))
            assertTrue("$tag: OFF", GifLabels.landscapeButton(f, false).contains(map.getValue("common_off")))
            assertNotEquals("$tag: on and off read the same", GifLabels.landscapeButton(f, true), GifLabels.landscapeButton(f, false))
            assertTrue("$tag: in square brackets", GifLabels.landscapeButton(f, true).contains("[") && GifLabels.landscapeButton(f, true).contains("]"))
        }
    }

    @Test
    fun theImportedToastHoldsTheImportedCountAndTheSkippedCountEachOnce_inEveryLanguage() {
        // 7 and 3 are different on purpose: an argument that moved would show a number twice.
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val plain = GifLabels.importedToast(f, 7, 0)
            val skipping = GifLabels.importedToast(f, 7, 3)
            assertEquals("$tag: the imported count once in '$plain'", 1, plain.count { it == '7' })
            assertEquals("$tag: the imported count once in '$skipping'", 1, skipping.count { it == '7' })
            assertEquals("$tag: the skipped count once in '$skipping'", 1, skipping.count { it == '3' })
            assertTrue("$tag: the skipped count follows its label ('$skipping')", skipping.contains(": 3"))
            assertFalse("$tag: nothing skipped says nothing about skipping ('$plain')", plain.contains(":") || plain.contains("3"))
            assertFalse("$tag: a placeholder leaked", plain.contains("%") || skipping.contains("%"))
            assertNotEquals("$tag: still English", "IMPORTED 7 GIFS -- RESTARTING", plain)
            assertTrue("$tag: it says ACK is restarting, like the other restart toasts", plain.contains("--") && skipping.contains("--"))
        }
    }

    @Test
    fun theExportToastNamesTheDeckWithTheLabelsItWasGiven_andFailureIsItsOwnSentence() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val said = GifLabels.exportToast(f, true, map.getValue("label_deck_type_gif"), map.getValue("label_deck"))
            assertTrue("$tag: GIF in '$said'", said.contains(map.getValue("label_deck_type_gif")))
            assertTrue("$tag: DECK in '$said'", said.contains(map.getValue("label_deck")))
            assertFalse("$tag: a placeholder leaked: $said", said.contains("%"))
            // The PLAIN WORDS labels flow through as given.
            assertTrue("$tag: plain labels", GifLabels.exportToast(f, true, "AAA", "BBB").let { it.contains("AAA") && it.contains("BBB") })
            assertEquals("$tag: failure", map.getValue("gif_export_failed"), GifLabels.exportToast(f, false, "AAA", "BBB"))
            assertNotEquals("$tag: success and failure read the same", said, GifLabels.exportToast(f, false, "AAA", "BBB"))
        }
    }

    @Test
    fun theEnglishPluralFormsSplitOnOneGif() {
        assertEquals("IMPORTED 1 GIF -- RESTARTING", t.count("gif_imported_toast", 1))
        assertEquals("IMPORTED 2 GIFS -- RESTARTING", t.count("gif_imported_toast", 2))
        assertEquals("IMPORTED 1 GIF, 4 SKIPPED -- RESTARTING", t.count("gif_imported_skipped_toast", 1, 4))
        assertEquals("IMPORTED 2 GIFS, 4 SKIPPED -- RESTARTING", t.count("gif_imported_skipped_toast", 2, 4))
    }
}
