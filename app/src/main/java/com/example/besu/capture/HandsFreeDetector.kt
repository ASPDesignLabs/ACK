// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

/** What the detector reports as it hears the stream. Times are in seconds from the first level it was given. */
sealed class DetectorEvent {
    /** A clip: where it starts and ends (with lead-in and tail), where the speech inside it starts and ends, and why it ended. */
    data class Clip(val startS: Double, val endS: Double, val speechStartS: Double, val speechEndS: Double, val reason: String) : DetectorEvent()

    /** Nothing was said for a long time, so the session should pause rather than listen forever. */
    data class IdleTimeout(val atS: Double) : DetectorEvent()
}

/**
 * Hears one card at a time without anyone touching the phone (format document, section 7). Feed it one level per 10 ms hop, in
 * order. It decides when speech has started (a short run of loud hops), when the card is finished (a pause of END_SILENCE_HOPS), and
 * where to cut the clip, keeping a little lead-in before the speech and a little tail after it.
 *
 * After a clip it listens again at once, starting at the end of that clip. The hops between the clip's end and the moment it was
 * closed were all quiet, so a card started straight away loses nothing. A line-for-line port of the reference code;
 * HandsFreeDetectorTest holds it to the shared test cases.
 */
class HandsFreeDetector(
    private val thresholdDb: Double,
    private val endSilenceHops: Int = CaptureConstants.END_SILENCE_HOPS,
    listenFromHop: Int = 0,
) {
    private enum class State { LISTENING, SPEECH, IDLE }

    private var hop = 0
    private var state = State.LISTENING
    private var listenHop = listenFromHop
    private var run = 0
    private var clipStart = 0
    private var speechStart = 0
    private var lastVoiced = 0

    /** The number of levels fed so far. */
    val hopsSeen: Int get() = hop

    /** True from the moment speech has started until the clip is closed, so a screen can show that it is listening to the person. */
    val isInSpeech: Boolean get() = state == State.SPEECH

    fun feed(levelDb: Double): DetectorEvent? {
        val h = hop
        hop += 1
        val above = levelDb > thresholdDb
        if (state == State.IDLE) return null
        if (state == State.LISTENING) {
            run = if (above) run + 1 else 0
            if (run >= CaptureConstants.START_RUN_HOPS) {
                speechStart = h - CaptureConstants.START_RUN_HOPS + 1
                clipStart = maxOf(listenHop, speechStart - CaptureConstants.PRE_ROLL_HOPS)
                lastVoiced = h
                state = State.SPEECH
                return null
            }
            if (h + 1 - listenHop >= CaptureConstants.NO_SPEECH_TIMEOUT_HOPS) {
                state = State.IDLE
                return DetectorEvent.IdleTimeout(LevelMath.sec((h + 1).toDouble()))
            }
            return null
        }
        if (above) lastVoiced = h
        if (h - lastVoiced >= endSilenceHops) return close("silence", lastVoiced + 1 + CaptureConstants.TAIL_HOPS)
        if (h + 1 - clipStart >= CaptureConstants.HARD_CLIP_HOPS) return close("max", h + 1)
        return null
    }

    /** Start listening again after the app has paused or resumed (for example the person tapped PAUSE), from hop [fromHop]. */
    fun resumeAt(fromHop: Int) {
        state = State.LISTENING
        listenHop = fromHop
        run = 0
    }

    private fun close(reason: String, endHop: Int): DetectorEvent.Clip {
        val event = DetectorEvent.Clip(
            startS = LevelMath.sec(clipStart.toDouble()), endS = LevelMath.sec(endHop.toDouble()),
            speechStartS = LevelMath.sec(speechStart.toDouble()), speechEndS = LevelMath.sec((lastVoiced + 1).toDouble()), reason = reason,
        )
        state = State.LISTENING
        listenHop = endHop
        run = 0
        return event
    }
}
