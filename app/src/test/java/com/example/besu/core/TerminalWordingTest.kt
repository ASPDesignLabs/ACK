// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Terminal's own chrome (the STATUSBOX and the prompt), its replies to typed commands, its /help list and its save dialog read their words from string resources. The screen cannot be compiled
 * here (`ui/DesignSystem.kt` uses the SDK; it is syntax-checked), so this reads it: the old English literals are gone, every string it names exists in every language and none is unused, each
 * word sits on the control that does what it says, and **the typed commands and the log type names, which are logic, were not translated**. TerminalTextTest holds the decisions.
 */
class TerminalWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val design get() = noComments(RepoFiles.read("$base/ui/DesignSystem.kt"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    private val names = listOf(
        "term_vars_hint", "term_targets_none", "term_targets_pick", "term_targets_empty", "term_info_button", "term_confirm_needed", "term_confirm_button", "term_typing", "term_awaiting", "term_prompt_hint", "term_already_saved",
        "term_resolve_v", "term_resolve_t", "term_cls_question", "term_cls_type", "term_unknown_command", "term_no_phrase", "term_no_emergency_deck", "term_services_restarted", "term_backup_cancelled", "term_log_cleared",
        "term_help_header", "term_help_help", "term_help_quiet", "term_help_nosave", "term_help_sticky", "term_help_emergency", "term_help_variables", "term_help_targets", "term_help_cls", "term_help_backup",
        "term_help_repair", "term_help_info", "term_help_manual",
    )
    private val pluralNames = listOf("term_chars")

    /** The command parser and the Terminal screen: from the result type to the Type screen, with the patch notes list (its own group) taken out. */
    private val terminal: String get() {
        val d = design
        val whole = d.substring(d.indexOf("private sealed class TerminalPromptResult"), d.indexOf("fun TypeView("))
        val start = whole.indexOf("private val PATCH_NOTES = listOf(")
        if (start < 0) return whole
        return whole.substring(0, start) + whole.substring(whole.indexOf("\n)\n", start) + 3)
    }

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringTheTerminalNamesExists_inEveryLanguage_andNoneIsLeftUnused() {
        val referenced = Regex("""R\.string\.(term_[a-z_]+)""").findAll(design).map { it.groupValues[1] }.toSet() +
            Regex(""""(term_[a-z_]+)"""").findAll(noComments(RepoFiles.read("$base/core/TerminalText.kt"))).map { it.groupValues[1] }.toSet()
        for ((tag, file) in listOf("en" to StringsXml.default) + StringsXml.translations().toList()) {
            val map = StringsXml.map(file)
            val missing = (referenced - pluralNames.toSet()).filter { it !in map }
            assertEquals("$tag: named but not defined: $missing", emptyList<String>(), missing)
            assertTrue("$tag: the plural is defined", StringsXml.plurals(file).containsKey("term_chars"))
        }
        assertEquals("defined but never used", emptyList<String>(), (names + pluralNames).filter { it !in referenced })
        assertEquals("used but not in the list this test holds", emptyList<String>(), (referenced - pluralNames.toSet()).filter { it !in names })
    }

    @Test
    fun theOldLiteralsAreGone_fromTheCommandParserAndTheTerminalScreen() {
        for (literal in listOf(
            "\"RESOLVE /v FIRST", "\"RESOLVE /t FIRST", "\"CLEAR ENTIRE LOG?", "\"UNKNOWN COMMAND:", "\"NO PHRASE GIVEN\"", "\"NO EMERGENCY DECK ACTIVE", "\"BACKGROUND SERVICES RESTARTED\"", "\"BACKUP CANCELLED\"",
            "\"LOG CLEARED\"", "else \"EMPTY\"", "\"TAP A ROOT ABOVE", "\"NO TARGET CATEGORIES", "\"TAP A CATEGORY ABOVE", "\"NOTHING HERE YET.\"", "label = \"INFO\"", "\"THIS COMMAND REQUIRES CONFIRMATION\"",
            "label = \"CONFIRM\"", "\"TYPING\",", "\" CHAR\${", "\"AWAITING INPUT\"", "\"TYPE A COMMAND...\"", "\"ALREADY SAVED:", "TightSectionLabel(\"ASSIGN A TAG\")", "Text(\"NEW TAG\")", "TightPanelButton(\"SAVE\"",
            "TightPanelButton(\"CANCEL\"", "TERMINAL_HELP_LINES", "\"SLASH COMMANDS:\"", "SHOW THIS LIST",
        )) assertFalse("the Terminal still holds $literal", terminal.contains(literal))
    }

    // ---- each word sits on the control that does what it says -----------------------------------------------------------------------

    @Test
    fun theInfoButtonStartsTheReveal_andConfirmSendsTheConfirmedCommand() {
        assertTrue(Regex("""StatusBoxItem\(label = stringResource\(R\.string\.term_info_button\)\) \{[\s\S]{0,300}?startInfoReveal\(\)""").containsMatchIn(terminal))
        // The warning is above the button, and the button types the confirmed command, exactly as typed, and submits it.
        assertTrue(Regex("""stringResource\(R\.string\.term_confirm_needed\),[\s\S]{0,700}?StatusBoxItem\(label = stringResource\(R\.string\.term_confirm_button\)\) \{[\s\S]{0,300}?TextFieldValue\("[$]confirmTriggerCommand confirm"\)[\s\S]{0,60}?submitPrompt\(\)""").containsMatchIn(terminal))
    }

    @Test
    fun theTypingStripSaysTypingThenTheCharCountOrAwaitingInput_andThePromptHintIsOnlyWhileEmpty() {
        assertTrue(Regex("""stringResource\(R\.string\.term_typing\),[\s\S]{0,700}?TerminalText\.charCount\(words, promptValue\.text\.length\)[\s\S]{0,200}?stringResource\(R\.string\.term_awaiting\)""").containsMatchIn(terminal))
        assertTrue(Regex("""if \(promptValue\.text\.isEmpty\(\)\) \{\s*Text\(\s*stringResource\(R\.string\.term_prompt_hint\)""").containsMatchIn(terminal))
        assertTrue("the chip count is of what was typed, not of a different text", terminal.contains("TerminalText.charCount(words, promptValue.text.length)"))
    }

    @Test
    fun thePickersHintsAreInTheStatesTheyDescribe() {
        assertTrue("the variable chip is built from the tag and its value, and is only clickable with a value", Regex("""label = TerminalText\.variableChip\(words, tag, slot\.value, hasValue\),\s*clickable = hasValue""").containsMatchIn(terminal))
        assertTrue("the hint is for the state with no grouping chosen", Regex("""if \(selectedVGrouping != null && config != null\) \{[\s\S]{0,1400}?\} else \{\s*Text\(\s*stringResource\(R\.string\.term_vars_hint\)""").containsMatchIn(terminal))
        assertTrue("no categories", Regex("""if \(tCategories\.isEmpty\(\)\) \{\s*Text\(\s*stringResource\(R\.string\.term_targets_none, labelFor\(LabelKey\.TARGET_COMPUTER\)\)""").containsMatchIn(terminal))
        assertTrue("no category chosen yet", Regex("""if \(tSelectedCategory == null\) \{\s*Text\(\s*stringResource\(R\.string\.term_targets_pick\)""").containsMatchIn(terminal))
        assertTrue("an empty level", Regex("""else if \(tCurrentChildren\.isEmpty\(\)\) \{\s*Text\(\s*stringResource\(R\.string\.term_targets_empty\)""").containsMatchIn(terminal))
    }

    @Test
    fun theSaveDialogNotesWhereALineIsAlreadySavedOnlyWhenItIs() {
        assertTrue(Regex("""if \(alreadySavedTags\.isNotEmpty\(\)\) \{[\s\S]{0,300}?TerminalText\.alreadySaved\(words, alreadySavedTags\)""").containsMatchIn(terminal))
        assertTrue("the dialog is titled by the label, as before", terminal.contains("title = labelFor(LabelKey.SAVE_TO_MEMORY_BANK)"))
    }

    @Test
    fun eachReplyKeepsItsLogType_soItIsStillShownAsAWarningOrAnErrorOrAPlainReply() {
        assertTrue(terminal.contains("logTerminalLocal(context, context.getString(R.string.term_resolve_v), \"CMD_WARN\")"))
        assertTrue(terminal.contains("logTerminalLocal(context, context.getString(R.string.term_resolve_t), \"CMD_WARN\")"))
        assertTrue(Regex("""TerminalText\.clearConfirmation\(ResourceText\(context\)\),\s*"CMD_WARN"""").containsMatchIn(terminal))
        assertTrue(terminal.contains("logTerminalLocal(context, TerminalText.unknownCommand(ResourceText(context), tokens[index]), \"CMD_ERR\")"))
        assertTrue(terminal.contains("logTerminalLocal(context, context.getString(R.string.term_no_phrase), \"CMD_WARN\")"))
        assertTrue(Regex("""TerminalText\.noEmergencyDeck\([\s\S]{0,400}?\),\s*"CMD_WARN"""").containsMatchIn(terminal))
        assertTrue(terminal.contains("logTerminalLocal(context, context.getString(R.string.term_backup_cancelled), \"CMD_WARN\")"))
        assertTrue("a plain reply keeps the default type", terminal.contains("logTerminalLocal(context, context.getString(R.string.term_log_cleared))"))
        assertTrue(terminal.contains("logTerminalLocal(context, context.getString(R.string.term_services_restarted))"))
        assertTrue(terminal.contains("logTerminalLocal(context, TerminalText.helpLines(ResourceText(context)).joinToString(\"\\n\"))"))
    }

    @Test
    fun theNoEmergencyDeckWarningIsGivenThePlainWordsLabelsAtTheMomentItIsWritten() {
        assertTrue(Regex("""LabelText\.resolve\(context, LabelKey\.DECK_TYPE_EMERGENCY, PlainWordsState\.on\),\s*LabelText\.resolve\(context, LabelKey\.DECK, PlainWordsState\.on\)""").containsMatchIn(terminal))
    }

    // ---- what is logic stayed as it was ---------------------------------------------------------------------------------------------------

    @Test
    fun theTypedCommandsAndTheConfirmWordAreLogic_andTheLogTypeNamesToo() {
        assertEquals("/cls and /backup both wait for the typed word confirm", 2, Regex("""if \(rest == "confirm"\) \{""").findAll(terminal).count())
        assertTrue(terminal.contains("\"\$confirmTriggerCommand confirm\""))
        assertTrue(terminal.contains("\"OUT\", \"EMERGENCY\", \"CMD\", \"CMD_WARN\", \"CMD_ERR\" -> true"))
        assertTrue(terminal.contains("\"PATH\" -> !hidePathTrace"))
        for (flag in listOf("\"/q\", \"/quiet\" -> flags = flags.copy(quiet = true)", "\"/n\", \"/nosave\" -> flags = flags.copy(skipLog = true)", "\"/s\", \"/sticky\" -> flags = flags.copy(sticky = true)", "\"/e\", \"/emergency\" -> flags = flags.copy(emergency = true)")) {
            assertTrue("the flag parser still has $flag", terminal.contains(flag))
        }
        assertTrue(terminal.contains("OutputService.SOURCE_TERMINAL_PROMPT"))
    }

    // ---- every language -------------------------------------------------------------------------------------------------------------

    @Test
    fun theArgumentsAreWhereTheCodePutsThem() {
        val one = setOf("term_targets_none", "term_unknown_command", "term_already_saved")
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in one) {
                assertTrue("$tag/$name takes its argument", map.getValue(name).contains("%1\$s"))
                assertFalse("$tag/$name takes only one", map.getValue(name).contains("%2"))
            }
            val deck = map.getValue("term_no_emergency_deck")
            assertTrue("$tag: the warning takes the EMERGENCY label then the DECK label (in either order on screen)", deck.contains("%1\$s") && deck.contains("%2\$s"))
            for (name in names - one - "term_no_emergency_deck") assertFalse("$tag/$name takes an argument nothing passes", Regex("""%\d""").containsMatchIn(map.getValue(name)))
        }
    }

    @Test
    fun theWordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "term_info_button" to "term_confirm_button", "term_typing" to "term_awaiting", "term_vars_hint" to "term_targets_pick", "term_targets_pick" to "term_targets_empty", "term_resolve_v" to "term_resolve_t",
            "term_cls_question" to "term_cls_type", "term_backup_cancelled" to "term_log_cleared", "term_log_cleared" to "term_services_restarted", "term_no_phrase" to "term_unknown_command",
            "term_help_quiet" to "term_help_nosave", "term_help_cls" to "term_help_backup", "term_help_variables" to "term_help_targets", "term_help_info" to "term_help_manual", "term_help_help" to "term_help_header",
            "term_confirm_needed" to "term_cls_type", "term_prompt_hint" to "term_awaiting",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val descriptions = TerminalText.HELP_COMMANDS.map { map.getValue(it.second) }
            assertEquals("$tag: twelve different descriptions", 12, descriptions.toSet().size)
        }
    }

    @Test
    fun theLatinLanguagesKeepTheCapitalsTheEnglishHas() {
        for (tag in listOf("es", "pt", "af")) {
            val map = translations.getValue(tag)
            for (name in names) {
                val words = map.getValue(name).replace(Regex("""%\d+\$[sd]"""), "")
                assertEquals("$tag/$name is in capitals like the English", words.uppercase().replace("/V", "/v").replace("/T", "/t").replace("/E", "/e").replace("/HELP", "/help").replace("/CLS CONFIRM", "/cls CONFIRM"), words.replace("/v", "/v"))
            }
        }
    }

    @Test
    fun theHindiAndArabicWordsAreInTheirOwnScript() {
        for (name in names) {
            val hi = translations.getValue("hi").getValue(name)
            val ar = translations.getValue("ar").getValue(name)
            assertTrue("hi/$name has Devanagari: $hi", hi.any { it in '\u0900'..'\u097F' })
            assertTrue("ar/$name has Arabic letters: $ar", ar.any { it in '\u0600'..'\u06FF' })
        }
    }
}
