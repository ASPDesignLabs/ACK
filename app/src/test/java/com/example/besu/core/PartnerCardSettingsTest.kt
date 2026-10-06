// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The person's choice for the partner card (core/PartnerCardSettings.kt and the own-sentence rules in core/PartnerCard.kt): which sentences are on, and the sentences they wrote. */
class PartnerCardSettingsTest {

    private val own1 = 5
    private val own2 = 6
    private val d = PartnerCardSettings.DEFAULT
    private val five = PartnerCard.message(EnglishText)

    // ---- what nothing stored means ------------------------------------------------------------------------------------------------------

    @Test
    fun nothingChosenIsTheCardAsItAlwaysWas_fiveSentencesOn_noOwn() {
        assertEquals(listOf("", ""), d.own)
        assertEquals(emptySet<Int>(), d.off)
        for (slot in 0..4) assertTrue("slot $slot", d.isOn(slot))
        assertFalse("an empty own slot is never on", d.isOn(own1))
        assertFalse(d.isOn(own2))
        assertTrue(d.anyOn)
        assertEquals(five, PartnerCard.message(EnglishText, d))
        assertEquals(PartnerCard.lines(EnglishText), PartnerCard.spoken(EnglishText, d))
    }

    @Test
    fun aSlotThatDoesNotExistIsNeverOn_andChangesNothing() {
        for (slot in listOf(-1, 7, 8, 100, Int.MIN_VALUE, Int.MAX_VALUE)) {
            assertFalse("slot $slot", d.isOn(slot))
            assertEquals(d, d.toggled(slot))
            assertEquals(d, d.withOwn(slot, "hello"))
        }
        // withOwn only writes the two own slots: a built-in slot is not a place for the person's words.
        for (slot in 0..4) assertEquals("slot $slot", d, d.withOwn(slot, "hello"))
    }

    // ---- turning sentences on and off -----------------------------------------------------------------------------------------------------

    @Test
    fun aBuiltInSentenceTurnsOffAndOnAgain() {
        val off = d.toggled(2)
        assertFalse(off.isOn(2))
        assertEquals(setOf(2), off.off)
        assertTrue(off.isOn(1) && off.isOn(3))
        assertEquals(d, off.toggled(2))
        val message = PartnerCard.message(EnglishText, off)
        assertFalse(message.contains("Please wait while I answer."))
        assertEquals(PartnerCard.lines(EnglishText).filterIndexed { i, _ -> i != 2 }.joinToString(" "), message)
    }

    @Test
    fun aSingleSentenceCanBeTheWholeCard() {
        var s = d
        for (slot in 0..4) if (slot != 3) s = s.toggled(slot)
        assertEquals(listOf(3), (0..6).filter { s.isOn(it) })
        assertEquals("Please do not take my phone.", PartnerCard.message(EnglishText, s))
        assertTrue(s.anyOn)
    }

    @Test
    fun withEverySentenceOffNothingIsSaid_andAnyOnIsFalse() {
        var s = d
        for (slot in 0..4) s = s.toggled(slot)
        assertFalse(s.anyOn)
        assertEquals("", PartnerCard.message(EnglishText, s))
        assertEquals(emptyList<String>(), PartnerCard.spoken(EnglishText, s))
        // ...and an own sentence that is written but off does not count either.
        val withOwn = s.withOwn(own1, "Call my mum.").toggled(own1)
        assertFalse(withOwn.isOn(own1))
        assertFalse(withOwn.anyOn)
        assertEquals("", PartnerCard.message(EnglishText, withOwn))
        // Turning it on makes the card say just that sentence.
        assertEquals("Call my mum.", PartnerCard.message(EnglishText, withOwn.toggled(own1)))
    }

    @Test
    fun anEmptyOwnSlotCannotBeToggled() {
        assertEquals(d, d.toggled(own1))
        assertEquals(d, d.toggled(own2))
        assertEquals(emptySet<Int>(), d.toggled(own1).off)
    }

    // ---- the person's own sentences -----------------------------------------------------------------------------------------------------

