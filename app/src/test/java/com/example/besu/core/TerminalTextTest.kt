// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the Terminal says in its own voice that is decided, in English exactly as it always was and in every language. **Typed commands are never translated**: they stay exactly as typed inside every
 * translated sentence, and a command the person typed is echoed back as typed. The lines other parts of ACK write into the Terminal are not covered here (they arrive as English text).
 */
class TerminalTextTest {

    private val t = EnglishText
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    /** The /help list exactly as the screen held it before it was built from resources (ui/DesignSystem.kt TERMINAL_HELP_LINES). */
    private val oldHelp = listOf(
        "SLASH COMMANDS:",
        "/help, /?        SHOW THIS LIST",
        "/q, /quiet       SEND WITHOUT AUDIO",
        "/n, /nosave      SEND WITHOUT LOGGING",
        "/s, /sticky      SEND, HOLD TO CLEAR",
        "/e, /emergency   SEND WITH EMERGENCY OVERRIDES",
        "/v               BROWSE SHARED ROOT VARIABLES",
        "/t               BROWSE TARGET COMPUTER ENTRIES",
        "/cls             CLEAR THE LOG (CONFIRM REQUIRED)",
        "/b, /backup      EXPORT ACK DATA (CONFIRM REQUIRED)",
        "/repair          RESTART BACKGROUND SERVICES",
        "/info            SHOW PATCH NOTES",
        "/m               OPEN CLASSIC MANUAL OVERRIDE",
    )

    // ---- English is exactly what it always said -------------------------------------------------------------------------------------

    @Test
    fun theEnglishHelpIsExactlyTheListItAlwaysWas_lineForLine() {
        assertEquals(oldHelp, TerminalText.helpLines(t))
        assertEquals(oldHelp.joinToString("\n"), TerminalText.helpLines(t).joinToString("\n"))
    }

    @Test
    fun theEnglishRepliesAreExactlyWhatTheTerminalAlwaysPrinted() {
        assertEquals("CLEAR ENTIRE LOG? THIS CANNOT BE UNDONE.\nTYPE /cls CONFIRM TO PROCEED.", TerminalText.clearConfirmation(t))
        assertEquals("UNKNOWN COMMAND: /zzz -- TRY /help", TerminalText.unknownCommand(t, "/zzz"))
        assertEquals("NO EMERGENCY DECK ACTIVE -- /e SENT PLAIN", TerminalText.noEmergencyDeck(t, "EMERGENCY", "DECK"))
        assertEquals("0 CHARS", TerminalText.charCount(t, 0))
        assertEquals("1 CHAR", TerminalText.charCount(t, 1))
        assertEquals("2 CHARS", TerminalText.charCount(t, 2))
        assertEquals("A:EMPTY", TerminalText.variableChip(t, "A", "", false))
        assertEquals("B:hello", TerminalText.variableChip(t, "B", "hello", true))
        assertEquals("ALREADY SAVED: HOME, WORK", TerminalText.alreadySaved(t, listOf("HOME", "WORK")))
        assertEquals("ALREADY SAVED: HOME", TerminalText.alreadySaved(t, listOf("HOME")))
    }

    @Test
    fun theSimpleWordsAreHeldExactly() {
        val expected = mapOf(
            "term_vars_hint" to "TAP A ROOT ABOVE TO VIEW ITS VARIABLES", "term_targets_pick" to "TAP A CATEGORY ABOVE TO BROWSE IT", "term_targets_empty" to "NOTHING HERE YET.",
            "term_info_button" to "INFO", "term_confirm_needed" to "THIS COMMAND REQUIRES CONFIRMATION", "term_confirm_button" to "CONFIRM", "term_typing" to "TYPING", "term_awaiting" to "AWAITING INPUT",
            "term_prompt_hint" to "TYPE A COMMAND...", "term_resolve_v" to "RESOLVE /v FIRST -- TAP A VARIABLE OR DELETE IT", "term_resolve_t" to "RESOLVE /t FIRST -- TAP A TARGET OR DELETE IT",
            "term_no_phrase" to "NO PHRASE GIVEN", "term_services_restarted" to "BACKGROUND SERVICES RESTARTED", "term_backup_cancelled" to "BACKUP CANCELLED", "term_log_cleared" to "LOG CLEARED",
        )
        for ((name, text) in expected) assertEquals(name, text, english.getValue(name))
        assertEquals("NO TARGET CATEGORIES -- ADD SOME FROM THE TARGET COMPUTER TAB.", t.get("term_targets_none", english.getValue("label_target_computer")))
    }

