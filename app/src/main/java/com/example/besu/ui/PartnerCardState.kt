// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.example.besu.core.PartnerCardSettings
import com.example.besu.data.PartnerCardRepository

/**
 * What the person chose for the partner card, as Compose state, so the question that asks first redraws at once when a sentence is turned on or off or written. Shaped like
 * UsageSummaryState. The values live in `ack_partner_card` (data/PartnerCardRepository.kt); every change is written with `commit()` first and only then shown, so the question never
 * shows a choice that was not kept. Nothing is spoken from here.
 */
object PartnerCardState {
    var settings by mutableStateOf(PartnerCardSettings.DEFAULT)
        private set

    /** Reads what is stored. Called when the question opens, so it is always the saved choice. */
    fun load(context: Context) {
        settings = PartnerCardRepository.load(context)
    }

    /** Turns sentence [slot] on or off. Returns whether it is kept (false: nothing changed). */
    fun toggle(context: Context, slot: Int): Boolean = change(context, settings.toggled(slot))

    /** Writes the person's own sentence into own slot [slot] (5 or 6), tidied; an empty text clears it. Returns whether it is kept (false: nothing changed). */
    fun writeOwn(context: Context, slot: Int, raw: String): Boolean = change(context, settings.withOwn(slot, raw))

    private fun change(context: Context, next: PartnerCardSettings): Boolean {
        if (next == settings) return true
        if (!PartnerCardRepository.save(context, next)) return false
        settings = next
        return true
    }
}
