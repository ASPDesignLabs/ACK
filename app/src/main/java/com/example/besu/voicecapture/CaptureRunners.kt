// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.voicecapture

import android.content.Context
import com.example.besu.capture.CaptureListener
import com.example.besu.capture.CaptureTime
import com.example.besu.capture.Card
import com.example.besu.capture.ClipFlags
import com.example.besu.capture.FreeCaptureEngine
import com.example.besu.capture.FreeCaptureListener
import com.example.besu.capture.LevelMath
import com.example.besu.capture.NoiseCheck
import com.example.besu.capture.PauseReason
import com.example.besu.capture.ScriptCaptureEngine
import com.example.besu.capture.StoredClip
import com.example.besu.capture.StoredRecording
import com.example.besu.capture.StoredSession
import com.example.besu.capture.TrainingScript

// Holders that connect the tested engines (com.example.besu.capture) to the screens. Audio arrives on the microphone's thread, a
// hundred hop-sized callbacks a second; the screens must not recompose that often. So these keep their state in @Volatile fields
// that a screen reads on its own timer (about ten times a second), and the engines never touch Compose.

/** The two-second quiet check, run on an already-open microphone. */
class NoiseCheckRunner(private val mic: TrainingMicrophone) {
    private val check = NoiseCheck(mic.sampleRate)

    @Volatile
    var seconds = 0.0
        private set

    @Volatile
    var done = false
        private set

    fun start() {
        mic.sink = { samples, n ->
            check.feed(samples, n)
            seconds = check.seconds
            if (check.isDone) {
                mic.sink = null
                done = true
            }
        }
    }

    fun cancel() { mic.sink = null }

    /** The finished check, or null while it is still listening. */
    fun result(): NoiseCheck? = if (done) check else null
}

enum class RunState { LISTENING, PAUSED, FINISHED }

/** One hands-free script session: creates its notes, runs the engine, and reports what the screen shows. */
class ScriptSessionRunner(
    context: Context,
    private val mic: TrainingMicrophone,
    val script: TrainingScript,
    val cards: List<Card>,
    pending: List<Int>,
    label: String,
    noiseFloorDbfs: Double?,
    endWaitHops: Int,
    paceWps: Double,
) : CaptureListener {
    private val appContext = context.applicationContext
    private val store = TrainingCapture.store(appContext)
    private val threshold = LevelMath.thresholdDb(noiseFloorDbfs)
    val sessionId: String
    private val engine: ScriptCaptureEngine

    @Volatile var state = RunState.PAUSED
        private set
    @Volatile var message = ""
        private set
    @Volatile var currentCard = pending.firstOrNull() ?: -1
        private set
    @Volatile var attempt = 1
        private set
    @Volatile var level = -120.0
        private set
    @Volatile var inSpeech = false
        private set
    @Volatile var kept = 0
        private set
    @Volatile var cardsLeft = pending.size
        private set
    @Volatile var lastKept: StoredClip? = null
        private set

    val canRedo: Boolean get() = engine.canRedo

    init {
        val now = System.currentTimeMillis()
        sessionId = store.newSessionId(now)
        store.createSession(
            StoredSession(
                id = sessionId, mode = "script", label = label, started = CaptureTime.utc(now), language = script.language,
                sampleRate = mic.sampleRate, source = mic.sourceUsed, sourceRequested = "UNPROCESSED",
                noiseFloorDbfs = noiseFloorDbfs, thresholdDbfs = threshold, deviceModel = TrainingCapture.deviceModel().take(60),
                deviceSdk = TrainingCapture.androidVersion(), scriptId = script.id, scriptTitle = script.title, cardsTotal = cards.size, paceWps = paceWps,
            ),
        )
        engine = ScriptCaptureEngine(
            store = store, sessionId = sessionId, cards = cards, pending = pending, sampleRate = mic.sampleRate, thresholdDb = threshold,
            endSilenceHops = endWaitHops, nowUtc = { CaptureTime.utc(System.currentTimeMillis()) },
            freeBytes = { TrainingCapture.usableBytes(appContext) }, listener = this,
        )
    }

    fun start() {
        mic.sink = { samples, n -> engine.feed(samples, n) }
        state = RunState.LISTENING
        engine.start()
    }

    fun pause() { engine.pause() }

    fun resume() {
        message = ""
        state = RunState.LISTENING
        engine.resume()
    }

    fun redoLast() { engine.redoLast() }

    /** Ends the session: whatever is kept stays kept. Safe to call twice. */
    fun end() {
        mic.sink = null
        engine.finish()
    }

    /** Stops the microphone's feed and ends the session. Called when the screen goes away. */
    fun close() = end()

    /** The marks the person has set on the clip just kept. */
    fun marks(): Set<String> = lastKept?.flags?.filter { it in ClipFlags.PERSON }?.toSet().orEmpty()

    /** Sets or clears one mark (noise, unclear, laugh, cough, stumble) on the clip just kept. */
    fun toggleMark(flag: String) {
        val clip = lastKept ?: return
        val now = store.getSession(sessionId)?.clips?.firstOrNull { it.index == clip.index } ?: return
        val set = now.flags.filter { it in ClipFlags.PERSON }.toMutableSet()
        if (!set.add(flag)) set.remove(flag)
        store.setPersonFlags(sessionId, clip.index, set)
        lastKept = store.getSession(sessionId)?.clips?.firstOrNull { it.index == clip.index }
    }

    // -- from the engine (on the microphone's thread) ---------------------------------------------------------------------
    override fun onCardStarted(cardIndex: Int, attempt: Int) {
        currentCard = cardIndex
        this.attempt = attempt
        cardsLeft = engine.cardsLeft
        state = RunState.LISTENING
        message = ""
    }

    override fun onClipKept(clip: StoredClip, cardsLeft: Int) {
        lastKept = clip
        kept += 1
        this.cardsLeft = cardsLeft
    }

    override fun onPaused(reason: PauseReason, message: String) {
        state = RunState.PAUSED
        this.message = if (reason == PauseReason.REQUESTED) "" else message
    }

    override fun onFinished() {
        state = RunState.FINISHED
        message = ""
    }

    override fun onLevel(db: Double, inSpeech: Boolean) {
        level = db
        this.inSpeech = inSpeech
    }
}