    @Test
    fun aNewSentenceStartsOn_andIsSaidAfterTheBuiltInOnes_endingInAFullStop() {
        val s = d.withOwn(own1, "Please call my mum")
        assertEquals("Please call my mum", s.own[0])
        assertTrue(s.isOn(own1))
        assertEquals(five + " Please call my mum.", PartnerCard.message(EnglishText, s))
        val both = s.withOwn(own2, "My name is Sam!")
        assertEquals(five + " Please call my mum. My name is Sam!", PartnerCard.message(EnglishText, both))
    }

    @Test
    fun aChangedSentenceTurnsOn_evenIfItWasOff_andAnUnchangedOneDoesNot() {
        val off = d.withOwn(own1, "Call my mum.").toggled(own1)
        assertFalse(off.isOn(own1))
        assertTrue("a different sentence is on", off.withOwn(own1, "Call my dad.").isOn(own1))
        assertEquals("the same sentence leaves the choice as it was", off, off.withOwn(own1, "  Call my mum.  "))
        assertFalse(off.withOwn(own1, "Call my mum.").isOn(own1))
    }

    @Test
    fun clearingASentenceEmptiesItsSlot_andTheNextSentenceWrittenThereStartsOn() {
        val written = d.withOwn(own1, "Call my mum.")
        val cleared = written.withOwn(own1, "")
        assertEquals(listOf("", ""), cleared.own)
        assertFalse(cleared.isOn(own1))
        assertEquals(five, PartnerCard.message(EnglishText, cleared))
        val offThenCleared = written.toggled(own1).withOwn(own1, "")
        assertEquals("clearing leaves nothing off behind", emptySet<Int>(), offThenCleared.off)
        assertTrue(offThenCleared.withOwn(own1, "Hello.").isOn(own1))
        assertEquals("whitespace is an empty sentence", cleared, written.withOwn(own1, " \n\t "))
    }

    @Test
    fun theOwnSentenceIsSaidExactlyAsWritten_inItsOwnLanguage_andIsNeverTranslated() {
        val arabic = "اتصل بأمي من فضلك."
        val s = d.withOwn(own1, arabic)
        assertEquals(arabic, PartnerCard.spoken(EnglishText, s).last())
        assertEquals(arabic, PartnerCard.spoken(FileText("es"), s).last())
        assertEquals("the built-in ones follow the language of the words", PartnerCard.lines(FileText("es")), PartnerCard.spoken(FileText("es"), s).dropLast(1))
    }

    @Test
    fun theRowsAreTheSevenSentencesInOrder_withTheirState() {
        val s = d.withOwn(own2, "Call my mum").toggled(1)
        val rows = PartnerCard.rows(EnglishText, s)
        assertEquals((0..6).toList(), rows.map { it.slot })
        assertEquals(listOf(false, false, false, false, false, true, true), rows.map { it.own })
        assertEquals(listOf(true, true, true, true, true, false, true), rows.map { it.written })
        assertEquals(listOf(true, false, true, true, true, false, true), rows.map { it.on })
        assertEquals("", rows[5].text)
        assertEquals("Call my mum.", rows[6].text)
        assertEquals(PartnerCard.lines(EnglishText), rows.take(5).map { it.text })
    }

    // ---- tidying: the boundaries -------------------------------------------------------------------------------------------------------

    @Test
    fun anOwnSentenceOfExactlyTheLimitIsKept_oneOverIsCut() {
        val exact = "a".repeat(PartnerCard.MAX_OWN_LENGTH)
        assertEquals(exact, PartnerCard.cleanOwn(exact))
        assertEquals(PartnerCard.MAX_OWN_LENGTH, PartnerCard.cleanOwn(exact + "b").length)
        assertEquals(exact, PartnerCard.cleanOwn(exact + "b"))
        assertEquals(PartnerCard.MAX_OWN_LENGTH, PartnerCard.cleanOwn("a".repeat(5000)).length)
        assertEquals(200, PartnerCard.MAX_OWN_LENGTH)
    }

