package com.example.besu.output

import kotlin.math.PI
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin

// Spectral-subtraction noise reduction for a recorded voice clip. This is
// the classic (Boll 1979 / Berouti et al.) approach: estimate a noise
// profile's average magnitude spectrum from the recording's own leading
// ~300ms (assumed to be background noise captured before speech starts --
// matches VoiceRecorder's "just start recording" flow, no separate
// calibration step), then subtract that noise magnitude from every frame's
// spectrum, bin by bin, before reconstructing the waveform. Nothing here
// depends on Android -- pure math, testable independent of a device.
//
// This is a basic implementation, not a production noise suppressor (no
// smoothing across frames, no musical-noise post-filtering beyond the
// spectral floor). It has not been -- cannot be, in this sandbox -- verified
// by ear. If recordings come out with audible artifacts, the spectral floor
// and oversubtraction factor below are the first things worth retuning.
object AudioDsp {
    private const val FRAME_SIZE = 1024
    private const val HOP_SIZE = FRAME_SIZE / 2
    private const val NOISE_PROFILE_SECONDS = 0.3
    private const val OVERSUBTRACTION_FACTOR = 1.5
    private const val SPECTRAL_FLOOR = 0.05

    // trimSilence's own tunables. A window's RMS counts as "speech" once it
    // clears SILENCE_RELATIVE_THRESHOLD of the recording's own loudest
    // window -- relative rather than a fixed absolute level, so this
    // adapts to how loud or quiet a given recording naturally is instead
    // of assuming everyone talks at the same volume into the mic.
    private const val SILENCE_WINDOW_MS = 20
    private const val SILENCE_RELATIVE_THRESHOLD = 0.08
    private const val SILENCE_PADDING_MS = 150

    // Candidate-specific tunables -- see the SilenceTrimMethod variants
    // below. Kept separate from the baseline constants above so tuning one
    // candidate during testing never risks accidentally drifting the
    // baseline everyone's already used to.
    private const val GUARD_DISCARD_MS = 75
    private const val ONSET_CONSECUTIVE_WINDOWS = 3
    private const val DUAL_ONSET_RELATIVE_THRESHOLD = 0.15
    private const val DUAL_CONTINUE_RELATIVE_THRESHOLD = 0.05
    private const val NOISE_FLOOR_THRESHOLD_MULTIPLIER = 4.0

    // Reported bug: trimSilence only ever clips trailing dead air, never
    // leading -- while VoiceRecorder's chosen source (UNPROCESSED, on API
    // 24+) explicitly opts out of the platform's own pop/click/AGC-settle
    // suppression, a brief elevated-energy transient right at capture
    // start is a known quirk of raw/unprocessed Android audio sources.
    // That transient would both (a) exceed the baseline's peak-relative
    // threshold on its own, making firstSpeechWindow land at/near 0
    // regardless of when real speech starts, and (b) sit inside
    // reduceNoise's leading-300ms profile window, skewing what "noise"
    // means for the whole clip. Nothing symmetric happens at capture end,
    // which fits trailing trim working fine.
    //
    // Four candidate fixes below, each targeting the theory differently,
    // for on-device A/B testing via PROTOCOL's (temporary) SILENCE TRIM
    // METHOD selector -- see VoiceRecordingRepository.getSilenceTrimMethod.
    // Once one is confirmed to actually work, the other three and this
    // whole selector should come out; there's no reason to ship four
    // implementations of the same feature.
    enum class SilenceTrimMethod {
        BASELINE,
        GUARD_DISCARD,
        ONSET_HYSTERESIS,
        DUAL_THRESHOLD,
        NOISE_FLOOR_RELATIVE
    }

