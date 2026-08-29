package com.example.besu.wear

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.SystemClock
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit
import kotlin.math.exp
import kotlin.math.pow
import kotlin.math.sin
import kotlin.random.Random

object TechSynth {

    private const val SAMPLE_RATE = 10_000

    // Keep the stream alive briefly after the latest sound so consecutive pose
    // feedback effects reuse one AudioTrack. It is released after quiet time.
    private const val AUDIO_TRACK_IDLE_RELEASE_MS = 10_000L

    // Existing navigation behavior is retained.
    private const val NAV_TONE_MIN_INTERVAL_MS = 80L

    // All audio state is accessed through this one worker. That prevents
    // concurrent AudioTrack writes and keeps cache state deterministic.
    private val audioExecutor = Executors.newSingleThreadExecutor()

    private val releaseScheduler: ScheduledExecutorService =
        Executors.newSingleThreadScheduledExecutor()

    private var currentTheme = 1
    private var masterVolume = 0.8f

    private var lastNavToneAt = 0L

    // A new generation is created whenever a sound plays. A scheduled cleanup
    // only releases the track if no newer sound has happened since scheduling.
    private var audioActivityGeneration = 0L

    // Theme-specific generated float PCM. These are generated once, then reused
    // until the sound theme changes.
    private val soundCache = mutableMapOf<Sfx, FloatArray>()
    private var cachedTheme = -1

    // Created lazily on first sound, then reused for the active audio session.
    // Only access from audioExecutor.
    private var streamTrack: AudioTrack? = null

    enum class Sfx {
        UNLOCK,
        TICK,
        LOCK,
        MODIFIER,
        FIRE,
    }

    /**
     * Called when the phone sends audio preferences.
     *
     * Theme changes invalidate synthesized waveform caches. Volume does not:
     * it is applied while converting each cached FloatArray to PCM.
     */
    fun updateConfig(theme: Int, volume: Float) {
        val sanitizedTheme = theme.coerceIn(0, 2)
        val sanitizedVolume = volume.coerceIn(0f, 1f)

        audioExecutor.execute {
            if (currentTheme != sanitizedTheme) {
                currentTheme = sanitizedTheme
                cachedTheme = -1
                soundCache.clear()
            }

            masterVolume = sanitizedVolume
        }
    }

    fun play(sfx: Sfx) {
        audioExecutor.execute {
            runCatching {
                val buffer = getCachedSoundBuffer(sfx)
                playBuffer(buffer)
            }.onFailure { error ->
                error.printStackTrace()
            }
        }
    }

    fun playNavTone(index: Int) {
        val now = SystemClock.elapsedRealtime()

        if (now - lastNavToneAt < NAV_TONE_MIN_INTERVAL_MS) {
            return
        }

        lastNavToneAt = now

        audioExecutor.execute {
            runCatching {
                val frequency = if (index >= 8) {
                    1500f
                } else {
                    400f + index * 100f
                }

                // Navigation tone frequency changes by index, so it is not
                // included in the fixed Sfx cache.
                val buffer = generateSineBlip(
                    freq = frequency,
                    durationMs = 35,
                )

                playBuffer(buffer)
            }.onFailure { error ->
                error.printStackTrace()
            }
        }
    }

    /**
     * Optional explicit cleanup hook. Call when the app/service truly shuts
     * down, but do not call after each sound.
     */
    fun release() {
        audioExecutor.execute {
            audioActivityGeneration++
            releaseStreamTrack()
        }
    }

    private fun getCachedSoundBuffer(sfx: Sfx): FloatArray {
        if (cachedTheme != currentTheme) {
            soundCache.clear()
            cachedTheme = currentTheme
        }

        return soundCache.getOrPut(sfx) {
            generateSound(sfx)
        }
    }

    private fun generateSound(sfx: Sfx): FloatArray {
        return when (sfx) {
            Sfx.UNLOCK -> {
                if (currentTheme == 0) {
                    generateSweep(
                        startFreq = 300f,
                        endFreq = 1000f,
                        durationMs = 200,
                    )
                } else {
                    generateSweep(
                        startFreq = 400f,
                        endFreq = 1200f,
                        durationMs = 250,
                    )
                }
            }

            Sfx.TICK -> {
                generateClick(
                    freq = if (currentTheme == 2) 800f else 2000f,
                    durationMs = 30,
                )
            }

            Sfx.LOCK -> generateKick(
                freq = 150f,
                durationMs = 200,
            )

            Sfx.MODIFIER -> generateSinePip(
                freq = 1800f,
                durationMs = 80,
            )

            Sfx.FIRE -> generateDataBurst(durationMs = 300)
        }
    }

    private fun generateSweep(
        startFreq: Float,
        endFreq: Float,
        durationMs: Int,
    ): FloatArray {
        val numSamples = SAMPLE_RATE * durationMs / 1000
        val buffer = FloatArray(numSamples)
        var phase = 0.0

        for (i in 0 until numSamples) {
            val t = i.toFloat() / numSamples
            val currentFreq = startFreq + (endFreq - startFreq) * t.pow(2)
            val envelope = 1.0 - t

            phase += 2.0 * Math.PI * currentFreq / SAMPLE_RATE

            var signal = sin(phase)

            if (currentTheme == 0) {
                signal = if (signal > 0.0) 0.8 else -0.8
            }

            buffer[i] = (signal * envelope).toFloat()
        }

        return buffer
    }

