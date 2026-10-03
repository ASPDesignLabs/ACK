// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import com.example.besu.core.RepoFiles
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FreeSpeechNoticeTest {
    private val screen = "app/src/main/java/com/example/besu/voicecapture/CaptureSessionScreen.kt"
    private val home = "app/src/main/java/com/example/besu/voicecapture/TrainingCaptureHome.kt"
    private val help = "app/src/main/java/com/example/besu/help/RecordTrainingDataHelp.kt"

    // --- the words ---

    @Test
    fun theSetupNoticeIsTheApprovedSentence() {
        assertEquals(
            "FREE SPEECH RECORDS EVERYTHING THE MICROPHONE HEARS, INCLUDING ANYONE NEARBY, FOR UP TO 90 MINUTES. " +
                "TELL THEM FIRST, OR RECORD SOMEWHERE ELSE.",
            FreeSpeechNotice.SETUP,
        )
    }

    @Test
    fun theMinutesInTheNoticeAreTheRealLimit() {
        assertEquals(5_400, CaptureConstants.MAX_FREE_SESSION_S) // 90 minutes: if this changes, the notice follows it
        assertTrue(FreeSpeechNotice.SETUP.contains("FOR UP TO ${CaptureConstants.MAX_FREE_SESSION_S / 60} MINUTES"))
    }

    @Test
    fun theHomeAndHelpSentencesAreTheApprovedOnes() {
        assertEquals("IT ALSO RECORDS ANYONE NEARBY.", FreeSpeechNotice.HOME)
        assertEquals("It also records anyone nearby.", FreeSpeechNotice.HELP)
    }

    @Test
    fun screenWordsAreCapitalsLikeTheRestOfTheApp() {
        assertEquals(FreeSpeechNotice.SETUP.uppercase(), FreeSpeechNotice.SETUP)
        assertEquals(FreeSpeechNotice.HOME.uppercase(), FreeSpeechNotice.HOME)
    }

    // --- where the words are used (the screens are Compose, so these read the source) ---

    @Test
    fun theSetupNoticeIsOnlyForFreeSpeechAndComesBeforeTheQuietCheckButton() {
        val source = RepoFiles.read(screen)
        val at = source.indexOf("FreeSpeechNotice.SETUP")
        assertTrue("the setup screen does not show FreeSpeechNotice.SETUP", at >= 0)
        assertEquals("the notice must be shown exactly once", at, source.lastIndexOf("FreeSpeechNotice.SETUP"))
        // The nearest condition above the notice must be exactly `if (free)`, so script recording is unchanged (comments in between are fine).
        val condition = source.lastIndexOf("if (", at)
        assertTrue("no condition above the notice", condition >= 0)
        assertTrue(
            "the notice must sit directly inside `if (free)`, not `${source.substring(condition, minOf(source.length, condition + 24)).lineSequence().first()}`",
            source.startsWith("if (free)", condition),
        )
        val button = source.indexOf("START QUIET CHECK")
        assertTrue(button >= 0)
        assertTrue("the notice must come before START QUIET CHECK", at < button)
        assertTrue("it belongs in the BEFORE YOU START block", source.lastIndexOf("BEFORE YOU START", at) in 0 until at)
    }

    @Test
    fun theHomeAndHelpTextsUseTheSameWords() {
        assertTrue(RepoFiles.read(home).contains("FreeSpeechNotice.HOME"))
        assertTrue(RepoFiles.read(help).contains("FreeSpeechNotice.HELP"))
    }

    @Test
    fun theNewTextIsAtLeastTwelveSp() {
        for ((file, token) in listOf(screen to "FreeSpeechNotice.SETUP", home to "FreeSpeechNotice.HOME")) {
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
        for ((file, token) in listOf(screen to "FreeSpeechNotice.SETUP", home to "FreeSpeechNotice.HOME")) {
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
