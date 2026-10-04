// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * MANAGE RECORDINGS (settings/ManageRecordingsDialog.kt), the voice recording panel four screens embed (output/VoiceRecordingPanel.kt) and the HELP offer's [GOT IT] read their words
 * from string resources, in the chosen language. They cannot be compiled or run here, so this reads them: the old English literals are gone, every string named exists and none is
 * unused, the tree is still identified by stored names, **what the preview sends to the overlay is still the English text**, each word sits on the control that does what it says, and a
 * recording is only deleted from the confirmation or the panel's own REMOVE.
 */
class ManageRecordingsWordingTest {

    private val base = "app/src/main/java/com/example/besu"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(path: String) = noComments(RepoFiles.read("$base/$path"))
    private val dialog get() = file("settings/ManageRecordingsDialog.kt")
    private val panel get() = file("output/VoiceRecordingPanel.kt")
    private val banner get() = file("help/HelpOfferBanner.kt")
    private val settings get() = file("settings/SettingsView.kt")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val recNames get() = english.keys.filter { it.startsWith("voice_rec_") || it.startsWith("manage_rec_") || it == "help_got_it" } +
        StringsXml.plurals(StringsXml.default).keys.filter { it.startsWith("manage_rec_") }

    @Test
    fun everyStringTheScreensNameExists_andNoneIsLeftUnused() {
        val screens = dialog + "\n" + panel + "\n" + banner + "\n" + settings
        val referenced = Regex("""R\.string\.((?:voice_rec_|manage_rec_|help_got_it)[a-z_]*)""").findAll(screens).map { it.groupValues[1] }.toSet()
        val missing = referenced.filter { it !in recNames }
        assertEquals("named but not defined: $missing", emptyList<String>(), missing)
        val named = Regex(""""((?:voice_rec_|manage_rec_)[a-z_]+)"""").findAll(screens + "\n" + file("core/RecordingLabels.kt")).map { it.groupValues[1] }.toSet()
        val unused = recNames.toSet() - referenced - named
        assertTrue("defined but never used: $unused", unused.isEmpty())
        for (name in listOf("common_cancel", "common_delete", "common_discard")) assertTrue("$name is not used", name in Regex("""R\.string\.(common_[a-z_]+)""").findAll(dialog + panel).map { it.groupValues[1] }.toSet())
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawn() {
        val goneDialog = listOf(
            "\"MANAGE RECORDINGS\"", "RECORDING\${if", "[OVERLAY: ON]", "[OVERLAY: OFF]", "NEW: VOICE RECORDINGS HAS A HELP WALKTHROUGH", "NO RECORDINGS YET", "\"DELETE RECORDING\"", "\"CANCEL\"",
            "This removes the recording", "\"DELETE\"", "\"RE-RECORD\"", "DISABLED -- entry text", "\"PLAYING...\"", "\"PLAY\"", "\"SLOT \${", "\"QUICK ACTIONS (", "\"QUICK-ACCESS KEYS (", "\"MATRIX (",
            "\"UNKNOWN NODE\"", "\"UNKNOWN\"",
        )
        for (literal in goneDialog) assertFalse("ManageRecordingsDialog.kt still holds $literal", dialog.contains(literal))
        val gonePanel = listOf(
            "\"VOICE RECORDING\"", "WHEN SET, THIS PLAYS INSTEAD OF THE SYNTHESIZED PHRASE", "NEW: VOICE RECORDINGS HAS", "\"RECORDED (", "\"PLAYING...\"", "\"PLAY\"", "\"REMOVE\"", "\"RE-RECORD\"", "\"RECORD\"",
            "\"RECORDING... ", "\"STOP\"", "\"CANCEL\"", "REDUCING NOISE", "\"PREVIEW (", "\"DISCARD\"", "\"ACCEPT\"",
        )
        for (literal in gonePanel) assertFalse("VoiceRecordingPanel.kt still holds $literal", panel.contains(literal))
        assertFalse("HelpOfferBanner.kt still holds [GOT IT]", banner.contains("[GOT IT]"))
        for (literal in listOf("\"\$keyLabel RECORDING\"", "WHEN SET, THIS PLAYS INSTEAD OF THE KEY'S TARGET PHRASE")) assertFalse("SettingsView.kt still holds $literal", settings.contains(literal))
        for ((name, text) in listOf("ManageRecordingsDialog.kt" to dialog, "VoiceRecordingPanel.kt" to panel, "HelpOfferBanner.kt" to banner)) {
            assertTrue("$name needs an explicit R import outside the base package", text.contains("import com.example.besu.R"))
        }
    }

    // ---- the tree is identified by stored names; the overlay is never translated -----------------------------------------------------------

    @Test
    fun theTreeIsStillGroupedAndIdentifiedByTheStoredNames_andANameThePersonGaveIsShownAsTyped() {
        assertTrue(dialog.contains("private fun buildRecordingTree(context: Context, text: TextSource, recordings: List<VoiceRecording>)"))
        assertTrue(dialog.contains("buildRecordingTree(context, text, recordings)"))
        assertTrue(dialog.contains("RecBranch(id = \"mtx_${'$'}{deckId}_${'$'}{profile}_${'$'}pose\", label = TreeLabels.poseOrLayer(text, pose), children = nodeLeaves)"))
        assertTrue(dialog.contains("RecBranch(id = \"mtx_${'$'}{deckId}_${'$'}profile\", label = profile, children = poseBranches)"))
        assertTrue(dialog.contains("RecBranch(id = \"qa_deck_${'$'}deckId\", label = deckName, children = qaGroupBranches)"))
        assertTrue(dialog.contains("val groupLabel = group?.label ?: \"G${'$'}{groupIndex + 1}\""))
        assertTrue(dialog.contains("val keyLabel = shortcuts.getOrNull(index)?.label ?: \"M${'$'}{index + 1}\""))
        assertTrue(dialog.contains("?: TreeLabels.defaultSlot(text, rec.slotIndex ?: 0)"))
        assertTrue(dialog.contains("?: TreeLabels.unknownNode(text)"))
        assertEquals("the missing pose is grouped under the key that cannot be a layer name", 1, Regex("""TreeLabels\.UNKNOWN_KEY""").findAll(dialog).count())
        for (kind in listOf("QUICK_ACTIONS", "QUICK_ACCESS_KEYS", "MATRIX")) assertTrue(kind, dialog.contains("TreeLabels.Kind.$kind"))
        for (id in listOf("kind_qa", "kind_qk", "kind_mtx")) assertTrue(id, dialog.contains("id = \"$id\""))
    }

    @Test
    fun whatThePreviewSendsToTheOverlayIsStillTheEnglishText() {
        assertTrue(dialog.contains("putExtra(\"preview_visual_text\", resolveOverlayText(context, recording))"))
        val start = dialog.indexOf("private fun resolveOverlayText(")
        val body = dialog.substring(start, dialog.indexOf("\n}\n", start))
        assertTrue(body.contains("found.text ?: found.missing.overlayText"))
        assertFalse("the overlay text must not read a string resource", body.contains("stringResource") || body.contains("text.get") || body.contains("missingText"))
        // The person's own list shows the language's placeholder instead, and only there.
        assertTrue(dialog.contains("found.text ?: RecordingLabels.missingText(text, found.missing)"))
        // And the cases are the ones there always were: a blank phrase and an unknown node are the only two stand-ins.
        assertEquals(2, RecordingLabels.Missing.values().size)
        assertEquals(1, Regex("""RecordingLabels\.Missing\.UNKNOWN_NODE""").findAll(dialog).count())
        assertTrue(dialog.contains("if (override.isNotBlank()) override else CommandRepository.getResolvedPhrase(context, path, deckId, profile).takeIf { it.isNotBlank() }"))
    }

    // ---- each word sits on the control that does what it says -------------------------------------------------------------------------------

    private fun wordThenAction(source: String, word: String, action: String, within: Int = 350) =
        Regex("""R\.string\.${Regex.escape(word)}[\s\S]{0,$within}?${Regex.escape(action)}""").containsMatchIn(source)

    @Test
    fun theDialogsButtonsAreOnTheControlsThatDoWhatTheySay_andARecordingIsOnlyDeletedFromTheConfirmation() {
        assertTrue("PLAY", wordThenAction(dialog, "voice_rec_play", "onClick = onPlay", 500))
        // PLAYING... and PLAY are two words and the prefix match above cannot tell them apart, so the exact choice is held too.
        assertTrue(dialog.contains("text = stringResource(if (isPlaying) R.string.voice_rec_playing else R.string.voice_rec_play),"))
        assertTrue("RE-RECORD in a row", wordThenAction(dialog, "voice_rec_rerecord)", "onClick = onReRecord", 250))
        assertTrue("DELETE in a row only asks", wordThenAction(dialog, "common_delete)", "onClick = onDeleteRequested", 250))
        assertTrue("the row's request is the question", dialog.contains("onDeleteRequested = { confirmingDeleteId = node.recording.id }"))
        assertTrue("DELETE in the question deletes", wordThenAction(dialog, "common_delete)", "deleteRecordingTarget(context, target)", 300))
        assertTrue("CANCEL in the question closes it", Regex("""R\.string\.common_cancel\), Modifier\.weight\(1f\), isActive = false, mainColor = primaryColor\) \{\s*confirmingDeleteId = null""").containsMatchIn(dialog))
        assertEquals("a recording is deleted from the question and from the re-record panel's own REMOVE", 2, Regex("""deleteRecordingTarget\(context, """).findAll(dialog).count())
        assertTrue("the overlay switch toggles the stored switch", Regex("""RecordingLabels\.overlayToggle\(text, showOverlayOnPreview\)[\s\S]{0,700}?showOverlayOnPreview = !showOverlayOnPreview""").containsMatchIn(dialog))
        assertTrue(dialog.contains("title = stringResource(R.string.manage_rec_delete_title),"))
        assertTrue(dialog.contains("subtitle = text.count(\"manage_rec_count\", recordings.size),"))
    }

    @Test
    fun thePanelsButtonsAreOnTheControlsThatDoWhatTheySay() {
        assertTrue("REMOVE removes", wordThenAction(panel, "voice_rec_remove", "onRemove()", 800))
        assertEquals("PLAYING... or PLAY, in the idle row and in the preview row", 2, Regex("""text = stringResource\(if \(isPlayingPreview\) R\.string\.voice_rec_playing else R\.string\.voice_rec_play\),""").findAll(panel).count())
        assertTrue("RECORD or RE-RECORD by whether there is one", panel.contains("text = stringResource(if (existingRecording != null) R.string.voice_rec_rerecord else R.string.voice_rec_record),"))
        assertTrue("RECORD starts", wordThenAction(panel, "voice_rec_record", "recorder.start(context)", 900))
        assertTrue("STOP finishes", wordThenAction(panel, "voice_rec_stop", "finishRecording()", 800))
        assertTrue("CANCEL while recording discards and goes back", wordThenAction(panel, "common_cancel", "recorder.discard()\n                        phase = RecordingPanelPhase.IDLE", 300))
        assertTrue("DISCARD drops the take", wordThenAction(panel, "common_discard", "previewPcm = null", 900))
        assertTrue("ACCEPT hands the take over", wordThenAction(panel, "voice_rec_accept", "onAccept(pcm, previewSampleRate)", 900))
        assertTrue("the durations are filled in by the strings", panel.contains("stringResource(R.string.voice_rec_recorded, VoiceRecordingRepository.formatDurationMs(existingRecording.durationMs))"))
        assertTrue(panel.contains("stringResource(R.string.voice_rec_recording_now, VoiceRecordingRepository.formatDurationMs(recordingDurationMs))"))
        assertTrue(panel.contains("stringResource(R.string.voice_rec_preview, VoiceRecordingRepository.formatDurationMs(recordingDurationMs))"))
        assertTrue(panel.contains("description: String = stringResource(R.string.voice_rec_description),"))
        assertTrue("the banner's tap dismisses", banner.contains("text = stringResource(R.string.help_got_it),") && banner.contains(".clickable(onClick = onDismiss)"))
        assertTrue(settings.contains("title = stringResource(R.string.voice_rec_key_title, keyLabel)"))
        assertTrue(settings.contains("description = stringResource(R.string.voice_rec_description_key),"))
    }

    // ---- every language ---------------------------------------------------------------------------------------------------------------------

    @Test
    fun theEnglishNamesStillOnScreenAreKeptInEveryLanguage() {
        // HELP is still the English name of the header's button and REC the English text of the Quick-Access key's button, so a sentence that sends someone to them keeps them.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            // Each place the English says HELP (twice) or REC (once) says it in every language too: a sentence that keeps one and translates the other still points at a button that does not exist.
            assertEquals("$tag: HELP as often as the English says it", Regex("""\bHELP\b""").findAll(english.getValue("voice_rec_help_offer")).count(), Regex("""\bHELP\b""").findAll(map.getValue("voice_rec_help_offer")).count())
            assertEquals("$tag: REC as often as the English says it", Regex("""\bREC\b""").findAll(english.getValue("manage_rec_empty")).count(), Regex("""\bREC\b""").findAll(map.getValue("manage_rec_empty")).count())
        }
    }

    @Test
    fun wordsThatAnswerOppositeQuestionsDifferInEveryLanguage() {
        val pairs = listOf(
            "voice_rec_play" to "voice_rec_playing", "voice_rec_record" to "voice_rec_rerecord", "voice_rec_stop" to "common_cancel", "voice_rec_accept" to "common_discard",
            "voice_rec_recorded" to "voice_rec_preview", "voice_rec_description" to "voice_rec_description_key", "manage_rec_empty_prompt" to "manage_rec_unknown_node",
            "manage_rec_delete_title" to "manage_rec_title", "voice_rec_record" to "voice_rec_stop",
        )
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for ((a, b) in pairs) assertNotEquals("$tag: $a and $b read the same", map.getValue(a), map.getValue(b))
            assertNotEquals("$tag: DELETE must not read like CANCEL", map.getValue("common_delete"), map.getValue("common_cancel"))
        }
    }

