// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** What the EMOJI deck says that is decided, in English exactly as it always was and in every language. A saved page name is never rewritten. */
class EmojiLabelsTest {

    private val t = EnglishText
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    @Test
    fun theEnglishWordsAreExactlyWhatTheDeckAlwaysSaid() {
        assertEquals("TAP: DISPLAY  //  HOLD: CONFIGURE", EmojiLabels.hint(t))
        assertEquals("PAGE 1", EmojiLabels.shownPageName(t, "PAGE 1", 0))
        assertEquals("PAGE 3", EmojiLabels.shownPageName(t, "PAGE 3", 2))
        assertEquals("RELATED // PANEL", EmojiLabels.relatedTitle(t, "", ""))
        assertEquals("RELATED // FOOD", EmojiLabels.relatedTitle(t, "FOOD", "🍽️"))
        assertEquals("RELATED // 🍽️", EmojiLabels.relatedTitle(t, "", "🍽️"))
    }

    @Test
    fun theSavedDefaultIsWhatTheDeckAndItsConfigDialogCreate_soAScreenCanRecogniseIt() {
        val deck = RepoFiles.read("app/src/main/java/com/example/besu/decks/EmojiDeck.kt")
        assertTrue(deck.contains("""name = "PAGE 1""""))
        assertTrue(deck.contains("""name = "PAGE ${'$'}nextNumber""""))
        assertEquals("PAGE 1", EmojiLabels.storedDefaultPageName(0))
        assertEquals("PAGE 4", EmojiLabels.storedDefaultPageName(3))
    }

    @Test
    fun aPageStillNamedByItsSavedDefaultIsShownInTheLanguage_anyOtherNameExactlyAsSaved() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val shown = EmojiLabels.shownPageName(f, "PAGE 2", 1)
            assertEquals("$tag", FileText(tag).get("emoji_page_default", 2), shown)
            assertNotEquals("$tag: still English", "PAGE 2", shown)
            assertTrue("$tag: the number is in '$shown'", shown.contains("2"))
            // The default of ANOTHER page, a typed name, and a name that reads like the language's own default are all shown as saved.
            assertEquals("$tag: another page's default", "PAGE 1", EmojiLabels.shownPageName(f, "PAGE 1", 1))
            assertEquals("$tag: typed", "MEALS", EmojiLabels.shownPageName(f, "MEALS", 1))
            assertEquals("$tag: reads like ours", shown, EmojiLabels.shownPageName(f, shown, 1))
            assertFalse("$tag: a placeholder leaked", shown.contains("%"))
        }
    }

    @Test
    fun theRelatedTitleShowsTheLabelThenTheEmojiThenTheLanguagesWordForAPanel() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            assertEquals("$tag: label first", FileText(tag).get("emoji_related_title", "FOOD"), EmojiLabels.relatedTitle(f, "FOOD", "🍽️"))
            assertTrue("$tag: emoji next", EmojiLabels.relatedTitle(f, "", "🍽️").endsWith("🍽️"))
            assertTrue("$tag: then the word for a panel", EmojiLabels.relatedTitle(f, "", "").endsWith(map.getValue("emoji_panel_default")))
            assertTrue("$tag: a blank label does not count (${EmojiLabels.relatedTitle(f, "   ", "")})", EmojiLabels.relatedTitle(f, "", "").isNotBlank())
            assertFalse("$tag: a placeholder leaked", EmojiLabels.relatedTitle(f, "", "").contains("%"))
        }
    }

    @Test
    fun theHintHasBothHalvesJoinedByTheAppsDoubleSpacedSeparator_inEveryLanguage() {
        for ((tag, map) in translations) {
            assertEquals("$tag", map.getValue("emoji_hint_tap") + "  //  " + map.getValue("emoji_hint_hold"), EmojiLabels.hint(FileText(tag)))
            assertTrue("$tag: a colon in each half", map.getValue("emoji_hint_tap").contains(":") && map.getValue("emoji_hint_hold").contains(":"))
            // The second half is the same words as the Emergency deck's hold hint, so the two decks say the same thing.
            assertEquals("$tag: HOLD: CONFIGURE", map.getValue("emergency_hint_hold"), map.getValue("emoji_hint_hold"))
        }
    }
}