    @Test
    fun theCutNeverSplitsAnEmoji_andNeverLeavesASpaceAtTheEnd() {
        val emoji = "😀" // two code units
        val fits = "a".repeat(PartnerCard.MAX_OWN_LENGTH - 2) + emoji // exactly the limit
        assertEquals(fits, PartnerCard.cleanOwn(fits))
        val over = "a".repeat(PartnerCard.MAX_OWN_LENGTH - 1) + emoji // one over: the emoji would be split
        val cut = PartnerCard.cleanOwn(over)
        assertEquals("a".repeat(PartnerCard.MAX_OWN_LENGTH - 1), cut)
        assertFalse("no half of an emoji is left", cut.any { Character.isSurrogate(it) })
        val spaced = PartnerCard.cleanOwn("a".repeat(PartnerCard.MAX_OWN_LENGTH - 1) + " b")
        assertEquals("a".repeat(PartnerCard.MAX_OWN_LENGTH - 1), spaced)
    }

    @Test
    fun whatIsTypedIsKeptToTheLimitWithoutSplittingAnEmoji() {
        val emoji = "😀"
        assertEquals("a".repeat(200), PartnerCard.limitDraft("a".repeat(200)))
        assertEquals("a".repeat(200), PartnerCard.limitDraft("a".repeat(201)))
        assertEquals("a".repeat(199), PartnerCard.limitDraft("a".repeat(199) + emoji))
        assertEquals("a".repeat(198) + emoji, PartnerCard.limitDraft("a".repeat(198) + emoji))
        assertEquals("", PartnerCard.limitDraft(""))
        assertEquals("  keep my spaces while I type  ", PartnerCard.limitDraft("  keep my spaces while I type  "))
    }

    @Test
    fun tidyingChangesOnlyWhatMakesASentenceUntidy() {
        assertEquals("hello", PartnerCard.cleanOwn("  hello  "))
        assertEquals("a b", PartnerCard.cleanOwn("a\nb"))
        assertEquals("a b", PartnerCard.cleanOwn("a\r\nb"))
        assertEquals("a b", PartnerCard.cleanOwn("a\t\t  b"))
        assertEquals("a b", PartnerCard.cleanOwn("a b"))
        assertEquals("a b", PartnerCard.cleanOwn("a b"))
        assertEquals("a b", PartnerCard.cleanOwn("a\u0085b"))
        assertEquals("ab", PartnerCard.cleanOwn("a\u0007b"))
        assertEquals("ab", PartnerCard.cleanOwn("a\u0000b"))
        assertEquals("", PartnerCard.cleanOwn(" \n \t \u0007 "))
        assertEquals("", PartnerCard.cleanOwn(""))
        // Capitals, punctuation, other scripts and an emoji joined with the zero-width joiner are the person's own and are left alone.
        for (kept in listOf("PLEASE CALL MY MUM", "Hello, it's me; \"quote\" (aside) 100%!", "مرحبا، اتصل بأمي", "नमस्ते, मेरी मदद करें।", "👨‍👩‍👧")) {
            assertEquals(kept, PartnerCard.cleanOwn(kept))
        }
        // Idempotent.
        for (raw in listOf(" a\nb ", "a".repeat(300), "x\u0007 y")) assertEquals(PartnerCard.cleanOwn(raw), PartnerCard.cleanOwn(PartnerCard.cleanOwn(raw)))
    }

    @Test
    fun aSentenceThatEndsLikeASentenceIsLeftAlone_otherwiseAFullStopIsAdded() {
        for (done in listOf("Hello.", "Hello?", "Hello!", "Hello…", "Hello.\"", "(Hello.)", "He said \"yes.\"", "Hello?!", "你好。", "نعم؟", "नमस्ते।", "مرحبا۔", ".")) {
            assertEquals(done, PartnerCard.terminated(done))
        }
        assertEquals("Hello.", PartnerCard.terminated("Hello"))
        assertEquals("Call my mum.", PartnerCard.terminated("Call my mum"))
        assertEquals("\"Hello\".", PartnerCard.terminated("\"Hello\""))
        assertEquals("", PartnerCard.terminated(""))
    }

    // ---- storage ---------------------------------------------------------------------------------------------------------------------------

