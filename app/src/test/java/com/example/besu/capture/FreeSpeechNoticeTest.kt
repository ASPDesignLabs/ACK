// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import com.example.besu.core.CaptureText
import com.example.besu.core.EnglishText
import com.example.besu.core.FileText
import com.example.besu.core.RepoFiles
import com.example.besu.core.StringsXml
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FreeSpeechNoticeTest {
    private val screen = "app/src/main/java/com/example/besu/voicecapture/CaptureSessionScreen.kt"
    private val home = "app/src/main/java/com/example/besu/voicecapture/TrainingCaptureHome.kt"
    private val help = "app/src/main/java/com/example/besu/help/RecordTrainingDataHelp.kt"
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    // The setup notice is read through the decision (it carries the engine's own limit); the home line is a plain string resource.
    private val setupToken = "CaptureText.freeNoticeSetup(words)"
    private val homeToken = "R.string.capture_free_notice_home"

    // --- the words ---

    @Test
    fun theSetupNoticeIsTheApprovedSentence() {
        assertEquals(
            "FREE SPEECH RECORDS EVERYTHING THE MICROPHONE HEARS, INCLUDING ANYONE NEARBY, FOR UP TO 90 MINUTES. " +
                "TELL THEM FIRST, OR RECORD SOMEWHERE ELSE.",
            CaptureText.freeNoticeSetup(EnglishText),
        )
    }

    @Test
    fun theMinutesInTheNoticeAreTheRealLimit() {
        assertEquals(5_400, CaptureConstants.MAX_FREE_SESSION_S) // 90 minutes: if this changes, the notice follows it
        assertTrue(CaptureText.freeNoticeSetup(EnglishText).contains("FOR UP TO ${CaptureConstants.MAX_FREE_SESSION_S / 60} MINUTES"))
        // The sentence under the timer says the same limit, from the same constant.
        assertTrue(CaptureText.freeNote(EnglishText).contains("AT ${CaptureConstants.MAX_FREE_SESSION_S / 60} MINUTES"))
        // In every language the number is written once, as the engine's own limit.
        for (tag in translations.keys) {
            val text = FileText(tag)
            for (sentence in listOf(CaptureText.freeNoticeSetup(text), CaptureText.freeNote(text))) {
                assertEquals("$tag: the limit once in '$sentence'", 1, Regex("90").findAll(sentence).count())
            }
        }
    }

    @Test
    fun theHomeAndHelpSentencesAreTheApprovedOnes() {
        assertEquals("IT ALSO RECORDS ANYONE NEARBY.", english.getValue("capture_free_notice_home"))
        assertEquals("It also records anyone nearby.", FreeSpeechNotice.HELP)
    }

    @Test
    fun screenWordsAreCapitalsLikeTheRestOfTheApp() {
        assertEquals(CaptureText.freeNoticeSetup(EnglishText).uppercase(), CaptureText.freeNoticeSetup(EnglishText))
        assertEquals(english.getValue("capture_free_notice_home").uppercase(), english.getValue("capture_free_notice_home"))
        for (tag in listOf("es", "pt", "af")) {
            assertEquals("$tag setup", CaptureText.freeNoticeSetup(FileText(tag)).uppercase(), CaptureText.freeNoticeSetup(FileText(tag)))
            assertEquals("$tag home", translations.getValue(tag).getValue("capture_free_notice_home").uppercase(), translations.getValue(tag).getValue("capture_free_notice_home"))
        }
    }

    @Test
    fun theNoticeIsInEveryLanguage_andSaysSomethingElseThanTheEnglish() {
        for ((tag, map) in translations) {
            assertTrue("$tag setup", map.getValue("capture_free_notice_setup") != english.getValue("capture_free_notice_setup"))
            assertTrue("$tag home", map.getValue("capture_free_notice_home") != english.getValue("capture_free_notice_home"))
            assertEquals("$tag: the minutes are the only placeholder", listOf("%1\$d"), StringsXml.placeholders(map.getValue("capture_free_notice_setup")))
            assertEquals("$tag: the home line has no placeholder", emptyList<String>(), StringsXml.placeholders(map.getValue("capture_free_notice_home")))
        }
    }

    // --- where the words are used (the screens are Compose, so these read the source) ---

    @Test
    fun theSetupNoticeIsOnlyForFreeSpeechAndComesBeforeTheQuietCheckButton() {
        val source = RepoFiles.read(screen)
        val at = source.indexOf(setupToken)
        assertTrue("the setup screen does not show the setup notice", at >= 0)
        assertEquals("the notice must be shown exactly once", at, source.lastIndexOf(setupToken))
        // The nearest condition above the notice must be exactly `if (free)`, so script recording is unchanged (comments in between are fine).
        val condition = source.lastIndexOf("if (", at)
        assertTrue("no condition above the notice", condition >= 0)
        assertTrue(
            "the notice must sit directly inside `if (free)`, not `${source.substring(condition, minOf(source.length, condition + 24)).lineSequence().first()}`",
            source.startsWith("if (free)", condition),
        )
        val button = source.indexOf("CaptureText.startQuietLabel(words)")
        assertTrue(button >= 0)
        assertTrue("the notice must come before START QUIET CHECK", at < button)
        assertTrue("it belongs in the BEFORE YOU START block", source.lastIndexOf("R.string.capture_before_title", at) in 0 until at)
    }

    @Test
    fun theHomeAndHelpTextsUseTheSameWords() {
        assertTrue(RepoFiles.read(home).contains(homeToken))
        // The walkthrough's step is a string resource now. English ends with the approved sentence (the constant), and every translation ends with the very sentence the home screen
        // shows in that language, so the walkthrough and the screen can never say different things about recording anyone nearby.
        val step = "helpmod_record_training_data_free_body"
        assertTrue(RepoFiles.read(help).contains("\"$step\""))
        assertTrue(english.getValue(step).endsWith(FreeSpeechNotice.HELP))
        for ((tag, map) in translations) {
            assertTrue("$tag: the free-speech step ends with the home screen's notice", map.getValue(step).endsWith(map.getValue("capture_free_notice_home")))
            assertEquals("$tag: the limit once in the step", 1, Regex("90").findAll(map.getValue(step)).count())
        }
        assertEquals("en: the limit once in the step", 1, Regex("90").findAll(english.getValue(step)).count())
    }

    @Test
    fun theNewTextIsAtLeastTwelveSp() {
        for ((file, token) in listOf(screen to setupToken, home to homeToken)) {
            val source = RepoFiles.read(file)
            val at = source.indexOf(token)
            assertTrue("$token not found in $file", at >= 0)
            val size = Regex("fontSize\\s*=\\s*(\\d+)\\.sp").find(source, at)?.groupValues?.get(1)?.toInt()
            assertTrue("no fontSize after $token in $file", size != null)
            assertTrue("$token is only $size sp", size!! >= 12)
        }
    }

    @Test
    fun theNoticesUseNoAlarmColour() {
        for ((file, token) in listOf(screen to setupToken, home to homeToken)) {
            val source = RepoFiles.read(file)
            val at = source.indexOf(token)
            assertTrue("$token is not shown in $file", at >= 0)
            val block = source.substring(at, minOf(source.length, at + 260))
            assertFalse("no alarm colour for $token: $block", block.contains("RadicalRed") || block.contains("ErrorRed"))
        }
    }

    @Test
    fun theCaptureScreenStillHasNoSoundVibrationToastOrStandardButtons() {
        // From CLAUDE.md: a buzz or thump while the microphone is open lands in the recording, so this screen is text only.
        val source = RepoFiles.read(screen)
        for (forbidden in listOf("NeonButton", "Toast", "performHapticFeedback", "LocalHapticFeedback", "Vibrator", "VibrationEffect", "ToneGenerator")) {
            assertFalse("CaptureSessionScreen.kt must not use $forbidden", source.contains(forbidden))
        }
    }
}
