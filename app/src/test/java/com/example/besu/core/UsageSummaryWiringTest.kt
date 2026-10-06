// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The usage summary touches files that cannot be compiled or run without the Android SDK (data/UsageTallyRepository.kt, data/UsageSummaryExporter.kt, data/AssistPrefs.kt,
 * output/OutputService.kt, MainActivity, SettingsView and the two settings screens). Every rule and word is plain Kotlin and tested elsewhere (UsageTallyTest, UsageKindsTest,
 * UsageSummaryTextTest, UsageSummaryFileTest); this reads those files and holds them to the promises in docs/USAGE_SUMMARY_DESIGN.md: off for everyone and never seeded, never in
 * a backup, counted off the speech path and never for `/n` or tutorial narration, no word of a message ever kept or logged, turning on and forgetting each ask first, saving
 * only through the picker, the Terminal's quiet line, its own DELETE DATA area, and nothing smaller than 12 sp.
 */
class UsageSummaryWiringTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun source(name: String) = RepoFiles.read("$base/$name")
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line.substringBefore(" // ")
    }
    private val repo get() = noComments(source("data/UsageTallyRepository.kt"))
    private val exporter get() = noComments(source("data/UsageSummaryExporter.kt"))
    private val section get() = noComments(source("settings/UsageSummarySection.kt"))
    private val saveFlow get() = noComments(source("settings/UsageSummarySave.kt"))
    private val outputService get() = noComments(source("output/OutputService.kt"))
    private val main get() = noComments(source("MainActivity.kt"))

    // ---- the switch: off for everyone, never seeded, never in a backup ------------------------------------------------------------------------

    @Test
    fun theSwitchIsOffWhenNothingIsStored_andItsKeyIsStable() {
        assertEquals("usage_summary", AssistSettings.KEY_USAGE_SUMMARY)
        assertFalse(AssistSettings.USAGE_SUMMARY_FALLBACK)
        val prefs = source("data/AssistPrefs.kt")
        assertEquals(AssistSettings.KEY_USAGE_SUMMARY, Regex("""const val KEY_USAGE_SUMMARY = "([^"]+)"""").find(prefs)?.groupValues?.get(1))
        val read = RepoFiles.declarationOf(prefs, "isUsageSummaryOn")
        assertTrue(read.contains("AssistSettings.USAGE_SUMMARY_FALLBACK"))
        assertFalse("reading must not write", read.contains("edit()"))
    }

    @Test
    fun theSwitchIsWrittenWithCommit_andNeverSeeded_andNeverInTheSeedKeys() {
        val prefs = source("data/AssistPrefs.kt")
        assertTrue(RepoFiles.declarationOf(prefs, "setUsageSummary").contains(".commit()"))
        val seed = prefs.substring(prefs.indexOf("fun seedFreshInstallDefaults("), prefs.indexOf("fun isWordSuggestionsOn("))
        assertFalse("a new install is never given it turned on", seed.contains("USAGE"))
        assertFalse(AssistSettings.KEY_USAGE_SUMMARY in AssistSettings.SEED_KEYS)
    }

    @Test
    fun neitherTheSwitchNorTheCountsAreEverInAnExportOrARestore() {
        for (file in listOf("backup/AckBackup.kt", "backup/TransferManager.kt", "core/ExportContents.kt", "core/BackupFingerprint.kt")) {
            val text = source(file)
            assertFalse("$file must not carry the usage summary", text.contains("UsageTally") || text.contains("usageSummary") || text.contains("usage_summary") || text.contains("UsageSummary"))
        }
    }

    // ---- counting: off the speech path, never /n, never tutorial, never a word kept ----------------------------------------------------------------

    @Test
    fun nothingIsWrittenWhileTheSwitchIsOff() {
        val record = RepoFiles.declarationOf(repo.replace("    fun recordMessage", "    fun recordMessage"), "recordMessage")
        assertTrue(record.indexOf("AssistPrefs.isUsageSummaryOn(app)") in 1 until record.indexOf("executor()"))
        assertTrue(record.contains("return"))
    }

    @Test
    fun theCallInOutputServiceSitsAfterTheMessageIsHandedOn_andSkipsSlashNAndTutorialNarration() {
        val at = outputService.indexOf("UsageTallyRepository.recordMessage(")
        assertTrue(at > 0)
        assertEquals("one call", 1, Regex("""UsageTallyRepository\.recordMessage\(""").findAll(outputService).count())
        val guard = outputService.substring(outputService.lastIndexOf("if (", at), at)
        assertTrue("tutorial narration is not counted", guard.contains("!isRobotic"))
        assertTrue("a message sent with /n (do not save) is not counted", guard.contains("!skipLog"))
        assertTrue("a message with no words and no recording is not counted", guard.contains("phrase.isNullOrEmpty()") && guard.contains("recordingId.isNullOrEmpty()"))
        val dispatch = outputService.indexOf("speechQueue.add(request)")
        assertTrue("it comes after the message has been dispatched", dispatch in 1 until at)
        assertTrue(outputService.substring(at, at + 120).contains("applicationContext, source, phrase.orEmpty()"))
    }

    @Test
    fun theTutorialFlagAndTheNoSaveFlagAreTheOnesTheAppReallySets() {
        // /n sets skip_log; the HELP guide's narration sets robotic. If either name moved, the guard above would silently count what it must not.
        assertTrue(source("ui/DesignSystem.kt").contains("putExtra(\"skip_log\", flags.skipLog)"))
        assertTrue(source("MainActivity.kt").contains("putExtra(\"robotic\", true)"))
        assertTrue(outputService.contains("val isRobotic = intent.getBooleanExtra(\"robotic\", false)"))
        assertTrue(outputService.contains("val skipLog = intent.getBooleanExtra(\"skip_log\", false)"))
    }

    @Test
    fun countingNeverBlocksAndNeverThrows_theWriteIsOnOneBackgroundThread_andEveryFailureIsSwallowed() {
        val record = RepoFiles.declarationOf(repo, "recordMessage")
        assertTrue(record.contains("executor().execute"))
        assertEquals("the caller's own try/catch and the worker's", 2, Regex("""catch \(e: Throwable\)""").findAll(record).count())
        assertTrue(repo.contains("Executors.newSingleThreadExecutor"))
        assertTrue("a daemon thread, so it can never keep the process alive", repo.contains("isDaemon = true"))
        // The word comparison happens before the hand-off, so the words are not in the lambda that outlives the call.
        val cellAt = record.indexOf("UsageTally.cellFor(")
        assertTrue(cellAt in 1 until record.indexOf("executor().execute"))
        val worker = record.substring(record.indexOf("executor().execute"))
        assertFalse("the words must not reach the background thread", worker.contains("text") || worker.contains("source"))
    }

    @Test
    fun noWordOfAMessageIsEverKeptOrLogged() {
        for ((name, text) in listOf("data/UsageTallyRepository.kt" to repo, "data/UsageSummaryExporter.kt" to exporter)) {
            val calls = Regex("""Log\.[a-z]\([^\n]*""").findAll(text).map { it.value }.toList()
            assertTrue("$name should log its outcome", calls.isNotEmpty())
            for (call in calls) for (word in listOf(".text", "text)", "text}", "source", "phrase", "message)", "words", "rawText")) {
                assertFalse("a Log call in $name must not mention '$word': $call", call.contains(word))
            }
        }
        // The only String the repository stores is a cell's own name, built from a date, an hour and two fixed names.
        val storing = Regex("""put(String|StringSet)\(""").findAll(repo).count()
        assertEquals("the counts are whole numbers; no string is ever stored", 0, storing)
        assertEquals("one number per cell", 1, Regex("""putInt\(""").findAll(repo).count())
    }

    @Test
    fun readingTheCountsChangesNothing_andOnlyForgetAllDeletes() {
        val load = RepoFiles.declarationOf(repo, "load")
        assertFalse(load.contains("edit()") || load.contains("remove(") || load.contains("clear()"))
        val deleting = Regex("""clear\(\)""").findAll(repo).count()
        assertEquals("only forgetAll clears", 1, deleting)
        assertTrue(RepoFiles.declarationOf(repo, "forgetAll").contains(".clear().commit()"))
    }

    @Test
    fun forgetAllIsCalledFromExactlyOnePlace_theSecondConfirmationsDeleteButton() {
        val callers = RepoFiles.appSource.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "UsageTallyRepository.kt" }
            .filter { it.readText().contains("UsageTallyRepository.forgetAll(") }.map { it.name }.toList()
        assertEquals(listOf("UsageSummarySection.kt"), callers)
        val step2 = section.substring(section.indexOf("if (forgetStep == 2)"))
        assertTrue(step2.indexOf("UsageSummaryText.FORGET_DELETE") in 1 until step2.indexOf("UsageTallyRepository.forgetAll(context)"))
        assertEquals("exactly one call", 1, Regex("""UsageTallyRepository\.forgetAll\(""").findAll(section).count())
        assertFalse("the first question must not delete", section.substring(section.indexOf("if (forgetStep == 1)"), section.indexOf("if (forgetStep == 2)")).contains("forgetAll"))
    }

    @Test
    fun everySourceTagTheAppSendsIsInTheChannelTable_soANewEntryPointCannotBeCountedAsOtherByAccident() {
        // Reads the real source for every tag a message is sent with: putExtra("source", "TAG"), speak(text, "TAG") and speakResolvedText(a, b, "TAG").
        val literal = Regex("""putExtra\("source",\s*"([^"]+)"\)|\bspeak\([^\n]*?,\s*"([^"]+)"\)|\bspeakResolvedText\([^\n]*?,\s*"([^"]+)"\)""")
        val found = HashSet<String>()
        RepoFiles.appSource.walkTopDown().filter { it.isFile && it.extension == "kt" }.forEach { file ->
            for (m in literal.findAll(noComments(file.readText()))) found += (1..3).map { m.groupValues[it] }.first { it.isNotEmpty() }
        }
        // The terminal prompt's tag is a constant: putExtra("source", OutputService.SOURCE_TERMINAL_PROMPT).
        found += Regex("""const val SOURCE_TERMINAL_PROMPT = "([^"]+)"""").find(source("output/OutputService.kt"))!!.groupValues[1]
        // The partner card's tag is a constant too: putExtra("source", PartnerCard.SOURCE).
        found += PartnerCard.SOURCE
        assertTrue("the scan should find the app's tags (found $found)", found.size >= 10)
        val known = UsageKinds.KNOWN_SOURCES.keys
        for (tag in found) {
            val prefix = tag.substringBefore("$")
            val ok = when {
                tag.startsWith("HELP/") -> true // tutorial narration: never counted, so never a channel
                "$" in tag -> "$prefix*" in known // MTX/${title}: the whole family
                else -> tag in known
            }
            assertTrue("the source tag '$tag' is not in UsageKinds.KNOWN_SOURCES: add it there (and to channelOf), or it is counted as OTHER", ok)
        }
        for ((tag, channel) in UsageKinds.KNOWN_SOURCES) assertTrue("$tag maps to a real channel", channel != UsageChannel.OTHER)
    }

    // ---- storage: its own file, its own area, no other key -----------------------------------------------------------------------------------

    @Test
    fun theFileNameMatchesTheCoreAndTheCatalogue_andIsOwnedByTheInstallState() {
        assertEquals("ack_usage_tally", UsageTally.PREFS_FILE)
        assertEquals(UsageTally.PREFS_FILE, Regex("""private const val PREFS = "([^"]+)"""").find(source("data/UsageTallyRepository.kt"))?.groupValues?.get(1))
        val area = StorageCatalogue.area(StorageCatalogue.ID_USAGE_SUMMARY)
        assertEquals(setOf(UsageTally.PREFS_FILE), area.prefsFilesCleared)
        assertEquals(StorageCatalogue.Coverage.NOT_BACKED_UP, area.coverage)
        assertFalse("no restart is needed: the repository keeps no copy of the counts in memory", area.restartAfter)
        assertTrue(source("data/InstallState.kt").contains("\"ack_usage_tally\""))
    }

    @Test
    fun theRepositoryKeepsNoCopyOfTheCounts_soAWipeCannotLeaveItStale() {
        // No field holds the counts: every read goes to the file. The only state is the lock, the worker and the day it last tidied up.
        val fields = Regex("""(?m)^    (private )?(val|var) (\w+)""").findAll(repo).map { it.groupValues[3] }.toList()
        assertEquals(listOf("TAG", "PREFS", "lock", "worker", "lastPrunedOn"), Regex("""(?m)^    (?:private )?(?:const )?(?:val|var) (\w+)""").findAll(repo).map { it.groupValues[1] }.toList())
        assertTrue(fields.none { it.contains("count", ignoreCase = true) || it.contains("cache", ignoreCase = true) })
    }

    // ---- the screens ---------------------------------------------------------------------------------------------------------------------------

    @Test
    fun turningOnAsksFirst_withCancelProminent_andOnlyTurnOnWritesTheSwitch() {
        val asking = section.substring(section.indexOf("if (askingToTurnOn)"), section.indexOf("if (forgetStep == 1)"))
        assertTrue(asking.contains("onDismiss = { askingToTurnOn = false }"))
        assertTrue("cancel comes before turn on", asking.indexOf("NeonButton(cancel") in 1 until asking.indexOf("UsageSummaryText.ON_CONFIRM"))
        assertTrue(asking.indexOf("mainColor = primaryColor) { askingToTurnOn = false }") in 1 until asking.indexOf("UsageSummaryState.set(context, true)"))
        assertEquals("the switch is turned on in exactly one place", 1, Regex("""UsageSummaryState\.set\(context, true\)""").findAll(section).count())
        // The button itself only opens the question when it is off.
        assertTrue(section.contains("if (on) UsageSummaryState.set(context, false) else askingToTurnOn = true"))
        assertTrue(asking.contains("UsageSummaryText.onQuestion(text)"))
    }

    @Test
    fun turningOffStopsCountingAndDeletesNothing() {
        val off = section.substring(section.indexOf("if (on) UsageSummaryState.set(context, false)"), section.indexOf("if (on) UsageSummaryState.set(context, false)") + 120)
        assertFalse(off.contains("forgetAll"))
        assertTrue(RepoFiles.declarationOf(source("ui/UsageSummaryState.kt").replace("    fun set(", "    fun set("), "set").contains("AssistPrefs.setUsageSummary(context, value)"))
    }

    @Test
    fun forgettingAsksTwice_cancelProminentBothTimes_namingTheSaveButtonFirst() {
        val first = section.substring(section.indexOf("if (forgetStep == 1)"), section.indexOf("if (forgetStep == 2)"))
        assertTrue(first.contains("UsageSummaryText.forgetFirst(text, text.get(UsageSummaryText.SAVE_BUTTON))"))
        assertTrue(first.indexOf("NeonButton(cancel") in 1 until first.indexOf("R.string.common_continue"))
        val second = section.substring(section.indexOf("if (forgetStep == 2)"))
        assertTrue(second.contains("UsageSummaryText.forgetFinal(text, summary.messages)"))
        assertTrue(second.indexOf("NeonButton(cancel") in 1 until second.indexOf("UsageSummaryText.FORGET_DELETE"))
        assertTrue("tapping outside either question is CANCEL", first.contains("onDismiss = { forgetStep = 0 }") && second.contains("onDismiss = { forgetStep = 0 }"))
    }

    @Test
    fun savingWarnsFirst_writesNothingUntilAPlaceIsChosen_andOnlyThroughThePicker() {
        assertEquals(1, Regex("""CreateDocument\(""").findAll(saveFlow).count())
        assertTrue(saveFlow.contains("CreateDocument(\"text/plain\")"))
        assertEquals("the picker is launched in exactly one place", 1, Regex("""launcher\.launch\(""").findAll(saveFlow).count())
        assertTrue(saveFlow.substring(saveFlow.indexOf("onChooseLocation = {")).contains("launcher.launch(UsageSummaryFile.fileName("))
        assertTrue("cancel only hides the warning", saveFlow.contains("onDismiss = { count = null },"))
        val start = saveFlow.substring(saveFlow.indexOf("return {"))
        assertTrue(start.contains("count = UsageTallyRepository.messageCount(context)"))
        assertFalse(start.contains("launch(") || start.contains("write("))
        val dialog = saveFlow.substring(saveFlow.indexOf("fun UsageSummarySaveDialog("))
        assertTrue("an empty summary shows a line and returns before the button", dialog.indexOf("if (messageCount == 0L)") in 1 until dialog.indexOf("NeonButton("))
        val callback = saveFlow.substring(saveFlow.indexOf("CreateDocument(\"text/plain\")"), saveFlow.indexOf("val shown = count"))
        assertTrue(callback.contains("uri?.let") && callback.contains("UsageSummaryExporter.write(context, it)") && callback.contains("UsageSummaryExporter.report(context, result)"))
    }

    @Test
    fun theExporterWritesOnlyToThePickersDocument_deletesAHalfMadeFile_andNeverSharesIt() {
        assertEquals(1, Regex("""openOutputStream\(""").findAll(exporter).count())
        assertTrue(exporter.contains("DocumentsContract.deleteDocument(resolver, uri)"))
        val write = exporter.substring(exporter.indexOf("fun write("))
        for (kind in listOf("SecurityException", "IOException", "Exception")) {
            val at = write.indexOf("catch (e: $kind)")
            assertTrue(kind, at >= 0)
            assertTrue("$kind goes through failed(...)", write.substring(at, at + 120).contains("failed("))
        }
        assertTrue(write.contains("?: return failed(BackupExporter.REASON_OPEN)"))
        for ((name, text) in listOf("data/UsageSummaryExporter.kt" to exporter, "settings/UsageSummarySave.kt" to saveFlow, "settings/UsageSummarySection.kt" to section)) {
            for (forbidden in listOf("ACTION_SEND", "createChooser", "ShareCompat", "FileProvider", "java.net", "HttpURLConnection", "OkHttp", "WebView", "startActivity", "ClipboardManager")) {
                assertFalse("$name must not use '$forbidden'", text.contains(forbidden))
            }
        }
    }

    @Test
    fun theSectionIsOneItemInSettings_afterTheTerminalSectionAndBeforeDataPort() {
        val settings = noComments(source("settings/SettingsView.kt"))
        assertEquals(1, Regex("""UsageSummarySection\(""").findAll(settings).count())
        val at = settings.indexOf("UsageSummarySection(")
        assertTrue("after the message-log button", at > settings.indexOf("startLogExport()"))
        assertTrue("before DATA PORT", at < settings.indexOf("labelFor(LabelKey.DATA_PORT)"))
        val users = RepoFiles.appSource.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "UsageSummarySection.kt" }
            .filter { it.readText().contains("UsageSummarySection(") }.map { it.name }.toList()
        assertEquals(listOf("SettingsView.kt"), users)
    }

    // ---- the Terminal's quiet line -----------------------------------------------------------------------------------------------------------------

    @Test
    fun theTerminalShowsOneQuietLineWhileItIsOn_andNoOtherScreenDoes() {
        assertTrue(main.contains("remember { UsageSummaryState.load(context) }"))
        val terminal = main.substring(main.indexOf("\"TERMINAL\" -> Column("))
        val branch = terminal.substring(0, terminal.indexOf("\"MATRIX\" ->"))
        assertTrue(branch.contains("if (UsageSummaryState.on)") && branch.contains("UsageSummaryTerminalLine()"))
        assertTrue("the line is above the Terminal", branch.indexOf("UsageSummaryTerminalLine()") in 1 until branch.indexOf("TerminalView("))
        assertEquals("drawn in exactly one place", 1, Regex("""UsageSummaryTerminalLine\(""").findAll(main).count())
        val line = noComments(source("ui/UsageSummaryState.kt"))
        for (forbidden in listOf("clickable", "animate", "Animated", "Toast", "vibrat", "HapticFeedback", "MediaPlayer", "ToneGenerator")) assertFalse(forbidden, line.contains(forbidden))
        assertTrue(line.contains("UsageSummaryText.terminalLine(text)"))
    }

    // ---- looks ---------------------------------------------------------------------------------------------------------------------------------------

    @Test
    fun nothingInTheUsageScreensIsSmallerThanTwelveSp_noChartNoAnimation() {
        for ((name, text) in listOf("settings/UsageSummarySection.kt" to section, "settings/UsageSummarySave.kt" to saveFlow, "ui/UsageSummaryState.kt" to noComments(source("ui/UsageSummaryState.kt")))) {
            val sizes = Regex("""fontSize\s*=\s*(\d+(?:\.\d+)?)\.sp""").findAll(text).map { it.groupValues[1].toDouble() }.toList()
            assertTrue("$name sets a size under 12 sp", sizes.all { it >= 12.0 })
            for (forbidden in listOf("Canvas", "animate", "Animated", "MediaPlayer", "ToneGenerator", "vibrat")) assertFalse("$name must not use '$forbidden'", text.contains(forbidden))
            assertFalse("$name must not type the English words itself", text.contains("MESSAGES COUNTED") || text.contains("NEVER THE WORDS"))
        }
        assertTrue(section.contains("ConfirmBodyText("))
    }

    @Test
    fun theSectionTypesNoWordsOfItsOwn_everythingComesFromTheCoreWords() {
        for (text in listOf(section, saveFlow)) {
            assertFalse("no raw R.string in the usage screens except the shared cancel, continue and picker words",
                Regex("""R\.string\.(?!common_cancel|common_continue|export_choose_where)""").containsMatchIn(text))
        }
        assertTrue(section.contains("UsageSummaryText.explanation(text)") && section.contains("UsageSummaryText.switchLabel(text, on)"))
    }
}