    @Test
    fun whatIsStoredIsExactlyThreeValues_andReadsBackTheSame() {
        val s = d.withOwn(own1, "Call my mum").withOwn(own2, "I am Sam.").toggled(0).toggled(own2).toggled(3)
        val stored = s.toStored()
        assertEquals(setOf("own_1", "own_2", "off"), stored.keys)
        assertEquals("0,3,6", stored.getValue("off"))
        assertEquals(s, PartnerCardSettings.fromStored(stored["own_1"], stored["own_2"], stored["off"]))
        assertEquals(d, PartnerCardSettings.fromStored(null, null, null))
        assertEquals(d, PartnerCardSettings.fromStored(d.toStored()["own_1"], d.toStored()["own_2"], d.toStored()["off"]))
        assertEquals("ack_partner_card", PartnerCardSettings.PREFS_FILE)
    }

    @Test
    fun theOffListIsReadStrictly_andNeverThrows() {
        assertEquals(setOf(0, 3, 5), PartnerCardSettings.parseOff("0,3,5"))
        assertEquals(setOf(1, 2), PartnerCardSettings.parseOff(" 1 , 2 "))
        assertEquals(setOf(0, 6), PartnerCardSettings.parseOff("0,6"))
        assertEquals("seven slots only: 7 is out", emptySet<Int>(), PartnerCardSettings.parseOff("7"))
        assertEquals(setOf(2), PartnerCardSettings.parseOff("abc,2,-1,,99,2.5,1e1,007"))
        assertEquals(setOf(1), PartnerCardSettings.parseOff("1,1,1"))
        assertEquals(emptySet<Int>(), PartnerCardSettings.parseOff(null))
        assertEquals(emptySet<Int>(), PartnerCardSettings.parseOff(""))
        assertEquals(emptySet<Int>(), PartnerCardSettings.parseOff("   "))
        assertEquals(emptySet<Int>(), PartnerCardSettings.parseOff("١,٢")) // Arabic-Indic digits are not slot numbers
        assertEquals("0,3,5", PartnerCardSettings.formatOff(setOf(5, 0, 3)))
        assertEquals("", PartnerCardSettings.formatOff(emptySet()))
        assertEquals("2", PartnerCardSettings.formatOff(setOf(2, 9, -4)))
    }

    @Test
    fun aDamagedOwnSentenceIsCleanedNotTrusted() {
        val long = "x".repeat(900) + "\n" + "y".repeat(900)
        val s = PartnerCardSettings.fromStored(long, "  two  \u0007", "4")
        assertEquals(PartnerCard.MAX_OWN_LENGTH, s.own[0].length)
        assertEquals("two", s.own[1])
        assertFalse(s.isOn(4))
        assertTrue(s.isOn(own1))
    }

    @Test
    fun aSavedOffFlagOnAnEmptySlotDoesNotMakeItOn() {
        val s = PartnerCardSettings.fromStored("", "", "5,6")
        assertFalse(s.isOn(own1))
        assertFalse(s.isOn(own2))
        assertTrue(s.anyOn)
    }

    // ---- restore only adds -----------------------------------------------------------------------------------------------------------------

    @Test
    fun restoreFillsEmptySlotsInOrder_andNeverOverwritesASentence() {
        assertEquals(listOf("A.", "B."), PartnerCardSettings.mergeOwn(d, listOf("A.", "B.")).own)
        assertEquals(listOf("X.", "A."), PartnerCardSettings.mergeOwn(d.withOwn(own1, "X."), listOf("A.", "B.")).own)
        assertEquals(listOf("A.", "X."), PartnerCardSettings.mergeOwn(d.withOwn(own2, "X."), listOf("A.", "B.")).own)
        val full = d.withOwn(own1, "X.").withOwn(own2, "Y.")
        assertEquals("both slots written: nothing is replaced", full, PartnerCardSettings.mergeOwn(full, listOf("A.", "B.")))
    }

