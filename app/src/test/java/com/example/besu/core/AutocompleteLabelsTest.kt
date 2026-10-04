// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The words MANAGE AUTOCOMPLETE's tree shows for a field, in English exactly as they always were and in every language. */
class AutocompleteLabelsTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    @Test
    fun theEnglishLabelsAreExactlyWhatTheTreeAlwaysSaid() {
        assertEquals("MATRIX (3)", AutocompleteLabels.kindHeading(t, AutocompleteLabels.Kind.MATRIX, 3))
        assertEquals("QUICK ACTIONS (12)", AutocompleteLabels.kindHeading(t, AutocompleteLabels.Kind.QUICK_ACTIONS, 12))
        assertEquals("SHARED ROOT VARIABLES (1)", AutocompleteLabels.kindHeading(t, AutocompleteLabels.Kind.SHARED_ROOT, 1))
        assertEquals("VARIABLE 1", AutocompleteLabels.variable(t, 0, null))
        assertEquals("VARIABLE 3 // ROOT B", AutocompleteLabels.variable(t, 2, "B"))
        assertEquals("VAR:A", AutocompleteLabels.quickActionField(t, 0, "A"))
        assertEquals("VAR 2", AutocompleteLabels.quickActionField(t, 1, null))
        assertEquals("TAG C", AutocompleteLabels.rootTag(t, "C"))
        assertEquals("SLOT 4", AutocompleteLabels.defaultSlot(t, 3))
        assertEquals("UNKNOWN", AutocompleteLabels.unknown(t))
        assertEquals("UNKNOWN NODE", AutocompleteLabels.unknownNode(t))
    }

    @Test
    fun aQuickActionsFieldNamedByItsTagKeepsTheTokenSyntaxInEveryLanguage() {
        // VAR:A is how the tag is written in a template, not a word: it is never translated, and a field with no tag is numbered instead.
        for ((tag, _) in translations) {
            val f = FileText(tag)
            assertEquals("$tag: token syntax", "VAR:B", AutocompleteLabels.quickActionField(f, 1, "B"))
            assertTrue("$tag: numbered", AutocompleteLabels.quickActionField(f, 4, null).contains("5"))
        }
    }

    @Test
    fun aPoseIsShownAsTheMatrixScreenShowsIt_aLayerAsTyped_andAMissingOneAsUnknown() {
        assertEquals("IDENTITY", AutocompleteLabels.poseOrLayer(t, "IDENTITY"))
        assertEquals("DEFEND", AutocompleteLabels.poseOrLayer(t, "DEFEND"))
        assertEquals("CONNECT", AutocompleteLabels.poseOrLayer(t, "CONNECT"))
        assertEquals("SCHOOL", AutocompleteLabels.poseOrLayer(t, "SCHOOL"))
        assertEquals("UNKNOWN", AutocompleteLabels.poseOrLayer(t, AutocompleteLabels.UNKNOWN_KEY))
        for ((tag, map) in translations) {
            val f = FileText(tag)
            assertEquals("$tag: IDENTITY", map.getValue("label_pose_identity"), AutocompleteLabels.poseOrLayer(f, "IDENTITY"))
            assertEquals("$tag: DEFEND", map.getValue("label_pose_defend"), AutocompleteLabels.poseOrLayer(f, "DEFEND"))
            assertEquals("$tag: CONNECT", map.getValue("label_pose_connect"), AutocompleteLabels.poseOrLayer(f, "CONNECT"))
            // A layer the person made, even one called like a translated word, is shown exactly as typed.
            assertEquals("$tag: a layer is shown as typed", "SCHOOL", AutocompleteLabels.poseOrLayer(f, "SCHOOL"))
            assertEquals("$tag: even when it reads like a word of ours", map.getValue("label_pose_identity"), AutocompleteLabels.poseOrLayer(f, map.getValue("label_pose_identity")))
            assertEquals("$tag: unknown", map.getValue("autocomplete_unknown"), AutocompleteLabels.poseOrLayer(f, AutocompleteLabels.UNKNOWN_KEY))
        }
    }

    @Test
    fun theUnknownKeyCanNeverBeTheNameOfALayerThePersonMade() {
        // A layer's name is capitals, digits, spaces, underscores and hyphens, one to 24 (CommandRepository's own pattern), so "?" can only ever mean "not found".
        val layerName = Regex("^[A-Z0-9 _-]{1,24}$")
        assertFalse(layerName.matches(AutocompleteLabels.UNKNOWN_KEY))
        // And a layer called UNKNOWN is shown as UNKNOWN because it is typed so, not because it is missing.
        assertEquals("UNKNOWN", AutocompleteLabels.poseOrLayer(t, "UNKNOWN"))
        for ((tag, _) in translations) {
            assertEquals("$tag: a layer called UNKNOWN stays as typed", "UNKNOWN", AutocompleteLabels.poseOrLayer(FileText(tag), "UNKNOWN"))
        }
        val repo = RepoFiles.read("app/src/main/java/com/example/besu/data/CommandRepository.kt")
        assertTrue("the pattern this test mirrors is still the real one", repo.contains("""Regex("^[A-Z0-9 _-]{1,24}$")"""))
    }

    @Test
    fun theKindHeadingsUseTheSameWordsTheDeckTypesAndSharedVariablesHaveElsewhere() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            assertTrue("$tag: MATRIX", AutocompleteLabels.kindHeading(f, AutocompleteLabels.Kind.MATRIX, 2).startsWith(map.getValue("label_deck_type_matrix")))
            assertTrue("$tag: QUICK ACTIONS", AutocompleteLabels.kindHeading(f, AutocompleteLabels.Kind.QUICK_ACTIONS, 2).startsWith(map.getValue("label_deck_type_quick")))
            assertTrue("$tag: SHARED ROOT VARIABLES", AutocompleteLabels.kindHeading(f, AutocompleteLabels.Kind.SHARED_ROOT, 2).startsWith(map.getValue("label_shared_variables")))
            for (kind in AutocompleteLabels.Kind.values()) assertTrue("$tag: the count is filled in", AutocompleteLabels.kindHeading(f, kind, 17).endsWith("(17)"))
        }
    }

    @Test
    fun everyLabelIsARealStringInEveryLanguage_andTheNumberedOnesTakeTheirNumber() {
        for ((tag, _) in translations) {
            val f = FileText(tag)
            for (said in listOf(
                AutocompleteLabels.variable(f, 0, null), AutocompleteLabels.variable(f, 0, "A"), AutocompleteLabels.quickActionField(f, 0, null), AutocompleteLabels.rootTag(f, "A"),
                AutocompleteLabels.defaultSlot(f, 0), AutocompleteLabels.unknown(f), AutocompleteLabels.unknownNode(f),
            )) assertFalse("$tag: a resource name was shown instead of words: $said", said.contains("autocomplete_"))
            assertTrue("$tag: variable number", AutocompleteLabels.variable(f, 6, null).contains("7"))
            assertTrue("$tag: root tag", AutocompleteLabels.variable(f, 6, "C").endsWith("C"))
            assertTrue("$tag: slot number", AutocompleteLabels.defaultSlot(f, 2).contains("3"))
            assertNotEquals("$tag: unknown and unknown node", AutocompleteLabels.unknown(f), AutocompleteLabels.unknownNode(f))
            assertNotEquals("$tag: still English", AutocompleteLabels.unknown(EnglishText), AutocompleteLabels.unknown(f))
        }
        assertTrue(english.getValue("autocomplete_kind_count") == "%1\$s (%2\$d)")
    }
}
