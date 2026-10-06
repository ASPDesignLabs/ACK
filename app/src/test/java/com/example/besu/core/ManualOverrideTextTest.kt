// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the legacy Manual Override screen and the BUILDER deck's tactical guide say that is decided, in English exactly as it always was and in every language: the empty memory-banks message that
 * names the ENCODE button, the two-part delete confirmation (the phrase exactly as saved, then the warning), and the guide's pose descriptions.
 */
class ManualOverrideTextTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    // ---- English is exactly what it always said -------------------------------------------------------------------------------------

    @Test
    fun theEnglishIsExactlyWhatTheScreenAlwaysSaid() {
        assertEquals("NO SAVED PHRASES YET. ENCODE ONE FROM THE TEXT FIELD ABOVE.", ManualOverrideText.emptyBanks(t, "ENCODE"))
        assertEquals(
            "Permanently remove the saved phrase \"Hello there\"? This cannot be undone -- consider exporting a backup first.",
            ManualOverrideText.deleteQuestion(t, "Hello there"),
        )
        assertEquals("POSE: ARM RAISED UP" to "Use for: Status reporting.", ManualOverrideText.guide(t, "POSE", "IDENTITY"))
        assertEquals("POSE: ARM FLAT / PALM DOWN" to "Use for: Boundaries, stops.", ManualOverrideText.guide(t, "POSE", "DEFEND"))
        assertEquals("POSE: HANDSHAKE / SIDEWAYS" to "Use for: Social protocols.", ManualOverrideText.guide(t, "POSE", "CONNECT"))
        assertEquals("UNKNOWN" to "No data available.", ManualOverrideText.guide(t, "POSE", "WORK"))
        assertEquals("// TACTICAL GUIDE: POSE: ARM RAISED UP", ManualOverrideText.guideHeader(t, "POSE: ARM RAISED UP"))
    }

    @Test
    fun theSimpleWordsAreHeldExactly() {
        val expected = mapOf(
            "manual_placeholder" to "ENTER SEQUENCE...", "manual_encode" to "ENCODE", "manual_transmit" to "TRANSMIT", "manual_hide_browser" to "[HIDE TARGET BROWSER]",
            "manual_cache_recent" to "CACHE [RECENT]", "manual_encode_to_bank" to "ENCODE TO BANK", "manual_assign_tag" to "ASSIGN A TAG", "manual_new_tag" to "NEW TAG",
            "manual_confirm_delete" to "CONFIRM DELETE", "manual_delete_permanently" to "DELETE PERMANENTLY", "manual_replay" to "REPLAY",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
    }

    @Test
    fun aGuideForAnythingButTheThreePosesIsUnknown_theStoredNamesBeingExact() {
        // The pose names are saved logic: only the exact capitals match, and a custom layer's name is unknown to the guide.
        for (category in listOf("identity", "Identity", "IDENTITY ", "", "WORK", "Twist 1")) {
            assertEquals(category, "UNKNOWN" to "No data available.", ManualOverrideText.guide(t, "POSE", category))
        }
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------

    @Test
    fun theEmptyMessageNamesTheEncodeButtonOnceWithTheWordItWasGiven_inEveryLanguage() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val said = ManualOverrideText.emptyBanks(f, map.getValue("manual_encode"))
            assertEquals("$tag: the button's word once in '$said'", 1, Regex(Regex.escape(map.getValue("manual_encode"))).findAll(said).count())
            // The word is whatever it is given (PLAIN WORDS or a later rename must flow through).
            assertTrue("$tag", ManualOverrideText.emptyBanks(f, "QQQ").contains("QQQ"))
            assertFalse("$tag: a placeholder leaked: $said", said.contains("%"))
            assertNotEquals("$tag: still English", "NO SAVED PHRASES YET. ENCODE ONE FROM THE TEXT FIELD ABOVE.", said)
        }
    }

    @Test
    fun theDeleteQuestionShowsThePhraseExactlyAsSaved_inQuotes_inEveryLanguage() {
        // A phrase can hold anything the person typed: a percent sign, a dollar, a quote, a line break. It is passed as an argument, never as part of the format.
        val phrases = listOf("Hello there", "100% sure %s %d", "price \$5 and \$1", "she said \"no\"", "line one\nline two", "")
        for ((tag, _) in translations) {
            val f = FileText(tag)
            for (phrase in phrases) {
                val said = ManualOverrideText.deleteQuestion(f, phrase)
                assertTrue("$tag: '$phrase' in quotes in '$said'", said.contains("\"$phrase\""))
                assertFalse("$tag: a leaked placeholder for '$phrase'", said.replace(phrase, "").contains("%"))
            }
        }
    }

    @Test
    fun theDeleteConfirmationAlwaysSaysBothPartsInEveryLanguage_theQuestionThenTheWarning_joinedByOneSpace() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val said = ManualOverrideText.deleteQuestion(f, "Hello")
            val question = f.get("manual_delete_question", "Hello")
            val warning = map.getValue("manual_delete_warning")
            assertEquals("$tag", "$question $warning", said)
            assertTrue("$tag: the warning comes last", said.endsWith(warning))
            assertNotEquals("$tag: the warning is not English", english.getValue("manual_delete_warning"), warning)
            assertNotEquals("$tag: the question is not English", english.getValue("manual_delete_question").format("Hello"), question)
            assertNotEquals("$tag: two different sentences", question, warning)
            assertFalse("$tag: no double space where they join", said.contains("  "))
            // The warning is the safety sentence: it keeps the app's own " -- " between "cannot be undone" and the advice to back up first.
            assertTrue("$tag: the two halves of the warning", warning.contains(" -- "))
            assertFalse("$tag: the warning takes no argument", Regex("""%\d""").containsMatchIn(warning))
        }
    }

    @Test
    fun theThreePosesAreDescribedByTheirOwnWords_andTheTitleTakesThePoseLabelItWasGiven() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            val guides = listOf("IDENTITY", "DEFEND", "CONNECT").map { ManualOverrideText.guide(f, "PPP", it) }
            for ((i, g) in guides.withIndex()) {
                assertTrue("$tag/$i: the pose label in '${g.first}'", g.first.contains("PPP"))
                assertFalse("$tag/$i: a placeholder leaked: ${g.first}", g.first.contains("%"))
            }
            assertEquals("$tag: three different titles", 3, guides.map { it.first }.toSet().size)
            assertEquals("$tag: three different bodies", 3, guides.map { it.second }.toSet().size)
            val unknown = ManualOverrideText.guide(f, "PPP", "WORK")
            assertEquals("$tag", map.getValue("manual_guide_unknown_title") to map.getValue("manual_guide_unknown_body"), unknown)
            assertFalse("$tag: the unknown title does not name a pose", unknown.first.contains("PPP"))
            assertNotEquals("$tag: still English", "UNKNOWN", unknown.first)
        }
    }

    @Test
    fun theGuideHeaderHoldsTheTitle_inEveryLanguage() {
        for ((tag, _) in translations) {
            val said = ManualOverrideText.guideHeader(FileText(tag), "TTT")
            assertTrue("$tag: '$said'", said.contains("TTT"))
            assertTrue("$tag: it keeps the leading slashes that mark it as a heading", said.startsWith("// "))
            assertFalse("$tag: a placeholder leaked", said.contains("%"))
            assertNotEquals("$tag: still English", "// TACTICAL GUIDE: TTT", said)
        }
    }
}