    @Test
    fun restoreDoesNotAddTheSameSentenceTwice_andIgnoresBlanksAndExtras() {
        assertEquals(listOf("A.", "B."), PartnerCardSettings.mergeOwn(d.withOwn(own1, "A."), listOf("A.", "B.")).own)
        assertEquals(listOf("A.", ""), PartnerCardSettings.mergeOwn(d, listOf("A.", "A.", "  ")).own)
        assertEquals(listOf("A.", "B."), PartnerCardSettings.mergeOwn(d, listOf("", "A.", "B.", "C.")).own)
        assertEquals("a dirty sentence is tidied on the way in", listOf("a b", ""), PartnerCardSettings.mergeOwn(d, listOf("a\nb")).own)
        assertEquals(d, PartnerCardSettings.mergeOwn(d, emptyList()))
    }

    @Test
    fun restoreLeavesTheOnOffChoicesAlone() {
        val s = d.toggled(0).toggled(4).withOwn(own1, "X.").toggled(own1)
        val merged = PartnerCardSettings.mergeOwn(s, listOf("A.", "B."))
        assertEquals(s.off, merged.off)
        assertEquals(listOf("X.", "A."), merged.own)
        assertTrue("a restored sentence goes in on (it was never turned off here)", merged.isOn(own2))
    }

    // ---- the backup's own shape -------------------------------------------------------------------------------------------------------------

    @Test
    fun aBackupHoldsAtMostTwoCleanLines_ofAtMostTheLimit() {
        assertNull(PartnerCardBackup().validate())
        assertNull(PartnerCardBackup(listOf("A.")).validate())
        assertNull(PartnerCardBackup(listOf("A.", "B.")).validate())
        assertNull(PartnerCardBackup(listOf("", "")).validate())
        assertNull(PartnerCardBackup(listOf("a".repeat(PartnerCard.MAX_OWN_LENGTH))).validate())
        assertNotNull(PartnerCardBackup(listOf("A.", "B.", "C.")).validate())
        assertNotNull(PartnerCardBackup(listOf("a".repeat(PartnerCard.MAX_OWN_LENGTH + 1))).validate())
        assertNotNull(PartnerCardBackup(listOf("a\nb")).validate())
        assertNotNull(PartnerCardBackup(listOf(" padded ")).validate())
        assertNotNull(PartnerCardBackup(listOf("a\u0007b")).validate())
    }

    @Test
    fun aFileTheAppWroteAlwaysPasses_becauseTheCheckIsTheScreensOwnRule() {
        for (raw in listOf("Call my mum", "a".repeat(5000), " a\n\nb ", "😀".repeat(300), "x\u0007y", "")) {
            val kept = PartnerCard.cleanOwn(raw)
            assertNull(raw.take(10), PartnerCardBackup(listOf(kept)).validate())
        }
    }

    @Test
    fun aRefusalNeverContainsTheSentence_onlySizes() {
        val secret = "SECRETSENTENCE"
        val reasons = listOf(
            PartnerCardBackup(listOf(secret, secret, secret)).validate(),
            PartnerCardBackup(listOf(secret + "a".repeat(PartnerCard.MAX_OWN_LENGTH))).validate(),
            PartnerCardBackup(listOf(secret + "\n")).validate(),
            PartnerCardBackup(listOf(" $secret ")).validate(),
        )
        for (reason in reasons) {
            assertNotNull(reason)
            assertFalse("the reason holds the sentence: $reason", reason!!.contains("SECRET"))
        }
        assertTrue(reasons[0]!!.contains("3 entries"))
        assertTrue(reasons[1]!!.contains("${PartnerCard.MAX_OWN_LENGTH + secret.length} characters"))
    }

    @Test
    fun theBackupIsOneFieldInTheJson_andAnOlderOrEmptyOneReadsAsNothing() {
        val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
        assertEquals("{\"ownSentences\":[\"A.\",\"B.\"]}", json.encodeToString(PartnerCardBackup(listOf("A.", "B."))))
        assertEquals(PartnerCardBackup(), json.decodeFromString<PartnerCardBackup>("{}"))
        assertEquals(PartnerCardBackup(listOf("A.")), json.decodeFromString<PartnerCardBackup>("{\"ownSentences\":[\"A.\"],\"somethingNewer\":1}"))
    }
}
