// SPDX-License-Identifier: GPL-3.0-or-later
package android.speech.tts
import java.util.Locale

// Stubs of the few members output/VoiceInfoMapping.kt and the voice picker read, written from the real signatures.
class Voice {
    val name: String = ""
    val locale: Locale = Locale.ROOT
    val isNetworkConnectionRequired: Boolean = false
    val features: Set<String>? = null
}
class TextToSpeech {
    class Engine { companion object { const val KEY_FEATURE_NOT_INSTALLED = "notInstalled" } }
}
