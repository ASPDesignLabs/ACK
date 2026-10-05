// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import com.example.besu.core.RepoFiles
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * While a session records, the microphone is open, and a buzz or thump lands in the card being read (CLAUDE.md, "Taps"). The recording
 * screen is Compose, so these read its source, like FreeSpeechNoticeTest. They cover the part that test cannot see: the box that asks
 * "END THIS SESSION?" used to come from the shared ConfirmDialog in another file, whose buttons are TightPanelButton (haptic feedback on
 * tap), and KEEP RECORDING leaves the recording running, so tapping the safe choice buzzed into the audio.
 */
class CaptureScreenQuietTest {
    private val screen = "app/src/main/java/com/example/besu/voicecapture/CaptureSessionScreen.kt"

    // Comments are dropped so a sentence that names a forbidden thing ("not TightPanelButton") is not mistaken for using it. This cuts
    // at the first "//" on a line, which is fine here: nothing in this screen's code has "//" inside a string.
    private fun code(): String = RepoFiles.read(screen).lineSequence().joinToString("\n") { it.substringBefore("//") }

    private fun matching(source: String, open: Int, openCh: Char, closeCh: Char): Int {
        var depth = 0
        for (i in open until source.length) {
            when (source[i]) {
                openCh -> depth++
                closeCh -> { depth--; if (depth == 0) return i }
            }
        }
        error("no closing '$closeCh' for the '$openCh' at $open in $screen")
    }

    // The text of `name`'s body, found by counting brackets from its parameter list onwards.
    private fun functionBody(source: String, name: String): String {
        val start = Regex("\\bfun\\s+$name\\s*\\(").find(source)?.range?.first ?: error("no function $name in $screen")
        val paramsEnd = matching(source, source.indexOf('(', start), '(', ')')
        val bodyStart = source.indexOf('{', paramsEnd)
        return source.substring(bodyStart, matching(source, bodyStart, '{', '}') + 1)
    }

    // The composable the recording screen shows when `confirmEnd` is set: the first call after `if (confirmEnd) {`.
    private fun shownDialogCall(source: String): Pair<String, String> {
        val marker = "if (confirmEnd) {"
        val at = source.indexOf(marker)
        assertTrue("the screen no longer shows a box for confirmEnd", at >= 0)
        val call = Regex("([A-Za-z_][A-Za-z0-9_]*)\\s*\\(").find(source, at + marker.length) ?: error("no call after `$marker`")
        val open = call.range.last
        return call.groupValues[1] to source.substring(open, matching(source, open, '(', ')') + 1)
    }

    private val sharedConfirmDialog = Regex("(?<![A-Za-z0-9_])ConfirmDialog\\s*\\(")
    private val standardButtons = listOf("TightPanelButton", "NeonButton")

    @Test
    fun theBoxThatAsksBeforeEndingIsNotTheSharedConfirmDialog() {
        val source = code()
        val (shown, _) = shownDialogCall(source)
        assertNotEquals("the end-session box must not be the shared ConfirmDialog (its buttons buzz with the microphone open)", "ConfirmDialog", shown)
        assertTrue("$shown must be defined in CaptureSessionScreen.kt, built from this screen's own buttons", Regex("\\bfun\\s+$shown\\s*\\(").containsMatchIn(source))
        assertFalse("CaptureSessionScreen.kt must not call the shared ConfirmDialog", sharedConfirmDialog.containsMatchIn(source))
    }

    @Test
    fun noViewShownWhileRecordingUsesAStandardButton() {
        val source = code()
        val shown = shownDialogCall(source).first
        for (view in listOf("ScriptCaptureView", "FreeCaptureView", shown)) {
            val body = functionBody(source, view)
            for (forbidden in standardButtons) assertFalse("$view is on screen while recording and must not use $forbidden (it gives haptic feedback)", body.contains(forbidden))
            assertFalse("$view must not call the shared ConfirmDialog", sharedConfirmDialog.containsMatchIn(body))
        }
    }

    @Test
    fun theEndSessionBoxIsBuiltFromCaptureButtonsWithNoAnimation() {
        val source = code()
        val body = functionBody(source, shownDialogCall(source).first)
        assertEquals("the box should have exactly its two buttons, both CaptureButton", 2, body.split("CaptureButton(").size - 1)
        for (forbidden in listOf("AnimatedVisibility", "AnimatedContent", "Crossfade", "animate", "Transition")) {
            assertFalse("the end-session box must not animate ($forbidden)", body.contains(forbidden))
        }
    }

    @Test
    fun theSafeChoiceComesFirstAndIsTheSameSizeAsTheRiskyOne() {
        val source = code()
        val body = functionBody(source, shownDialogCall(source).first)
        val calls = body.split("CaptureButton(").drop(1)
        assertEquals(2, calls.size)
        assertTrue("the first button must be the cancel (KEEP RECORDING) one", calls[0].contains("onClick = onCancel"))
        assertTrue("the second button must be the confirm (END SESSION) one", calls[1].contains("onClick = onConfirm"))
        for (call in calls) {
            assertTrue("both buttons are full width, so neither is smaller than the other", call.contains("Modifier.fillMaxWidth(),"))
            assertFalse("neither button may be compact or dimmed", call.contains("compact =") || call.contains("active ="))
        }
    }

    @Test
    fun tappingOutsideOrPressingBackKeepsRecording() {
        val source = code()
        val (shown, call) = shownDialogCall(source)
        assertTrue("$shown must treat a dismissal as cancel", Regex("Dialog\\(\\s*onDismissRequest\\s*=\\s*onCancel\\s*\\)").containsMatchIn(functionBody(source, shown)))
        assertTrue("cancelling must only close the box, never end the session", call.contains("onCancel = { confirmEnd = false }"))
    }

    @Test
    fun theEndSessionBoxAndItsButtonsAreAtLeastTwelveSp() {
        val source = code()
        val sizes = Regex("fontSize\\s*=\\s*(\\d+)\\.sp").findAll(functionBody(source, shownDialogCall(source).first)).map { it.groupValues[1].toInt() }.toList()
        assertTrue("the box has no font sizes to check", sizes.size >= 2)
        assertTrue("the box has text under 12 sp: $sizes", sizes.all { it >= 12 })
        // CaptureButton is 9 sp when `compact` and the box never passes that (checked above); its normal size is what the box shows.
        val normal = Regex("fontSize\\s*=\\s*if\\s*\\(compact\\)\\s*\\d+\\.sp\\s*else\\s*(\\d+)\\.sp").find(functionBody(source, "CaptureButton"))?.groupValues?.get(1)?.toInt()
        assertTrue("CaptureButton's normal text size was not found", normal != null)
        assertTrue("CaptureButton's normal text is only $normal sp", normal!! >= 12)
    }
}
