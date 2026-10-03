// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.nio.file.StandardCopyOption

enum class PauseReason { REQUESTED, IDLE, DISK_FULL, ERROR }

/** What the engine tells the screen. Called on whichever thread is feeding audio, so post to the UI thread rather than doing work here. */
interface CaptureListener {
    /** A card is now being listened for. [attempt] is 1 the first time and 2 or more after a redo. */
    fun onCardStarted(cardIndex: Int, attempt: Int) {}
    /** A card's clip was cut, measured and kept. [cardsLeft] is how many cards remain after it. */
    fun onClipKept(clip: StoredClip, cardsLeft: Int) {}
    fun onPaused(reason: PauseReason, message: String) {}
    /** The last card was kept, or the person ended the session. The session's notes are closed. */
    fun onFinished() {}
    /** The level of the latest hop, for a live meter. Called every 10 ms of audio. */
    fun onLevel(db: Double, inSpeech: Boolean) {}
}

// Turns a stream of microphone samples into kept clips, one card at a time, with nobody touching the phone (format document, section
// 7). Plain Kotlin: the Android recorder only has to hand it samples. Everything is decided one 10 ms hop at a time, so the clips come
// out the same however the microphone chops the stream into chunks.
//
// How audio is kept safe: from the moment a card starts being listened for, every sample goes straight to that card's file on disk
// (and the card is already in the notes as OPEN). When the detector decides the card is finished, the file is cut down to the clip
// (lead-in, speech, tail) and the audio that came after the clip's end is carried over into the next card's file, so a card started
// promptly loses nothing. If the app dies in between, TrainingStore.recoverOpenSessions repairs the file.
//
// All public methods are safe to call from any thread.
class ScriptCaptureEngine(
    private val store: TrainingStore,
    private val sessionId: String,
    private val cards: List<Card>,
    /** Indices into [cards] still to be recorded, in order. Cards that already have a kept clip are left out by the caller. */
    pending: List<Int>,
    private val sampleRate: Int,
    private val thresholdDb: Double,
    private val endSilenceHops: Int = CaptureConstants.END_SILENCE_HOPS,
    private val nowUtc: () -> String,
    private val freeBytes: () -> Long = { Long.MAX_VALUE },
    private val listener: CaptureListener,
) {
    private class OpenCard(val cardIndex: Int, val clip: StoredClip, val file: File, val writer: WavStreamWriter, val originHop: Int)

    private val hop = sampleRate / 100
    private val queue = ArrayDeque(pending)
    private var detector = HandsFreeDetector(thresholdDb, endSilenceHops)
    private var open: OpenCard? = null
    private val hopBuf = ShortArray(hop)
    private var hopFill = 0
    private var hopsSinceRoomCheck = 0
    private var lastKept: Pair<StoredClip, Int>? = null

    @Volatile
    var isPaused = true
        private set

    @Volatile
    var isFinished = false
        private set

    /** The card being listened for, or null when paused or finished. */
    val currentCard: Int? @Synchronized get() = open?.cardIndex

    val cardsLeft: Int @Synchronized get() = queue.size

    /** True when a kept clip can be redone. */
    val canRedo: Boolean @Synchronized get() = lastKept != null && !isFinished

    // -- control ----------------------------------------------------------------------------------------------------------
    /** Starts listening for the first pending card. */
    @Synchronized
    fun start() {
        if (isFinished) return
        if (queue.isEmpty()) { finishInternal(); return }
        beginListening()
    }

    @Synchronized
    fun pause() {
        if (isPaused || isFinished) return
        pauseInternal(PauseReason.REQUESTED, "PAUSED")
    }

    @Synchronized
    fun resume() {
        if (!isPaused || isFinished) return
        beginListening()
    }

    /** Throws away the last kept clip's place in the package (the audio stays on disk) and listens for that card again. */
    @Synchronized
    fun redoLast(): Boolean {
        val (kept, cardIndex) = lastKept ?: return false
        if (isFinished) return false
        abandonOpenCard()
        store.markRedone(sessionId, kept.index)
        queue.addFirst(cardIndex)
        lastKept = null
        if (!isPaused) beginListening()
        return true
    }

    /** Ends the session now. The card being listened for, if the person had not started it, is dropped. */
    @Synchronized
    fun finish() {
        if (isFinished) return
        finishInternal()
    }

    // -- audio in ---------------------------------------------------------------------------------------------------------
    /** Hands over [count] samples from the microphone. Ignored while paused or finished. */
    @Synchronized
    fun feed(samples: ShortArray, count: Int = samples.size) {
        var i = 0
        while (i < count) {
            if (isPaused || isFinished) return
            val take = minOf(hop - hopFill, count - i)
            System.arraycopy(samples, i, hopBuf, hopFill, take)
            hopFill += take
            i += take
            if (hopFill == hop) {
                hopFill = 0
                try {
                    processHop()
                } catch (e: IOException) {
                    abandonOpenCard()
                    pauseInternal(PauseReason.ERROR, "THE RECORDING COULD NOT BE SAVED: ${e.message ?: "STORAGE ERROR"}")
                }
            }
        }
    }

    // -- inside -----------------------------------------------------------------------------------------------------------
    private fun beginListening() {
        detector.resumeAt(detector.hopsSeen)
        hopFill = 0
        hopsSinceRoomCheck = 0
        isPaused = false
        openCard(detector.hopsSeen, null)
    }

    private fun openCard(originHop: Int, carry: ShortArray?) {
        val cardIndex = queue.first()
        val (clip, file) = store.beginClip(sessionId, cardIndex + 1, cards[cardIndex].text, nowUtc())
        val writer = WavStreamWriter(file, sampleRate)
        if (carry != null && carry.isNotEmpty()) writer.write(carry)
        open = OpenCard(cardIndex, clip, file, writer, originHop)
        listener.onCardStarted(cardIndex, clip.attempt)
    }

    private fun processHop() {
        val o = open ?: return
        o.writer.write(hopBuf, 0, hop)
        var sum = 0.0
        for (k in 0 until hop) { val v = hopBuf[k].toDouble(); sum += v * v }
        val level = LevelMath.levelDb(Math.sqrt(sum / hop))
        val event = detector.feed(level)
        listener.onLevel(level, detector.isInSpeech)
        if (++hopsSinceRoomCheck >= 200) {
            hopsSinceRoomCheck = 0
            val free = freeBytes()
            if (DiskGuard.mustStop(free)) {
                abandonOpenCard()
                pauseInternal(PauseReason.DISK_FULL, "OUT OF ROOM: ${DiskGuard.describe(free, sampleRate)}. KEPT CLIPS ARE SAFE")
                return
            }
        }
        when (event) {
            is DetectorEvent.Clip -> closeCard(o, event)
            is DetectorEvent.IdleTimeout -> {
                abandonOpenCard()
                pauseInternal(PauseReason.IDLE, "NOTHING HEARD FOR 20 SECONDS: PAUSED")
            }
            null -> {}
        }
    }

    private fun hopOf(seconds: Double): Int = Math.round(seconds / CaptureConstants.HOP_S).toInt()

    private fun closeCard(o: OpenCard, e: DetectorEvent.Clip) {
        val nowHop = detector.hopsSeen
        val startHop = hopOf(e.startS)
        val endHop = hopOf(e.endS)
        check(nowHop >= endHop && startHop >= o.originHop) { "a clip cannot reach outside the audio heard for this card" }
        o.writer.close()
        val info = WavFile.inspect(o.file)
        val startFrame = (startHop - o.originHop).toLong() * hop
        val endFrame = (endHop - o.originHop).toLong() * hop
        val clipSamples = AudioScan.readSamples(o.file, info, startFrame, endFrame)
        val carry = AudioScan.readSamples(o.file, info, endFrame, info.frames)
        replaceWithClip(o.file, clipSamples)
        val metrics = LevelMath.clipMetrics(clipSamples, sampleRate, thresholdDb)
        val kept = store.finishClip(sessionId, o.clip.index, clipSamples.size.toDouble() / sampleRate, metrics, endedByLimit = e.reason == "max")
        open = null
        queue.removeFirst()
        lastKept = kept to o.cardIndex
        listener.onClipKept(kept, queue.size)
        if (queue.isEmpty()) finishInternal() else openCard(endHop, carry)
    }

    private fun replaceWithClip(file: File, samples: ShortArray) {
        val part = File(file.parentFile, file.name + ".part")
        WavStreamWriter(part, sampleRate).use { it.write(samples) }
        Files.move(part.toPath(), file.toPath(), StandardCopyOption.ATOMIC_MOVE)
    }

    /**
     * Stops listening for the open card. If the person had not started speaking, the empty card is removed; if they had, its audio
     * is kept on disk (as a redone attempt, not packaged) rather than thrown away.
     */
    private fun abandonOpenCard() {
        val o = open ?: return
        open = null
        try { o.writer.close() } catch (e: IOException) { /* the audio written so far is on disk */ }
        if (detector.isInSpeech) store.markRedone(sessionId, o.clip.index) else store.deleteClip(sessionId, o.clip.index)
    }

    private fun pauseInternal(reason: PauseReason, message: String) {
        abandonOpenCard()
        isPaused = true
        hopFill = 0
        listener.onPaused(reason, message)
    }

    private fun finishInternal() {
        abandonOpenCard()
        isPaused = true
        isFinished = true
        store.closeSession(sessionId, nowUtc())
        listener.onFinished()
    }
}
