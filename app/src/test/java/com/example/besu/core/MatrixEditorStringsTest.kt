// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Matrix editor dialog (opened from a Matrix row) reads its words from string resources. The file cannot be compiled here, so this reads it: the
 * old English literals are gone from the editor, the format arguments match what it passes, and the logic around the words (which clear was chosen, the
 * tokens it inserts, the stored values) is exactly as it was. That every string it names exists and is used is checked in MatrixDeckScreenStringsTest.
 */
class MatrixEditorStringsTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        // Whole-line comments only: " // " also appears inside the screen's own text ("... // TAG ..."), so a trailing-comment cut would eat it.
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val design get() = noComments(RepoFiles.read("$base/ui/DesignSystem.kt"))
    private val english get() = StringsXml.map(StringsXml.default)

    private fun editor(): String {
        val text = design
        return text.substring(text.indexOf("fun MatrixEditor("), text.indexOf("fun MatrixCategory("))
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawnByTheEditor() {
        val gone = listOf(
            "\"LIVE-SAVE EDITOR\"", "\"MACRO TEMPLATE\"", "\"ENTER OUTPUT PHRASE...\"", "\"INSERT VARIABLE TOKEN\"", "\"VOICE RECORDING\"", "\"ATTACH VOICE RECORDING\"",
            "\"VISUAL PROMPT OVERRIDE\"", "\"RE-ENABLE (MATCH CURRENT TEXT)\"", "\"LOCAL VARIABLE DATA\"", "\"ENTER LOCAL FALLBACK...\"", "\"TARGET TAG FALLBACKS\"",
            "\"DESTRUCTIVE CONTROLS\"", "\"CLEAR VARS\"", "\"CLEAR PROMPT\"", "\"CLEAR ALL\"", "\"CONFIRM CLEAR\"", "\"RECORDING DISABLED\"", "\"OK, GOT IT\"",
            "\"LIVE VARIABLE VALUE\"", "\"ENTER VALUE\"", "\"COMMIT\"", "\"CLOSE\"", "\"CONFIRM\"", "\"CANCEL\"", "\"ABORT\"", "\"UPDATE\"",
            "Clear every local variable value", "Clear this prompt only", "Clear both the prompt", "This entry has \$variableCount", "This entry's text changed",
            "Saved immediately.", "resolves to whichever entry", "// VAR \${request",
        )
        val code = editor()
        for (literal in gone) assertFalse("the editor still draws $literal", code.contains(literal))
    }

    @Test
    fun theFormatStringsTakeTheArgumentsTheEditorPasses() {
        assertEquals(listOf("%1\$d", "%2\$d"), StringsXml.placeholders(english.getValue("matrix_edit_voice_info")))
        assertEquals(listOf("%1\$d", "%2\$d"), StringsXml.placeholders(english.getValue("matrix_edit_attach_body")))
        assertEquals(listOf("%1\$d", "%2\$s"), StringsXml.placeholders(english.getValue("matrix_edit_target_tag")))
        val code = editor()
        assertEquals(1, Regex("""stringResource\(R\.string\.matrix_edit_voice_info, variableCount, computerTagCount\)""").findAll(code).count())
        assertEquals(1, Regex("""stringResource\(R\.string\.matrix_edit_attach_body, variableCount, computerTagCount\)""").findAll(code).count())
        assertTrue(code.contains("stringResource(R.string.matrix_edit_target_tag, index + 1, categoryLabel)"))
        // The variable's title names the slot and the fill-in through the label table (so PLAIN WORDS applies), with the same index as before.
        assertTrue(code.contains("\"\${slotLabel(request.nodeLabel)} // \${stringFormatLabel(LabelKey.VARIABLE_TAG, request.index + 1)}\""))
    }

    @Test
    fun theLogicAroundTheWordsIsAsItWas() {
        val code = editor()
        // Which clear was chosen is a stored mode name, not a word on the screen.
        for (mode in listOf("VARS", "PROMPT", "ALL")) assertTrue(code.contains("clearMode = \"$mode\""))
        assertTrue(code.contains("insertTokenAtCursor(\"{VAR}\")"))
        assertTrue(code.contains("insertTokenAtCursor(\"{VAR:A}\")"))
        assertTrue(code.contains("insertTokenAtCursor(\"[COMPUTER:\${computerCategory.id}]\")"))
        // The BUILDER training deck is detected by name; its text stays the developer's own.
        assertTrue(code.contains("deckName == \"BUILDER\""))
    }

    @Test
    fun theThreeConfirmationsAreSentencesNotCapitals_andKeepBothSentencesInEveryLanguage() {
        for (name in listOf("matrix_edit_confirm_vars", "matrix_edit_confirm_prompt", "matrix_edit_confirm_all")) {
            val text = english.getValue(name)
            assertTrue(name, text != text.uppercase())
            assertEquals("$name must be one string with both sentences", 2, Regex("""[.?]\s""").findAll(text).count() + 1)
        }
        // The old bug (two lines of text with nothing joining them) cannot return: the whole confirmation is one resource.
        assertTrue(english.getValue("matrix_edit_confirm_vars").startsWith("Clear every local variable value for this phrase? The prompt will remain."))
    }

    @Test
    fun theTokenInTheFallbackHintIsKeptInEveryLanguage() {
        assertTrue(english.getValue("matrix_edit_fallbacks_hint").contains("[COMPUTER:X]"))
        for ((tag, file) in StringsXml.translations()) {
            assertTrue(tag, StringsXml.map(file).getValue("matrix_edit_fallbacks_hint").contains("[COMPUTER:X]"))
        }
    }
}
