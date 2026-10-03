// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Which of the newer, safer defaults an EXISTING install is offered (once, in AUDIO ARCHITECT). Nothing is ever changed by
 * this: it only decides what the banner and the review dialog show; the person chooses, and confirms, each change.
 *
 * Plain Kotlin (no `android.*`) so the rule is tested without a phone.
 */
data class DefaultsOffer(
    /** Offer the unprocessed ORGANIC voice (the person is still on CYBER). */
    val unprocessedVoice: Boolean,
    /** Offer showing the whole message on screen (the active display preset cuts messages over 5 words). */
    val fullMessage: Boolean
) {
    val any: Boolean get() = unprocessedVoice || fullMessage
}

/**
 * A new install already starts on the safer defaults, and anyone who dismissed the offer (or applied it) is never asked
 * again. Otherwise only what is still on the old default is offered.
 *
 * @param voiceIsCyber the voice in use is CYBER, which includes an install that never chose one
 * @param presetTruncates the active display preset cuts messages over 5 words (a bypassTruncation of false)
 */
fun defaultsOffer(
    isExistingInstall: Boolean,
    dismissed: Boolean,
    voiceIsCyber: Boolean,
    presetTruncates: Boolean
): DefaultsOffer =
    if (!isExistingInstall || dismissed) {
        DefaultsOffer(unprocessedVoice = false, fullMessage = false)
    } else {
        DefaultsOffer(unprocessedVoice = voiceIsCyber, fullMessage = presetTruncates)
    }
