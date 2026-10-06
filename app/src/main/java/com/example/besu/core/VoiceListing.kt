// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.text.Collator
import java.util.Locale

/**
 * One system text-to-speech voice as the picker needs it. Plain Kotlin (no `android.*`): the Android edge (MainActivity) turns each
 * `android.speech.tts.Voice` into this, with [languageDisplay] being the language's name in the phone's own language ("German (Germany)"),
 * not just its code.
 */
data class VoiceInfo(
    val name: String,
    val languageTag: String,
    val languageDisplay: String,
    /** The voice sends text to a server. ACK has no network permission and promises local-only speech, so such a voice is never offered. */
    val networkRequired: Boolean,
    /** False for a voice the speech engine lists but has not downloaded. Choosing it would fail silently, so it is never offered. */
    val installed: Boolean,
)

/**
 * The voice picker's list: every language (it used to be English only), without a voice that needs the internet or is not installed, sorted by
 * language and then by name so a person can find their own. The voice's name is never changed (a profile stores it exactly).
 */
object VoiceListing {

    const val NOTE_HIDDEN = "voice_list_note_hidden"
    const val NOTE_CHOSEN = "voice_list_note_chosen"

    /** Why a voice may be missing from the list, and that a voice already chosen stays chosen. Two sentences, joined here. */
    fun listNote(text: TextSource): String = listOf(text.get(NOTE_HIDDEN), text.get(NOTE_CHOSEN)).joinToString(" ")

    // Case and accents are ignored when ordering languages ("Čeština" sorts with C, "danish" with D), and the result does not depend on the phone's
    // own language: Locale.ROOT, like the suggestion rules that avoid a Turkish-locale surprise.
    private val collator: Collator = Collator.getInstance(Locale.ROOT).apply { strength = Collator.PRIMARY }
    private val languageOrder = Comparator<String> { a, b -> collator.compare(a, b) }

    fun usable(voices: List<VoiceInfo>): List<VoiceInfo> =
        voices
            .filter { !it.networkRequired && it.installed }
            .sortedWith(
                compareBy<VoiceInfo, String>(languageOrder) { it.languageDisplay.trim() }
                    .thenBy { it.name }
                    .thenBy { it.languageTag }
            )

    /** The row's language text: the display name, or the tag if the engine gave none, so a row is never left without a language. */
    fun languageLine(voice: VoiceInfo): String = voice.languageDisplay.trim().ifBlank { voice.languageTag }
}