    fun reduceNoise(pcm: ShortArray, sampleRate: Int): ShortArray {
        // Too short to extract a meaningful noise profile and still leave
        // frames worth processing -- return unchanged rather than risk
        // mangling a very short clip.
        if (pcm.size < FRAME_SIZE * 2) return pcm

        val window = hannWindow(FRAME_SIZE)
        val noiseMagnitude = estimateNoiseProfile(pcm, sampleRate, window)

        val output = DoubleArray(pcm.size)
        val windowSum = DoubleArray(pcm.size)

        var pos = 0
        while (pos + FRAME_SIZE <= pcm.size) {
            val re = DoubleArray(FRAME_SIZE)
            val im = DoubleArray(FRAME_SIZE)
            for (i in 0 until FRAME_SIZE) {
                re[i] = pcm[pos + i] * window[i]
            }

            fft(re, im)
            subtractNoise(re, im, noiseMagnitude)
            ifft(re, im)

            for (i in 0 until FRAME_SIZE) {
                output[pos + i] += re[i] * window[i]
                windowSum[pos + i] += window[i] * window[i]
            }

            pos += HOP_SIZE
        }

        val result = ShortArray(pcm.size)
        for (i in pcm.indices) {
            // Any sample no frame's overlap-add actually covered (the tail
            // past the last full frame) falls back to its original value
            // rather than silence.
            val normalized = if (windowSum[i] > 1e-6) output[i] / windowSum[i] else pcm[i].toDouble()
            result[i] = normalized.toInt()
                .coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
                .toShort()
        }
        return result
    }

    // Cuts the dead air off the start and end of a recording automatically
    // -- no scrubbing/editing UI, just "record, and don't make the user
    // manually trim it." Call this AFTER reduceNoise, not before: reduceNoise
    // relies on genuine quiet at the very start of the clip to estimate its
    // noise profile, and trimming first would remove that.
    //
    // method picks which candidate implementation runs -- see
    // SilenceTrimMethod above. Every candidate shares the same window size,
    // padding, and RMS measurement (computeWindowRms below); only how the
    // speech region's boundaries get decided differs between them.
    fun trimSilence(
        pcm: ShortArray,
        sampleRate: Int,
        method: SilenceTrimMethod = SilenceTrimMethod.BASELINE
    ): ShortArray = when (method) {
        SilenceTrimMethod.BASELINE -> trimSilenceBaseline(pcm, sampleRate)
        SilenceTrimMethod.GUARD_DISCARD -> trimSilenceGuardDiscard(pcm, sampleRate)
        SilenceTrimMethod.ONSET_HYSTERESIS -> trimSilenceOnsetHysteresis(pcm, sampleRate)
        SilenceTrimMethod.DUAL_THRESHOLD -> trimSilenceDualThreshold(pcm, sampleRate)
        SilenceTrimMethod.NOISE_FLOOR_RELATIVE -> trimSilenceNoiseFloorRelative(pcm, sampleRate)
    }

    // Splits pcm into SILENCE_WINDOW_MS windows and measures each one's RMS
    // -- shared by every trim candidate below so they're all reasoning
    // about the exact same measurement, differing only in how they turn it
    // into a start/end decision.
    private fun computeWindowRms(pcm: ShortArray, windowSize: Int, windowCount: Int): DoubleArray {
        val rms = DoubleArray(windowCount)
        for (w in 0 until windowCount) {
            var sum = 0.0
            val start = w * windowSize
            for (i in start until start + windowSize) {
                val sample = pcm[i].toDouble()
                sum += sample * sample
            }
            rms[w] = kotlin.math.sqrt(sum / windowSize)
        }
        return rms
    }

    private fun windowToSampleRange(
        pcm: ShortArray,
        sampleRate: Int,
        windowSize: Int,
        firstSpeechWindow: Int,
        lastSpeechWindow: Int
    ): ShortArray {
        val paddingSamples = sampleRate * SILENCE_PADDING_MS / 1000
        val startSample = (firstSpeechWindow * windowSize - paddingSamples).coerceAtLeast(0)
        val endSample = ((lastSpeechWindow + 1) * windowSize + paddingSamples).coerceAtMost(pcm.size)
        return pcm.copyOfRange(startSample, endSample)
    }