    @Test
    fun theCommandsAreTheOnesTheParserKnows_andInTheOrderTheyWereListed() {
        assertEquals(
            listOf("/help, /?", "/q, /quiet", "/n, /nosave", "/s, /sticky", "/e, /emergency", "/v", "/t", "/cls", "/b, /backup", "/repair", "/info", "/m"),
            TerminalText.HELP_COMMANDS.map { it.first },
        )
        assertEquals(17, TerminalText.HELP_COMMAND_WIDTH)
        // Every command listed is a command the parser matches, as typed.
        val design = RepoFiles.read("app/src/main/java/com/example/besu/ui/DesignSystem.kt")
        for (command in listOf("\"/help\"", "\"/?\"", "\"/q\"", "\"/quiet\"", "\"/n\"", "\"/nosave\"", "\"/s\"", "\"/sticky\"", "\"/e\"", "\"/emergency\"", "\"/cls\"", "\"/b\"", "\"/backup\"", "\"/repair\"", "\"/info\"", "\"/m\"")) {
            assertTrue("the parser matches $command", design.contains(command))
        }
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------

    @Test
    fun theHelpKeepsEveryCommandExactlyAsTyped_inTheSameColumn_inEveryLanguage() {
        for ((tag, map) in translations) {
            val lines = TerminalText.helpLines(FileText(tag))
            assertEquals("$tag: a heading and twelve commands", 13, lines.size)
            assertEquals("$tag: the heading", map.getValue("term_help_header"), lines.first())
            assertNotEquals("$tag: the heading is not English", "SLASH COMMANDS:", lines.first())
            for ((i, pair) in TerminalText.HELP_COMMANDS.withIndex()) {
                val line = lines[i + 1]
                assertEquals("$tag: the command column of '$line'", pair.first.padEnd(TerminalText.HELP_COMMAND_WIDTH), line.substring(0, TerminalText.HELP_COMMAND_WIDTH))
                val description = line.substring(TerminalText.HELP_COMMAND_WIDTH)
                assertEquals("$tag: the description", map.getValue(pair.second), description)
                assertNotEquals("$tag: ${pair.first} is still English", english.getValue(pair.second), description)
                assertTrue("$tag: ${pair.first} has a description", description.isNotBlank() && !description.startsWith(" "))
            }
        }
    }

    @Test
    fun aHelpDescriptionThatNamesAScreenNamesItTheWayTheLanguagesOwnLabelDoes() {
        for ((tag, map) in translations) {
            assertTrue("$tag: /v names SHARED ROOT VARIABLES", map.getValue("term_help_variables").contains(map.getValue("label_shared_variables")))
            assertTrue("$tag: /t names TARGET COMPUTER", map.getValue("term_help_targets").contains(map.getValue("label_target_computer")))
            assertTrue("$tag: /m names MANUAL OVERRIDE", map.getValue("term_help_manual").contains(map.getValue("label_manual_override")))
        }
    }

    @Test
    fun theCommandsInsideTheSentencesStayExactlyAsTyped_inEveryLanguage() {
        for ((tag, map) in translations) {
            assertTrue("$tag: /v", map.getValue("term_resolve_v").contains("/v"))
            assertTrue("$tag: /t", map.getValue("term_resolve_t").contains("/t"))
            assertTrue("$tag: /cls CONFIRM is typed exactly so", map.getValue("term_cls_type").contains("/cls CONFIRM"))
            assertTrue("$tag: /help", map.getValue("term_unknown_command").contains("/help"))
            assertTrue("$tag: /e", map.getValue("term_no_emergency_deck").contains("/e"))
        }
    }

    @Test
    fun theClearConfirmationSaysItCannotBeUndone_thenHowToProceed_onTwoLines_inEveryLanguage() {
        for ((tag, map) in translations) {
            val said = TerminalText.clearConfirmation(FileText(tag))
            val lines = said.split("\n")
            assertEquals("$tag: two lines", 2, lines.size)
            assertEquals("$tag: the question and its warning first", map.getValue("term_cls_question"), lines[0])
            assertNotEquals("$tag: the warning is not English", "CLEAR ENTIRE LOG? THIS CANNOT BE UNDONE.", lines[0])
            assertTrue("$tag: the typed confirmation last: ${lines[1]}", lines[1].contains("/cls CONFIRM"))
            assertNotEquals("$tag: two different lines", lines[0], lines[1])
        }
    }

    @Test
    fun anUnknownCommandIsEchoedExactlyAsTyped_whateverItHolds() {
        val typed = listOf("/zzz", "/100%", "/\$1", "/%s", "/عربي", "/a\"b")
        for ((tag, _) in translations) {
            for (token in typed) {
                val said = TerminalText.unknownCommand(FileText(tag), token)
                assertTrue("$tag: '$token' in '$said'", said.contains(token))
                assertTrue("$tag: it points at /help", said.contains("/help"))
            }
        }
    }

    @Test
    fun theNoEmergencyDeckWarningNamesTheLabelsItWasGiven_andStillSaysE_inEveryLanguage() {
        for ((tag, map) in translations) {
            val said = TerminalText.noEmergencyDeck(FileText(tag), "QQQ", "WWW")
            assertTrue("$tag: both labels in '$said'", said.contains("QQQ") && said.contains("WWW"))
            assertTrue("$tag: /e", said.contains("/e"))
            assertFalse("$tag: a placeholder leaked", said.contains("%"))
            assertNotEquals("$tag: still English", "NO QQQ WWW ACTIVE -- /e SENT PLAIN", said)
            assertTrue("$tag: it keeps the app's -- separator", map.getValue("term_no_emergency_deck").contains(" -- "))
        }
    }

    @Test
    fun theVariableChipHoldsTheTagAndTheValueExactly_orTheLanguagesWordForEmpty() {
        for ((tag, map) in translations) {
            val f = FileText(tag)
            assertEquals("$tag", "A:100% sure", TerminalText.variableChip(f, "A", "100% sure", true))
            assertEquals("$tag", "C:" + map.getValue("common_empty"), TerminalText.variableChip(f, "C", "", false))
            assertNotEquals("$tag: EMPTY is translated", "C:EMPTY", TerminalText.variableChip(f, "C", "", false))
            // A slot that has a value but is switched off reads as empty (the screen passes hasValue), and a value is never replaced.
            assertEquals("$tag", "B:" + map.getValue("common_empty"), TerminalText.variableChip(f, "B", "hidden", false))
        }
    }

    @Test
    fun theAlreadySavedLineHoldsTheTagsAsTyped_joinedByCommas_inEveryLanguage() {
        for ((tag, _) in translations) {
            val said = TerminalText.alreadySaved(FileText(tag), listOf("HOME", "100% BANK", "رمز"))
            assertTrue("$tag: '$said'", said.contains("HOME, 100% BANK, رمز"))
            assertFalse("$tag: a placeholder leaked", said.replace("100% BANK", "").contains("%"))
            assertNotEquals("$tag: still English", "ALREADY SAVED: HOME, 100% BANK, رمز", said)
        }
    }

    @Test
    fun theCharCountHoldsTheNumber_inEveryLanguage() {
        for ((tag, _) in translations) {
            for (n in listOf(0, 1, 2, 7, 12, 400)) assertTrue("$tag/$n: '${TerminalText.charCount(FileText(tag), n)}'", TerminalText.charCount(FileText(tag), n).contains(n.toString()))
            assertNotEquals("$tag: still English", "7 CHARS", TerminalText.charCount(FileText(tag), 7))
        }
    }
}
