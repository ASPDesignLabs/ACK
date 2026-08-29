package com.example.besu

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Build
import android.os.IBinder
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.core.app.NotificationCompat
import kotlinx.serialization.json.Json
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Locale
import java.util.Queue
import java.util.UUID
import kotlin.math.sin
import kotlin.random.Random
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.PI

class OutputService : Service(), TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private var isTtsReady = false
    
    private val jsonParser = Json { 
        ignoreUnknownKeys = true 
        encodeDefaults = true
        isLenient = true
    }
    
    // Global Config
    private var activeProfileId = "CYBER"
    private var tutorialProfileId = "MECH"
    private var cadenceFactor = 0f
    private var forceSpeaker = false 
    
    // Gain State
    private var masterGain = 1.0f

    private var customVoices: List<VoiceProfile> = emptyList()

    private val FACTORY_PRESETS = mapOf(
        "CYBER" to VoiceProfile("CYBER", "CYBER", 1.2f, 1.2f, 50f, 0.6f, 0.3f), 
        "MECH" to VoiceProfile("MECH", "MECH", 0.7f, 0.85f, 30f, 0.85f, 0.4f), 
        "ORGANIC" to VoiceProfile("ORGANIC", "ORGANIC", 1.0f, 1.0f, 0f, 0f, 0f) 
    )

    private data class EmergencyOptions(
        val enabled: Boolean = false,
        val forceSpeaker: Boolean = false,
        val boostVolume: Boolean = false,
        val tone: EmergencyTone = EmergencyTone.OFF,
        val preventTimedClear: Boolean = false,
        val requireHoldToClear: Boolean = false
    )

    private data class RenderRequest(
        val profileId: String,
        val emergency: EmergencyOptions
    )

    private val renderRequests = ConcurrentHashMap<String, RenderRequest>()

    private data class QueuedSpeech(
        val text: String,
        val roboticOverride: Boolean,
        val source: String,
        val emergency: EmergencyOptions = EmergencyOptions()
    )


    private val speechQueue = java.util.concurrent.ConcurrentLinkedQueue<QueuedSpeech>()

    /*
     * TTS only returns our utterance ID when synthesis completes. Keep the
     * per-request output behavior here so emergency flags cannot leak into later
     * standard requests.
     */



    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        startForeground(1337, createNotification())
        loadSettingsFromDisk()

        tts = TextToSpeech(applicationContext, this)
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}

            override fun onDone(utteranceId: String?) {
                if (utteranceId == null || !utteranceId.startsWith("FILE_")) {
                    return
                }

                val uniqueFileId = utteranceId.removePrefix("FILE_")
                val request = renderRequests.remove(uniqueFileId) ?: return

                processAndPlayAudio(
                    uniqueFileId = uniqueFileId,
                    profileId = request.profileId,
                    emergency = request.emergency
                )
            }
            override fun onError(utteranceId: String?) {
                if (utteranceId?.startsWith("FILE_") == true) {
                    val uniqueFileId = utteranceId.removePrefix("FILE_")
                    renderRequests.remove(uniqueFileId)

                    File(cacheDir, "tts_${uniqueFileId}.wav").delete()
                    broadcastLog("TTS SYNTHESIS FAILED", "ERR")
                }
            }
        })
    }

    private fun loadSettingsFromDisk() {
        val prefs = getSharedPreferences("ack_prefs", Context.MODE_PRIVATE)
        activeProfileId = prefs.getString("USER_VOX_PROFILE", "CYBER") ?: "CYBER"
        tutorialProfileId = prefs.getString("TUT_VOX_PROFILE", "MECH") ?: "MECH"
        cadenceFactor = prefs.getFloat("VOX_CADENCE", 0.0f)
        forceSpeaker = prefs.getBoolean("FORCE_SPEAKER", false)
        masterGain = prefs.getFloat("MASTER_GAIN", 1.0f)
        
        val customJson = prefs.getString("CUSTOM_VOICES", "[]") ?: "[]"
        try { 
            customVoices = jsonParser.decodeFromString(customJson) 
        } catch (e: Exception) { 
            customVoices = emptyList() 
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent == null) { loadSettingsFromDisk(); return START_STICKY }

        when (intent.action) {
            "UPDATE_DSP" -> {
                activeProfileId = intent.getStringExtra("user_profile") ?: activeProfileId
                tutorialProfileId = intent.getStringExtra("tutorial_profile")
                ?: tutorialProfileId
                cadenceFactor = intent.getFloatExtra("cadence", cadenceFactor)
                forceSpeaker = intent.getBooleanExtra("speaker", forceSpeaker)
                masterGain = intent.getFloatExtra("master_gain", masterGain)
                
                val rawCustoms = intent.getStringExtra("custom_voices_json")
                if (rawCustoms != null) { 
                    try { 
                        customVoices = jsonParser.decodeFromString(rawCustoms)
                    } catch(e: Exception){
                        broadcastLog("DSP JSON ERR: ${e.message}", "ERR")
                    } 
                }
            }
            "TEST_SIGNAL" -> {
                processSpeech("Audio Check. 1, 2, 3.", false, "SYS/TEST")
            }
            "CHANGE_PROFILE" -> {
                val newProfile = intent.getStringExtra("NEW_PROFILE") ?: "DEFAULT"
                CommandRepository.setActiveProfile(this, newProfile)
                processSpeech("Profile Engaged.", true, "SYS/CONFIG")
            }
            else -> {
                val phrase = intent.getStringExtra("phrase")
                val isRobotic = intent.getBooleanExtra("robotic", false)
                val source = intent.getStringExtra("source") ?: "EXT"

                val emergency = EmergencyOptions(
                    enabled = intent.getBooleanExtra("emergency_mode", false),
                    forceSpeaker = intent.getBooleanExtra(
                        "emergency_force_speaker",
                        false
                    ),
                    boostVolume = intent.getBooleanExtra(
                        "emergency_boost_volume",
                        false
                    ),
                    tone = parseEmergencyTone(
                        intent.getStringExtra("emergency_tone")
                    ),
                    preventTimedClear = intent.getBooleanExtra(
                        "emergency_prevent_timed_clear",
                        false
                    ),
                    requireHoldToClear = intent.getBooleanExtra(
                        "emergency_require_hold_to_clear",
                        false
                    )
                )

                if (!phrase.isNullOrEmpty()) {
                    val request = QueuedSpeech(
                        text = phrase,
                        roboticOverride = isRobotic,
                        source = source,
                        emergency = emergency
                    )

                    if (isTtsReady) {
                        processSpeech(
                            rawText = request.text,
                            isTutorialOverride = request.roboticOverride,
                            source = request.source,
                            emergency = request.emergency
                        )
                    } else {
                        speechQueue.add(request)
                    }
                }
            }
        }
        return START_STICKY
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.setLanguage(Locale.US)
            isTtsReady = true
            drainQueue()
        }
    }

    private fun drainQueue() {
        while (speechQueue.isNotEmpty()) {
            val item = speechQueue.poll() ?: continue

            processSpeech(
                rawText = item.text,
                isTutorialOverride = item.roboticOverride,
                source = item.source,
                emergency = item.emergency
            )
        }
    }

    private fun getProfile(id: String): VoiceProfile {
        customVoices.find { it.id == id }?.let { return it }
        FACTORY_PRESETS[id]?.let { return it }
        return FACTORY_PRESETS["CYBER"]!!
    }

    private fun parseEmergencyTone(rawTone: String?): EmergencyTone {
        return try {
            EmergencyTone.valueOf(rawTone ?: EmergencyTone.OFF.name)
        } catch (_: IllegalArgumentException) {
            EmergencyTone.OFF
        }
    }

    private fun showVisualPrompt(
        rawText: String,
        emergency: EmergencyOptions
    ) {
        if (!android.provider.Settings.canDrawOverlays(this)) {
            return
        }

        val preset = VisualPresetRepository.getActivePreset(this)
        val visualText = VisualLogicEngine.resolveDisplayPrompt(
            rawText,
            null,
            null,
            preset
        )

        val overlayIntent = Intent(this, VisualPromptService::class.java).apply {
            action = "SHOW_PROMPT"
            putExtra("text", visualText)

            /*
             * These extras are harmless for normal output. VisualPromptService
             * treats absent/false values as its ordinary timeout behavior.
             */
            putExtra(
                "prevent_timed_clear",
                emergency.enabled && emergency.preventTimedClear
            )
            putExtra(
                "require_hold_to_clear",
                emergency.enabled && emergency.requireHoldToClear
            )
        }

        startService(overlayIntent)
    }

    private fun processSpeech(
        rawText: String,
        isTutorialOverride: Boolean,
        source: String,
        emergency: EmergencyOptions = EmergencyOptions()
    ) {
        val targetId = if (isTutorialOverride) {
            tutorialProfileId
        } else {
            activeProfileId
        }

        val profile = getProfile(targetId)
        val logType = if (emergency.enabled) {
            "EMERGENCY"
        } else if (isTutorialOverride) {
            "SYS"
        } else {
            "OUT"
        }

        broadcastLog("$source > \"$rawText\"", logType)

        if (!isTutorialOverride) {
            showVisualPrompt(
                rawText = rawText,
                emergency = emergency
                        )
            }

        val effectiveCadence = if (isTutorialOverride) {
            0.0f
        } else {
            cadenceFactor
        }

        val finalText = if (effectiveCadence > 0.1f) {
            applyCadenceWarp(rawText, effectiveCadence)
        } else {
            rawText
        }

        tts?.setPitch(profile.pitch)
        tts?.setSpeechRate(profile.speed)

        if (profile.systemVoiceName.isNotEmpty()) {
            try {
                val desiredVoice = tts?.voices?.find { voice ->
                    voice.name == profile.systemVoiceName
                }

                if (desiredVoice != null && tts?.voice != desiredVoice) {
                    tts?.voice = desiredVoice
                }
            } catch (_: Exception) {
                // Fall back to the current system TTS voice.
            }
        }

        val uniqueId = UUID.randomUUID().toString()
        val destFile = File(cacheDir, "tts_${uniqueId}.wav")
        val utteranceId = "FILE_$uniqueId"

        renderRequests[uniqueId] = RenderRequest(
            profileId = targetId,
            emergency = emergency
        )

        val result = tts?.synthesizeToFile(
            finalText,
            null,
            destFile,
            utteranceId
        )

        if (result != TextToSpeech.SUCCESS) {
            renderRequests.remove(uniqueId)
            destFile.delete()
            broadcastLog("TTS QUEUE FAILED", "ERR")
        }
    }

    private fun processAndPlayAudio(
        uniqueFileId: String,
        profileId: String,
        emergency: EmergencyOptions
    ) {
        val file = File(cacheDir, "tts_${uniqueFileId}.wav")

        if (!file.exists()) {
            return
        }

        try {
            val profile = getProfile(profileId)
            val rawBytes = file.readBytes()
            val headerSize = 44


            if (rawBytes.size <= headerSize) {
                return
            }

            val sampleRate = ByteBuffer.wrap(rawBytes, 24, 4)
                .order(ByteOrder.LITTLE_ENDIAN)
                .int

            val audioData = ShortArray((rawBytes.size - headerSize) / 2)

            ByteBuffer.wrap(
                rawBytes,
                headerSize,
                rawBytes.size - headerSize
            )
                .order(ByteOrder.LITTLE_ENDIAN)
                .asShortBuffer()
                .get(audioData)

            val effectiveGain = getEffectiveGain(emergency)
            applyAudioEffects(
                audioData = audioData,
                crush = profile.crush,
                gain = effectiveGain
            )

            /*
             * A tone occurs immediately before speech, after TTS synthesis is
             * complete. This keeps the audible sequence predictable:
             *
             * tone -> spoken prompt
             */
            if (emergency.enabled && emergency.tone != EmergencyTone.OFF) {
                playEmergencyTone(
                    tone = emergency.tone,
                    forceSpeaker = emergency.forceSpeaker || forceSpeaker
                )
            }

            playPcm(
                audioData = audioData,
                sampleRate = sampleRate,
                forceSpeakerForRequest = emergency.forceSpeaker || forceSpeaker,
                allowVolumeEnforcement = !emergency.enabled && masterGain > 1.2f
            )
        } catch (error: Exception) {
            error.printStackTrace()
            broadcastLog("AUDIO PLAYBACK FAILED", "ERR")
        } finally {
            file.delete()
        }
    }

    private fun getEffectiveGain(emergency: EmergencyOptions): Float {
        val baseGain = masterGain.coerceIn(0f, 3.0f)

        if (!emergency.enabled || !emergency.boostVolume) {
            return baseGain
        }

        /*
         * A per-request PCM boost. This never changes the user's system volume.
         * The final cap also protects against harsh clipping on loud profiles.
         */
        return (baseGain * 1.35f).coerceAtMost(3.0f)
    }

    private fun applyAudioEffects(
        audioData: ShortArray,
        crush: Float,
        gain: Float
    ) {
        val applyCrush = crush > 0.01f
        val quantize = 1 + (crush * 100f).toInt()

        for (index in audioData.indices) {
            var sample = audioData[index].toDouble()

            if (applyCrush) {
                sample = (sample.toInt() / quantize * quantize).toDouble()
            }

            sample *= gain

            audioData[index] = sample
                .toInt()
                .coerceIn(
                    Short.MIN_VALUE.toInt(),
                    Short.MAX_VALUE.toInt()
                )
                .toShort()
        }
    }

    private fun playPcm(
        audioData: ShortArray,
        sampleRate: Int,
        forceSpeakerForRequest: Boolean,
        allowVolumeEnforcement: Boolean
    ) {
        val attributes = AudioAttributes.Builder()

        val targetStreamType = if (forceSpeakerForRequest) {
            attributes.setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
            attributes.setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
            AudioManager.STREAM_ACCESSIBILITY
        } else {
            attributes.setUsage(AudioAttributes.USAGE_MEDIA)
            attributes.setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
            AudioManager.STREAM_MUSIC
        }

        val track = AudioTrack.Builder()
            .setAudioAttributes(attributes.build())
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(audioData.size * 2)
            .build()

        try {
            /*
             * Preserve the existing normal-output behavior, but explicitly do
             * not alter system volume for an Emergency request.
             */
            if (allowVolumeEnforcement) {
                ensureStreamVolume(targetStreamType)
            }

            routeToSpeakerIfRequested(
                audioTrack = track,
                forceSpeakerForRequest = forceSpeakerForRequest
            )

            track.play()
            track.write(audioData, 0, audioData.size)

            while (
                track.playState == AudioTrack.PLAYSTATE_PLAYING &&
                track.playbackHeadPosition < audioData.size
            ) {
                Thread.sleep(10)
            }
        } finally {
            try {
                track.stop()
            } catch (_: IllegalStateException) {
                // Track may already be stopped by the platform.
            }

            track.release()
        }
    }

    private fun routeToSpeakerIfRequested(
        audioTrack: AudioTrack,
        forceSpeakerForRequest: Boolean
    ) {
        if (
            !forceSpeakerForRequest ||
            Build.VERSION.SDK_INT < Build.VERSION_CODES.M
        ) {
            return
        }

        val audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager

        val speaker = audioManager
            .getDevices(AudioManager.GET_DEVICES_OUTPUTS)
            .find { device ->
                device.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
            }

        if (speaker != null) {
            audioTrack.preferredDevice = speaker
        }
    }

    private fun playEmergencyTone(
        tone: EmergencyTone,
        forceSpeaker: Boolean
    ) {
        val notes = when (tone) {
            EmergencyTone.OFF -> emptyList()

            /*
             * PULSE:
             * Two short neutral beeps. Useful when a small acknowledgement is
             * wanted without sounding like an alarm.
             */
            EmergencyTone.TONE_1 -> listOf(
                ToneNote(frequencyHz = 660.0, durationMs = 90),
                ToneNote(frequencyHz = 660.0, durationMs = 90)
            )

            /*
             * SIGNAL:
             * Three ascending tones. Clearly recognizable without being urgent.
             */
            EmergencyTone.TONE_2 -> listOf(
                ToneNote(frequencyHz = 523.25, durationMs = 80),
                ToneNote(frequencyHz = 659.25, durationMs = 80),
                ToneNote(frequencyHz = 783.99, durationMs = 120)
            )

            /*
             * URGENT:
             * A compact lower/higher alternating pattern. It is intentionally
             * short and never loops.
             */
            EmergencyTone.TONE_3 -> listOf(
                ToneNote(frequencyHz = 440.0, durationMs = 110),
                ToneNote(frequencyHz = 330.0, durationMs = 110),
                ToneNote(frequencyHz = 440.0, durationMs = 150)
            )
        }

        if (notes.isEmpty()) {
            return
        }

        val sampleRate = 22_050
        val pcm = buildTonePcm(
            notes = notes,
            sampleRate = sampleRate
        )

        playPcm(
            audioData = pcm,
            sampleRate = sampleRate,
            forceSpeakerForRequest = forceSpeaker,
            allowVolumeEnforcement = false
        )
    }

    private data class ToneNote(
        val frequencyHz: Double,
        val durationMs: Int
    )

    private fun buildTonePcm(
        notes: List<ToneNote>,
        sampleRate: Int
    ): ShortArray {
        val silenceSamples = sampleRate / 25
        val totalSamples = notes.sumOf { note ->
            (sampleRate * note.durationMs) / 1_000 + silenceSamples
        }

        val output = ShortArray(totalSamples)
        var cursor = 0

        notes.forEach { note ->
            val noteSamples = (sampleRate * note.durationMs) / 1_000
            val fadeSamples = minOf(noteSamples / 8, sampleRate / 100)

            for (index in 0 until noteSamples) {
                val envelope = toneEnvelope(
                    index = index,
                    totalSamples = noteSamples,
                    fadeSamples = fadeSamples
                )

                val radians = 2.0 * PI * note.frequencyHz * index / sampleRate
                val sample = sin(radians) * envelope * 0.34

                output[cursor++] = (sample * Short.MAX_VALUE)
                    .toInt()
                    .coerceIn(
                        Short.MIN_VALUE.toInt(),
                        Short.MAX_VALUE.toInt()
                    )
                    .toShort()
            }

            cursor += silenceSamples
        }

        return output
    }

    private fun toneEnvelope(
        index: Int,
        totalSamples: Int,
        fadeSamples: Int
    ): Double {
        if (fadeSamples <= 0) {
            return 1.0
        }

        return when {
            index < fadeSamples -> index.toDouble() / fadeSamples
            index > totalSamples - fadeSamples -> {
                (totalSamples - index).toDouble() / fadeSamples
            }
            else -> 1.0
        }.coerceIn(0.0, 1.0)
    }
    
    // NEW: Volume Consistency Enforcer
    private fun ensureStreamVolume(streamType: Int) {
        try {
            val am = getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val maxVol = am.getStreamMaxVolume(streamType)
            val currentVol = am.getStreamVolume(streamType)
            val targetVol = (maxVol * 0.8).toInt() // Target 80% volume
            
            if (currentVol < targetVol) {
                // We gently bump it up. 
                // Note: Apps are generally discouraged from maxing volume without user input, 
                // but for an Assistive Tool, ensuring audibility is key.
                am.setStreamVolume(streamType, targetVol, 0)
            }
        } catch (e: Exception) {
            // Permission might be denied on some devices, ignore safe failure
        }
    }

    private fun applyCadenceWarp(text: String, intensity: Float): String {
        val sb = StringBuilder("<speak>")
        text.split(" ").forEach { word ->
            if (Random.nextFloat() < intensity) sb.append("<prosody rate=\"${if (Random.nextBoolean()) "x-fast" else "slow"}\">$word</prosody> ") else sb.append("$word ")
        }
        sb.append("</speak>")
        return sb.toString()
    }

    private fun broadcastLog(msg: String, type: String) {
        val intent = Intent("ACK_LOG"); intent.setPackage(packageName)
        intent.putExtra("msg", msg); intent.putExtra("type", type); sendBroadcast(intent)
    }

    private fun createNotification(): Notification {
        val channelId = "ack_core_v2"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val chan = NotificationChannel(channelId, "ACK Voice Synthesis", NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(chan)
        }
        return NotificationCompat.Builder(this, channelId)
            .setContentTitle("ACK // ONLINE").setContentText("Neural Core Active")
            .setSmallIcon(android.R.drawable.ic_lock_silent_mode_off).setOngoing(true).build()
    }

    override fun onDestroy() { tts?.stop(); tts?.shutdown(); super.onDestroy() }
}