    // The original implementation, unchanged: a window counts as "speech"
    // once its RMS clears SILENCE_RELATIVE_THRESHOLD of the recording's own
    // loudest window. Relative rather than a fixed absolute level, so this
    // adapts to how loud or quiet a given recording naturally is -- but
    // nothing here guards against a single loud window right at the start
    // (a capture-start transient, say) being mistaken for speech onset.
    private fun trimSilenceBaseline(pcm: ShortArray, sampleRate: Int): ShortArray {
        val windowSize = (sampleRate * SILENCE_WINDOW_MS / 1000).coerceAtLeast(1)
        val windowCount = pcm.size / windowSize
        if (windowCount == 0) return pcm

        val rms = computeWindowRms(pcm, windowSize, windowCount)
        val peakRms = rms.maxOrNull() ?: 0.0
        if (peakRms <= 0.0) return pcm

        val threshold = peakRms * SILENCE_RELATIVE_THRESHOLD
        val firstSpeechWindow = rms.indexOfFirst { it > threshold }
        val lastSpeechWindow = rms.indexOfLast { it > threshold }
        if (firstSpeechWindow == -1) return pcm

        return windowToSampleRange(pcm, sampleRate, windowSize, firstSpeechWindow, lastSpeechWindow)
    }

    // Candidate 1: unconditionally discards the first GUARD_DISCARD_MS of
    // the (already noise-reduced) clip before running the baseline scan on
    // what's left -- treating a capture-start transient as known garbage
    // rather than something worth measuring at all. Simplest and cheapest
    // candidate, but it always costs the same fixed amount regardless of
    // whether a transient is actually present, and would clip real speech
    // if someone starts talking within that guard window.
    private fun trimSilenceGuardDiscard(pcm: ShortArray, sampleRate: Int): ShortArray {
        val guardSamples = (sampleRate * GUARD_DISCARD_MS / 1000).coerceAtMost(pcm.size)
        // A clip no longer than the guard period itself has nothing left
        // to discard from -- fall back to scanning it whole rather than
        // handing trimSilenceBaseline an empty array (which would return
        // that empty array right back, violating "never trim to nothing").
        if (guardSamples <= 0 || guardSamples >= pcm.size) return trimSilenceBaseline(pcm, sampleRate)

        val guarded = pcm.copyOfRange(guardSamples, pcm.size)
        return trimSilenceBaseline(guarded, sampleRate)
    }

    // Candidate 2: speech onset requires ONSET_CONSECUTIVE_WINDOWS in a row
    // above threshold, not just one -- a lone transient (a capture-start
    // click, say) doesn't sustain long enough to trigger it, but real
    // speech does. Self-adapts to however long the transient actually
    // lasts, unlike the fixed-duration guard discard above. Trailing edge
    // uses the same single-window rule as baseline -- there's no reported
    // problem there to fix.
    private fun trimSilenceOnsetHysteresis(pcm: ShortArray, sampleRate: Int): ShortArray {
        val windowSize = (sampleRate * SILENCE_WINDOW_MS / 1000).coerceAtLeast(1)
        val windowCount = pcm.size / windowSize
        if (windowCount == 0) return pcm

        val rms = computeWindowRms(pcm, windowSize, windowCount)
        val peakRms = rms.maxOrNull() ?: 0.0
        if (peakRms <= 0.0) return pcm

        val threshold = peakRms * SILENCE_RELATIVE_THRESHOLD

        var firstSpeechWindow = -1
        var run = 0
        for (w in 0 until windowCount) {
            if (rms[w] > threshold) {
                run++
                if (run >= ONSET_CONSECUTIVE_WINDOWS) {
                    firstSpeechWindow = w - ONSET_CONSECUTIVE_WINDOWS + 1
                    break
                }
            } else {
                run = 0
            }
        }
        if (firstSpeechWindow == -1) return pcm

        val lastSpeechWindow = rms.indexOfLast { it > threshold }
        return windowToSampleRange(pcm, sampleRate, windowSize, firstSpeechWindow, lastSpeechWindow)
    }