    private fun generateClick(
        freq: Float,
        durationMs: Int,
    ): FloatArray {
        val numSamples = SAMPLE_RATE * durationMs / 1000
        val buffer = FloatArray(numSamples)

        for (i in 0 until numSamples) {
            val t = i.toDouble() / SAMPLE_RATE
            val envelope = exp(-t * 800.0)

            var signal = sin(2.0 * Math.PI * freq * t)

            if (currentTheme == 0) {
                signal = (Random.nextFloat() * 2f - 1f).toDouble()
            }

            buffer[i] = (signal * envelope).toFloat()
        }

        return buffer
    }

    private fun generateKick(
        freq: Float,
        durationMs: Int,
    ): FloatArray {
        val numSamples = SAMPLE_RATE * durationMs / 1000
        val buffer = FloatArray(numSamples)
        var phase = 0.0

        for (i in 0 until numSamples) {
            val t = i.toFloat() / numSamples
            val currentFreq = freq * (1.0 - t).pow(4)

            phase += 2.0 * Math.PI * currentFreq / SAMPLE_RATE
            buffer[i] = sin(phase).toFloat()
        }

        return buffer
    }

    private fun generateSinePip(
        freq: Float,
        durationMs: Int,
    ): FloatArray {
        val numSamples = SAMPLE_RATE * durationMs / 1000
        val buffer = FloatArray(numSamples)
        var phase = 0.0

        for (i in 0 until numSamples) {
            val t = i.toFloat() / numSamples
            val envelope = sin(Math.PI * t)

            phase += 2.0 * Math.PI * freq / SAMPLE_RATE
            buffer[i] = (sin(phase) * envelope).toFloat()
        }

        return buffer
    }

    private fun generateDataBurst(durationMs: Int): FloatArray {
        val numSamples = SAMPLE_RATE * durationMs / 1000
        val buffer = FloatArray(numSamples)

        var phase = 0.0
        var frequency = 800.0

        for (i in 0 until numSamples) {
            if (i % 800 == 0) {
                frequency = Random.nextDouble(600.0, 2000.0)
            }

            phase += 2.0 * Math.PI * frequency / SAMPLE_RATE
            buffer[i] = (sin(phase) * 0.5).toFloat()
        }

        return buffer
    }

    private fun generateSineBlip(
        freq: Float,
        durationMs: Int,
    ): FloatArray {
        val numSamples = SAMPLE_RATE * durationMs / 1000
        val buffer = FloatArray(numSamples)

        for (i in 0 until numSamples) {
            val t = i.toDouble() / SAMPLE_RATE
            val signal = sin(2.0 * Math.PI * freq * t)

            val progress = i.toFloat() / numSamples
            val envelope = if (progress < 0.2f) {
                progress / 0.2f
            } else {
                1f - (progress - 0.2f) / 0.8f
            }

            buffer[i] = (signal * envelope).toFloat()
        }

        return buffer
    }

    private fun playBuffer(floatBuffer: FloatArray) {
        if (floatBuffer.isEmpty()) {
            return
        }

        val pcmBuffer = ShortArray(floatBuffer.size)

        for (i in floatBuffer.indices) {
            val sample = (
                floatBuffer[i]
                    .coerceIn(-1f, 1f) *
                    masterVolume *
                    Short.MAX_VALUE
                ).toInt()

            pcmBuffer[i] = sample.toShort()
        }

        val track = getOrCreateStreamTrack()

        val written = track.write(
            pcmBuffer,
            0,
            pcmBuffer.size,
            AudioTrack.WRITE_BLOCKING,
        )

        if (written < 0) {
            throw IllegalStateException(
                "AudioTrack write failed with error code: $written",
            )
        }

        scheduleIdleRelease()
    }

    private fun getOrCreateStreamTrack(): AudioTrack {
        val existingTrack = streamTrack

        if (
            existingTrack != null &&
            existingTrack.state == AudioTrack.STATE_INITIALIZED
        ) {
            if (existingTrack.playState != AudioTrack.PLAYSTATE_PLAYING) {
                existingTrack.play()
            }

            return existingTrack
        }

        existingTrack?.release()
        streamTrack = null

        val minBufferBytes = AudioTrack.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )

        check(minBufferBytes > 0) {
            "AudioTrack minimum buffer size unavailable: $minBufferBytes"
        }

        // 250 ms is large enough to avoid underruns but modest enough not to
        // introduce a huge backlog of sound effects.
        val preferredBufferBytes = SAMPLE_RATE / 4 * Short.SIZE_BYTES
        val bufferSizeBytes = maxOf(minBufferBytes, preferredBufferBytes)

        val track = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build(),
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(SAMPLE_RATE)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build(),
            )
            .setBufferSizeInBytes(bufferSizeBytes)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()

        check(track.state == AudioTrack.STATE_INITIALIZED) {
            "Unable to initialize streaming AudioTrack"
        }

        track.play()
        streamTrack = track

        return track
    }

    private fun scheduleIdleRelease() {
        audioActivityGeneration++
        val generationAtSchedule = audioActivityGeneration

        releaseScheduler.schedule(
            {
                audioExecutor.execute {
                    if (generationAtSchedule == audioActivityGeneration) {
                        releaseStreamTrack()
                    }
                }
            },
            AUDIO_TRACK_IDLE_RELEASE_MS,
            TimeUnit.MILLISECONDS,
        )
    }

    private fun releaseStreamTrack() {
        val track = streamTrack ?: return

        streamTrack = null

        runCatching {
            if (track.playState == AudioTrack.PLAYSTATE_PLAYING) {
                track.pause()
                track.flush()
                track.stop()
            }
        }

        track.release()
    }
}
