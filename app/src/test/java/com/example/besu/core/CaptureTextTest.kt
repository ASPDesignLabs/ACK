// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import com.example.besu.capture.ClipFlags
import com.example.besu.capture.ClipState
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
}