    // Candidate 3: a higher bar to START the speech region
    // (DUAL_ONSET_RELATIVE_THRESHOLD) than to CONTINUE it once started
    // (DUAL_CONTINUE_RELATIVE_THRESHOLD) -- the classic two-threshold
    // hysteresis approach behind tools like ffmpeg's silenceremove. The
    // stricter onset bar makes a brief transient less likely to qualify on
    // its own; once genuine speech is confirmed, the looser bar walks
    // outward in both directions so quieter syllables right at the edges
    // of a word don't get clipped just for falling under the stricter bar.
    private fun trimSilenceDualThreshold(pcm: ShortArray, sampleRate: Int): ShortArray {
        val windowSize = (sampleRate * SILENCE_WINDOW_MS / 1000).coerceAtLeast(1)
        val windowCount = pcm.size / windowSize
        if (windowCount == 0) return pcm

        val rms = computeWindowRms(pcm, windowSize, windowCount)
        val peakRms = rms.maxOrNull() ?: 0.0
        if (peakRms <= 0.0) return pcm

        val onsetThreshold = peakRms * DUAL_ONSET_RELATIVE_THRESHOLD
        val continueThreshold = peakRms * DUAL_CONTINUE_RELATIVE_THRESHOLD

        val onsetWindow = rms.indexOfFirst { it > onsetThreshold }
        if (onsetWindow == -1) return pcm
        val lastOnsetWindow = rms.indexOfLast { it > onsetThreshold }

        var startWindow = onsetWindow
        while (startWindow - 1 >= 0 && rms[startWindow - 1] > continueThreshold) startWindow--

        var endWindow = lastOnsetWindow
        while (endWindow + 1 < windowCount && rms[endWindow + 1] > continueThreshold) endWindow++

        return windowToSampleRange(pcm, sampleRate, windowSize, startWindow, endWindow)
    }

    // Candidate 4: a different theory of the bug -- rather than a
    // transient specifically, maybe the residual noise floor left behind
    // by reduceNoise just isn't quiet enough relative to peak for
    // baseline's fixed 8%-of-peak threshold to tell silence from speech.
    // This measures the clip's own typical "quiet" directly (the MEDIAN
    // window RMS -- resistant to a single outlier spike skewing it, unlike
    // using the first window or a mean would be) and requires several
    // times louder than that, rather than assuming a fixed fraction of
    // peak already accounts for it.
    private fun trimSilenceNoiseFloorRelative(pcm: ShortArray, sampleRate: Int): ShortArray {
        val windowSize = (sampleRate * SILENCE_WINDOW_MS / 1000).coerceAtLeast(1)
        val windowCount = pcm.size / windowSize
        if (windowCount == 0) return pcm

        val rms = computeWindowRms(pcm, windowSize, windowCount)
        val peakRms = rms.maxOrNull() ?: 0.0
        if (peakRms <= 0.0) return pcm

        val sorted = rms.sortedArray()
        val noiseFloor = sorted[sorted.size / 2]

        val threshold = (noiseFloor * NOISE_FLOOR_THRESHOLD_MULTIPLIER).coerceAtMost(peakRms * 0.5)
        val firstSpeechWindow = rms.indexOfFirst { it > threshold }
        val lastSpeechWindow = rms.indexOfLast { it > threshold }
        if (firstSpeechWindow == -1) return pcm

        return windowToSampleRange(pcm, sampleRate, windowSize, firstSpeechWindow, lastSpeechWindow)
    }

