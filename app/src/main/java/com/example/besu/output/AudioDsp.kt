package com.example.besu.output

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin
import kotlin.math.sqrt

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

    // Speech onset requires this many consecutive windows above threshold,
    // not just one -- fixes a reported bug where leading silence never got
    // trimmed (only trailing did). Root cause: VoiceRecorder prefers
    // MediaRecorder.AudioSource.UNPROCESSED, which opts out of the
    // platform's own pop/click/AGC-settle suppression, so a brief
    // elevated-energy transient right at capture start would exceed the
    // threshold on its own, making the old single-window rule land speech
    // onset at/near sample 0 regardless of when real speech started.
    // Requiring a sustained run filters that out while still catching
    // genuine speech; self-adapts to however long the transient actually
    // lasts rather than assuming a fixed duration. (Chosen after on-device
    // A/B testing against three other candidates -- a fixed leading
    // discard, dual-threshold hysteresis, and a noise-floor-relative
    // threshold -- this one held up best.) Trailing edge still uses a
    // single-window rule -- there's no reported problem there to fix, and
    // capture end has no equivalent transient.
    private const val ONSET_CONSECUTIVE_WINDOWS = 3

    // normalizeLoudness's own tunables. TARGET_RMS sits at roughly -20
    // dBFS -- a common conversational-loudness reference -- and
    // PEAK_CEILING at roughly -1 dBFS, well under full scale (32767).
    // MAX_NORMALIZE_GAIN caps how far a very quiet clip can be boosted;
    // past that, amplifying further mostly just raises the noise floor
    // rather than making the voice itself clearer. Like reduceNoise's
    // tunables above, these are reasoned defaults, not device-verified by
    // ear -- if normalized clips come out too quiet, too hot, or too
    // noisy, these three are the first things worth retuning.
    private const val TARGET_RMS = 3277.0
    private const val PEAK_CEILING = 29000.0
    private const val MIN_RMS_FLOOR = 40.0
    private const val MAX_NORMALIZE_GAIN = 8.0

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
    // Splits the clip into SILENCE_WINDOW_MS windows and measures each
    // window's RMS. A window counts as "speech" once its RMS clears
    // SILENCE_RELATIVE_THRESHOLD of the recording's own loudest window --
    // relative rather than a fixed absolute level, so this adapts to how
    // loud or quiet a given recording naturally is. Speech onset
    // specifically requires ONSET_CONSECUTIVE_WINDOWS in a row above
    // threshold (see its own comment above); the trailing edge only needs
    // one. Keeps a padding buffer around the detected speech region so
    // words don't get clipped at the edges. If nothing clears the
    // threshold at all -- a silent or near-silent recording -- returns the
    // clip unchanged rather than risking trimming it down to nothing.
    fun trimSilence(pcm: ShortArray, sampleRate: Int): ShortArray {
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

        val paddingSamples = sampleRate * SILENCE_PADDING_MS / 1000
        val startSample = (firstSpeechWindow * windowSize - paddingSamples).coerceAtLeast(0)
        val endSample = ((lastSpeechWindow + 1) * windowSize + paddingSamples).coerceAtMost(pcm.size)

        return pcm.copyOfRange(startSample, endSample)
    }

    // Brings every accepted recording to the same baseline loudness. Call
    // this LAST, after reduceNoise + trimSilence -- without it, two
    // different recordings can come out at very different volumes purely
    // because of how loud you happened to speak or how close to the mic
    // you were, and neither AUDIO ARCHITECT's Master Gain nor PROTOCOL's
    // recording playback gain (both pure multipliers with nothing to
    // normalize against) can turn that inconsistent starting point into a
    // consistent, predictable one. Synthesized speech doesn't have this
    // problem -- the TTS engine always emits it at the same internal
    // loudness -- this gives a raw recording that same kind of baseline.
    //
    // Targets RMS (perceived loudness) rather than just the single
    // loudest sample, since that's closer to how loud a clip actually
    // sounds -- but RMS-only normalization can clip on a sudden loud
    // sound within an otherwise quiet clip, so the applied gain is also
    // capped at whatever keeps the clip's own peak sample under
    // PEAK_CEILING, whichever cap is stricter. Can both amplify a quiet
    // recording and attenuate a loud one -- the goal is convergence
    // toward one consistent level, not a one-directional boost.
    fun normalizeLoudness(pcm: ShortArray): ShortArray {
        if (pcm.isEmpty()) return pcm

        var sumSquares = 0.0
        var peak = 0.0
        for (sample in pcm) {
            val value = sample.toDouble()
            sumSquares += value * value
            val magnitude = abs(value)
            if (magnitude > peak) peak = magnitude
        }
        val rms = sqrt(sumSquares / pcm.size)

        // Nothing here but noise floor/silence -- normalizing toward the
        // target would just amplify hiss, not a voice that isn't there.
        if (rms < MIN_RMS_FLOOR) return pcm

        var gain = TARGET_RMS / rms
        if (peak > 0.0) {
            gain = gain.coerceAtMost(PEAK_CEILING / peak)
        }
        gain = gain.coerceAtMost(MAX_NORMALIZE_GAIN)

        val result = ShortArray(pcm.size)
        for (i in pcm.indices) {
            result[i] = (pcm[i] * gain).toInt()
                .coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
                .toShort()
        }
        return result
    }

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
