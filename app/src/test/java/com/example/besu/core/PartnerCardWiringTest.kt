// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Android files that carry the partner card (ui/PartnerCardButton.kt, output/PartnerCardPlayer.kt, MainActivity.kt, OutputService.kt) cannot be compiled without the SDK, so this reads
 * them. It holds the rules the developer chose: the normal output path and never Emergency (so it follows audio routing and is silent when silent output is on), a tap that only asks, a
 * header icon of about 24 dp that is always shown, and a whole-message display that is requested only by the card.
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
    private val main get() = noComments(source("MainActivity.kt"))
    private val service get() = noComments(source("output/OutputService.kt"))

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
        assertTrue(play.contains("putExtra(\"phrase\", PartnerCard.message(words(context)))"))
        assertTrue(play.contains("context.startService(intent)"))
    }

    @Test
    fun whatIsShownInTheQuestionIsWhatIsSpoken() {
        assertTrue(RepoFiles.declarationOf(player, "lines").contains("PartnerCard.lines(words(context))"))
        assertTrue(RepoFiles.declarationOf(player, "play").contains("PartnerCard.message(words(context))"))
        val words = player.substring(player.indexOf("private fun words"), player.indexOf("fun lines"))
        assertTrue("the translated card only under the HELP rule", words.contains("PartnerCard.speaksInterfaceLanguage(AssistPrefs.speechLanguage(context), ActiveScript.tag, Locale.getDefault().language)"))
        assertTrue("otherwise the English card", words.contains("EnglishResources.context(context)"))
    }

    @Test
    fun theCardReadsNoStorageAndWritesNone() {
        assertFalse(player.contains("getSharedPreferences"))
        assertFalse(player.contains(".edit()"))
        assertFalse(player.contains("File("))
        // And there is no setting for it anywhere: no hide switch (the developer's choice).
        for (file in listOf("core/AssistSettings.kt", "data/AssistPrefs.kt", "core/StorageCatalogue.kt", "data/InstallState.kt")) {
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
        val onPlay = dialog.substring(dialog.indexOf("onPlay = {"), dialog.indexOf("PartnerCardPlayer.play(context)"))
        assertTrue("the question closes, then the card plays", onPlay.contains("showPartnerCardDialog = false"))
    }

    // ---- the header ------------------------------------------------------------------------------------------------------------------------

    @Test
    fun theIconSitsBetweenTheSaveIconAndHelp_alwaysShown_andATapOnlyOpensTheQuestion() {
        val save = main.indexOf("BackupSaveIndicator(")
        val card = main.indexOf("PartnerCardIndicator(")
        val help = main.indexOf("AckTags.HELP_BUTTON", card)
        assertTrue("the save icon, then the card, then HELP", save in 1 until card && card < help)
        val between = main.substring(save, card)
        assertFalse("not inside a condition: there is no way to hide it", Regex("""\bif\s*\(|\bwhen\s*\(""").containsMatchIn(between))
        val call = main.substring(card, main.indexOf(")", main.indexOf("onClick", card)) + 1)
        assertTrue("a tap only opens the question", call.contains("onClick = { showPartnerCardDialog = true }"))
        assertFalse(call.contains("PartnerCardPlayer"))
    }

    @Test
    fun theQuestionsCancelAndBackAndTapOutsideDoNothingElse() {
        val dialog = main.substring(main.indexOf("if (showPartnerCardDialog) {"), main.indexOf("PartnerCardPlayer.play(context)"))
        assertTrue(dialog.contains("onCancel = { showPartnerCardDialog = false }"))
        assertTrue("the silent-mode name is handed in as the label the person sees", dialog.contains("silentModeName = labelFor(LabelKey.SILENT_MODE)"))
        assertTrue("the question shows the words that will be spoken", dialog.contains("lines = PartnerCardPlayer.lines(context)"))
        val ui = button.substring(button.indexOf("fun PartnerCardDialog"))
        assertTrue("onDismiss (back, tap outside) is the same as CANCEL", ui.contains("onDismiss = onCancel"))
    }

    @Test
    fun theIconIsAbout24dp_aPlainOutline_withNoAnimationOrHaptics() {
        assertTrue(button.contains("val PartnerCardIconSize = 24.dp"))
        val indicator = button.substring(button.indexOf("fun PartnerCardIndicator"), button.indexOf("private fun BubbleGlyph"))
        assertTrue(indicator.contains(".size(PartnerCardIconSize)"))
        assertTrue("a plain click: no ripple library, no long press", indicator.contains(".clickable(onClick = onClick)") && !indicator.contains("combinedClickable"))
        assertTrue("it has a screen-reader name", indicator.contains("contentDescription = description") && indicator.contains("PartnerCard.ICON_DESCRIPTION"))
        for (word in listOf("animate", "AnimatedVisibility", "Haptic", "vibrate", "Vibrat", "infiniteRepeatable")) assertFalse("$word must not appear in the icon or its question", button.contains(word))
    }

    @Test
    fun theQuestionHasCancelProminent_andUsesTheAppsOrdinaryButtons_at12spOrMore() {
        val ui = button.substring(button.indexOf("fun PartnerCardDialog"))
        val cancel = ui.indexOf("NeonButton(cancel, Modifier.fillMaxWidth(), mainColor = primaryColor) { onCancel() }")
        val play = ui.indexOf("NeonButton(text.get(PartnerCard.ASK_PLAY), Modifier.fillMaxWidth(), mainColor = Color.White) { onPlay() }")
        assertTrue("CANCEL in the theme colour comes first; PLAY IT is plainer and comes after", cancel in 0 until play)
        assertFalse("not the 10 sp button", button.contains("TightPanelButton"))
        assertFalse("no text below 12 sp", Regex("""fontSize\s*=\s*(\d|1[01])(\.\d+)?\.sp""").containsMatchIn(button))
        assertTrue("its text is ConfirmBodyText (12 sp)", ui.contains("ConfirmBodyText(") && !Regex("""(?<![A-Za-z])Text\(""").containsMatchIn(ui))
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
