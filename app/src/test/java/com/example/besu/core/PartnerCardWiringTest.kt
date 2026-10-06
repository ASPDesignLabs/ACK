// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Android files that carry the partner card (ui/PartnerCardButton.kt, ui/PartnerCardState.kt, output/PartnerCardPlayer.kt, data/PartnerCardRepository.kt, MainActivity.kt, OutputService.kt and the
 * backup) cannot all be compiled without the SDK, so this reads them. It holds the rules the developer chose: the normal output path and never Emergency (so it follows audio routing and is silent when
 * silent output is on), a tap that only asks, a header icon of about 24 dp that is always shown, a switch for every sentence, the person's own sentences kept as they wrote them (backed up, wiped with
 * their messages, never logged), and a whole-message display that is requested only by the card.
 */
class PartnerCardWiringTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line.substringBefore(" // ")
    }
    private val player get() = noComments(source("output/PartnerCardPlayer.kt"))
    private val button get() = noComments(source("ui/PartnerCardButton.kt"))
    private val state get() = noComments(source("ui/PartnerCardState.kt"))
    private val repo get() = noComments(source("data/PartnerCardRepository.kt"))
    private val main get() = noComments(source("MainActivity.kt"))
    private val service get() = noComments(source("output/OutputService.kt"))

    /** The text of one composable function in ui/PartnerCardButton.kt, from its `fun` to the next top-level declaration. */
    private fun composable(name: String): String {
        val at = button.indexOf("fun $name(")
        check(at >= 0) { "fun $name( not found" }
        val next = Regex("""\n(@Composable|private fun|fun |val |object )""").find(button, at + 1)
        return button.substring(at, next?.range?.first ?: button.length)
    }

    // ---- the normal path, never Emergency ---------------------------------------------------------------------------------------------

    @Test
    fun theCardIsSentOnTheNormalPath_neverEmergency_andNotQuietOrStickyBecauseThosePicksAreThePersonsOwn() {
        val play = RepoFiles.declarationOf(player, "play")
        assertTrue("it sends an intent to the output service", play.contains("Intent(context, OutputService::class.java)"))
        assertFalse("no action: the message branch is the normal path", play.contains("action") || player.contains("setAction"))
        assertFalse("the card must never take the Emergency path (it always speaks on the phone and ignores silent output)", player.contains("emergency", ignoreCase = true))
        assertFalse("no forced quiet (silent output is the person's own setting)", player.contains("\"quiet\""))
        assertFalse("no skip_log: it is a message and appears in the log like one", player.contains("skip_log"))
        assertFalse("no forced sticky", player.contains("\"sticky\""))
        assertTrue(play.contains("putExtra(\"robotic\", false)"))
        assertTrue(play.contains("putExtra(\"source\", PartnerCard.SOURCE)"))
        assertTrue(play.contains("putExtra(\"phrase\", message)"))
        assertTrue(play.contains("putExtra(\"full_text\", true)"))
        assertTrue(play.contains("context.startService(intent)"))
    }

    @Test
    fun whatIsSaidIsTheChoiceTheQuestionShowed_andNothingIsSaidWhenNothingIsOn() {
        val play = RepoFiles.declarationOf(player, "play")
        assertTrue(play.contains("val message = PartnerCard.message(words(context), settings)"))
        assertTrue("an empty card sends nothing", play.indexOf("if (message.isEmpty()) return") in 0 until play.indexOf("context.startService(intent)"))
        assertTrue(RepoFiles.declarationOf(player, "rows").contains("PartnerCard.rows(words(context), settings)"))
        val words = player.substring(player.indexOf("private fun words"), player.indexOf("fun rows"))
        assertTrue("the built-in sentences in the translated card only under the HELP rule", words.contains("PartnerCard.speaksInterfaceLanguage(AssistPrefs.speechLanguage(context), ActiveScript.tag, Locale.getDefault().language)"))
        assertTrue("otherwise the English card", words.contains("EnglishResources.context(context)"))
    }

    @Test
    fun theSenderReadsNoStorage_andThereIsNoSettingToHideTheIcon() {
        assertFalse(player.contains("getSharedPreferences"))
        assertFalse(player.contains("PartnerCardRepository"))
        assertFalse(player.contains(".edit()"))
        // No hide switch (the developer's choice): none of the switch files holds anything about the card.
        for (file in listOf("core/AssistSettings.kt", "data/AssistPrefs.kt")) {
            assertFalse("$file must not hold a partner-card setting", source(file).contains("partner", ignoreCase = true))
        }
    }

    @Test
    fun onlyTheQuestionsPlayButtonSendsIt() {
        val callers = RepoFiles.appSource.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "PartnerCardPlayer.kt" }
            .filter { noComments(it.readText()).contains("PartnerCardPlayer.play(") }.map { it.name }.toList()
        assertEquals(listOf("MainActivity.kt"), callers)
        assertEquals("exactly one call", 1, Regex("""PartnerCardPlayer\.play\(""").findAll(main).count())
        val dialog = main.substring(main.indexOf("if (showPartnerCardDialog) {"))
        val onPlay = dialog.substring(dialog.indexOf("onPlay = {"), dialog.indexOf("PartnerCardPlayer.play(context, partnerSettings)"))
        assertTrue("the question closes, then the card plays what the question showed", onPlay.contains("showPartnerCardDialog = false"))
    }

    // ---- the header ------------------------------------------------------------------------------------------------------------------------

    @Test
    fun theIconSitsBetweenTheSaveIconAndHelp_alwaysShown_andATapOnlyOpensTheQuestion() {
        val save = main.indexOf("BackupSaveIndicator(")
        val card = main.indexOf("PartnerCardIndicator(")
        val help = main.indexOf("AckTags.HELP_BUTTON", card)
        assertTrue("the save icon, then the card, then HELP", save in 1 until card && card < help)
        assertFalse("not inside a condition: there is no way to hide it", Regex("""\bif\s*\(|\bwhen\s*\(""").containsMatchIn(main.substring(save, card)))
        val call = main.substring(card, main.indexOf("Spacer(modifier = Modifier.width(4.dp))", card))
        assertTrue("a tap reads the saved choice, then opens the question", call.indexOf("PartnerCardState.load(context)") in 0 until call.indexOf("showPartnerCardDialog = true"))
        assertFalse("a tap speaks nothing", call.contains("PartnerCardPlayer"))
    }

    @Test
    fun theQuestionsCancelAndBackAndTapOutsideDoNothingElse() {
        val dialog = main.substring(main.indexOf("if (showPartnerCardDialog) {"), main.indexOf("PartnerCardPlayer.play(context, partnerSettings)"))
        assertTrue(dialog.contains("onCancel = { showPartnerCardDialog = false }"))
        assertTrue("the silent-mode name is handed in as the label the person sees", dialog.contains("silentModeName = labelFor(LabelKey.SILENT_MODE)"))
        assertTrue("the question shows the sentences as they will be said, with the saved choice", dialog.contains("rows = PartnerCardPlayer.rows(context, partnerSettings)"))
        assertTrue(dialog.contains("anyOn = partnerSettings.anyOn"))
        assertTrue("onDismiss (back, tap outside) is the same as CANCEL", composable("PartnerCardDialog").contains("onDismiss = onCancel"))
        assertTrue(composable("PartnerCardEditDialog").contains("onDismiss = onCancel"))
    }

    @Test
    fun theIconIsAbout24dp_aPlainOutline_withNoAnimationOrHaptics() {
        assertTrue(button.contains("val PartnerCardIconSize = 24.dp"))
        val indicator = composable("PartnerCardIndicator")
        assertTrue(indicator.contains(".size(PartnerCardIconSize)"))
        assertTrue("a plain click: no long press", indicator.contains(".clickable(onClick = onClick)") && !indicator.contains("combinedClickable"))
        assertTrue("it has a screen-reader name", indicator.contains("contentDescription = description") && indicator.contains("PartnerCard.ICON_DESCRIPTION"))
        for (word in listOf("animate", "AnimatedVisibility", "Haptic", "vibrate", "Vibrat", "infiniteRepeatable")) assertFalse("$word must not appear in the icon or its dialogs", button.contains(word))
    }

    // ---- the question: a switch for every sentence ------------------------------------------------------------------------------------

    @Test
    fun everySentenceIsAWholeRowSwitch_atLeast48dp_withOnOrOffWritten_andNoHaptics() {
        val row = composable("SentenceRow")
        assertTrue("a switch row", row.contains(".toggleable(value = row.on, role = Role.Switch, onValueChange = { onToggle() })"))
        assertTrue("at least 48 dp tall", row.contains(".heightIn(min = 48.dp)"))
        assertTrue("ON or OFF in words, not only a colour", row.contains("R.string.common_on") && row.contains("R.string.common_off"))
        assertFalse("not a NeonButton (they vibrate): the switch row is a plain toggle", row.substring(0, row.indexOf("if (row.own)")).contains("NeonButton"))
        assertTrue("an own sentence has an EDIT button and an empty slot a WRITE button", row.contains("PartnerCard.EDIT") && row.contains("PartnerCard.WRITE"))
        assertTrue("an empty slot has no switch: WRITE is in the branch where nothing is written", row.indexOf("PartnerCard.WRITE") > row.indexOf("} else {"))
        val dialog = composable("PartnerCardDialog")
        assertTrue("one row per sentence", dialog.contains("rows.forEach { row ->") && dialog.contains("SentenceRow(row, primaryColor, onToggle = { onToggle(row.slot) }, onEdit = { onEditOwn(row.slot) })"))
    }

    @Test
    fun playItIsOnlyOfferedWhenSomethingIsOn_andALineSaysWhatToDoOtherwise() {
        val dialog = composable("PartnerCardDialog")
        assertTrue(Regex("""if \(anyOn\) \{\s*Spacer\(modifier = Modifier\.height\(8\.dp\)\)\s*NeonButton\(text\.get\(PartnerCard\.ASK_PLAY\)""").containsMatchIn(dialog))
        assertEquals("PLAY IT appears once", 1, Regex("""PartnerCard\.ASK_PLAY""").findAll(dialog).count())
        assertTrue("the line that says what to do", dialog.contains("PartnerCard.NONE_ON"))
        assertTrue("the silent-mode sentence only when it will play", dialog.indexOf("PartnerCard.ASK_SILENT") < dialog.indexOf("PartnerCard.NONE_ON"))
    }

    @Test
    fun theQuestionHasCancelProminent_andUsesTheAppsOrdinaryButtons_at12spOrMore() {
        val ui = composable("PartnerCardDialog")
        val cancel = ui.indexOf("NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }")
        val play = ui.indexOf("NeonButton(text.get(PartnerCard.ASK_PLAY), Modifier.fillMaxWidth(), mainColor = Color.White) { onPlay() }")
        assertTrue("CANCEL in the theme colour comes first; PLAY IT is plainer and comes after", cancel in 0 until play)
        assertFalse("not the 10 sp button", button.contains("TightPanelButton"))
        assertFalse("no text below 12 sp", Regex("""fontSize\s*=\s*(\d|1[01])(\.\d+)?\.sp""").containsMatchIn(button))
        for (name in listOf("PartnerCardDialog", "SentenceRow")) {
            val part = composable(name)
            assertTrue("$name draws its words with ConfirmBodyText (12 sp)", part.contains("ConfirmBodyText(") && !Regex("""(?<![A-Za-z])Text\(""").containsMatchIn(part))
        }
    }

    // ---- the person's own sentences ---------------------------------------------------------------------------------------------------

    @Test
    fun writingASentenceNeedsASave_andNothingIsKeptWhileTyping() {
        val edit = composable("PartnerCardEditDialog")
        assertTrue("the box keeps the typed text in a local draft and limits it", edit.contains("var draft by remember { mutableStateOf(current) }") && edit.contains("draft = PartnerCard.limitDraft(it)"))
        assertEquals("onSave is called from exactly one place: the SAVE button", 1, Regex("""onSave\(""").findAll(edit).count())
        assertTrue("SAVE is offered only when something is written", Regex("""if \(PartnerCard\.cleanOwn\(draft\)\.isNotEmpty\(\)\) \{[\s\S]{0,200}stringResource\(R\.string\.common_save\)[\s\S]{0,120}onSave\(draft\)""").containsMatchIn(edit))
        val cancel = edit.indexOf("NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }")
        assertTrue("CANCEL is prominent and first", cancel in 0 until edit.indexOf("stringResource(R.string.common_save)"))
        assertTrue("it says what the text box is for and that it is in the export", edit.contains("PartnerCard.EDIT_HINT, exportName, PartnerCard.MAX_OWN_LENGTH.toString()"))
        assertFalse("the edit dialog never speaks", edit.contains("PartnerCardPlayer") || edit.contains("startService"))
    }

    @Test
    fun clearingASentenceAsksASecondTime_andOnlyTheSecondQuestionClears() {
        val edit = composable("PartnerCardEditDialog")
        assertEquals("onClear is called from exactly one place", 1, Regex("""onClear\(\)""").findAll(edit).count())
        val first = edit.substring(edit.indexOf("PartnerCard.CLEAR)"), edit.indexOf("if (asking) {"))
        assertTrue("the first button only asks", first.contains("asking = true") && !first.contains("onClear"))
        assertTrue("CLEAR is offered only for a written sentence", Regex("""if \(current\.isNotEmpty\(\)\) \{[\s\S]{0,200}PartnerCard\.CLEAR\)""").containsMatchIn(edit))
        val second = edit.substring(edit.indexOf("if (asking) {"))
        assertTrue("CANCEL is prominent and first in the second question", second.indexOf("mainColor = primaryColor) { asking = false }") in 0 until second.indexOf("PartnerCard.CLEAR_CONFIRM"))
        assertTrue("the second question's last button clears", second.indexOf("PartnerCard.CLEAR_CONFIRM") < second.indexOf("onClear()"))
        assertTrue("both asks say it cannot be undone", second.contains("PartnerCard.CLEAR_BODY"))
    }

    @Test
    fun everyChangeIsKeptBeforeItIsShown_andAFailureSaysNothingChanged() {
        val change = state.substring(state.indexOf("private fun change("))
        assertTrue(change.indexOf("PartnerCardRepository.save(context, next)") in 1 until change.indexOf("settings = next"))
        assertTrue("a failed save leaves the shown choice alone", change.contains("if (!PartnerCardRepository.save(context, next)) return false"))
        assertTrue(state.contains("fun toggle(context: Context, slot: Int): Boolean = change(context, settings.toggled(slot))"))
        assertTrue(state.contains("fun writeOwn(context: Context, slot: Int, raw: String): Boolean = change(context, settings.withOwn(slot, raw))"))
        assertFalse("nothing is spoken from the state", state.contains("OutputService") || state.contains("startService"))
        val dialog = main.substring(main.indexOf("if (showPartnerCardDialog) {"), main.indexOf("if (showHelpMenu) {"))
        assertTrue("the person is told when a choice could not be kept", dialog.contains("R.string.partner_card_save_failed") && Regex("""Toast\.makeText""").findAll(dialog).count() == 3)
        assertTrue(dialog.contains("if (PartnerCardState.writeOwn(context, ownSlot, raw)) editingOwnSlot = null"))
        assertTrue("clearing writes an empty sentence", dialog.contains("PartnerCardState.writeOwn(context, ownSlot, \"\")"))
        assertTrue("the edit dialog is shown only while a slot is being edited, over the question", dialog.contains("if (ownSlot == null) {") && dialog.contains("onEditOwn = { slot -> editingOwnSlot = slot }"))
        assertTrue("CANCEL on the edit dialog changes nothing", dialog.contains("onCancel = { editingOwnSlot = null }"))
    }

    // ---- storage, DELETE DATA and the backup ------------------------------------------------------------------------------------------

    @Test
    fun theRepositoryKeepsThreeValuesInItsOwnFile_commitsThem_andLogsNoSentence() {
        assertEquals("ack_partner_card", PartnerCardSettings.PREFS_FILE)
        assertEquals(PartnerCardSettings.PREFS_FILE, Regex("""private const val PREFS = "([^"]+)"""").find(repo)?.groupValues?.get(1))
        assertTrue(RepoFiles.declarationOf(repo, "save").contains("edit.commit()"))
        assertTrue("it stores exactly what the settings say, nothing else", RepoFiles.declarationOf(repo, "save").contains("settings.toStored()"))
        // Every log line is a fixed sentence: nothing the person wrote is ever logged, not even in an error.
        val logs = Regex("""Log\.\w\([^\n]*\)""").findAll(repo).map { it.value }.toList()
        assertTrue("it logs something only on failure", logs.isNotEmpty())
        for (line in logs) assertTrue("a fixed sentence only: $line", Regex("""Log\.\w\(TAG, "[^"$]*"\)""").matches(line))
        assertFalse(repo.contains("println") || repo.contains("e.message") || repo.contains("e.toString"))
    }

    @Test
    fun theOwnSentencesAreWipedWithTheMessagesArea_andOwnedByTheInstallState() {
        val area = StorageCatalogue.area(StorageCatalogue.ID_MESSAGES_AND_DECKS)
        assertTrue(PartnerCardSettings.PREFS_FILE in area.prefsFilesCleared)
        assertEquals("they are in EXPORT .JSON", StorageCatalogue.Coverage.EXPORT_JSON, area.coverage)
        assertTrue(source("data/InstallState.kt").contains("\"ack_partner_card\""))
    }

    @Test
    fun theBackupHoldsOnlyTheOwnSentences_validatesThem_andRestoreOnlyAdds() {
        assertTrue(noComments(source("backup/AckBackup.kt")).contains("val partnerCard: PartnerCardBackup? = null"))
        val export = RepoFiles.declarationOf(noComments(source("data/PartnerCardRepository.kt")), "exportForBackup")
        assertTrue("nothing written means nothing to say", export.contains("if (written.isEmpty()) null else PartnerCardBackup(written)"))
        assertFalse("the on/off choices are not in a backup", export.contains(".off"))
        val transfer = noComments(source("backup/TransferManager.kt"))
        assertTrue(transfer.contains("partnerCard = PartnerCardRepository.exportForBackup(context)"))
        val validate = transfer.substring(transfer.indexOf("backup.partnerCard?.validate()"))
        assertTrue("a refusal logs the reason (sizes only) and refuses", validate.substring(0, 160).contains("Log.e(\"ACK_IMPORT\", reason)") && validate.substring(0, 200).contains("return false"))
        assertTrue(transfer.contains("backup.partnerCard?.let { PartnerCardRepository.mergeFromBackup(context, it) }"))
        val merge = RepoFiles.declarationOf(repo, "mergeFromBackup")
        assertTrue("restore goes through the adding rule", merge.contains("PartnerCardSettings.mergeOwn(device, backup.ownSentences)"))
        assertFalse("restore never turns a sentence on or off", merge.contains("toggled") || merge.contains("withOwn"))
    }

    @Test
    fun theExportWarningNamesTheCardsSentences() {
        val category = ExportContents.categories.single { "partnerCard" in it.fields }
        assertEquals("partner_card", category.key)
        assertEquals("export_cat_partner_card", category.resource)
    }

    @Test
    fun aPlayIsCountedAsThePartnerCardKind_byItsTagNotItsWords() {
        val record = RepoFiles.declarationOf(noComments(source("data/UsageTallyRepository.kt")).replace("    fun recordMessage", "    fun recordMessage"), "recordMessage")
        assertTrue(record.contains("UsageKinds.kindOf(source, text)"))
        assertFalse("the words alone never decide the kind any more", record.contains("UsageKinds.kindOf(text)"))
    }

    // ---- the whole message is shown, only when the card asks ------------------------------------------------------------------------

    @Test
    fun theWholeMessageIsShownOnlyWhenTheCardAsksForIt_andItTravelsEveryRouteToTheScreen() {
        assertTrue("the extra is read", service.contains("""intent.getBooleanExtra("full_text", false)"""))
        assertTrue("the queued request carries it", service.contains("val fullText: Boolean = false") && service.contains("fullText = fullText\n"))
        assertEquals("both ways a request reaches processSpeech pass it on (straight away, and after the queue)", 2, Regex("""fullText = (request|item)\.fullText""").findAll(service).count())
        assertTrue(service.contains("fullText: Boolean = false\n    ) {\n        val targetId"))
        assertTrue("processSpeech hands it to the visual prompt", Regex("""willSpeak = !speechIsSilenced\(quiet, emergency\),\s*fullText = fullText""").containsMatchIn(service))
        assertTrue("the preset is changed only for this message", service.contains("val preset = if (fullText) activePreset.copy(bypassTruncation = true) else activePreset"))
        // Nothing else asks: only the card sends the extra, so every other message follows the person's own preset exactly as before.
        val senders = RepoFiles.appSource.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "OutputService.kt" }
            .filter { noComments(it.readText()).contains("\"full_text\"") }.map { it.name }.toList()
        assertEquals(listOf("PartnerCardPlayer.kt"), senders)
    }
}
