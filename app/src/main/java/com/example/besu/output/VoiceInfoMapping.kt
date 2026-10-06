// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.output

import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import com.example.besu.core.VoiceInfo
import java.util.Locale

/**
 * The one place an Android `Voice` becomes the plain-Kotlin [VoiceInfo] that core/VoiceListing.kt works on, so the list and its rows
 * (MainActivity, AudioView) can never disagree about a voice's language or whether it is usable.
 */
fun Voice.toVoiceInfo(): VoiceInfo = VoiceInfo(
    name = name,
    languageTag = locale.toLanguageTag(),
    // The language's name in the phone's own language ("German (Germany)"), not just its code.
    languageDisplay = locale.getDisplayName(Locale.getDefault()),
    networkRequired = isNetworkConnectionRequired,
    installed = features?.contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED) != true
)