    @Test
    fun theDurationsAndNamesAreFilledInByTheStrings_andTheCountIsAPlural() {
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            for (name in listOf("voice_rec_recorded", "voice_rec_recording_now", "voice_rec_preview", "voice_rec_key_title", "manage_rec_overlay")) {
                assertEquals("$tag/$name takes one value", listOf("%1\$s"), StringsXml.placeholders(map.getValue(name)))
            }
        }
        assertEquals("1 RECORDING", EnglishText.count("manage_rec_count", 1))
        assertEquals("0 RECORDINGS", EnglishText.count("manage_rec_count", 0))
        assertEquals("7 RECORDINGS", EnglishText.count("manage_rec_count", 7))
        for ((tag, _) in translations) assertTrue("$tag: the count", FileText(tag).count("manage_rec_count", 12).contains("12"))
    }

    @Test
    fun theDeleteQuestionKeepsAllThreeSentences_inEveryLanguage() {
        // "This removes the recording." / what it is bound to falls back / "This cannot be undone." -- a translation that loses one is caught by the sentence ends.
        for ((tag, map) in listOf("en" to english) + translations.toList()) {
            assertEquals("$tag: three sentences", 3, Regex("""[.。।]""").findAll(map.getValue("manage_rec_delete_body")).count())
        }
        for ((tag, map) in translations) assertNotEquals("$tag: the question is still English", english.getValue("manage_rec_delete_body"), map.getValue("manage_rec_delete_body"))
    }

    @Test
    fun theEnglishIsHeldExactly() {
        assertEquals("VOICE RECORDING", english.getValue("voice_rec_title"))
        assertEquals("WHEN SET, THIS PLAYS INSTEAD OF THE SYNTHESIZED PHRASE ABOVE.", english.getValue("voice_rec_description"))
        assertEquals("WHEN SET, THIS PLAYS INSTEAD OF THE KEY'S TARGET PHRASE.", english.getValue("voice_rec_description_key"))
        assertEquals("NEW: VOICE RECORDINGS HAS A HELP WALKTHROUGH -- RECORDING, MATRIX NOTES, AND MANAGING WHAT YOU'VE RECORDED. FIND IT UNDER HELP ANYTIME.", english.getValue("voice_rec_help_offer"))
        assertEquals("REDUCING NOISE, TRIMMING SILENCE & LEVELING VOLUME...", english.getValue("voice_rec_processing"))
        assertEquals("NO RECORDINGS YET. RECORD ONE FROM A QUICK ACTIONS SLOT'S EDIT SCREEN, A QUICK-ACCESS KEY'S REC BUTTON, OR A MATRIX NODE'S EDITOR.", english.getValue("manage_rec_empty"))
        assertEquals("DISABLED -- entry text changed since this was recorded", english.getValue("manage_rec_disabled"))
        assertEquals("This removes the recording. Whatever it's bound to stays and falls back to synthesized speech (or, for a Matrix entry, its normal variable-resolved text). This cannot be undone.", english.getValue("manage_rec_delete_body"))
        assertEquals("[GOT IT]", english.getValue("help_got_it"))
        assertEquals("DISCARD", english.getValue("common_discard"))
        assertEquals("RECORDING (0:07)".replace("RECORDING", "RECORDED"), EnglishText.get("voice_rec_recorded", "0:07"))
        assertEquals("PREVIEW (0:07)", EnglishText.get("voice_rec_preview", "0:07"))
        assertEquals("RECORDING... 0:03", EnglishText.get("voice_rec_recording_now", "0:03"))
        assertEquals("M2 RECORDING", EnglishText.get("voice_rec_key_title", "M2"))
    }
}
