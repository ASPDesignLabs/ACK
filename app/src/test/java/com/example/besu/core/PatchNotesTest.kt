// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Terminal's `/info` rundown. In English it reveals exactly the lines it always did (the old Kotlin list is copied here as the golden, with the two edits the translation work needed); in every
 * other language each bullet is one line as it reads there. A new release's notes need no translation to ship (they show in English until one is added). The names that are not words (commands, file names,
 * the buttons that are still English on their own screens) must come through every translation exactly.
 */
class PatchNotesTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    /** The list as ui/DesignSystem.kt held it before it moved to string resources (one entry per revealed line), verbatim. */
    private val oldPatchNotes = listOf(
        "=== NEXT RELEASE (NOT YET NUMBERED) ===",
        "-- PRIVACY AND DATA --",
        "- NEW: EXPORT .JSON NOW SAYS WHAT THE FILE CAN CONTAIN AND THAT IT IS",
        "  NOT ENCRYPTED, BEFORE THE FILE PICKER OPENS. /backup SAYS IT TOO",
        "- A FAILED EXPORT NOW SAYS SO AND LEAVES NO HALF-MADE FILE",
        "- NEW: DELETE DATA IN DATA PORT. TWELVE AREAS, EACH WITH WHAT IT HOLDS",
        "  AND HOW MUCH. EVERY DELETE ASKS TWICE AND NAMES A BACKUP FIRST",
        "- NEW: DELETE CUSTOM VOICE IN AUDIO ARCHITECT. VOICES THAT USED IT",
        "  SWITCH TO A NORMAL ONE",
        "- NEW: SAFETY COPIES. THE PRIVATE COPY ACK MAKES BEFORE A DATA UPGRADE",
        "  IS LISTED IN DATA PORT AND CAN BE DELETED",
        "- NEW: A BACKUP REMINDER AFTER 7 DAYS IF SETTINGS OR DECKS CHANGED.",
        "  A BANNER ON TERMINAL AND SETTINGS, AND A SAVE ICON LEFT OF HELP.",
        "  NOT NOW HIDES IT FOR A DAY. A SWITCH IN DATA PORT. IT NEVER MAKES",
        "  A FILE FOR YOU",
        "- NEW: RECORD FREE SPEECH NOW SAYS IT RECORDS ANYONE NEARBY",
        "- NO NEW PERMISSIONS. SEE DOCS/PERMISSIONS.MD",
        "-- STARTER PHRASES --",
        "- NEW: A BRAND-NEW INSTALL OPENS WITH PLAIN STARTER PHRASES (YES, NO,",
        "  I NEED HELP, SAY THAT AGAIN, I AM TYPING, I NEED A BREAK) INSTEAD OF",
        "  THE DEVELOPER'S OWN WORDS, AND A SMALL STARTERS QUICK ACTIONS DECK.",
        "  A PHONE THAT ALREADY HAS ACK IS NOT CHANGED",
        "- A NEW MATRIX DECK ON SUCH A PHONE STARTS WITH THEM TOO. DELETE DATA >",
        "  MESSAGES AND DECKS SAVES THEM AGAIN",
        "- FULL RESTORE OF AN OLDER BACKUP TAKES BACK ONLY THE STARTER PHRASES",
        "  YOU NEVER EDITED. THE WORDING IS A DRAFT: DOCS/STARTER_PHRASES.MD",
        "-- TYPING AND INSERTING --",
        "- THE SAME INSERT BUTTON NOW BEHAVES THE SAME EVERYWHERE: IT GOES AT",
        "  THE CURSOR (OR REPLACES WHAT IS SELECTED), NEVER SPLITS A TAG OR AN",
        "  EMOJI, AND ADDS A SPACE ONLY WHERE ONE IS NEEDED",
        "- CHANGED: /m MANUAL OVERRIDE NOW ADDS A SPACE AFTER AN INSERTED WORD",
        "  (IT ADDED NONE BEFORE), LIKE THE COMPOSER AND THE TERMINAL",
        "- CHANGED: THE MATRIX AND QUICK ACTIONS EDITORS' + VAR, + A / B / C",
        "  AND INSERT TARGET TAG BUTTONS INSERT AT THE CURSOR INSTEAD OF ALWAYS",
        "  AT THE END. VALUES YOU TYPED FOR OTHER TAGS STAY WITH THEIR OWN TAG",
        "- THE HISTORY CHIPS UNDER VARIABLE FIELDS NOW NARROW AS YOU TYPE, ARE",
        "  LARGER AND EASIER TO TAP, SHOW BOTH ENDS OF A LONG VALUE, AND NO",
        "  LONGER MOVE THE SCREEN. MUM AND mum NOW COUNT AS ONE WORD",
        "-- PROFILES --",
        "- NEW: BEFORE A PROFILE CHANGE MAKES A MATRIX GESTURE SAY SOMETHING",
        "  DIFFERENT, ACK SHOWS WHICH GESTURES AND ASKS. CHANGE PROFILE OR STAY.",
        "  NO WARNING IF NOTHING WOULD CHANGE. SWITCH: WARN BEFORE PROFILE",
        "  CHANGES IN SETTINGS. ON FOR A NEW INSTALL; OFF FOR AN INSTALL THAT",
        "  ALREADY EXISTS, WHICH IS OFFERED IT ONCE. ONLY THE IN-APP PROFILE",
        "  MENU ASKS: THE WIDGET AND THE WATCH CHANGE PROFILE WITHOUT ASKING",
        "-- VOICES AND LANGUAGES --",
        "- NEW: THE VOICE LIST IN AUDIO ARCHITECT NOW SHOWS EVERY LANGUAGE,",
        "  SORTED BY LANGUAGE, WITH THE LANGUAGE NAMED UNDER EACH VOICE. IT",
        "  USED TO SHOW ENGLISH ONLY",
        "- CHANGED: VOICES THAT NEED THE INTERNET OR ARE NOT INSTALLED ARE NOT",
        "  LISTED. A VOICE A PROFILE ALREADY CHOSE STAYS CHOSEN",
        "- NEW: SPEECH LANGUAGE IN AUDIO ARCHITECT (THIS PHONE'S LANGUAGE OR",
        "  ENGLISH (US)) FOR A PROFILE WITH NO VOICE OF ITS OWN. A NEW INSTALL",
        "  FOLLOWS THE PHONE. AN INSTALL THAT ALREADY EXISTS STAYS ON ENGLISH",
        "  (US) UNTIL YOU CHANGE IT. A LANGUAGE THE ENGINE LACKS NEVER MEANS",
        "  SILENCE",
        "-- WORD SUGGESTIONS --",
        "- NEW: THE STATEMENT COMPOSER CAN OFFER THE REST OF THE WORD YOU ARE",
        "  TYPING, OR THE WORD THAT USUALLY COMES NEXT, AS BUTTONS UNDER THE",
        "  TEXT BOX. NOTHING IS ADDED UNTIL YOU TAP ONE. IT IS OFF UNTIL YOU",
        "  TURN IT ON (A ONE-TIME BOX IN THE COMPOSER, OR SETTINGS > WORD",
        "  SUGGESTIONS)",
        "- IT LEARNS ONLY FROM STATEMENTS YOU SAVE, SPEAK OR COPY IN THE",
        "  COMPOSER. NEVER FROM EMERGENCY, THE TERMINAL, MANUAL OVERRIDE, TAGS",
        "  OR NUMBERS. NAMES IN TARGET COMPUTER AND SHARED VARIABLES ARE",
        "  OFFERED TOO, READ LIVE AND NEVER COPIED",
        "- THE WORDS STAY ON THIS PHONE. FORGET WORDS IN SETTINGS REMOVES ONE",
        "  WORD OR ALL OF THEM. THEY ARE IN EXPORT .JSON, WHICH NOW NAMES THEM,",
        "  AND GO WITH DELETE DATA > MESSAGES AND DECKS",
        "-- PLAIN WORDS --",
        "- NEW: A SWITCH AT THE TOP OF SETTINGS SHOWS EVERYDAY NAMES FOR ACK'S",
        "  OWN WORDS (PEOPLE AND PLACES, SETTINGS, ABOUT ME, ...). IT IS OFF",
        "  FOR EVERYONE. IT CHANGES AT ONCE AND ONLY WHAT THINGS ARE CALLED.",
        "  THE LIST IS DOCS/PLAIN_LANGUAGE.MD, WORDING STILL A DRAFT",
        "- NEW: WITH IT ON, THIS SCREEN GETS WHAT'S NEW, CLEAR HISTORY AND",
        "  SEND OPTIONS: SEND QUIETLY, DO NOT SAVE IN HISTORY, KEEP ON SCREEN",
        "  UNTIL I CLEAR IT, EMERGENCY. THEY STAY ON UNTIL YOU TURN THEM OFF,",
        "  AND CLOSING ACK TURNS THEM OFF. THE TYPED COMMANDS STILL WORK",
        "- NEW: TYPE AND SPEAK (CLASSIC) ON THE TYPE TAB, FIX PROBLEMS IN",
        "  SETTINGS. LONG-TAIL TEXT AND THIS LIST STAY IN ACK'S OWN WORDS",
        "-- LANGUAGE --",
        "- NEW: A LANGUAGE CONTROL IN SETTINGS: ACK'S OWN WORDS IN SPANISH,",
        "  PORTUGUESE, HINDI, ARABIC OR AFRIKAANS. AN INSTALL THAT ALREADY",
        "  EXISTS STAYS ENGLISH UNTIL YOU CHOOSE; A NEW INSTALL FOLLOWS THE",
        "  PHONE. CHOOSING ASKS FIRST AND RESTARTS ACK ONCE",
        "- THESE ARE DRAFTS NOT YET CHECKED BY NATIVE SPEAKERS. HELP, THIS",
        "  SCREEN AND MANY DIALOGS STAY IN ENGLISH. SEE DOCS/TRANSLATIONS.MD",
        "-- FIXES --",
        "- FIXED: THE CONFIRMATION BEFORE CLEARING A PHRASE'S VARIABLES OR",
        "  PROMPT SHOWED ONLY ITS SECOND SENTENCE. IT NOW SHOWS THE WHOLE",
        "  QUESTION, WORDED AS BEFORE",
        "=== ACK v1.0-BETA.8 PATCH NOTES ===",
        "-- CUSTOM VOICE --",
        "- NEW: SPEAK IN A VOICE TRAINED FROM YOUR OWN RECORDINGS, ENTIRELY",
        "  ON THE PHONE. NO NETWORK, NO CLOUD",
        "- NEW: IMPORT CUSTOM VOICE IN AUDIO ARCHITECT. PICK THE .ONNX AND",
        "  .ONNX.JSON TOGETHER. ACK RESTARTS ONCE TO LOAD IT",
        "- NEW: A MY VOICE CHIP IN THE VOICE PROFILE ROW, OR USE MY VOICE IN",
        "  ANY CUSTOM SLOT'S DSP CHAIN EDITOR",
        "- MASTER GAIN APPLIES. ROBOTIC OVERLAY, BITCRUSH, PITCH AND SPEED DO",
        "  NOT -- THIS ENGINE HAS NO DSP CONTROLS OF ITS OWN",
        "- IF THE VOICE FAILS ON AN UTTERANCE, ACK SPEAKS IT WITH THE PHONE'S",
        "  NORMAL VOICE INSTEAD OF GOING SILENT. SHAKE STILL STOPS IT",
        "- NEW: EXPORT / IMPORT VOICE BACKUP (.ZIP), SEPARATE FROM EXPORT .JSON",
        "-- RECORD TRAINING DATA --",
        "- NEW: RECORD VOICE-TRAINING DATA ON THE PHONE, AWAY FROM YOUR",
        "  COMPUTER. AUDIO ARCHITECT > CUSTOM VOICE > RECORD TRAINING DATA",
        "- WRITE OR PASTE A SCRIPT. ACK SPLITS IT INTO CARDS OF ABOUT TEN",
        "  SECONDS. READ A CARD; ACK HEARS YOU FINISH, KEEPS THE CLIP, AND",
        "  SHOWS THE NEXT CARD. NO TOUCHING THE PHONE BETWEEN CARDS",
        "- OR RECORD FREE SPEECH, UP TO 90 MINUTES. THE PHONE ONLY SUGGESTS",
        "  CUTS. THE RAW AUDIO IS NEVER CUT ON THE PHONE",
        "- A TWO-SECOND QUIET CHECK COMES FIRST: ROOM LEVEL, A COVERED MIC,",
        "  OR AN INTERRUPTION",
        "- REDO LAST, PAUSE, AND MARKS: NOISE, UNCLEAR, LAUGH, COUGH, STUMBLE",
        "- RECORDS AT 48 KHZ WHEN THE PHONE ALLOWS IT, ELSE 44.1 KHZ, WITH NO",
        "  PHONE-SIDE PROCESSING WHERE THE PHONE OFFERS THAT",
        "- NO SOUND OR VIBRATION WHILE LISTENING. THE SCREEN STAYS ON AND DOES",
        "  NOT ROTATE. LEAVING THE APP PAUSES",
        "- IF ACK CLOSES MID-CARD, THAT CLIP IS REPAIRED NEXT TIME AND HELD",
        "  BACK UNTIL YOU LISTEN AND CHOOSE TO KEEP IT",
        "- SAVE ALL TO A FILE WRITES ONE .ZIP THROUGH ANDROID'S SAVE SCREEN,",
        "  THEN READS IT BACK AND CHECKS IT. NO SHARE SHEET, NO NETWORK",
        "- TRAINING SCRIPTS (TEXT ONLY) ARE IN EXPORT .JSON AND FULL RESTORE.",
        "  RECORDINGS TRAVEL AS .ZIP PACKAGES INSTEAD",
        "- NEW: A RECORD TRAINING DATA WALKTHROUGH IN HELP",
        "- NEW AND NOT YET PROVEN ON MANY PHONES. SEE",
        "  DOCS/TRAINING_CAPTURE_DEVICE_TEST.MD",
        "-- STATEMENT COMPOSER --",
        "- NEW: TYPE IS NOW THE STATEMENT COMPOSER. BUILD MULTI-SENTENCE",
        "  STATEMENTS FROM TARGET COMPUTER ENTRIES AND SHARED ROOT VARIABLES,",
        "  WITH A LIVE PREVIEW OF EXACTLY WHAT IT'LL SAY",
        "- NEW: SAVE, COPY, OR SPEAK A STATEMENT. SAVED STATEMENTS STAY",
        "  MUTABLE -- THEY KEEP RESOLVING LIVE AGAINST WHATEVER THE ENTRIES OR",
        "  VARIABLES THEY REFERENCE CURRENTLY HOLD, NEVER A FROZEN SNAPSHOT",
        "- NEW: COPY PUTS THE FINISHED TEXT ON THE CLIPBOARD SO YOU CAN PASTE",
        "  IT INTO ANY OTHER APP. EVERY SAVED STATEMENT HAS COPY TOO",
        "- NEW: TAP A TARGET COMPUTER CHIP FOR A LIVE REFERENCE, OR BROWSE",
        "  TARGETS FOR A SPECIFIC ENTRY AS PLAIN TEXT. LONG-PRESS A CHIP TO",
        "  RETARGET ITS ACTIVE ENTRY, APP-WIDE, WITHOUT LEAVING THE COMPOSER",
        "- NEW: MY STATEMENTS ORGANIZES SAVED STATEMENTS INTO FOLDERS, TREE >",
        "  LEAF -- SAME SHAPE AS TARGET COMPUTER ENTRIES. RELOAD, COPY, SPEAK,",
        "  OR DELETE ANY STATEMENT RIGHT FROM THE LIST. INCLUDED IN EXPORT",
        "  .JSON BACKUPS",
        "- NEW: FULL SCREEN HIDES THE HEADER AND BOTTOM NAV FOR MORE ROOM WHILE",
        "  COMPOSING. PINNED TOGGLE, ALWAYS REACHABLE",
        "- MOVED: CLASSIC MANUAL OVERRIDE (MEMORY BANKS, SAVED PHRASES, DIRECT",
        "  TEXT OUTPUT) IS UNCHANGED BUT NOW REACHED WITH /m AT THE TERMINAL",
        "  PROMPT INSTEAD OF THE TYPE TAB",
        "- NEW: A STATEMENT COMPOSER WALKTHROUGH IN HELP",
        "-- GIF DECK --",
        "- NEW: SHARE NEXT TO DISPLAY FULL SCREEN SENDS THE GIF ITSELF THROUGH",
        "  ANDROID'S SHARE SHEET. NO NEW PERMISSION",
        "-- TARGET COMPUTER --",
        "- THE WATCH'S COPY IS NOW RE-SYNCED AFTER EVERY PICK OR CLEAR, FROM",
        "  ANY SCREEN, NOT JUST WHEN A DECK IS ACTIVATED",
        "- NEW: ACK WEAR RELAYS TARGET COMPUTER TO OVERSEER AND PASSES A PICK",
        "  MADE THERE BACK TO THE PHONE",
        "-- PRIVACY AND LICENSE --",
        "- CHANGED: ACK'S DATA IS NO LONGER INCLUDED IN GOOGLE CLOUD BACKUP.",
        "  PHONE-TO-PHONE SETUP TRANSFER IS STILL ALLOWED. EXPORT .JSON AND THE",
        "  GIF AND VOICE .ZIP BACKUPS ARE HOW YOU MOVE YOUR DATA",
        "- NO NEW PERMISSIONS IN THIS RELEASE",
        "- ACK IS NOW EXPLICITLY GPL-3.0-OR-LATER. SEE THIRD_PARTY_NOTICES.MD",
        "-- VOICE TRAINING TOOLS --",
        "- NEW: FREEFORM STUDIO, A DESKTOP TOOL IN THE REPOSITORY, TURNS",
        "  RECORDINGS INTO TRAINING CLIPS ON YOUR OWN COMPUTER. IT NEVER GOES",
        "  ONLINE. SEE DOCS/VOICE_TRAINING_GUIDE.MD",
        "- TO INSTALL: CLONE THE REPOSITORY, RUN TOOLS/FREEFORM_STUDIO/",
        "  INSTALL.SH, THEN FETCH THE SPEECH MODEL ONCE. SEE ITS README.MD",
        "- NEW: BRING RECORD TRAINING DATA PACKAGES IN WITH ADD RECORDINGS",
        "  FROM ACK ON THE REVIEW PAGE, OR THE ACK_IMPORT COMMAND. IMPORTING",
        "  ONLY ADDS AND IS SAFE TO REPEAT",
        "- CHANGED: THE INSTALL COMMAND NOW CLONES THE DEFAULT BRANCH",
        "-- FIXES --",
        "- FIXED ACK WEAR MISSING TARGET COMPUTER UPDATES WHILE ITS APP WASN'T",
        "  ON SCREEN",
        "=== END PATCH NOTES ===",
    )

    /** What English reveals now: the old list, except that the LANGUAGE section's honesty bullet no longer says this screen stays English, and a new bullet says it is translated. */
    private val expected: List<String> get() {
        val at = oldPatchNotes.indexOf("- THESE ARE DRAFTS NOT YET CHECKED BY NATIVE SPEAKERS. HELP, THIS")
        assertTrue("the old bullet is there", at > 0)
        assertEquals("  SCREEN AND MANY DIALOGS STAY IN ENGLISH. SEE DOCS/TRANSLATIONS.MD", oldPatchNotes[at + 1])
        return oldPatchNotes.take(at) + listOf(
            "- NEW: THIS SCREEN'S OWN WORDS, ITS /help LIST AND THESE NOTES ARE",
            "  TRANSLATED TOO. COMMANDS YOU TYPE STAY EXACTLY AS TYPED. NOTES FOR A",
            "  NEW RELEASE SHOW IN ENGLISH UNTIL THEY ARE TRANSLATED",
            "- THESE ARE DRAFTS NOT YET CHECKED BY NATIVE SPEAKERS. HELP'S",
            "  WALKTHROUGHS, LINES OTHER PARTS OF ACK WRITE INTO THIS SCREEN AND",
            "  MANY DIALOGS STAY IN ENGLISH. SEE DOCS/TRANSLATIONS.MD",
        ) + oldPatchNotes.drop(at + 2)
    }

    // ---- English is exactly what /info always revealed -------------------------------------------------------------------------------

    @Test
    fun theEnglishRundownIsTheOldListLineForLine_exceptTheTwoEditsTheTranslationWorkNeeded() {
        assertEquals(expected, PatchNotes.lines(t))
    }

    @Test
    fun noEnglishLineIsLongerThanTheUnitThePacingIsMeasuredIn() {
        // A line of up to PACE_CHARS characters waits one step, as every line always did.
        for (line in PatchNotes.lines(t)) assertTrue("'$line' is ${line.length} characters", line.length <= PatchNotes.PACE_CHARS)
        assertEquals(PatchNotes.PACE_CHARS, PatchNotes.lines(t).maxOf { it.length })
        for (line in PatchNotes.lines(t)) assertEquals(2000L, PatchNotes.pauseMillis(line))
    }

    @Test
    fun theContinuationLinesAreIndentedInCode_theStringsHoldNoLeadingSpace() {
        // Android collapses runs of spaces in a resource, so the two-space indent is added here, not stored.
        for (name in PatchNotes.ENTRIES) {
            val text = english.getValue(name)
            for (line in text.split("\n")) assertEquals("$name: '$line'", line.trim(), line)
        }
        val lines = PatchNotes.lines(t)
        assertEquals("  NOT ENCRYPTED, BEFORE THE FILE PICKER OPENS. /backup SAYS IT TOO", lines[lines.indexOf("- NEW: EXPORT .JSON NOW SAYS WHAT THE FILE CAN CONTAIN AND THAT IT IS") + 1])
        assertEquals("  ", PatchNotes.CONTINUATION_INDENT)
    }

    // ---- pacing -----------------------------------------------------------------------------------------------------------------------

    @Test
    fun aLongerLineWaitsOneMoreStepPerStartedUnit_andAnEmptyOneWaitsOne() {
        assertEquals(2000L, PatchNotes.pauseMillis(""))
        assertEquals(2000L, PatchNotes.pauseMillis("x".repeat(71)))
        assertEquals(4000L, PatchNotes.pauseMillis("x".repeat(72)))
        assertEquals(4000L, PatchNotes.pauseMillis("x".repeat(142)))
        assertEquals(6000L, PatchNotes.pauseMillis("x".repeat(143)))
        assertEquals(2000L * 4, PatchNotes.pauseMillis("x".repeat(284)))
    }

    // ---- the list and the strings agree ---------------------------------------------------------------------------------------------

    @Test
    fun everyListedNameHasAnEnglishString_andEveryEnglishInfoStringIsListedOnce() {
        val names = PatchNotes.ENTRIES
        assertEquals("a name listed twice", names.size, names.toSet().size)
        assertEquals("listed but not written", emptyList<String>(), names.filter { it !in english })
        assertEquals("written but not listed", emptyList<String>(), english.keys.filter { it.startsWith("info_") && it !in names.toSet() })
        assertEquals("info_nr_title", names.first())
        assertEquals("info_end", names.last())
    }

    @Test
    fun theShapeOfEveryEntryIsKeptInEveryLanguage_headingsKeepTheirDashesAndBulletsTheirDash() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in PatchNotes.ENTRIES) {
                val text = map[name] ?: continue
                val first = text.lines().first()
                when {
                    name.endsWith("_title") || name == "info_end" -> assertTrue("$tag/$name: '$text'", first.startsWith("=== ") && first.endsWith(" ==="))
                    name.endsWith("_head") -> assertTrue("$tag/$name: '$text'", first.startsWith("-- ") && first.endsWith(" --"))
                    else -> assertTrue("$tag/$name: '$text'", first.startsWith("- "))
                }
            }
        }
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------

    @Test
    fun aTranslationIsOneLinePerEntry_soTheRundownIsShorterButEveryNoteIsThere() {
        for ((tag, _) in translations) {
            val lines = PatchNotes.lines(FileText(tag))
            assertEquals("$tag: one line for each of the entries", PatchNotes.ENTRIES.size, lines.size)
            assertFalse("$tag: a leaked resource name", lines.any { it.startsWith("info_") })
            assertEquals("$tag: starts with the release heading", "=== ", lines.first().take(4))
            assertEquals("$tag: ends with the closing line", " ===", lines.last().takeLast(4))
            assertTrue("$tag: no line is empty", lines.none { it.isBlank() })
        }
    }

    @Test
    fun everyTranslatedNoteIsInTheLanguage_notEnglish_andHindiAndArabicInTheirOwnScript() {
        for ((tag, map) in translations) {
            for (name in PatchNotes.ENTRIES) {
                val text = map.getValue(name)
                assertNotEquals("$tag/$name is still English", english.getValue(name).replace("\n", "\n"), text)
                if (tag == "hi") assertTrue("hi/$name has Devanagari: $text", text.any { it in '\u0900'..'\u097F' })
                if (tag == "ar") assertTrue("ar/$name has Arabic letters: $text", text.any { it in '\u0600'..'\u06FF' })
                assertFalse("$tag/$name has a line break (a translation is one line)", text.contains("\n"))
                assertEquals("$tag/$name has stray space at an end", text.trim(), text)
            }
        }
    }

    @Test
    fun theLatinLanguagesKeepTheCapitalsTheEnglishHasWhereTheEnglishIsAllCapitals() {
        for (tag in listOf("es", "pt", "af")) {
            val map = translations.getValue(tag)
            for (name in PatchNotes.ENTRIES) {
                val en = english.getValue(name).replace("\n", " ")
                // An English entry with a typed command or a deliberate lower-case word (/backup, mum, v1.0) is mixed case in English too.
                if (en != en.uppercase()) continue
                val text = map.getValue(name)
                assertEquals("$tag/$name is in capitals like the English", text.uppercase(), text)
            }
        }
    }

    @Test
    fun thingsThatAreNotWordsComeThroughEveryTranslationExactly() {
        val tokens = listOf(
            Regex("""(?<![A-Za-z])/[a-z]+"""), Regex("""[A-Z][A-Z_0-9]*\.MD"""), Regex("""\.ONNX(\.JSON)?"""), Regex("""\.ZIP"""), Regex("""ACK_IMPORT"""), Regex("""GPL-3\.0-OR-LATER"""),
            Regex("""ADD RECORDINGS FROM ACK"""), Regex("""RECORD FREE SPEECH"""), Regex("""SAVE ALL TO A FILE"""), Regex("""REDO LAST"""), Regex("""STARTERS"""), Regex("""FREEFORM STUDIO"""), Regex("""ACK WEAR"""),
            Regex("""OVERSEER"""), Regex("""MY VOICE"""), Regex("""v1\.0-BETA\.8"""), Regex("""TOOLS/FREEFORM_STUDIO/INSTALL\.SH"""), Regex("""DOCS/[A-Z_]+\.MD"""),
        )
        for ((tag, map) in translations) for (name in PatchNotes.ENTRIES) {
            // The English breaks a long file name over two lines; joined, it is one token.
            val en = english.getValue(name).replace("\n", "")
            val text = map.getValue(name)
            // A name must come through as that name, not as the start of a longer word ("/cls CONFIRMAR" is not "/cls CONFIRM"), so it is looked for with a word boundary on each side.
            for (token in tokens) for (match in token.findAll(en)) {
                val whole = Regex("(?<![A-Za-z0-9_])" + Regex.escape(match.value) + "(?![A-Za-z0-9_])")
                assertTrue("$tag/$name keeps '${match.value}' as a name in '$text'", whole.containsMatchIn(text))
            }
        }
    }

    @Test
    fun theCommandsYouTypeAreNamedExactlyAsTheyAreTyped_inTheNotesThatMentionThem() {
        for ((tag, map) in translations) {
            assertTrue("$tag: /backup", map.getValue("info_nr_privacy_1").contains("/backup"))
            assertTrue("$tag: /m", map.getValue("info_nr_typing_2").contains("/m ") && map.getValue("info_b8_composer_7").contains("/m "))
            assertTrue("$tag: /help", map.getValue("info_nr_language_terminal").contains("/help"))
        }
    }

    // ---- what the notes say is still true ----------------------------------------------------------------------------------------------

    @Test
    fun theLanguageSectionNoLongerSaysThisScreenStaysEnglish_andSaysItIsTranslated() {
        val joined = PatchNotes.lines(t).joinToString(" ")
        assertFalse("the old claim", joined.contains("HELP, THIS SCREEN AND MANY DIALOGS STAY IN ENGLISH"))
        assertTrue(joined.contains("THIS SCREEN'S OWN WORDS, ITS /help LIST AND THESE NOTES ARE"))
        assertTrue(joined.contains("LINES OTHER PARTS OF ACK WRITE INTO THIS SCREEN"))
    }

    // ---- the screen reads them ---------------------------------------------------------------------------------------------------------

    @Test
    fun theRevealReadsTheNotesFromResources_paysTheLineItsOwnPause_andKeepsTheShakeToStop() {
        val design = RepoFiles.read("app/src/main/java/com/example/besu/ui/DesignSystem.kt")
        assertTrue(design.contains("for (line in PatchNotes.lines(ResourceText(context))) {"))
        assertTrue(Regex("""logTerminalLocal\(context, line, "CMD"\)\s*delay\(PatchNotes\.pauseMillis\(line\)\)""").containsMatchIn(design))
        assertFalse("no hand-written list of notes in the screen", design.contains("PATCH_NOTES = listOf"))
        assertFalse("the fixed two-second wait is gone from the reveal", Regex("""for \(line in PatchNotes[\s\S]{0,200}?delay\(2000\)""").containsMatchIn(design))
        assertTrue("shake still stops the reveal", design.contains("infoRevealJob?.cancel()"))
    }
}
