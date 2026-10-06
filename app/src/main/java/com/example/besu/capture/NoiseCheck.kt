// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.capture

import kotlin.math.max
import kotlin.math.sqrt

/** What the quiet check found. The words for it are in core/CaptureText.noiseVerdict, in the chosen language. */
enum class NoiseVerdict { GOOD, LOUD_ROOM, NO_SIGNAL, INTERRUPTED }

// The two-second check taken before the first card: the person stays quiet, and the room's level sets what counts as speech (format
// document, section 5.2). Feed it the microphone's samples as they arrive.
class NoiseCheck(private val sampleRate: Int) {
    companion object {
        /** A room louder than this makes the speech threshold hit its ceiling, and quiet speech may then be missed. */
        const val LOUD_ROOM_DB = -40.0
        /** Quieter than this means the microphone is giving digital silence: covered, muted or blocked. */
        const val NO_SIGNAL_DB = -90.0
        /** A hop this much louder than the room's typical (median) hop means something happened during the check. */
        const val INTERRUPTION_DB = 20.0
    }

    private val hop = sampleRate / 100
    private var sumSquares = 0.0
    private var count = 0L
    private var hopSum = 0.0
    private var hopCount = 0
    private val hopLevels = ArrayList<Double>()

    /** Seconds of audio heard so far. */
    val seconds: Double get() = count.toDouble() / sampleRate

    val isDone: Boolean get() = seconds >= CaptureConstants.NOISE_CHECK_S

    fun feed(samples: ShortArray, n: Int = samples.size) {
        for (i in 0 until n) {
            val v = samples[i].toDouble()
            sumSquares += v * v
            hopSum += v * v
            hopCount++
            if (hopCount == hop) {
                hopLevels.add(LevelMath.levelDb(sqrt(hopSum / hop)))
                hopSum = 0.0
                hopCount = 0
            }
        }
        count += n
    }

    /** The room's level over everything heard, to one decimal; null until some audio has been heard. */
    fun floorDbfs(): Double? {
        if (count == 0L) return null
        return LevelMath.rnd(max(LevelMath.levelDb(sqrt(sumSquares / count)), -120.0), 1)
    }

    fun verdict(): NoiseVerdict {
        val floor = floorDbfs() ?: return NoiseVerdict.NO_SIGNAL
        return when {
            floor < NO_SIGNAL_DB -> NoiseVerdict.NO_SIGNAL
            hopLevels.isNotEmpty() && hopLevels.max() - hopLevels.sorted()[hopLevels.size / 2] > INTERRUPTION_DB -> NoiseVerdict.INTERRUPTED
            floor > LOUD_ROOM_DB -> NoiseVerdict.LOUD_ROOM
            else -> NoiseVerdict.GOOD
        }
    }
}
