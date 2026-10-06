// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The deck menu in MainActivity's header (the deck list, MANAGE mode, the edit panel and the two dialogs that delete a deck) and the Manual Override overlay's [CLOSE] read their words from string resources.
 * `MainActivity.kt` uses the SDK and cannot be compiled here (it is syntax-checked), so this reads it: the old English literals are gone, every string it names exists in every language and none is unused, each word
 * sits on the control that does what it says, deleting a deck still takes two steps with the delete only in the second, and a deck is still chosen by its id while only its type's word follows the language.
 * DeckMenuTextTest holds the decisions.
 */
class DeckMenuWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private val main get() = noComments(RepoFiles.read("$base/MainActivity.kt"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    private val names get() = english.keys.filter { it.startsWith("deckmenu_") } + "manual_close"

    private val firstDialog: String get() {
        val m = main
        return m.substring(m.indexOf("if (showDeleteDeckConfirm) {"), m.indexOf("if (showComputerSummary) {"))
    }
    private val finalDialog: String get() {
        val m = main
        return m.substring(m.indexOf("if (showDeleteDeckFinalConfirm) {"))
    }

    // ---- the strings and the old literals --------------------------------------------------------------------------------------------------

    @Test
    fun everyStringTheMenuNamesExists_inEveryLanguage_andNoneIsLeftUnused() {
        val referenced = Regex("""R\.string\.((?:deckmenu_|manual_close)[a-z_]*)""").findAll(main).map { it.groupValues[1] }.toSet() +
            Regex(""""(deckmenu_[a-z_]+)"""").findAll(noComments(RepoFiles.read("$base/core/DeckMenuText.kt"))).map { it.groupValues[1] }.toSet()
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            val missing = referenced.filter { it !in map }
            assertEquals("$tag: named but not defined: $missing", emptyList<String>(), missing)
        }
        assertEquals("defined but never used", emptyList<String>(), names.filter { it !in referenced })
        assertEquals("used but not defined", emptyList<String>(), referenced.filter { it !in names })
    }

    @Test
    fun theOldLiteralsAreGone() {
        val m = main
        for (literal in listOf(
            "SYSTEM DEFAULT // MATRIX", "\"+ CREATE DECK\"", "text = \"MANAGE\"", "SELECT A DECK TO RENAME", "SYSTEM MATRIX DECK LOCKED", "THE PERMANENT MATRIX DECK", "\"EXIT MANAGE\"", "\"[CLOSE]\"",
            "CONFIRM DECK DELETION", "MARK \${deck.name}", "\"[CONTINUE]\"", "\"[CANCEL]\"", "FINAL CONFIRMATION", "DELETE \${deck.name} PERMANENTLY", "THIS REMOVES THE DECK", "GIF FILES BELONGING",
            "\"[DELETE PERMANENTLY]\"", "\"[LOCKED]\"", "\"[EDIT]\"", "\"EDIT: ", "\"UI COLOR\"", "text = \"SAVE\"", "text = \"DELETE\"",
        )) assertFalse("MainActivity still holds $literal", m.contains(literal))
        assertFalse("a deck's type is never drawn from its enum name", m.contains(".type.name.replace("))
    }

    // ---- each word sits on the control that does what it says -----------------------------------------------------------------------

    @Test
    fun createAndManageOpenWhatTheirWordsSay_andTheCreateButtonReadsTheDeckCreateLabel() {
        assertTrue(Regex("""text = "\+ \$\{labelFor\(LabelKey\.DECK_CREATE\)\}",[\s\S]{0,700}?showCreateDeckDialog = true""").containsMatchIn(main))
        assertTrue(Regex("""R\.string\.deckmenu_manage\),[\s\S]{0,700}?isDeckManageMode = true""").containsMatchIn(main))
        assertTrue(Regex("""R\.string\.deckmenu_exit_manage\),[\s\S]{0,300}?exitDeckManageMode\(\)""").containsMatchIn(main))
        assertTrue("the manage heading is still the label", main.contains("text = labelFor(LabelKey.DECK_MANAGE),"))
    }

    @Test
    fun theDeckRowsShowTheSavedNameAndTheTypesWord_andAreStillChosenByTheDecksId() {
        assertEquals("the deck list and the manage list", 2, Regex("""name = DeckMenuText\.deckRow\(deck\.name, deckTypeLabel\(deck\.type\)\),""").findAll(main).count())
        assertEquals("the permanent deck's two rows", 2, Regex("""name = DeckMenuText\.systemDefaultRow\(rememberText\(\), deckTypeLabel\(DeckType\.MATRIX\)\),""").findAll(main).count())
        assertTrue(Regex("""activateDeck\(\s*deck\.id,\s*deck\.colorIndex\s*\)""").containsMatchIn(main))
        assertTrue(main.contains("managedDeckId = deck.id"))
        assertTrue(main.contains("""activateDeck("DEFAULT", 0)"""))
        assertTrue(main.contains("""managedDeckId = "DEFAULT""""))
        assertTrue("the tag at the end of a manage row", main.contains("text = DeckMenuText.rowTag(rememberText(), locked),"))
    }

    @Test
    fun theLockedNoticeAppearsOnlyForThePermanentDeck_andNamesItWithTheMatrixAndDeckWords() {
        assertTrue(Regex("""if \(managedDeckId == "DEFAULT"\) \{[\s\S]{0,300}?DeckMenuText\.lockedTitle\(rememberText\(\), deckTypeLabel\(DeckType\.MATRIX\), labelFor\(LabelKey\.DECK\)\)[\s\S]{0,600}?DeckMenuText\.lockedBody\(rememberText\(\), deckTypeLabel\(DeckType\.MATRIX\), labelFor\(LabelKey\.DECK\)\)""").containsMatchIn(main))
        assertTrue(main.contains("DeckMenuText.manageHint(rememberText(), labelFor(LabelKey.DECK))"))
    }

    @Test
    fun theEditPanelTitlesItselfWithTheTypesWord_andSaveAndDeleteDoWhatTheirWordsSay() {
        assertTrue(main.contains("text = DeckMenuText.editTitle(rememberText(), deckTypeLabel(deck.type)),"))
        assertTrue(Regex("""R\.string\.deckmenu_ui_color\)""").containsMatchIn(main))
        assertTrue("SAVE saves the name and the colour", Regex("""R\.string\.common_save\),[\s\S]{0,300}?onSave\(\s*editedName,\s*selectedColorIndex\s*\)""").containsMatchIn(main))
        assertTrue("DELETE only asks (it opens the first dialog)", Regex("""R\.string\.common_delete\),[\s\S]{0,300}?onDelete\(\)""").containsMatchIn(main))
        assertTrue("the editor's DELETE opens the first dialog, not the delete", Regex("""onDelete = \{\s*showDeleteDeckConfirm = true\s*\}""").containsMatchIn(main))
        assertTrue("the name is still capped at forty", main.contains("editedName = value.take(40)"))
    }

    @Test
    fun deletingADeckStillTakesTwoSteps_theFirstNeverDeletes_theSecondHasTheDeleteButton() {
        val first = firstDialog
        val last = finalDialog
        assertFalse("the first dialog never deletes", first.contains("deleteDeck("))
        assertEquals("the delete is in the final dialog only", 1, Regex("""CommandRepository\.deleteDeck\(""").findAll(main).count())
        assertTrue(last.contains("CommandRepository.deleteDeck("))
        assertTrue("CONTINUE only moves to the final dialog", Regex("""R\.string\.deckmenu_continue\),[\s\S]{0,700}?showDeleteDeckConfirm = false\s*showDeleteDeckFinalConfirm = true""").containsMatchIn(first))
        assertTrue("the first dialog's CANCEL only closes it", Regex("""R\.string\.deckmenu_cancel\),[\s\S]{0,500}?showDeleteDeckConfirm = false""").containsMatchIn(first))
        assertTrue("the final dialog's CANCEL only closes it", Regex("""R\.string\.deckmenu_cancel\),[\s\S]{0,500}?showDeleteDeckFinalConfirm = false""").containsMatchIn(last))
        assertTrue("DELETE PERMANENTLY deletes the managed deck", Regex("""R\.string\.deckmenu_delete_permanently\),[\s\S]{0,1200}?CommandRepository\.deleteDeck\(\s*context = context,\s*deckId = deletedDeckId""").containsMatchIn(last))
        assertTrue("the deck's own id is what is deleted", last.contains("val deletedDeckId = deck.id"))
        assertTrue(first.contains("text = DeckMenuText.deleteTitle(deckMenuWords, deckWord),") && first.contains("text = DeckMenuText.deleteQuestion(deckMenuWords, deck.name),"))
        assertTrue(last.contains("text = stringResource(R.string.deckmenu_final_title),"))
    }

    @Test
    fun theFinalDialogShowsTheGifSentenceOnlyWhenTheDecisionGivesOne_andTheDeckIsTestedByItsType() {
        val last = finalDialog
        assertTrue(Regex("""DeckMenuText\.finalConfirmation\(\s*deckMenuWords,\s*deck\.name,\s*deckWord,\s*deck\.type == DeckType\.GIF,\s*DeckMenuText\.BackupWords\(""").containsMatchIn(last))
        assertTrue(Regex("""if \(confirmation\.gifWarning != null\) \{[\s\S]{0,300}?text = confirmation\.gifWarning,""").containsMatchIn(last))
        assertTrue(last.contains("text = confirmation.question,") && last.contains("text = confirmation.removes,"))
        assertEquals("the word for DECK is the label, in both dialogs", 2, Regex("""val deckWord = labelFor\(LabelKey\.DECK\)""").findAll(main).count())
    }

    @Test
    fun theFinalDialogShowsTheBackUpAdviceNextToTheDeleteButton_inTwelvePoint_withTheWordsOfTheScreensItNames() {
        val last = finalDialog
        assertTrue("the advice is drawn at 12 sp (new text keeps the floor) and in white", Regex("""text = confirmation\.backupAdvice,\s*color = Color\.White,\s*fontSize = 12\.sp,""").containsMatchIn(last))
        assertTrue("it is in the same dialog as the delete button, before it", last.indexOf("confirmation.backupAdvice") in 1 until last.indexOf("R.string.deckmenu_delete_permanently"))
        assertFalse("the first dialog does not carry it", firstDialog.contains("backupAdvice"))
        assertTrue("EXPORT .JSON, as that button reads", last.contains("exportJson = labelFor(LabelKey.EXPORT_JSON),"))
        assertTrue("the GIF screen's export entry, worded the way that screen words it", last.contains("gifExportEntry = stringResource(R.string.gif_export_deck, deckWord),"))
        assertTrue("the GIF screen's BACKUP button", last.contains("gifBackupMenu = stringResource(R.string.gif_backup),"))
        assertTrue("the GIF deck type's label", last.contains("gifLabel = labelFor(LabelKey.DECK_TYPE_GIF)"))
    }

    @Test
    fun theManualOverrideOverlayClosesWithItsWord() {
        assertTrue(Regex("""R\.string\.manual_close\),[\s\S]{0,500}?showLegacyManualOverride = false""").containsMatchIn(main))
    }

    // ---- the type's word comes from the label table ------------------------------------------------------------------------------------

    @Test
    fun aDecksTypeWordIsTheLabelTablesWordForThatType_forEveryType_withNoFallback() {
        val source = noComments(RepoFiles.read("$base/ui/DeckTypeLabel.kt"))
        val pairs = mapOf(
            "MATRIX" to "DECK_TYPE_MATRIX", "QUICK_ACTIONS" to "DECK_TYPE_QUICK", "EMERGENCY" to "DECK_TYPE_EMERGENCY", "EMOJI" to "DECK_TYPE_EMOJI", "GIF" to "DECK_TYPE_GIF",
        )
        for ((type, key) in pairs) assertTrue("$type -> $key", source.contains("DeckType.$type -> LabelKey.$key"))
        assertFalse("no else: a new deck type must fail the build until it has a label", source.contains("else ->"))
        val types = Regex("""enum class DeckType\s*\{([^}]*)\}""").find(RepoFiles.read("$base/data/CommandRepository.kt"))?.groupValues?.get(1)
            ?.split(",")?.map { it.trim() }?.filter { it.isNotEmpty() }?.toSet()
        if (types != null) assertEquals("the helper covers every deck type", types, pairs.keys)
    }
}