    private fun estimateNoiseProfile(pcm: ShortArray, sampleRate: Int, window: DoubleArray): DoubleArray {
        val profileSampleCount = minOf(pcm.size, (sampleRate * NOISE_PROFILE_SECONDS).toInt())
            .coerceAtLeast(FRAME_SIZE)
        val magnitude = DoubleArray(FRAME_SIZE / 2 + 1)
        var frameCount = 0

        var pos = 0
        while (pos + FRAME_SIZE <= profileSampleCount) {
            val re = DoubleArray(FRAME_SIZE)
            val im = DoubleArray(FRAME_SIZE)
            for (i in 0 until FRAME_SIZE) {
                re[i] = pcm[pos + i] * window[i]
            }
            fft(re, im)
            for (bin in magnitude.indices) {
                magnitude[bin] += hypot(re[bin], im[bin])
            }
            frameCount++
            pos += HOP_SIZE
        }

        if (frameCount > 0) {
            for (bin in magnitude.indices) magnitude[bin] /= frameCount
        }
        return magnitude
    }

    // A real signal's FFT is Hermitian-symmetric (bin k and bin N-k share a
    // magnitude), so the noise profile only needs bins 0..N/2 -- mirror
    // back out for the upper half here.
    private fun subtractNoise(re: DoubleArray, im: DoubleArray, noiseMagnitude: DoubleArray) {
        val n = re.size
        for (bin in 0 until n) {
            val mirrorBin = if (bin <= n / 2) bin else n - bin
            val mag = hypot(re[bin], im[bin])
            val phase = atan2(im[bin], re[bin])
            val subtracted = mag - OVERSUBTRACTION_FACTOR * noiseMagnitude[mirrorBin]
            val newMag = maxOf(subtracted, SPECTRAL_FLOOR * mag)
            re[bin] = newMag * cos(phase)
            im[bin] = newMag * sin(phase)
        }
    }

    private fun hannWindow(size: Int): DoubleArray =
        DoubleArray(size) { i -> 0.5 - 0.5 * cos(2.0 * PI * i / (size - 1)) }

    // Iterative in-place radix-2 Cooley-Tukey FFT. re/im must be the same
    // power-of-2 length.
    private fun fft(re: DoubleArray, im: DoubleArray) {
        val n = re.size
        if (n <= 1) return

        var j = 0
        for (i in 1 until n) {
            var bit = n shr 1
            while (j and bit != 0) {
                j = j xor bit
                bit = bit shr 1
            }
            j = j or bit
            if (i < j) {
                val tRe = re[i]; re[i] = re[j]; re[j] = tRe
                val tIm = im[i]; im[i] = im[j]; im[j] = tIm
            }
        }

        var len = 2
        while (len <= n) {
            val ang = -2.0 * PI / len
            val wRe = cos(ang)
            val wIm = sin(ang)
            var i = 0
            while (i < n) {
                var curRe = 1.0
                var curIm = 0.0
                for (k in 0 until len / 2) {
                    val uRe = re[i + k]
                    val uIm = im[i + k]
                    val vRe = re[i + k + len / 2] * curRe - im[i + k + len / 2] * curIm
                    val vIm = re[i + k + len / 2] * curIm + im[i + k + len / 2] * curRe
                    re[i + k] = uRe + vRe
                    im[i + k] = uIm + vIm
                    re[i + k + len / 2] = uRe - vRe
                    im[i + k + len / 2] = uIm - vIm
                    val nextCurRe = curRe * wRe - curIm * wIm
                    val nextCurIm = curRe * wIm + curIm * wRe
                    curRe = nextCurRe
                    curIm = nextCurIm
                }
                i += len
            }
            len = len shl 1
        }
    }

    private fun ifft(re: DoubleArray, im: DoubleArray) {
        val n = re.size
        for (i in im.indices) im[i] = -im[i]
        fft(re, im)
        for (i in re.indices) {
            re[i] /= n
            im[i] = -im[i] / n
        }
    }
}
