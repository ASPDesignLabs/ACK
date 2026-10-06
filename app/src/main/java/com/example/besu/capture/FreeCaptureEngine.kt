// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import java.io.IOException

/** What the screen hears from a free-speech recording. Called on the thread that feeds audio, so post to the UI thread. */
interface FreeCaptureListener {
    /** The level of the latest hop and whether it counts as speech, for a live meter. Called every 10 ms of audio. */
    fun onLevel(db: Double, isSpeech: Boolean) {}
    /** Recording stopped by itself: the disk is nearly full, a write failed, or the longest allowed recording was reached. */
    fun onStoppedByItself(reason: PauseReason, notice: CaptureNotice) {}
}

// Records one long, unscripted stretch of speech into a single file (format document, section 4.4). The phone never cuts the audio:
// when the person stops, it is scanned once for the pieces the phone suggests, and those go in the notes as hints for the PC.
// Every sample goes straight to disk as it arrives, and the session is in the notes as OPEN, so the app closing unexpectedly leaves a
// file that TrainingStore.recoverOpenSessions repairs. Plain Kotlin, tested on a JVM; the Android recorder only hands over samples.
class FreeCaptureEngine(
    private val store: TrainingStore,
    private val sessionId: String,
    private val sampleRate: Int,
    private val thresholdDb: Double,
    private val nowUtc: () -> String,
    private val freeBytes: () -> Long = { Long.MAX_VALUE },
    /** The longest recording; a longer talk becomes a second session. */
    private val maxSeconds: Int = CaptureConstants.MAX_FREE_SESSION_S,
    private val listener: FreeCaptureListener,
) {
    private val hop = sampleRate / 100
    private var writer: WavStreamWriter? = null
    private val hopBuf = ShortArray(hop)
    private var hopFill = 0
    private var hops = 0L
    private var hopsSinceRoomCheck = 0

    @Volatile
    var isPaused = false
        private set

    @Volatile
    var isStopped = false
        private set

    /** What the recording was found to hold once it stopped (by the person or by itself); null if nothing was recorded or it is still going. */
    @Volatile
    var result: StoredRecording? = null
        private set

    /** Seconds recorded so far. */
    val seconds: Double @Synchronized get() = hops * CaptureConstants.HOP_S

    @Synchronized
    fun start() {
        check(writer == null && !isStopped) { "already started" }
        writer = WavStreamWriter(store.beginFreeRecording(sessionId), sampleRate)
    }

    @Synchronized
    fun pause() { if (writer != null && !isStopped) { isPaused = true; hopFill = 0 } }

    @Synchronized
    fun resume() { if (writer != null && !isStopped) isPaused = false }

    @Synchronized
    fun feed(samples: ShortArray, count: Int = samples.size) {
        var i = 0
        while (i < count) {
            if (isPaused || isStopped) return
            val take = minOf(hop - hopFill, count - i)
            System.arraycopy(samples, i, hopBuf, hopFill, take)
            hopFill += take
            i += take
            if (hopFill == hop) {
                hopFill = 0
                try {
                    processHop()
                } catch (e: IOException) {
                    stoppedByItself(PauseReason.ERROR, CaptureNotice.CouldNotSave(e.message))
                }
            }
        }
    }

    private fun processHop() {
        val w = writer ?: return
        w.write(hopBuf, 0, hop)
        hops++
        var sum = 0.0
        for (k in 0 until hop) { val v = hopBuf[k].toDouble(); sum += v * v }
        val level = LevelMath.levelDb(Math.sqrt(sum / hop))
        listener.onLevel(level, level > thresholdDb)
        if (hops >= maxSeconds * 100L) {
            stoppedByItself(PauseReason.REQUESTED, CaptureNotice.LongestRecording(maxSeconds / 60))
            return
        }
        if (++hopsSinceRoomCheck >= 200) {
            hopsSinceRoomCheck = 0
            val free = freeBytes()
            if (DiskGuard.mustStop(free)) {
                stoppedByItself(PauseReason.DISK_FULL, CaptureNotice.OutOfRoomRecordingSaved(DiskGuard.room(free, sampleRate)))
            }
        }
    }

    private fun stoppedByItself(reason: PauseReason, notice: CaptureNotice) {
        listener.onStoppedByItself(reason, notice)
        stopInternal()
    }

    /**
     * Ends the recording: closes the file, scans it for the pieces the phone suggests, and closes the session's notes. Returns what
     * was found, or null if nothing was recorded (the empty session is left in the notes as closed, with no recording). Calling it
     * again, or after the recording stopped by itself, returns the same result.
     */
    @Synchronized
    fun stop(): StoredRecording? = if (isStopped) result else stopInternal()

    private fun stopInternal(): StoredRecording? {
        if (isStopped) return null
        isStopped = true
        val w = writer ?: return null
        writer = null
        try { w.close() } catch (e: IOException) { /* what was written is on disk; the scan below will say if it is usable */ }
        val result = try {
            if (hops == 0L) null else AudioScan.scanRecording(w.file, thresholdDb)
        } catch (e: WavException) {
            null
        }
        if (result != null) store.finishFreeRecording(sessionId, result)
        else if (hops == 0L) w.file.delete()
        store.closeSession(sessionId, nowUtc())
        this.result = result
        return result
    }
}