/** One free-speech session. */
class FreeSessionRunner(
    context: Context,
    private val mic: TrainingMicrophone,
    label: String,
    topic: String,
    noiseFloorDbfs: Double?,
) : FreeCaptureListener {
    private val appContext = context.applicationContext
    private val store = TrainingCapture.store(appContext)
    private val threshold = LevelMath.thresholdDb(noiseFloorDbfs)
    val sessionId: String
    private val engine: FreeCaptureEngine

    @Volatile var level = -120.0
        private set
    @Volatile var isSpeech = false
        private set
    @Volatile var message = ""
        private set
    @Volatile var stoppedByItself = false
        private set

    val seconds: Double get() = engine.seconds
    val isPaused: Boolean get() = engine.isPaused
    val isStopped: Boolean get() = engine.isStopped

    init {
        val now = System.currentTimeMillis()
        sessionId = store.newSessionId(now)
        store.createSession(
            StoredSession(
                id = sessionId, mode = "free", label = label, started = CaptureTime.utc(now), language = TrainingCapture.defaultLanguage(),
                sampleRate = mic.sampleRate, source = mic.sourceUsed, sourceRequested = "UNPROCESSED",
                noiseFloorDbfs = noiseFloorDbfs, thresholdDbfs = threshold, deviceModel = TrainingCapture.deviceModel().take(60),
                deviceSdk = TrainingCapture.androidVersion(), topic = topic.take(200),
            ),
        )
        engine = FreeCaptureEngine(
            store = store, sessionId = sessionId, sampleRate = mic.sampleRate, thresholdDb = threshold,
            nowUtc = { CaptureTime.utc(System.currentTimeMillis()) }, freeBytes = { TrainingCapture.usableBytes(appContext) }, listener = this,
        )
    }

    fun start() {
        engine.start()
        mic.sink = { samples, n -> engine.feed(samples, n) }
    }

    fun pause() { engine.pause() }

    fun resume() { engine.resume() }

    /**
     * Ends the recording and scans it for suggested pieces. A long recording takes a few seconds to scan, so call this off the main
     * thread. Returns null if nothing was recorded.
     */
    fun stop(): StoredRecording? {
        mic.sink = null
        return engine.stop()
    }

    override fun onLevel(db: Double, isSpeech: Boolean) {
        level = db
        this.isSpeech = isSpeech
    }

    override fun onStoppedByItself(reason: PauseReason, message: String) {
        this.message = message
        stoppedByItself = true
        mic.sink = null
    }
}
