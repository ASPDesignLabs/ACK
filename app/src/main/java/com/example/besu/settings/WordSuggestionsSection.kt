// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.settings

import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.AckTags
import com.example.besu.core.WordSuggestionText
import com.example.besu.data.AssistPrefs
import com.example.besu.data.LearnedWordsRepository
import com.example.besu.help.helpTarget
import com.example.besu.ui.NeonButton
import com.example.besu.ui.RadicalRed
import com.example.besu.ui.TightDialogSurface

/**
 * SETTINGS > WORD SUGGESTIONS: the switch, what it learns and where the words are kept, how many there are, and FORGET WORDS. The decisions and
 * the wording are in core/ (AssistSettings, WordSuggestionText), tested; the learned words are in data/LearnedWordsRepository.kt.
 *
 * Quiet and predictable: the switch says ON or OFF in words, nothing animates and nothing happens on a timer. Turning the switch ON learns
 * nothing from before (it starts empty); turning it OFF keeps the words already learned (FORGET WORDS removes them); neither is ever done
 * for the person. Removing a word asks once more, and FORGET ALL WORDS asks twice. Text is 12 sp or larger and the buttons are NeonButton (12 sp).
 */
@Composable
fun WordSuggestionsSection(
    context: Context,
    primaryColor: Color,
    /** Starts the EXPORT .JSON flow (its warning comes first). */
    onBackUpFirst: () -> Unit
) {
    var on by remember { mutableStateOf(AssistPrefs.isWordSuggestionsOn(context)) }
    var showForget by remember { mutableStateOf(false) }
    var refresh by remember { mutableIntStateOf(0) }
    val count = remember(refresh) { LearnedWordsRepository.wordCount(context) }

    Text("WORD SUGGESTIONS", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
    Spacer(modifier = Modifier.height(10.dp))

    // On or off, said in words (not only colour) and without animation. Choosing it by hand also answers the composer's one-time offer.
    NeonButton(
        WordSuggestionText.switchLabel(on),
        Modifier
            .fillMaxWidth()
            .testTag(AckTags.WORD_SUGGESTIONS_SWITCH)
            .helpTarget(AckTags.WORD_SUGGESTIONS_SWITCH, primaryColor),
        mainColor = if (on) primaryColor else Color.White
    ) {
        on = !on
        AssistPrefs.setWordSuggestions(context, on)
    }
    Spacer(modifier = Modifier.height(6.dp))
    Text(
        WordSuggestionText.SWITCH_EXPLANATION,
        color = Color.Gray,
        fontSize = 12.sp,
        fontFamily = FontFamily.Monospace
    )
    Spacer(modifier = Modifier.height(10.dp))
    Text(
        WordSuggestionText.countLine(count),
        color = Color.LightGray,
        fontSize = 12.sp,
        fontFamily = FontFamily.Monospace
    )
    Spacer(modifier = Modifier.height(8.dp))
    NeonButton(
        WordSuggestionText.FORGET_BUTTON,
        Modifier
            .fillMaxWidth()
            .testTag(AckTags.WORD_SUGGESTIONS_FORGET_BTN)
            .helpTarget(AckTags.WORD_SUGGESTIONS_FORGET_BTN, primaryColor),
        mainColor = primaryColor
    ) {
        showForget = true
    }

    if (showForget) {
        ForgetWordsDialog(
            context = context,
            primaryColor = primaryColor,
            onBackUpFirst = onBackUpFirst,
            onChanged = { refresh++ },
            onDismiss = { showForget = false; refresh++ }
        )
    }
}

/**
 * Every learned word, most used first, with REMOVE on each (one more tap confirms it) and FORGET ALL WORDS (asks twice, CANCEL prominent, a backup
 * named first, like DELETE DATA). Works whether or not the switch is on: the words are the person's data either way.
 */
@Composable
private fun ForgetWordsDialog(
    context: Context,
    primaryColor: Color,
    onBackUpFirst: () -> Unit,
    onChanged: () -> Unit,
    onDismiss: () -> Unit
) {
    var refresh by remember { mutableIntStateOf(0) }
    val words = remember(refresh) { LearnedWordsRepository.listWords(context) }
    var confirmingKey by remember { mutableStateOf<String?>(null) }
    var firstForAll by remember { mutableStateOf(false) }
    var secondForAll by remember { mutableStateOf(false) }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = WordSuggestionText.FORGET_TITLE,
        subtitle = WordSuggestionText.countLine(words.size),
        dismissLabel = "CLOSE"
    ) {
        if (words.isEmpty()) {
            ConfirmBodyText(WordSuggestionText.FORGET_EMPTY, color = Color.Gray)
        } else {
            LazyColumn(modifier = Modifier.heightIn(max = 420.dp)) {
                items(words, key = { it.key }) { word ->
                    Column(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(word.form, color = Color.White, fontSize = 14.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                                ConfirmBodyText(WordSuggestionText.usedLine(word.count), color = Color.Gray)
                            }
                            if (confirmingKey != word.key) {
                                NeonButton(WordSuggestionText.REMOVE, Modifier.widthIn(min = 96.dp), mainColor = RadicalRed) {
                                    confirmingKey = word.key
                                }
                            }
                        }
                        // The question and its two buttons open below their own row; the rows above are not moved.
                        if (confirmingKey == word.key) {
                            Spacer(modifier = Modifier.height(6.dp))
                            ConfirmBodyText(WordSuggestionText.REMOVE_QUESTION, bold = true)
                            Spacer(modifier = Modifier.height(6.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                                NeonButton(WordSuggestionText.REMOVE_CANCEL, Modifier.weight(1f), mainColor = primaryColor) {
                                    confirmingKey = null
                                }
                                NeonButton(WordSuggestionText.REMOVE, Modifier.weight(1f), mainColor = RadicalRed) {
                                    LearnedWordsRepository.forget(context, word.key)
                                    confirmingKey = null
                                    refresh++
                                    onChanged()
                                }
                            }
                        }
                    }
                }
            }
            Spacer(modifier = Modifier.height(12.dp))
            NeonButton(WordSuggestionText.FORGET_ALL, Modifier.fillMaxWidth(), mainColor = RadicalRed) {
                firstForAll = true
            }
        }
    }

    // --- FORGET ALL: first confirmation (what, how many, how to save it first) ---
    if (firstForAll && !secondForAll) {
        TightDialogSurface(
            onDismiss = { firstForAll = false },
            primaryColor = primaryColor,
            title = WordSuggestionText.FORGET_ALL,
            dismissLabel = WordSuggestionText.CANCEL
        ) {
            WordSuggestionText.forgetAllFirstConfirmation(words.size).forEachIndexed { index, text ->
                if (index > 0) Spacer(modifier = Modifier.height(10.dp))
                ConfirmBodyText(text, bold = index == 1)
            }
            Spacer(modifier = Modifier.height(16.dp))
            NeonButton(WordSuggestionText.BACK_UP_FIRST, Modifier.fillMaxWidth(), mainColor = primaryColor) { onBackUpFirst() }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(WordSuggestionText.CONTINUE, Modifier.fillMaxWidth(), mainColor = RadicalRed) { secondForAll = true }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(WordSuggestionText.CANCEL, Modifier.fillMaxWidth(), isActive = false, mainColor = primaryColor) { firstForAll = false }
        }
    }

    // --- FORGET ALL: second confirmation. CANCEL is the prominent choice and abandons the whole thing. ---
    if (secondForAll) {
        val cancelBoth = { secondForAll = false; firstForAll = false }
        TightDialogSurface(
            onDismiss = { cancelBoth() },
            primaryColor = primaryColor,
            title = WordSuggestionText.FORGET_ALL,
            dismissLabel = WordSuggestionText.CANCEL
        ) {
            ConfirmBodyText(WordSuggestionText.FORGET_ALL_SECOND, bold = true, color = RadicalRed)
            Spacer(modifier = Modifier.height(16.dp))
            NeonButton(WordSuggestionText.CANCEL, Modifier.fillMaxWidth(), mainColor = primaryColor) { cancelBoth() }
            Spacer(modifier = Modifier.height(8.dp))
            NeonButton(WordSuggestionText.FORGET_ALL, Modifier.fillMaxWidth(), mainColor = RadicalRed) {
                LearnedWordsRepository.forgetAll(context)
                cancelBoth()
                refresh++
                onChanged()
            }
        }
    }
}
