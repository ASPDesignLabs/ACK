package com.example.besu

import kotlinx.serialization.Serializable

@Serializable
data class VoiceProfile(
    val id: String,         // "USER_1"
    val label: String,      // "CUSTOM A"
    val pitch: Float,       // 0.5 - 2.0
    val speed: Float,       // 0.5 - 2.0
    val modFreq: Float,     // 0 - 100 Hz
    val modDepth: Float,    // 0.0 - 1.0
    val crush: Float,       // 0.0 - 1.0
    val systemVoiceName: String = "" // NEW: Binds to Android TTS Engine
)
