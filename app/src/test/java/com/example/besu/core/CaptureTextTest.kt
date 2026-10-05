// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import com.example.besu.capture.CaptureConstants
import com.example.besu.capture.CaptureNotice
import com.example.besu.capture.ClipFlags
import com.example.besu.capture.ClipState
import com.example.besu.capture.DiskRoom
import com.example.besu.capture.NoiseVerdict
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the RECORD TRAINING DATA screens say that is decided (the library's lines and notices, the script editor's counts, a session's and a clip's lines, the messages after a save), in English exactly as it
 * always was and in every language. A session's mode, a mark's id and a clip's state are stored and read by the computer, so only the word drawn for them follows the language; the person's own text (a script's
 * title, a session's name) and what the storage layer says are shown as they come, and no value is ever used as a format.
 */
class CaptureTextTest {

    private val t = EnglishText
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val english get() = StringsXml.map(StringsXml.default)
    private fun count(text: String, part: String) = Regex(Regex.escape(part)).findAll(text).count()
    private val awkward = "100% %s %d \$1 \"q\"\nline"
    private val languages: List<Pair<String, TextSource>> get() = translations.keys.map { it to FileText(it) as TextSource }

    // ---- English is exactly what the screens always said -------------------------------------------------------------------------------

    @Test
    fun theLibraryEnglishIsExactlyWhatItAlwaysSaid() {
        assertEquals("NEW: RECORD TRAINING DATA HAS A HELP WALKTHROUGH. FIND IT UNDER HELP ANYTIME.", CaptureText.helpOffer(t, "HELP", "RECORD TRAINING DATA"))
        assertEquals("ON THIS PHONE: 3 SESSIONS, 1.0 MB USED, 4000.0 MB FREE", CaptureText.phoneLine(t, 3, "1.0 MB", "4000.0 MB"))
        assertEquals(
            "THE APP CLOSED BEFORE 2 SESSION(S) WERE ENDED. 3 UNFINISHED RECORDING(S) WERE REPAIRED AND ARE HELD BACK UNTIL YOU LISTEN AND KEEP THEM (OPEN THE SESSION).",
            CaptureText.recoveryNotice(t, 2, 3, emptyList()),
        )
        assertEquals("SOME RECORDINGS COULD NOT BE REPAIRED: disk full", CaptureText.recoveryNotice(t, 2, 3, listOf("disk full", "second")))
        assertEquals(
            "COULD NOT READ: script a1, session b2. THEIR FILES WERE LEFT AS THEY ARE.",
            CaptureText.damagedNotice(t, listOf(CaptureText.Damaged(CaptureText.DamagedKind.SCRIPT, "a1"), CaptureText.Damaged(CaptureText.DamagedKind.SESSION, "b2"))),
        )
        assertEquals("5 CARDS, 2 RECORDED", CaptureText.scriptCardsLine(t, 5, 2))
        assertEquals("5 CARDS, 5 RECORDED (ALL DONE)", CaptureText.scriptCardsLine(t, 5, 5))
        assertEquals("0 CARDS, 0 RECORDED", CaptureText.scriptCardsLine(t, 0, 0))
        assertEquals("1 CARDS, 0 RECORDED", CaptureText.scriptCardsLine(t, 1, 0))
        assertEquals("TALK ABOUT ANYTHING FOR AS LONG AS YOU LIKE (UP TO 90 MINUTES). THE AUDIO IS KEPT WHOLE; THE PHONE ONLY SUGGESTS WHERE IT COULD BE CUT, AND THE COMPUTER DECIDES.", CaptureText.freeIntro(t, 90))
        assertEquals("2026-01-02 03:04:05 UTC  //  3 KEPT  //  1.0 MB", CaptureText.sessionLine(t, "2026-01-02T03:04:05Z", "script", 3, null, 1_048_576L, closed = true))
        assertEquals("2026-01-02 03:04:05 UTC  //  1:05  //  2.0 MB", CaptureText.sessionLine(t, "2026-01-02T03:04:05Z", "free", 0, 65.0, 2_097_152L, closed = true))
        assertEquals("2026-01-02 03:04:05 UTC  //  NO RECORDING  //  0.0 MB  //  NOT ENDED", CaptureText.sessionLine(t, "2026-01-02T03:04:05Z", "free", 0, null, 0L, closed = false))
        assertEquals("2 RECORDING(S) WAITING FOR YOU TO LISTEN AND DECIDE", CaptureText.heldLine(t, 2))
        assertEquals("SAVING FILE 2 OF 3... THEN CHECKING IT", CaptureText.savingLine(t, 2, 3))
        assertEquals("1.0 MB OF 2.0 MB OF AUDIO", CaptureText.savingBytes(t, 1_048_576L, 2_097_152L))
        assertEquals(
            "THIS REMOVES 1.0 MB OF RECORDINGS FROM THIS PHONE. IF YOU HAVE NOT SAVED A PACKAGE AND CHECKED IT ON YOUR COMPUTER, THEY ARE GONE FOR GOOD.",
            CaptureText.deleteSessionBody(t, 1_048_576L),
        )
        assertEquals(
            "THIS REMOVES ITS RECORDINGS FROM THIS PHONE. IF YOU HAVE NOT SAVED A PACKAGE AND CHECKED IT ON YOUR COMPUTER, THEY ARE GONE FOR GOOD.",
            CaptureText.deleteSessionBody(t, null),
        )
    }

    @Test
    fun aSessionsHeadingIsItsScriptsTitleAsSavedOrTheModesWord_thenTheNameThePersonGaveIt() {
        assertEquals("My Script // night", CaptureText.sessionTitle(t, "script", "My Script", "night"))
        assertEquals("SCRIPT", CaptureText.sessionTitle(t, "script", null, ""))
        assertEquals("FREE SPEECH", CaptureText.sessionTitle(t, "free", null, ""))
        assertEquals("FREE SPEECH // x", CaptureText.sessionTitle(t, "free", "ignored title", "x"))
        // A title typed as the word SCRIPT is the person's own and is not mistaken for the default.
        assertEquals("SCRIPT // a", CaptureText.sessionTitle(t, "script", "SCRIPT", "a"))
        // A mode this build does not know reads as free speech, as it always did (the stored word is never drawn).
        assertEquals("FREE SPEECH", CaptureText.sessionTitle(t, "other", "T", ""))
    }

    @Test
    fun theSaveNoticesInEnglishAreExactlyWhatTheyAlwaysSaid() {
        assertEquals("THERE IS NOTHING TO SAVE YET: NO KEPT CLIPS IN THE CHOSEN SESSIONS.", CaptureText.saveNotice(t, CaptureText.SaveNotice.NothingToSave))
        assertEquals(
            "A SESSION IS TOO BIG FOR ONE FILE: a, b. IT CAN BE DELETED OR LEFT; THE REST CAN BE SAVED ONE AT A TIME.",
            CaptureText.saveNotice(t, CaptureText.SaveNotice.TooBig(listOf("a", "b"))),
        )
        assertEquals("THE FILE COULD NOT BE OPENED FOR WRITING.", CaptureText.saveNotice(t, CaptureText.SaveNotice.CouldNotOpen))
        assertEquals("THE SAVED FILE COULD NOT BE READ BACK, SO IT WAS REMOVED. NOTHING WAS LOST FROM THE PHONE.", CaptureText.saveNotice(t, CaptureText.SaveNotice.CouldNotReadBack))
        assertEquals("THE SAVED FILE FAILED ITS CHECK (bad sum), SO IT WAS REMOVED. NOTHING WAS LOST FROM THE PHONE.", CaptureText.saveNotice(t, CaptureText.SaveNotice.FailedCheck("bad sum")))
        assertEquals("THE PACKAGE COULD NOT BE MADE.", CaptureText.saveNotice(t, CaptureText.SaveNotice.CouldNotMake(null)))
        assertEquals("a technical sentence", CaptureText.saveNotice(t, CaptureText.SaveNotice.CouldNotMake("a technical sentence")))
        assertEquals("SAVING FAILED: boom. NOTHING WAS LOST FROM THE PHONE.", CaptureText.saveNotice(t, CaptureText.SaveNotice.Failed("boom")))
    }

    @Test
    fun theScriptEditorEnglishIsExactlyWhatItAlwaysSaid() {
        assertEquals("120 OF 20000 CHARACTERS", CaptureText.charsLine(t, 120, 20000))
        assertEquals("A LINE BREAK IS JUST A SPACE; A BLANK LINE STARTS A NEW PARAGRAPH.", CaptureText.lineBreakNote(t, "join"))
        assertEquals("EVERY LINE IS ITS OWN PARAGRAPH, SO NO CARD RUNS ACROSS TWO LINES.", CaptureText.lineBreakNote(t, "keep"))
        assertEquals("10 CARDS, ABOUT 2 MINUTES AT 2.5 WORDS A SECOND (A TYPICAL PACE; THE PHONE LEARNS YOURS)", CaptureText.cardsSummary(t, 10, 2.4, 2.5, measured = false))
        assertEquals("10 CARDS, ABOUT 3 MINUTES AT 2.5 WORDS A SECOND (YOUR PACE)", CaptureText.cardsSummary(t, 10, 2.5, 2.5, measured = true))
        assertEquals("3 CARD(S) HAVE DIGITS OR SYMBOLS. IF YOU WOULD SAY THEM DIFFERENTLY, REWRITE THEM AS WORDS.", CaptureText.symbolCards(t, 3))
        assertEquals("...AND 4 MORE", CaptureText.andMore(t, 4))
        assertEquals("THE LANGUAGE CODE SHOULD LOOK LIKE EN-US.", CaptureText.languageCodeBad(t, "EN-US"))
        assertEquals(
            "THE SCRIPT \"Mine\" WILL BE REPLACED BY WHAT IS ON THIS SCREEN. RECORDINGS ALREADY MADE FROM IT ARE NOT CHANGED.",
            CaptureText.saveChangesBody(t, "Mine"),
        )
        assertEquals(
            "THE SCRIPT \"\" WILL BE REPLACED BY WHAT IS ON THIS SCREEN. RECORDINGS ALREADY MADE FROM IT ARE NOT CHANGED.",
            CaptureText.saveChangesBody(t, null),
        )
    }

    @Test
    fun theSessionDetailEnglishIsExactlyWhatItAlwaysSaid() {
        assertEquals("s1  //  44.1 KHZ  //  UNPROCESSED  //  ROOM -52.5 DB  //  NOT ENDED", CaptureText.detailsLine(t, "s1", 44100, "UNPROCESSED", -52.5, closed = false))
        assertEquals("s1  //  48.0 KHZ  //  UNPROCESSED", CaptureText.detailsLine(t, "s1", 48000, "UNPROCESSED", null, closed = true))
        assertEquals("1:05 RECORDED, 3 SUGGESTED PIECE(S)  //  KEPT", CaptureText.recordingLine(t, 65.0, 3, ClipState.DONE))
        assertEquals("1:05 RECORDED, 3 SUGGESTED PIECE(S)  //  REPAIRED, WAITING FOR YOU", CaptureText.recordingLine(t, 65.0, 3, ClipState.RECOVERED))
        assertEquals("1:05 RECORDED, 3 SUGGESTED PIECE(S)  //  UNFINISHED", CaptureText.recordingLine(t, 65.0, 3, ClipState.OPEN))
        assertEquals("1:01:01 RECORDED, 0 SUGGESTED PIECE(S)  //  KEPT", CaptureText.recordingLine(t, 3661.0, 0, ClipState.DONE))
        assertEquals("CARD 2, TRY 1  //  3.2 S  //  KEPT", CaptureText.clipLine(t, 2, 1, 3.24, ClipState.DONE))
        assertEquals("CARD 2, TRY 1  //  3.3 S  //  SET ASIDE", CaptureText.clipLine(t, 2, 1, 3.25, ClipState.REDONE))
        assertEquals("CARD 2, TRY 2  //  0.0 S  //  REPAIRED: LISTEN AND DECIDE", CaptureText.clipLine(t, 2, 2, 0.0, ClipState.RECOVERED))
        assertEquals("CARD 2, TRY 2  //  0.0 S  //  UNFINISHED", CaptureText.clipLine(t, 2, 2, 0.0, ClipState.OPEN))
        assertEquals("3 KEPT, 2 SET ASIDE OR WAITING", CaptureText.keptAside(t, 3, 2))
    }

    @Test
    fun theMarkWordsAreTheStoredIdsInCapitalsInEnglish_andAnUnknownMarkIsShownAsItsOwnId() {
        for (id in ClipFlags.PERSON + listOf("long", "short", "no_end")) assertEquals(id.uppercase(), CaptureText.markWord(t, id))
        // A mark this build has no word for (one the person's computer added) is shown as its id in capitals, as it always was.
        assertEquals("FUTURE_MARK", CaptureText.markWord(t, "future_mark"))
        assertEquals("NOTES: LONG, NO_END", CaptureText.notesLine(t, listOf("long", "noise", "no_end")))
        assertEquals("NOTES: ", CaptureText.notesLine(t, listOf("noise", "cough")))
        assertEquals("NOTES: SHORT, FUTURE_MARK", CaptureText.notesLine(t, listOf("short", "future_mark", "laugh")))
    }

    @Test
    fun theNumbersAreWrittenAsTheyAlwaysWere() {
        assertEquals("0.0 MB", CaptureText.megabytes(0L))
        assertEquals("1.5 MB", CaptureText.megabytes(1_572_864L))
        assertEquals("0:00", CaptureText.clock(0.0))
        assertEquals("0:59", CaptureText.clock(59.9))
        assertEquals("1:00", CaptureText.clock(60.0))
        assertEquals("59:59", CaptureText.clock(3599.0))
        assertEquals("1:00:00", CaptureText.clock(3600.0))
        assertEquals("1.0", CaptureText.oneDecimal(0.96))
        assertEquals("0", CaptureText.wholeNumber(0.49))
        assertEquals("1", CaptureText.wholeNumber(0.5))
    }

    // ---- every language ---------------------------------------------------------------------------------------------------------------

    @Test
    fun everyDecisionReadsInTheLanguage_andNeverTheEnglish() {
        for ((tag, f) in languages) {
            val pairs = mapOf(
                "helpOffer" to (CaptureText.helpOffer(f, "HHH", "SSS") to CaptureText.helpOffer(t, "HHH", "SSS")),
                "phoneLine" to (CaptureText.phoneLine(f, 3, "1.0 MB", "2.0 MB") to CaptureText.phoneLine(t, 3, "1.0 MB", "2.0 MB")),
                "recoveryNotice" to (CaptureText.recoveryNotice(f, 2, 3, emptyList()) to CaptureText.recoveryNotice(t, 2, 3, emptyList())),
                "recoveryProblem" to (CaptureText.recoveryNotice(f, 2, 3, listOf("x")) to CaptureText.recoveryNotice(t, 2, 3, listOf("x"))),
                "damaged" to (CaptureText.damagedNotice(f, listOf(CaptureText.Damaged(CaptureText.DamagedKind.SCRIPT, "a"))) to CaptureText.damagedNotice(t, listOf(CaptureText.Damaged(CaptureText.DamagedKind.SCRIPT, "a")))),
                "scriptCards" to (CaptureText.scriptCardsLine(f, 5, 2) to CaptureText.scriptCardsLine(t, 5, 2)),
                "freeIntro" to (CaptureText.freeIntro(f, 90) to CaptureText.freeIntro(t, 90)),
                "kept" to (CaptureText.sessionLine(f, "2026-01-02T03:04:05Z", "script", 3, null, 0L, true) to CaptureText.sessionLine(t, "2026-01-02T03:04:05Z", "script", 3, null, 0L, true)),
                "held" to (CaptureText.heldLine(f, 2) to CaptureText.heldLine(t, 2)),
                "saving" to (CaptureText.savingLine(f, 2, 3) to CaptureText.savingLine(t, 2, 3)),
                "savingBytes" to (CaptureText.savingBytes(f, 1L, 2L) to CaptureText.savingBytes(t, 1L, 2L)),
                "deleteBody" to (CaptureText.deleteSessionBody(f, 5L) to CaptureText.deleteSessionBody(t, 5L)),
                "deleteBodyUnknown" to (CaptureText.deleteSessionBody(f, null) to CaptureText.deleteSessionBody(t, null)),
                "chars" to (CaptureText.charsLine(f, 1, 2) to CaptureText.charsLine(t, 1, 2)),
                "joinNote" to (CaptureText.lineBreakNote(f, "join") to CaptureText.lineBreakNote(t, "join")),
                "keepNote" to (CaptureText.lineBreakNote(f, "keep") to CaptureText.lineBreakNote(t, "keep")),
                "cardsTypical" to (CaptureText.cardsSummary(f, 1, 2.0, 3.0, false) to CaptureText.cardsSummary(t, 1, 2.0, 3.0, false)),
                "cardsOwn" to (CaptureText.cardsSummary(f, 1, 2.0, 3.0, true) to CaptureText.cardsSummary(t, 1, 2.0, 3.0, true)),
                "symbols" to (CaptureText.symbolCards(f, 2) to CaptureText.symbolCards(t, 2)),
                "andMore" to (CaptureText.andMore(f, 2) to CaptureText.andMore(t, 2)),
                "languageCode" to (CaptureText.languageCodeBad(f, "EN-US") to CaptureText.languageCodeBad(t, "EN-US")),
                "saveChanges" to (CaptureText.saveChangesBody(f, "T") to CaptureText.saveChangesBody(t, "T")),
                "recordingLine" to (CaptureText.recordingLine(f, 5.0, 1, ClipState.DONE) to CaptureText.recordingLine(t, 5.0, 1, ClipState.DONE)),
                "clipLine" to (CaptureText.clipLine(f, 1, 1, 1.0, ClipState.DONE) to CaptureText.clipLine(t, 1, 1, 1.0, ClipState.DONE)),
                "keptAside" to (CaptureText.keptAside(f, 1, 2) to CaptureText.keptAside(t, 1, 2)),
                "notes" to (CaptureText.notesLine(f, listOf("long")) to CaptureText.notesLine(t, listOf("long"))),
                "title" to (CaptureText.sessionTitle(f, "free", null, "") to CaptureText.sessionTitle(t, "free", null, "")),
            )
            for ((what, both) in pairs) assertNotEquals("$tag/$what is still English: ${both.first}", both.second, both.first)
            for (notice in listOf(CaptureText.SaveNotice.NothingToSave, CaptureText.SaveNotice.CouldNotOpen, CaptureText.SaveNotice.CouldNotReadBack, CaptureText.SaveNotice.CouldNotMake(null))) {
                assertNotEquals("$tag/$notice is still English", CaptureText.saveNotice(t, notice), CaptureText.saveNotice(f, notice))
            }
            assertNotEquals("$tag/FailedCheck", CaptureText.saveNotice(t, CaptureText.SaveNotice.FailedCheck("x")), CaptureText.saveNotice(f, CaptureText.SaveNotice.FailedCheck("x")))
            assertNotEquals("$tag/Failed", CaptureText.saveNotice(t, CaptureText.SaveNotice.Failed("x")), CaptureText.saveNotice(f, CaptureText.SaveNotice.Failed("x")))
            assertNotEquals("$tag/TooBig", CaptureText.saveNotice(t, CaptureText.SaveNotice.TooBig(listOf("x"))), CaptureText.saveNotice(f, CaptureText.SaveNotice.TooBig(listOf("x"))))
        }
    }

    @Test
    fun theNumbersAndSeparatorsInALineAreTheAppsOwn_inEveryLanguage() {
        for ((tag, f) in languages) {
            // Latin digits and the app's own separators and units, whatever the language: a size, a clock, the sample rate and the room level are symbols, not words.
            val line = CaptureText.sessionLine(f, "2026-01-02T03:04:05Z", "free", 0, 3661.0, 1_572_864L, closed = false)
            assertTrue("$tag: $line", line.startsWith("2026-01-02 03:04:05 UTC  //  1:01:01  //  1.5 MB  //  "))
            assertEquals("$tag: three separators in $line", 3, count(line, "  //  "))
            val details = CaptureText.detailsLine(f, "id-1", 44100, "UNPROCESSED", -52.5, closed = false)
            assertTrue("$tag: $details", details.startsWith("id-1  //  44.1 KHZ  //  UNPROCESSED  //  "))
            assertTrue("$tag: the room level is a number with its own words around it: $details", details.contains("-52.5"))
            assertEquals("$tag: four separators in $details", 4, count(details, "  //  "))
            val clip = CaptureText.clipLine(f, 12, 3, 4.56, ClipState.DONE)
            assertTrue("$tag: $clip", clip.contains("12") && clip.contains("3") && clip.contains("  //  4.6 S  //  "))
            assertEquals("$tag: two separators in $clip", 2, count(clip, "  //  "))
            val recording = CaptureText.recordingLine(f, 3661.0, 7, ClipState.DONE)
            assertTrue("$tag: $recording", recording.contains("1:01:01") && recording.contains("7"))
            assertEquals("$tag: one separator in $recording", 1, count(recording, "  //  "))
            assertTrue("$tag: sizes are written by the app: ${CaptureText.savingBytes(f, 1_048_576L, 2_097_152L)}", CaptureText.savingBytes(f, 1_048_576L, 2_097_152L).let { it.contains("1.0 MB") && it.contains("2.0 MB") })
            val phone = CaptureText.phoneLine(f, 3, "12.5 MB", "4000.0 MB")
            assertTrue("$tag: $phone", phone.contains("3") && phone.contains("12.5 MB") && phone.contains("4000.0 MB"))
        }
    }

    @Test
    fun aValueTheStorageLayerOrThePersonGaveIsShownExactlyAsItCame_neverUsedAsAFormat_inEveryLanguage() {
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val v = awkward
            // The HELP button's name is in the sentence as many times as its resource says (the English says it twice); the screen's name is in it once.
            val helpNames = StringsXml.placeholders(if (tag == "en") english.getValue("capture_help_offer") else translations.getValue(tag).getValue("capture_help_offer")).count { it == "%1\$s" }
            assertEquals("$tag: help names", helpNames, count(CaptureText.helpOffer(f, v, "SSS"), v))
            assertEquals("$tag: help screen", 1, count(CaptureText.helpOffer(f, "HHH", v), v))
            assertEquals("$tag: recovery problem", 1, count(CaptureText.recoveryNotice(f, 1, 1, listOf(v)), v))
            assertEquals("$tag: damaged name", 1, count(CaptureText.damagedNotice(f, listOf(CaptureText.Damaged(CaptureText.DamagedKind.SESSION, v))), v))
            assertEquals("$tag: script title", 1, count(CaptureText.sessionTitle(f, "script", v, ""), v))
            assertEquals("$tag: session label", 1, count(CaptureText.sessionTitle(f, "free", null, v), v))
            assertEquals("$tag: id", 1, count(CaptureText.detailsLine(f, v, 44100, "UNPROCESSED", null, true), v))
            assertEquals("$tag: source", 1, count(CaptureText.detailsLine(f, "id", 44100, v, null, true), v))
            assertEquals("$tag: save title", 1, count(CaptureText.saveChangesBody(f, v), v))
            assertEquals("$tag: language example", 1, count(CaptureText.languageCodeBad(f, v), v))
            assertEquals("$tag: too big", 1, count(CaptureText.saveNotice(f, CaptureText.SaveNotice.TooBig(listOf(v))), v))
            assertEquals("$tag: failed check", 1, count(CaptureText.saveNotice(f, CaptureText.SaveNotice.FailedCheck(v)), v))
            assertEquals("$tag: failed", 1, count(CaptureText.saveNotice(f, CaptureText.SaveNotice.Failed(v)), v))
            assertEquals("$tag: could not make (the layer's own sentence, not wrapped)", v, CaptureText.saveNotice(f, CaptureText.SaveNotice.CouldNotMake(v)))
        }
    }

    @Test
    fun aSavedTitleIsShownTrimmedOfNothingAndItsQuotesAreTheStraightOnes_inEveryLanguage() {
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val body = CaptureText.saveChangesBody(f, "  Padded  ")
            assertTrue("$tag: the title as saved, in straight quotes: $body", body.contains("\"  Padded  \""))
        }
    }

    @Test
    fun theStoredIdsAreNeverDrawnAsTranslatedWords_andEveryMarkHasAShortWord_inEveryLanguage() {
        val ids = ClipFlags.PERSON.toList() + listOf("long", "short", "no_end")
        for ((tag, f) in languages) {
            val drawn = ids.map { CaptureText.markWord(f, it) }
            for ((id, word) in ids.zip(drawn)) {
                assertTrue("$tag/$id has a word", word.isNotBlank())
                assertTrue("$tag/$id: '$word' fits a button three across (14 characters at most)", word.length <= 14)
                assertFalse("$tag/$id: a stored id is not shown as an underscore name: $word", word.contains("_") && id != "no_end")
                assertNotEquals("$tag/$id is still English", CaptureText.markWord(t, id), word)
            }
            assertEquals("$tag: eight marks, eight different words", 8, drawn.toSet().size)
            // The unknown mark is the id in capitals in every language: the word is the computer's, not ours.
            assertEquals("$tag: unknown mark", "FUTURE_MARK", CaptureText.markWord(f, "future_mark"))
        }
    }

    @Test
    fun theNotesLineHoldsOnlyTheAutomaticMarks_inTheLanguage_inTheOrderGiven() {
        for ((tag, f) in languages) {
            val line = CaptureText.notesLine(f, listOf("short", "noise", "long", "future_mark", "cough"))
            val expected = listOf("short", "long", "future_mark").joinToString(", ") { CaptureText.markWord(f, it) }
            assertTrue("$tag: $line", line.contains(expected))
            for (person in listOf("noise", "cough")) assertFalse("$tag: the person's own mark $person is not a note", line.contains(CaptureText.markWord(f, person)))
        }
    }

    @Test
    fun aRecordingAndAClipEachHaveAStateWord_andAnUnknownStateIsUnfinished_inEveryLanguage() {
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val clip = listOf(ClipState.DONE, ClipState.REDONE, ClipState.RECOVERED, ClipState.OPEN).map { CaptureText.clipState(f, it) }
            assertEquals("$tag: four clip states, four words", 4, clip.toSet().size)
            val recording = listOf(ClipState.DONE, ClipState.RECOVERED, ClipState.OPEN).map { CaptureText.recordingState(f, it) }
            assertEquals("$tag: three recording states, three words", 3, recording.toSet().size)
            assertEquals("$tag: unknown clip state", CaptureText.clipState(f, ClipState.OPEN), CaptureText.clipState(f, "SOMETHING_NEW"))
            assertEquals("$tag: unknown recording state", CaptureText.recordingState(f, ClipState.OPEN), CaptureText.recordingState(f, "SOMETHING_NEW"))
            // A recording that is REDONE is not a thing (only clips are redone); it reads as unfinished, as it always did.
            assertEquals("$tag: redone recording", CaptureText.recordingState(f, ClipState.OPEN), CaptureText.recordingState(f, ClipState.REDONE))
        }
    }

    @Test
    fun aScriptsCardsLineSaysAllDoneOnlyWhenEveryCardHasAClip_inEveryLanguage() {
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val allDone = f.get("capture_all_done")
            assertEquals("$tag: every card has a clip", f.get("capture_script_cards", 4, 4) + " " + allDone, CaptureText.scriptCardsLine(f, 4, 4))
            assertEquals("$tag: one card short", f.get("capture_script_cards", 4, 3), CaptureText.scriptCardsLine(f, 4, 3))
            assertEquals("$tag: more clips than cards is still all done", f.get("capture_script_cards", 4, 5) + " " + allDone, CaptureText.scriptCardsLine(f, 4, 5))
            assertEquals("$tag: a script with no cards is not all done", f.get("capture_script_cards", 0, 0), CaptureText.scriptCardsLine(f, 0, 0))
            assertTrue("$tag: all-done words are not empty", allDone.isNotBlank())
        }
    }

    @Test
    fun theLineBreakSettingIsReadFromItsStoredValue_notFromAWord() {
        // join and keep are what the script file stores; any other stored value reads as keep, as the screen always did.
        for ((_, f) in listOf("en" to t as TextSource) + languages) {
            assertEquals(CaptureText.lineBreakNote(f, "keep"), CaptureText.lineBreakNote(f, "anything else"))
            assertNotEquals(CaptureText.lineBreakNote(f, "join"), CaptureText.lineBreakNote(f, "keep"))
        }
    }

    @Test
    fun theTwoCardSummariesDifferOnlyInWhoseThePaceIs_inEveryLanguage() {
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val typical = CaptureText.cardsSummary(f, 12, 3.0, 2.5, measured = false)
            val own = CaptureText.cardsSummary(f, 12, 3.0, 2.5, measured = true)
            assertNotEquals("$tag", typical, own)
            for (summary in listOf(typical, own)) {
                assertEquals("$tag: the card count once in '$summary'", 1, count(summary, "12"))
                assertEquals("$tag: the minutes once in '$summary'", 1, count(summary, "3"))
                assertEquals("$tag: the pace once in '$summary'", 1, count(summary, "2.5"))
            }
        }
    }

    // ---- the recording screen ---------------------------------------------------------------------------------------------------------

    private val lrm = "\u200e"

    @Test
    fun theRecordingScreenEnglishIsExactlyWhatItAlwaysSaid() {
        assertEquals("10 CARDS", CaptureText.setupCardsLine(t, 10, 10, includeDone = false))
        assertEquals("10 CARDS, 4 ALREADY RECORDED. THIS SESSION STARTS AT THE FIRST ONE THAT IS NOT.", CaptureText.setupCardsLine(t, 10, 6, includeDone = false))
        assertEquals("including the recorded ones, nothing is skipped", "10 CARDS", CaptureText.setupCardsLine(t, 10, 6, includeDone = true))
        assertEquals("0 CARDS", CaptureText.setupCardsLine(t, 0, 0, includeDone = false))
        assertEquals("INCLUDING CARDS ALREADY RECORDED", CaptureText.includeDoneLabel(t, includeDone = true, allDone = false))
        assertEquals("INCLUDING CARDS ALREADY RECORDED", CaptureText.includeDoneLabel(t, includeDone = false, allDone = true))
        assertEquals("SKIPPING CARDS ALREADY RECORDED", CaptureText.includeDoneLabel(t, includeDone = false, allDone = false))
        assertEquals("CARDS ARE SIZED FOR 2.6 WORDS A SECOND (YOUR PACE).", CaptureText.paceLine(t, 2.6, own = true))
        assertEquals("CARDS ARE SIZED FOR 2.6 WORDS A SECOND (A TYPICAL PACE; THE PHONE LEARNS YOURS FROM WHAT YOU KEEP).", CaptureText.paceLine(t, 2.6, own = false))
        assertEquals("1.2 SECONDS OF QUIET ENDS A CARD. RAISE IT IF YOU PAUSE A LOT IN THE MIDDLE OF A SENTENCE.", CaptureText.waitNote(t, 120))
        assertEquals("0.5 SECONDS OF QUIET ENDS A CARD. RAISE IT IF YOU PAUSE A LOT IN THE MIDDLE OF A SENTENCE.", CaptureText.waitNote(t, 50))
        assertEquals("START QUIET CHECK (2 SECONDS)", CaptureText.startQuietLabel(t))
        assertEquals(
            "THE AUDIO IS KEPT WHOLE. WHEN YOU STOP, THE PHONE SUGGESTS WHERE IT COULD BE CUT AND THE COMPUTER DECIDES. IT STOPS BY ITSELF AT 90 MINUTES OR WHEN THE PHONE IS NEARLY FULL, KEEPING EVERYTHING.",
            CaptureText.freeNote(t),
        )
        assertEquals("ROOM LEVEL -60.8 dB: GOOD.", CaptureText.noiseVerdict(t, NoiseVerdict.GOOD, -60.8))
        assertEquals("ROOM LEVEL -24.0 dB: LOUD. QUIET WORDS MAY BE MISSED. A QUIETER SPOT WILL GIVE BETTER TRAINING DATA.", CaptureText.noiseVerdict(t, NoiseVerdict.LOUD_ROOM, -24.0))
        assertEquals("NOTHING WAS HEARD. IS THE MICROPHONE COVERED OR MUTED?", CaptureText.noiseVerdict(t, NoiseVerdict.NO_SIGNAL, -120.0))
        assertEquals("A SOUND INTERRUPTED THE QUIET CHECK. STAY QUIET AND TRY AGAIN.", CaptureText.noiseVerdict(t, NoiseVerdict.INTERRUPTED, -50.0))
        assertEquals("CARD 3 OF 10", CaptureText.cardHeading(t, 3, 10, attempt = 1))
        assertEquals("CARD 3 OF 10  (TRY 2)", CaptureText.cardHeading(t, 3, 10, attempt = 2))
        assertEquals("2 KEPT, 3 LEFT", CaptureText.keptLeft(t, 2, 3))
        assertEquals("PAUSED", CaptureText.scriptStatus(t, paused = true, inSpeech = false))
        assertEquals("a pause wins over hearing", "PAUSED", CaptureText.scriptStatus(t, paused = true, inSpeech = true))
        assertEquals("HEARING YOU...", CaptureText.scriptStatus(t, paused = false, inSpeech = true))
        assertEquals("LISTENING. READ THE CARD WHEN YOU ARE READY.", CaptureText.scriptStatus(t, paused = false, inSpeech = false))
        assertEquals("PAUSED", CaptureText.freeStatus(t, paused = true, inSpeech = true))
        assertEquals("RECORDING. HEARING YOU...", CaptureText.freeStatus(t, paused = false, inSpeech = true))
        assertEquals("RECORDING. TALK WHENEVER YOU LIKE.", CaptureText.freeStatus(t, paused = false, inSpeech = false))
        assertEquals("NEXT: A short one.", CaptureText.nextLine(t, "A short one."))
        assertEquals("NEXT: " + "x".repeat(70), CaptureText.nextLine(t, "x".repeat(70)))
        assertEquals("NEXT: " + "x".repeat(70) + "...", CaptureText.nextLine(t, "x".repeat(71)))
        assertEquals("LAST SAVED: CARD 4, 3.2 S. MARK IT IF NEEDED:", CaptureText.lastSaved(t, 4, 3.24))
        assertEquals("3 CLIP(S) KEPT, 2 CARD(S) LEFT FOR NEXT TIME.", CaptureText.summary(t, CaptureText.SessionSummary.Script(3, 2)))
        assertEquals("3 CLIP(S) KEPT. EVERY CARD IN THIS SCRIPT NOW HAS A CLIP.", CaptureText.summary(t, CaptureText.SessionSummary.Script(3, 0)))
        assertEquals("1:05 RECORDED. THE PHONE SUGGESTS 3 PIECE(S); THE COMPUTER DECIDES THE REAL CUTS.", CaptureText.summary(t, CaptureText.SessionSummary.Free(65.0, 3)))
        assertEquals("NOTHING WAS RECORDED.", CaptureText.summary(t, CaptureText.SessionSummary.NothingRecorded))
        assertEquals(
            "EVERYTHING KEPT IS SAFE ON THIS PHONE. OPEN THE SESSION FROM THE LIST TO LISTEN TO CLIPS, THEN USE SAVE TO A FILE AND MOVE THE FILE TO YOUR COMPUTER.",
            CaptureText.finishedNote(t),
        )
    }

    @Test
    fun theNoticesInEnglishAreExactlyWhatTheEnginesAndTheMicrophoneAlwaysSaid() {
        val room = "50 MB free, room for about 0 minutes of recording"
        assertEquals("THE RECORDING COULD NOT BE SAVED: disk gone", CaptureText.notice(t, CaptureNotice.CouldNotSave("disk gone")))
        assertEquals("THE RECORDING COULD NOT BE SAVED: STORAGE ERROR", CaptureText.notice(t, CaptureNotice.CouldNotSave(null)))
        assertEquals("OUT OF ROOM: $room. KEPT CLIPS ARE SAFE", CaptureText.notice(t, CaptureNotice.OutOfRoomKeptClipsSafe(DiskRoom(50, 0))))
        assertEquals("OUT OF ROOM: $room. WHAT WAS RECORDED IS SAVED", CaptureText.notice(t, CaptureNotice.OutOfRoomRecordingSaved(DiskRoom(50, 0))))
        assertEquals("OUT OF ROOM: 1234 MB free, room for about 56 minutes of recording. KEPT CLIPS ARE SAFE", CaptureText.notice(t, CaptureNotice.OutOfRoomKeptClipsSafe(DiskRoom(1234, 56))))
        assertEquals("NOTHING HEARD FOR 20 SECONDS: PAUSED", CaptureText.notice(t, CaptureNotice.NothingHeard(20)))
        assertEquals("THE LONGEST RECORDING (90 MINUTES) WAS REACHED: SAVED. START A NEW ONE TO CARRY ON", CaptureText.notice(t, CaptureNotice.LongestRecording(90)))
        assertEquals("THE MICROPHONE IS NOT ALLOWED. ALLOW IT IN THE PHONE'S SETTINGS FOR ACK.", CaptureText.notice(t, CaptureNotice.MicNotAllowed))
        assertEquals("THE MICROPHONE IS NOT ALLOWED. ALLOW IT IN THE PHONE'S SETTINGS FOR ACK, THEN TRY AGAIN.", CaptureText.notice(t, CaptureNotice.MicDenied))
        assertEquals("THE MICROPHONE COULD NOT BE OPENED. ANOTHER APP MAY BE USING IT.", CaptureText.notice(t, CaptureNotice.MicCouldNotOpen))
        assertEquals("SOMETHING WENT WRONG WHILE RECORDING: IllegalStateException", CaptureText.notice(t, CaptureNotice.MicTrouble("IllegalStateException")))
        assertEquals("THE MICROPHONE STOPPED (ERROR -3). ANOTHER APP MAY BE USING IT.", CaptureText.notice(t, CaptureNotice.MicStopped(-3)))
        assertEquals(
            "NOT ENOUGH ROOM TO RECORD: 120 MB free, room for about 0 minutes of recording. FREE UP SPACE FIRST (NEEDS 300 MB).",
            CaptureText.notice(t, CaptureNotice.NotEnoughRoomToStart(DiskRoom(120, 0), 300)),
        )
        assertEquals("THE SCRIPT IS NOT ON THIS PHONE ANY MORE.", CaptureText.notice(t, CaptureNotice.ScriptGone))
        assertEquals("THE SCRIPT COULD NOT BE READ.", CaptureText.notice(t, CaptureNotice.ScriptUnreadable(null)))
        assertEquals("what the store said, as it said it", "left as it is", CaptureText.notice(t, CaptureNotice.ScriptUnreadable("left as it is")))
        assertEquals("THE SESSION COULD NOT BE STARTED.", CaptureText.notice(t, CaptureNotice.CouldNotStart(null)))
        assertEquals("already exists", CaptureText.notice(t, CaptureNotice.CouldNotStart("already exists")))
    }

    @Test
    fun theNumbersInTheNoticesAreTheEnginesOwn_inEveryLanguage() {
        // The idle limit and the longest recording are the engine's own constants, so a notice cannot say a limit the engine does not keep.
        assertEquals(20, CaptureConstants.NO_SPEECH_TIMEOUT_HOPS / 100)
        assertEquals(90, CaptureConstants.MAX_FREE_SESSION_S / 60)
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            assertTrue("$tag idle", CaptureText.notice(f, CaptureNotice.NothingHeard(20)).contains("20"))
            assertTrue("$tag longest", CaptureText.notice(f, CaptureNotice.LongestRecording(90)).contains("90"))
            val room = CaptureText.notice(f, CaptureNotice.OutOfRoomKeptClipsSafe(DiskRoom(1234, 56)))
            assertTrue("$tag room: $room", room.contains("1234") && room.contains("56"))
            val noRoom = CaptureText.notice(f, CaptureNotice.NotEnoughRoomToStart(DiskRoom(120, 7), 300))
            assertTrue("$tag no room: $noRoom", noRoom.contains("120") && noRoom.contains("7") && noRoom.contains("300"))
            assertEquals("$tag: the same room sentence inside both out-of-room notices", 1, count(CaptureText.notice(f, CaptureNotice.OutOfRoomRecordingSaved(DiskRoom(1234, 56))), CaptureText.roomLeft(f, DiskRoom(1234, 56))))
            val stopped = CaptureText.notice(f, CaptureNotice.MicStopped(-3))
            assertTrue("$tag stopped: $stopped", stopped.contains("-3"))
        }
    }

    @Test
    fun everyRecordingScreenWordReadsInTheLanguage_andNeverTheEnglish() {
        val kinds = listOf(
            CaptureNotice.CouldNotSave("x"), CaptureNotice.CouldNotSave(null), CaptureNotice.OutOfRoomKeptClipsSafe(DiskRoom(1, 2)), CaptureNotice.OutOfRoomRecordingSaved(DiskRoom(1, 2)),
            CaptureNotice.NothingHeard(20), CaptureNotice.LongestRecording(90), CaptureNotice.MicNotAllowed, CaptureNotice.MicDenied, CaptureNotice.MicCouldNotOpen, CaptureNotice.MicTrouble("x"),
            CaptureNotice.MicStopped(-3), CaptureNotice.NotEnoughRoomToStart(DiskRoom(1, 2), 300), CaptureNotice.ScriptGone, CaptureNotice.ScriptUnreadable(null), CaptureNotice.CouldNotStart(null),
        )
        for ((tag, f) in languages) {
            for (kind in kinds) assertNotEquals("$tag/$kind is still English", CaptureText.notice(t, kind), CaptureText.notice(f, kind))
            val pairs = mapOf(
                "setupCards" to (CaptureText.setupCardsLine(f, 10, 10, false) to CaptureText.setupCardsLine(t, 10, 10, false)),
                "setupSkipping" to (CaptureText.setupCardsLine(f, 10, 6, false) to CaptureText.setupCardsLine(t, 10, 6, false)),
                "includeDone" to (CaptureText.includeDoneLabel(f, true, false) to CaptureText.includeDoneLabel(t, true, false)),
                "skipping" to (CaptureText.includeDoneLabel(f, false, false) to CaptureText.includeDoneLabel(t, false, false)),
                "paceOwn" to (CaptureText.paceLine(f, 2.6, true) to CaptureText.paceLine(t, 2.6, true)),
                "paceTypical" to (CaptureText.paceLine(f, 2.6, false) to CaptureText.paceLine(t, 2.6, false)),
                "waitNote" to (CaptureText.waitNote(f, 120) to CaptureText.waitNote(t, 120)),
                "startQuiet" to (CaptureText.startQuietLabel(f) to CaptureText.startQuietLabel(t)),
                "freeNote" to (CaptureText.freeNote(f) to CaptureText.freeNote(t)),
                "freeNotice" to (CaptureText.freeNoticeSetup(f) to CaptureText.freeNoticeSetup(t)),
                "good" to (CaptureText.noiseVerdict(f, NoiseVerdict.GOOD, -60.8) to CaptureText.noiseVerdict(t, NoiseVerdict.GOOD, -60.8)),
                "loud" to (CaptureText.noiseVerdict(f, NoiseVerdict.LOUD_ROOM, -24.0) to CaptureText.noiseVerdict(t, NoiseVerdict.LOUD_ROOM, -24.0)),
                "none" to (CaptureText.noiseVerdict(f, NoiseVerdict.NO_SIGNAL, -120.0) to CaptureText.noiseVerdict(t, NoiseVerdict.NO_SIGNAL, -120.0)),
                "interrupted" to (CaptureText.noiseVerdict(f, NoiseVerdict.INTERRUPTED, -50.0) to CaptureText.noiseVerdict(t, NoiseVerdict.INTERRUPTED, -50.0)),
                "heading" to (CaptureText.cardHeading(f, 3, 10, 1) to CaptureText.cardHeading(t, 3, 10, 1)),
                "keptLeft" to (CaptureText.keptLeft(f, 2, 3) to CaptureText.keptLeft(t, 2, 3)),
                "paused" to (CaptureText.scriptStatus(f, true, false) to CaptureText.scriptStatus(t, true, false)),
                "hearing" to (CaptureText.scriptStatus(f, false, true) to CaptureText.scriptStatus(t, false, true)),
                "listening" to (CaptureText.scriptStatus(f, false, false) to CaptureText.scriptStatus(t, false, false)),
                "freeHearing" to (CaptureText.freeStatus(f, false, true) to CaptureText.freeStatus(t, false, true)),
                "freeTalk" to (CaptureText.freeStatus(f, false, false) to CaptureText.freeStatus(t, false, false)),
                "next" to (CaptureText.nextLine(f, "abc") to CaptureText.nextLine(t, "abc")),
                "lastSaved" to (CaptureText.lastSaved(f, 4, 3.2) to CaptureText.lastSaved(t, 4, 3.2)),
                "summaryLeft" to (CaptureText.summary(f, CaptureText.SessionSummary.Script(3, 2)) to CaptureText.summary(t, CaptureText.SessionSummary.Script(3, 2))),
                "summaryAll" to (CaptureText.summary(f, CaptureText.SessionSummary.Script(3, 0)) to CaptureText.summary(t, CaptureText.SessionSummary.Script(3, 0))),
                "summaryFree" to (CaptureText.summary(f, CaptureText.SessionSummary.Free(65.0, 3)) to CaptureText.summary(t, CaptureText.SessionSummary.Free(65.0, 3))),
                "nothing" to (CaptureText.summary(f, CaptureText.SessionSummary.NothingRecorded) to CaptureText.summary(t, CaptureText.SessionSummary.NothingRecorded)),
                "finishedNote" to (CaptureText.finishedNote(f) to CaptureText.finishedNote(t)),
            )
            for ((what, both) in pairs) assertNotEquals("$tag/$what is still English: ${both.first}", both.second, both.first)
        }
    }

    @Test
    fun aNumberThatCanBeNegativeHasALeftToRightMarkInArabicAndNowhereElse() {
        // The room level and the microphone's error code are negative: in a right-to-left paragraph a minus sign in front of a bare number is drawn after it. Arabic puts a mark directly before the number; no other language does.
        val signed = listOf("capture_room_db", "capture_noise_good", "capture_noise_loud", "capture_n_mic_stopped")
        for ((tag, map) in translations) for (name in signed) {
            val text = map.getValue(name)
            val number = Regex("""%1\$[sd]""").find(text)!!
            if (tag == "ar") assertTrue("$tag/$name: a mark directly before the number: $text", text.substring(0, number.range.first).endsWith(lrm))
            else assertFalse("$tag/$name must not hold a mark", text.contains(lrm))
        }
        for (name in signed) assertFalse("en/$name must not hold a mark", english.getValue(name).contains(lrm))
        // Everything else in these screens (sizes, counts, lengths) is never negative, so no other Arabic string holds one.
        val withMark = translations.getValue("ar").filter { it.key.startsWith("capture_") && it.value.contains(lrm) }.keys
        assertEquals(signed.toSet(), withMark)
    }

    @Test
    fun theCardHeadingKeepsItsOwnTwoSpaces_inEveryLanguage() {
        // Android trims a resource's leading space, so the two spaces before "(TRY n)" are written by the decision, not by the string.
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val first = CaptureText.cardHeading(f, 2, 9, 1)
            val second = CaptureText.cardHeading(f, 2, 9, 2)
            assertTrue("$tag: $second", second.startsWith(first + "  ") && second.length > first.length + 2)
            assertFalse("$tag: the first try has no try mark: $first", first.contains("  "))
        }
        assertFalse("no capture string starts or ends with a space", english.filter { it.key.startsWith("capture_") }.any { it.value != it.value.trim() })
    }

    @Test
    fun aLongNextCardIsCutAtSeventyCharactersWithThreeDots_inEveryLanguage() {
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val exact = CaptureText.nextLine(f, "y".repeat(70))
            val over = CaptureText.nextLine(f, "y".repeat(71))
            assertEquals("$tag: seventy is not cut", 70, count(exact, "y"))
            assertFalse("$tag: no dots at seventy: $exact", exact.contains("..."))
            assertEquals("$tag: seventy-one is cut to seventy", 70, count(over, "y"))
            assertTrue("$tag: and shows dots: $over", over.contains("..."))
        }
    }

    @Test
    fun theFinishedNoteNamesTheSaveButtonAsItReadsInTheLanguage() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val f = if (tag == "en") t else FileText(tag)
            assertEquals("$tag: the button's name once", 1, count(CaptureText.finishedNote(f), map.getValue("capture_save_file")))
        }
    }

    @Test
    fun theScriptSummaryIsChosenByTheCardsLeft_notByAWord() {
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val left = CaptureText.summary(f, CaptureText.SessionSummary.Script(3, 1))
            val all = CaptureText.summary(f, CaptureText.SessionSummary.Script(3, 0))
            assertNotEquals("$tag", left, all)
            assertTrue("$tag: kept count in both", left.contains("3") && all.contains("3"))
            assertTrue("$tag: cards left in the one that has some: $left", left.contains("1"))
        }
    }

    // ---- gaps found by breaking the code on purpose --------------------------------------------------------------------------------------

    @Test
    fun aNameWithOnlySpacesIsStillShown_aSizeOfZeroIsStillASize_andAnUnknownModeReadsAsFree() {
        assertEquals("FREE SPEECH //  ", CaptureText.sessionTitle(t, "free", null, " "))
        assertEquals("a name is shown as typed, spaces and all", "SCRIPT //  x ", CaptureText.sessionTitle(t, "script", null, " x "))
        assertEquals(
            "THIS REMOVES 0.0 MB OF RECORDINGS FROM THIS PHONE. IF YOU HAVE NOT SAVED A PACKAGE AND CHECKED IT ON YOUR COMPUTER, THEY ARE GONE FOR GOOD.",
            CaptureText.deleteSessionBody(t, 0L),
        )
        // A mode this build does not know is listed the way free speech is (how long, not how many were kept).
        assertEquals("2026-01-02 03:04:05 UTC  //  1:05  //  0.0 MB", CaptureText.sessionLine(t, "2026-01-02T03:04:05Z", "other", 3, 65.0, 0L, closed = true))
        assertEquals("2026-01-02 03:04:05 UTC  //  NO RECORDING  //  0.0 MB", CaptureText.sessionLine(t, "2026-01-02T03:04:05Z", "other", 3, null, 0L, closed = true))
    }

    @Test
    fun aSentenceWithTwoOrThreeNumbersKeepsThemInTheOrderTheEnglishHasThem_inEveryLanguage() {
        // Distinct numbers, so a swapped argument shows: in every language here the first number the English names comes first in the text (logical order, which is also the order in Arabic).
        // One sentence is reordered on purpose: Hindi says "X out of Y" as "Y में से X", so its two numbers are in the other order. Any other reorder is a swapped argument.
        val reordered = setOf("hi/saving bytes", "hi/characters")
        fun inOrder(tag: String, what: String, text: String, vararg numbers: String) {
            val at = numbers.map { text.indexOf(it) }
            assertTrue("$tag/$what holds every number: $text", at.all { it >= 0 })
            if ("$tag/$what" in reordered) assertEquals("$tag/$what is reordered on purpose: $text", at.sortedDescending(), at)
            else assertEquals("$tag/$what keeps its numbers in order: $text", at.sorted(), at)
        }
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            inOrder(tag, "phone line", CaptureText.phoneLine(f, 11, "22.0 MB", "33.0 MB"), "11", "22.0 MB", "33.0 MB")
            inOrder(tag, "recovery", CaptureText.recoveryNotice(f, 11, 22, emptyList()), "11", "22")
            inOrder(tag, "script cards", CaptureText.scriptCardsLine(f, 11, 2), "11", "2")
            inOrder(tag, "saving", CaptureText.savingLine(f, 11, 22), "11", "22")
            inOrder(tag, "saving bytes", CaptureText.savingBytes(f, 1_048_576L, 2_097_152L), "1.0 MB", "2.0 MB")
            inOrder(tag, "characters", CaptureText.charsLine(f, 111, 20000), "111", "20000")
            inOrder(tag, "cards summary", CaptureText.cardsSummary(f, 11, 7.0, 2.5, false), "11", "7", "2.5")
            inOrder(tag, "recorded pieces", CaptureText.recordingLine(f, 3661.0, 7, ClipState.DONE), "1:01:01", "7")
            inOrder(tag, "clip line", CaptureText.clipLine(f, 12, 34, 5.6, ClipState.DONE), "12", "34", "5.6")
            inOrder(tag, "kept and aside", CaptureText.keptAside(f, 21, 34), "21", "34")
            inOrder(tag, "setup cards", CaptureText.setupCardsLine(f, 41, 13, false), "41", "28")
            inOrder(tag, "card heading", CaptureText.cardHeading(f, 3, 10, 1), "3", "10")
            inOrder(tag, "card heading try", CaptureText.cardHeading(f, 3, 10, 7), "3", "10", "7")
            inOrder(tag, "kept and left", CaptureText.keptLeft(f, 21, 34), "21", "34")
            inOrder(tag, "last saved", CaptureText.lastSaved(f, 14, 3.2), "14", "3.2")
            inOrder(tag, "script summary", CaptureText.summary(f, CaptureText.SessionSummary.Script(17, 29)), "17", "29")
            inOrder(tag, "free summary", CaptureText.summary(f, CaptureText.SessionSummary.Free(3661.0, 29)), "1:01:01", "29")
            inOrder(tag, "room", CaptureText.roomLeft(f, DiskRoom(1234, 56)), "1234", "56")
            inOrder(tag, "no room", CaptureText.notice(f, CaptureNotice.NotEnoughRoomToStart(DiskRoom(1234, 56), 300)), "1234", "56", "300")
        }
    }

    @Test
    fun theQuietChecksVerdictShowsTheRoomLevelAsMeasured_inEveryLanguage() {
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            for (verdict in listOf(NoiseVerdict.GOOD, NoiseVerdict.LOUD_ROOM)) {
                val text = CaptureText.noiseVerdict(f, verdict, -52.5)
                assertEquals("$tag/$verdict: the level once in $text", 1, count(text, "-52.5"))
                assertTrue("$tag/$verdict: its unit stays Latin: $text", text.contains("dB"))
            }
            for (verdict in listOf(NoiseVerdict.NO_SIGNAL, NoiseVerdict.INTERRUPTED)) assertFalse("$tag/$verdict has no number", CaptureText.noiseVerdict(f, verdict, -52.5).contains("52"))
        }
    }

    @Test
    fun theFourQuietCheckAndPauseNoticesAreAllDifferentFromEachOther_inEveryLanguage() {
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val verdicts = NoiseVerdict.values().map { CaptureText.noiseVerdict(f, it, -52.5) }
            assertEquals("$tag: four verdicts, four sentences", 4, verdicts.toSet().size)
            val notices = listOf(
                CaptureNotice.CouldNotSave("x"), CaptureNotice.OutOfRoomKeptClipsSafe(DiskRoom(1, 2)), CaptureNotice.OutOfRoomRecordingSaved(DiskRoom(1, 2)), CaptureNotice.NothingHeard(20),
                CaptureNotice.LongestRecording(90), CaptureNotice.MicNotAllowed, CaptureNotice.MicDenied, CaptureNotice.MicCouldNotOpen, CaptureNotice.MicTrouble("x"), CaptureNotice.MicStopped(-3),
                CaptureNotice.NotEnoughRoomToStart(DiskRoom(1, 2), 300), CaptureNotice.ScriptGone, CaptureNotice.ScriptUnreadable(null), CaptureNotice.CouldNotStart(null),
            ).map { CaptureText.notice(f, it) }
            assertEquals("$tag: every kind of notice has its own sentence", notices.size, notices.toSet().size)
        }
    }

    @Test
    fun aNoticeSaysTheNumberItWasGiven_notTheOneTheEnginesUseToday_inEveryLanguage() {
        // The engines pass their own constants (20 s, 90 min); the wording must print what it is given, so a different limit later is said as it is.
        for ((tag, f) in listOf("en" to t as TextSource) + languages) {
            val idle = CaptureText.notice(f, CaptureNotice.NothingHeard(7))
            assertTrue("$tag idle: $idle", idle.contains("7") && !idle.contains("20"))
            val longest = CaptureText.notice(f, CaptureNotice.LongestRecording(45))
            assertTrue("$tag longest: $longest", longest.contains("45") && !longest.contains("90"))
            val stopped = CaptureText.notice(f, CaptureNotice.MicStopped(-9))
            assertTrue("$tag stopped: $stopped", stopped.contains("-9") && !stopped.contains("-3"))
        }
    }
}
