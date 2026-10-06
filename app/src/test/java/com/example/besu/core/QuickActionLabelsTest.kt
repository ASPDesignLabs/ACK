// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** What the QUICK ACTIONS deck says that is decided, in English exactly as it always was and in every language. A saved name is never rewritten. */
class QuickActionLabelsTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    // ---- English is exactly what it always said -------------------------------------------------------------------------------------

    @Test
    fun theEnglishWordsAreExactlyWhatTheDeckAlwaysSaid() {
        assertEquals("TAP: EXECUTE  //  HOLD: EDIT", QuickActionLabels.hint(t))
        assertEquals("G1", QuickActionLabels.groupTab(t, 0))
        assertEquals("G3", QuickActionLabels.groupTab(t, 2))
        assertEquals("ACTION 1", QuickActionLabels.shownSlotLabel(t, "ACTION 1", 0))
        assertEquals("ACTION 4", QuickActionLabels.shownSlotLabel(t, "ACTION 4", 3))
        assertEquals("GROUP 2", QuickActionLabels.shownGroupLabel(t, "GROUP 2", 1))
        assertEquals("IDE", QuickActionLabels.poseShort(t, "IDENTITY"))
        assertEquals("DEF", QuickActionLabels.poseShort(t, "DEFEND"))
        assertEquals("CON", QuickActionLabels.poseShort(t, "CONNECT"))
        assertEquals("WOR", QuickActionLabels.poseShort(t, "WORKPLACE"))
        assertEquals("POSE: IDENTITY  //  ROOT: DEFEND", QuickActionLabels.poseRootLine(t, "POSE", "IDENTITY", "DEFEND"))
        assertEquals("[HOLD TO CONFIGURE]", english.getValue("qa_hold_configure"))
    }

    @Test
    fun theSavedDefaultsAreWhatTheModelsCreate_soAScreenCanRecogniseThem() {
        val models = RepoFiles.read("app/src/main/java/com/example/besu/decks/QuickActionsModels.kt")
        assertTrue(models.contains("""val label: String = "ACTION ${'$'}{slotIndex + 1}","""))
        assertTrue(models.contains("""val label: String = "GROUP ${'$'}{groupIndex + 1}","""))
        assertEquals("ACTION 3", QuickActionLabels.storedDefaultSlotLabel(2))
        assertEquals("GROUP 3", QuickActionLabels.storedDefaultGroupLabel(2))
        assertTrue(models.contains("""val POSE_CATEGORIES = listOf("IDENTITY", "DEFEND", "CONNECT")"""))
    }

    // ---- a saved name is never rewritten ----------------------------------------------------------------------------------------------

    @Test
    fun aSlotOrGroupStillNamedByItsSavedDefaultIsShownInTheLanguage_aTypedNameIsShownAsTyped() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val slot = QuickActionLabels.shownSlotLabel(f, "ACTION 3", 2)
            val group = QuickActionLabels.shownGroupLabel(f, "GROUP 2", 1)
            assertEquals("$tag: slot", FileText(tag).get("qa_slot_default", 3), slot)
            assertEquals("$tag: group", FileText(tag).get("qa_group_default", 2), group)
            assertNotEquals("$tag: slot still English", "ACTION 3", slot)
            assertNotEquals("$tag: group still English", "GROUP 2", group)
            assertTrue("$tag: the number is in the slot's name", slot.contains("3"))
            // A name the person typed is never rewritten, even one that reads like one of ours or like the default of another slot.
            assertEquals("$tag: typed", "FOOD ORDER", QuickActionLabels.shownSlotLabel(f, "FOOD ORDER", 2))
            assertEquals("$tag: typed like the language's own default", map.getValue("qa_slot_default").replace("%1\$d", "3"), QuickActionLabels.shownSlotLabel(f, map.getValue("qa_slot_default").replace("%1\$d", "3"), 2))
            assertEquals("$tag: the default of ANOTHER slot is a name the person typed", "ACTION 1", QuickActionLabels.shownSlotLabel(f, "ACTION 1", 2))
            assertEquals("$tag: the default of ANOTHER group is a name the person typed", "GROUP 1", QuickActionLabels.shownGroupLabel(f, "GROUP 1", 1))
        }
    }

    @Test
    fun savingFromAnEditorWithoutTouchingTheNameSavesWhatWasStored_andAnEditSavesWhatWasTyped() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            val shown = QuickActionLabels.shownSlotLabel(f, "ACTION 1", 0)
            assertEquals("$tag: untouched", "ACTION 1", QuickActionLabels.labelToSave(shown, shown, "ACTION 1"))
            assertEquals("$tag: edited", "WATER", QuickActionLabels.labelToSave("WATER", shown, "ACTION 1"))
            // A name the person had typed, left alone, stays exactly as it was.
            assertEquals("$tag: typed and untouched", "MY WORD", QuickActionLabels.labelToSave("MY WORD", "MY WORD", "MY WORD"))
        }
        assertEquals("ACTION 1", QuickActionLabels.labelToSave("ACTION 1", "ACTION 1", "ACTION 1"))
        assertEquals("", QuickActionLabels.labelToSave("", "ACTION 1", "ACTION 1"))
    }

    // ---- every language ------------------------------------------------------------------------------------------------------------------

    @Test
    fun theHintHasBothHalvesJoinedByTheAppsDoubleSpacedSeparator_inEveryLanguage() {
        for ((tag, map) in translations) {
            val said = QuickActionLabels.hint(FileText(tag))
            assertEquals("$tag", map.getValue("qa_hint_tap") + "  //  " + map.getValue("qa_hint_hold"), said)
            assertTrue("$tag: both halves say what a tap and a hold do (a colon in each)", map.getValue("qa_hint_tap").contains(":") && map.getValue("qa_hint_hold").contains(":"))
            assertNotEquals("$tag: still English", "TAP: EXECUTE  //  HOLD: EDIT", said)
        }
    }

    @Test
    fun theGroupTabCarriesTheNumber_inTheLanguagesOwnLetter() {
        for ((tag, _) in translations) {
            for (i in 0..2) assertTrue("$tag: $i", QuickActionLabels.groupTab(FileText(tag), i).contains("${i + 1}"))
        }
        // Hindi and Arabic use their own letter for a group, not a Latin G.
        assertFalse(QuickActionLabels.groupTab(FileText("hi"), 0).startsWith("G"))
        assertFalse(QuickActionLabels.groupTab(FileText("ar"), 0).startsWith("G"))
    }

    @Test
    fun thePoseShortNamesAreThreeDifferentWordsInEveryLanguage_andACustomNameIsCutToThreeLettersAsBefore() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val shorts = listOf("IDENTITY", "DEFEND", "CONNECT").map { QuickActionLabels.poseShort(f, it) }
            assertEquals("$tag: three different short names $shorts", 3, shorts.toSet().size)
            for (short in shorts) assertTrue("$tag: '$short' is short enough for a small label", short.length <= 8 && short.isNotBlank())
            assertEquals("$tag: a name that is not a pose keeps being cut to three letters", "WOR", QuickActionLabels.poseShort(f, "WORKPLACE"))
        }
        // Where the language uses Latin letters the short names stay short (three or four letters), as in English.
        for (tag in listOf("es", "pt", "af")) for (key in listOf("identity", "defend", "connect")) assertTrue("$tag/$key", translations.getValue(tag).getValue("qa_pose_short_$key").length in 3..4)
    }

    @Test
    fun thePoseAndRootLineHoldsTheWordsAndNamesItWasGiven_inEveryLanguage() {
        for ((tag, map) in translations) {
            val said = QuickActionLabels.poseRootLine(FileText(tag), map.getValue("label_pose"), map.getValue("label_pose_identity"), map.getValue("label_pose_defend"))
            assertTrue("$tag: POSE word and pose name in '$said'", said.contains(map.getValue("label_pose")) && said.contains(map.getValue("label_pose_identity")))
            assertTrue("$tag: root name in '$said'", said.contains(map.getValue("label_pose_defend")))
            assertTrue("$tag: the two halves are joined by the double-spaced separator", said.contains("  //  "))
            assertEquals("$tag: pose first, then root", true, said.indexOf(map.getValue("label_pose_identity")) < said.indexOf(map.getValue("label_pose_defend")))
        }
    }

    @Test
    fun theRootWordIsTheLanguagesWordForRootUsedOnTheMatrixScreen() {
        // "ROOT: IDENTITY" says ROOT the way "ROOT IDENTITY" does on the Matrix screen (matrix_root_tag), in every language.
        for ((tag, map) in translations) {
            val rootWord = map.getValue("matrix_root_tag").replace("%1\$s", "").trim()
            assertTrue("$tag: '$rootWord' is in '${map.getValue("qa_root_part")}'", map.getValue("qa_root_part").contains(rootWord))
        }
    }
}
