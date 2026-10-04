// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import com.example.besu.core.HelpPlaceholders
import com.example.besu.core.LabelKey
import com.example.besu.data.AssistPrefs

/**
 * PLAIN WORDS (docs/PLAIN_LANGUAGE.md): the switch, and how a screen asks for a label.
 *
 * The mode is Compose state provided at the root next to LocalHelpManager (MainActivity), so flipping the switch redraws every screen in place: no
 * restart, no lost screen, no lost typed text. **Not the restartApp pattern.** The words are string resources (`label_<key>` and `label_<key>_plain`,
 * in every language); this file only chooses which one to read. A label is display text only: it never names an id, a storage key or a token.
 */
val LocalPlainWords = compositionLocalOf { false }

/** The one place the live value is kept; the switch writes through [set] and the root reads [on]. */
object PlainWordsState {
    var on by mutableStateOf(false)
        private set

    /** Reads the saved choice. Safe to call more than once. */
    fun load(context: Context) {
        on = AssistPrefs.isPlainWordsOn(context)
    }

    /** commit()s the choice, answers the one-time offer, and redraws everything that reads [on]. */
    fun set(context: Context, value: Boolean) {
        AssistPrefs.setPlainWords(context, value)
        on = value
        // The Terminal's send switches only act while they can be seen (core/SendFlags.kt), so they go off with this.
        if (!value) TerminalSendSwitches.reset()
    }
}

/** Reads label text from resources. Nothing here throws: a missing name reads as the key's own name, so a gap is visible rather than a crash. */
object LabelText {
    fun resolveOrNull(context: Context, key: LabelKey, plain: Boolean): String? {
        val id = context.resources.getIdentifier(key.resourceName(plain), "string", context.packageName)
        return if (id != 0) context.getString(id) else null
    }

    fun resolve(context: Context, key: LabelKey, plain: Boolean): String = resolveOrNull(context, key, plain) ?: key.name
}

/** The label for [key] in the wording the person chose (standard or plain) and the language of the phone. */
@Composable
fun labelFor(key: LabelKey): String {
    val plain = LocalPlainWords.current
    val context = LocalContext.current
    val configuration = LocalConfiguration.current // a change of language re-reads the resource
    return remember(key, plain, configuration) { LabelText.resolve(context, key, plain) }
}

/** A label that holds a format placeholder (`VAR %1$s`), filled in with [args]. */
@Composable
fun stringFormatLabel(key: LabelKey, vararg args: Any): String = String.format(labelFor(key), *args)

/** The label for a Matrix slot's stored name ("Twist 1"), or the stored text itself when it is a name the person typed. */
@Composable
fun slotLabel(stored: String): String {
    val key = com.example.besu.core.PlainLabels.slotLabelKey(stored) ?: return stored
    return labelFor(key)
}

/** The label for a pose name (IDENTITY, DEFEND, CONNECT), or the name itself when it is a custom layer's own name. */
@Composable
fun poseLabel(stored: String): String {
    val key = com.example.besu.core.PlainLabels.poseLabelKey(stored) ?: return stored
    return labelFor(key)
}

/** A pose name as a heading: its label, or a layer the person named in capitals, as the app has always shown it. */
@Composable
fun poseHeading(stored: String): String {
    val key = com.example.besu.core.PlainLabels.poseLabelKey(stored) ?: return stored.uppercase()
    return labelFor(key)
}

/** HELP text with its `{{KEY:Original}}` placeholders filled in for the chosen wording (core/PlainLabels.kt `HelpPlaceholders`). */
@Composable
fun helpText(text: String): String {
    if (!text.contains("{{")) return text
    val plain = LocalPlainWords.current
    val context = LocalContext.current
    val configuration = LocalConfiguration.current
    return remember(text, plain, configuration) {
        HelpPlaceholders.substitute(text, plain) { key, usePlain -> LabelText.resolveOrNull(context, key, usePlain) }
    }
}
