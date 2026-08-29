package com.example.besu

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import androidx.core.app.ActivityCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import kotlin.math.log10
import kotlin.math.sqrt

class AmbientAudioAnalyzer {
    private var audioRecord: AudioRecord? = null
    var isRecording = false
        private set

    // Adjust this value if the meter reads too high or too low compared to a real dB meter
    private val calibrationOffset = 10.0

    fun start(context: Context) {
        if (isRecording) return

        if (ActivityCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            Log.e("AudioAnalyzer", "Missing RECORD_AUDIO permission")
            return
        }

        try {
            val sampleRate = 44100
            val channelConfig = AudioFormat.CHANNEL_IN_MONO
            val audioFormat = AudioFormat.ENCODING_PCM_16BIT
            val bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)

            // Attempt UNPROCESSED first, fallback to VOICE_RECOGNITION
            val audioSource = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                MediaRecorder.AudioSource.UNPROCESSED
            } else {
                MediaRecorder.AudioSource.VOICE_RECOGNITION
            }

            audioRecord = AudioRecord(audioSource, sampleRate, channelConfig, audioFormat, bufferSize)

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                // Fallback to VOICE_RECOGNITION if UNPROCESSED fails initialization
                audioRecord?.release()
                audioRecord = AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, sampleRate, channelConfig, audioFormat, bufferSize)
            }

            audioRecord?.startRecording()
            isRecording = true
        } catch (e: Exception) {
            Log.e("AudioAnalyzer", "Failed to start AudioRecord", e)
            isRecording = false
        }
    }

    fun stop() {
        if (!isRecording) return
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {
            Log.e("AudioAnalyzer", "Failed to stop AudioRecord", e)
        } finally {
            audioRecord = null
            isRecording = false
        }
    }

    suspend fun collectDbLevels(onLevelUpdate: (Float) -> Unit) {
        withContext(Dispatchers.IO) {
            val bufferSize = AudioRecord.getMinBufferSize(44100, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            val audioData = ShortArray(bufferSize)

            while (isRecording && isActive) {
                val readSize = audioRecord?.read(audioData, 0, bufferSize) ?: 0

                if (readSize > 0) {
                    var sum = 0.0
                    for (i in 0 until readSize) {
                        val sample = audioData[i].toDouble()
                        sum += sample * sample
                    }

                    // Root Mean Square (RMS) calculation
                    val rms = sqrt(sum / readSize)

                    if (rms > 0) {
                        // Base calculation + calibration offset to approximate actual SPL
                        val db = (20 * log10(rms)) + calibrationOffset

                        // Pass back to UI thread
                        withContext(Dispatchers.Main) {
                            onLevelUpdate(db.toFloat().coerceAtLeast(0f))
                        }
                    } else {
                        withContext(Dispatchers.Main) { onLevelUpdate(0f) }
                    }
                }
                // Short delay to avoid UI thrashing, but keep it responsive
                delay(100)
            }
        }
    }
}