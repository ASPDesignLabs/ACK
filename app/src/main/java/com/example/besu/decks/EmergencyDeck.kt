// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.decks

import com.example.besu.ui.looseSpacing
import com.example.besu.*
import com.example.besu.R
import com.example.besu.core.EmergencyLabels
import com.example.besu.core.EmergencyLabels.CardLabel
import com.example.besu.core.LabelKey
import com.example.besu.ui.labelFor
import com.example.besu.ui.rememberText
import com.example.besu.ui.stringFormatLabel
import com.example.besu.data.*
import com.example.besu.help.*
import com.example.besu.output.*
import android.content.Context
import android.content.Intent
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.Text
import androidx.compose.ui.window.Dialog
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.serialization.Serializable

@Serializable
enum class EmergencyTone {
    OFF,
    TONE_1,
    TONE_2,
    TONE_3
}

@Serializable
data class EmergencyPromptSlot(
    val slotIndex: Int,
    val label: String = "EMERGENCY ${slotIndex + 1}",
    val template: String = "",
    val localValues: List<String> = emptyList()
)

@Serializable
data class EmergencyDeckConfig(
    val deckId: String,
    val slots: List<EmergencyPromptSlot> = (0..3).map { index ->
        EmergencyPromptSlot(slotIndex = index)
    },
    // Defaults to persisting: an emergency message disappearing on its own
    // before a bystander or responder finishes reading it is a worse
    // failure than it staying up until someone dismisses it (a plain tap
    // still clears it immediately -- see requireHoldToClear below).
    val preventTimedClear: Boolean = true,
    val requireHoldToClear: Boolean = false,
    val forceSpeaker: Boolean = false,
    val boostVolume: Boolean = false,
    val tone: EmergencyTone = EmergencyTone.OFF,
    // When on, tapping an emergency tile first shows what it will say and asks to confirm, so an
    // accidental touch cannot speak an emergency message at full priority. Off by default for
    // everyone (a decision recorded with the developer); a config or backup saved before this
    // field existed decodes as off.
    val confirmBeforeSend: Boolean = false
)

// A tapped tile's label and its phrase, already resolved, while the confirmation dialog is up.
// SEND speaks exactly this text, so what was checked is what is said.
private data class PendingEmergencySend(
    val slotLabel: String,
    val phrase: String
)

@Serializable
data class EmergencyContact(
    val name: String = "",
    val relationship: String = "",
    val phone: String = ""
) {
    val isBlank: Boolean
        get() = name.isBlank() && relationship.isBlank() && phone.isBlank()
}

// A one-glance medical ID card for a bystander or first responder -- not
// deck-specific, since it describes the person, not a communication style.
@Serializable
data class EmergencyInfoCard(
    val fullName: String = "",
    val dateOfBirth: String = "",
    val bloodType: String = "",
    val communicationNote: String = "I am non-verbal or unable to speak right now " +
        "and communicate using this device.",
    val conditions: String = "",
    val allergies: String = "",
    val medications: String = "",
    val contacts: List<EmergencyContact> = listOf(EmergencyContact(), EmergencyContact()),
    val notes: String = ""
) {
    val isBlank: Boolean
        get() = fullName.isBlank() && dateOfBirth.isBlank() && bloodType.isBlank() &&
            conditions.isBlank() && allergies.isBlank() && medications.isBlank() &&
            notes.isBlank() && contacts.all { it.isBlank }
}

@Composable
fun EmergencyDeck(
    context: Context,
    deckId: String,
    primaryColor: Color
) {
    var config by remember(deckId) {
        mutableStateOf(
            CommandRepository.getEmergencyConfig(
                context = context,
                deckId = deckId
            )
        )
    }

    var editingSlot by remember {
        mutableStateOf<EmergencyPromptSlot?>(null)
    }

    var showOverrides by remember {
        mutableStateOf(false)
    }

    var showInfoCard by remember {
        mutableStateOf(false)
    }

    var infoCard by remember {
        mutableStateOf(CommandRepository.getEmergencyInfoCard(context))
    }

    // Set while the CONFIRM BEFORE SENDING dialog is up for a tapped tile.
    var pendingConfirm by remember {
        mutableStateOf<PendingEmergencySend?>(null)
    }

    val helpManager = LocalHelpManager.current
    val words = rememberText()

    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(HelpEvent.Interacted(tag))
    }

    fun reportTextCommit(tag: String) {
        helpManager?.onEvent(HelpEvent.TextCommitted(tag))
    }

    fun reloadConfig() {
        config = CommandRepository.getEmergencyConfig(
            context = context,
            deckId = deckId
        )
    }

    // Speaks an already-resolved emergency phrase with this deck's overrides. This is the send
    // a tile tap has always done, unchanged; it is only pulled out so a confirmation can come
    // before it.
    fun sendEmergency(phrase: String) {
        context.startService(
            Intent(context, OutputService::class.java).apply {
                putExtra("phrase", phrase)
                putExtra("robotic", false)
                putExtra("source", "EMERGENCY")

                putExtra("emergency_mode", true)
                putExtra(
                    "emergency_force_speaker",
                    config.forceSpeaker
                )
                putExtra(
                    "emergency_boost_volume",
                    config.boostVolume
                )
                putExtra(
                    "emergency_tone",
                    config.tone.name
                )
                putExtra(
                    "emergency_prevent_timed_clear",
                    config.preventTimedClear
                )
                putExtra(
                    "emergency_require_hold_to_clear",
                    config.requireHoldToClear
                )
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Text(
            text = labelFor(LabelKey.DECK_TYPE_EMERGENCY),
            color = primaryColor,
            fontSize = 20.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace,
            letterSpacing = looseSpacing(2.sp)
        )

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = EmergencyLabels.hint(words),
            color = Color.Gray,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(16.dp))

        EmergencyStatusStrip(
            config = config,
            primaryColor = primaryColor
        )

        Spacer(modifier = Modifier.height(16.dp))

        config.slots.chunked(2).forEach { rowSlots ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                rowSlots.forEach { slot ->
                    EmergencyPromptButton(
                        modifier = Modifier.weight(1f),
                        slot = slot,
                        primaryColor = primaryColor,
                        onExecute = {
                            val phrase = CommandRepository.resolveEmergencyPrompt(
                                context = context,
                                deckId = deckId,
                                slotIndex = slot.slotIndex
                            )

                            if (phrase.isBlank()) {
                                return@EmergencyPromptButton
                            }

                            if (config.confirmBeforeSend) {
                                // Resolving a phrase has no side effects, so it is safe to
                                // resolve it once here to show it.
                                pendingConfirm = PendingEmergencySend(
                                    slotLabel = EmergencyLabels.shownLabel(words, slot.label, slot.slotIndex),
                                    phrase = phrase
                                )
                            } else {
                                sendEmergency(phrase)
                            }
                        },
                        onEdit = {
                            editingSlot = slot
                            reportHelpInteraction(AckTags.EMERGENCY_SLOT)
                        }
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))
        }

        Spacer(modifier = Modifier.height(4.dp))

        AckOutlineButton(
            text = stringResource(R.string.emergency_configure_overrides),
            primaryColor = primaryColor,
            modifier = Modifier
                .fillMaxWidth()
                .testTag(AckTags.EMERGENCY_OVERRIDES)
                .helpTarget(AckTags.EMERGENCY_OVERRIDES, primaryColor)
        ) {
            showOverrides = true
            reportHelpInteraction(AckTags.EMERGENCY_OVERRIDES)
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Below CONFIGURE OVERRIDES at double the vertical padding so it's an
        // easy target to hit, and white instead of the deck's accent color so
        // it reads as the "for someone else looking at this screen" action.
        AckOutlineButton(
            text = stringResource(R.string.emergency_info_title),
            primaryColor = Color.White,
            verticalPadding = 24.dp,
            modifier = Modifier
                .fillMaxWidth()
                .testTag(AckTags.EMERGENCY_INFO)
                .helpTarget(AckTags.EMERGENCY_INFO, Color.White)
        ) {
            showInfoCard = true
            reportHelpInteraction(AckTags.EMERGENCY_INFO)
        }
    }

    editingSlot?.let { slot ->
        EmergencySlotEditorDialog(
            slot = slot,
            primaryColor = primaryColor,
            onDismiss = {
                editingSlot = null
            },
            onSave = { label, template, localValues ->
                CommandRepository.updateEmergencySlot(
                    context = context,
                    deckId = deckId,
                    slotIndex = slot.slotIndex,
                    label = label,
                    template = template,
                    localValues = localValues
                )

                reloadConfig()
                reportTextCommit(AckTags.EMERGENCY_SAVE)
                editingSlot = null
            }
        )
    }

    if (showOverrides) {
        EmergencyOverridesDialog(
            config = config,
            primaryColor = primaryColor,
            onDismiss = {
                showOverrides = false
            },
            onSave = { updatedConfig ->
                CommandRepository.saveEmergencyConfig(
                    context = context,
                    config = updatedConfig
                )

                reloadConfig()
                showOverrides = false
            }
        )
    }

    pendingConfirm?.let { pending ->
        EmergencyConfirmDialog(
            slotLabel = pending.slotLabel,
            phrase = pending.phrase,
            primaryColor = primaryColor,
            onSend = {
                pendingConfirm = null
                sendEmergency(pending.phrase)
            },
            // Cancel, tapping outside and Back all land here: nothing is spoken or shown.
            onCancel = {
                pendingConfirm = null
            }
        )
    }

    if (showInfoCard) {
        EmergencyInfoDialog(
            card = infoCard,
            onDismiss = {
                showInfoCard = false
            },
            onSave = { updatedCard ->
                CommandRepository.saveEmergencyInfoCard(context, updatedCard)
                infoCard = updatedCard
                reportTextCommit(AckTags.EMERGENCY_INFO_SAVE)
            }
        )
    }
}

@Composable
private fun EmergencyStatusStrip(
    config: EmergencyDeckConfig,
    primaryColor: Color
) {
    // Which overrides are on and how they read is decided in core/EmergencyLabels.kt (tested); this only draws it. The saved tone is mapped to 0..3 here.
    val overrides = EmergencyLabels.Overrides(
        preventTimedClear = config.preventTimedClear,
        requireHoldToClear = config.requireHoldToClear,
        forceSpeaker = config.forceSpeaker,
        boostVolume = config.boostVolume,
        tone = when (config.tone) {
            EmergencyTone.OFF -> 0
            EmergencyTone.TONE_1 -> 1
            EmergencyTone.TONE_2 -> 2
            EmergencyTone.TONE_3 -> 3
        },
        confirmBeforeSend = config.confirmBeforeSend
    )

    Text(
        text = EmergencyLabels.overridesLine(rememberText(), overrides),
        color = if (overrides.isStandard) Color.Gray else primaryColor,
        fontSize = 9.sp,
        fontFamily = FontFamily.Monospace,
        fontWeight = FontWeight.Bold
    )
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun EmergencyPromptButton(
    modifier: Modifier = Modifier,
    slot: EmergencyPromptSlot,
    primaryColor: Color,
    onExecute: () -> Unit,
    onEdit: () -> Unit
) {
    val isConfigured = slot.template.isNotBlank()
    val shape = CutCornerShape(topStart = 14.dp, bottomEnd = 14.dp)

    Column(
        modifier = modifier
            .aspectRatio(1f)
            .testTag(AckTags.EMERGENCY_SLOT)
            .helpTarget(AckTags.EMERGENCY_SLOT, primaryColor)
            .border(
                width = 1.dp,
                color = if (isConfigured) primaryColor else Color.DarkGray,
                shape = shape
            )
            .background(
                color = if (isConfigured) {
                    primaryColor.copy(alpha = 0.13f)
                } else {
                    Color.Black.copy(alpha = 0.24f)
                },
                shape = shape
            )
            .clip(shape)
            .combinedClickable(
                onClick = onExecute,
                onLongClick = onEdit
            )
            .padding(14.dp),
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = "E${slot.slotIndex + 1}",
            color = if (isConfigured) primaryColor else Color.Gray,
            fontSize = 10.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace
        )

        Text(
            text = EmergencyLabels.shownLabel(rememberText(), slot.label, slot.slotIndex),
            color = if (isConfigured) primaryColor else Color.Gray,
            fontSize = 15.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace,
            textAlign = TextAlign.Center,
            maxLines = 2,
            modifier = Modifier.fillMaxWidth()
        )

        Text(
            text = if (isConfigured) {
                stringResource(R.string.emergency_slot_ready)
            } else {
                stringResource(R.string.emergency_slot_hold_to_set)
            },
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth()
        )
    }
}

@Composable
private fun EmergencySlotEditorDialog(
    slot: EmergencyPromptSlot,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (
        label: String,
        template: String,
        localValues: List<String>
    ) -> Unit
) {
    // The field starts with the name as it is shown (the default in the chosen language). Left untouched, saving keeps what was stored: a saved name is never rewritten.
    val words = rememberText()
    val shownAtStart = remember(slot.slotIndex) {
        EmergencyLabels.shownLabel(words, slot.label, slot.slotIndex)
    }

    var label by remember(slot.slotIndex) {
        mutableStateOf(shownAtStart)
    }

    var template by remember(slot.slotIndex) {
        mutableStateOf(slot.template)
    }

    val tags = remember(template) {
        TemplateEngine.getVariableTags(template)
    }

    var localValues by remember(slot.slotIndex, template) {
        mutableStateOf(
            List(tags.size) { index ->
                slot.localValues.getOrNull(index).orEmpty()
            }
        )
    }

    AckDialogShell(
        title = stringResource(R.string.emergency_configure_slot, slot.slotIndex + 1),
        primaryColor = primaryColor,
        onDismiss = onDismiss
    ) {
        AckTextField(
            label = stringResource(R.string.emergency_button_label),
            value = label,
            primaryColor = primaryColor,
            onValueChange = {
                label = it
            }
        )

        Spacer(modifier = Modifier.height(12.dp))

        AckTextField(
            label = stringResource(R.string.emergency_phrase),
            value = template,
            primaryColor = primaryColor,
            singleLine = false,
            onValueChange = {
                template = it
            }
        )

        if (tags.isNotEmpty()) {
            Spacer(modifier = Modifier.height(14.dp))

            Text(
                text = stringResource(R.string.emergency_local_variables),
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )

            tags.forEachIndexed { index, tag ->
                Spacer(modifier = Modifier.height(8.dp))

                AckTextField(
                    label = tag?.let { stringFormatLabel(LabelKey.VARIABLE_TAG, it) } ?: "${labelFor(LabelKey.VARIABLE)} ${index + 1}",
                    value = localValues.getOrNull(index).orEmpty(),
                    primaryColor = primaryColor,
                    onValueChange = { value ->
                        localValues = localValues.toMutableList().apply {
                            this[index] = value
                        }
                    }
                )
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            AckOutlineButton(
                text = stringResource(R.string.common_cancel),
                primaryColor = Color.Gray,
                modifier = Modifier.weight(1f)
            ) {
                onDismiss()
            }

            AckOutlineButton(
                text = stringResource(R.string.common_save),
                primaryColor = primaryColor,
                modifier = Modifier
                    .weight(1f)
                    .testTag(AckTags.EMERGENCY_SAVE)
                    .helpTarget(AckTags.EMERGENCY_SAVE, primaryColor)
            ) {
                onSave(
                    EmergencyLabels.labelToSave(label, shownAtStart, slot.label),
                    template,
                    localValues
                )
            }
        }
    }
}

@Composable
private fun EmergencyOverridesDialog(
    config: EmergencyDeckConfig,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (EmergencyDeckConfig) -> Unit
) {
    var preventTimedClear by remember {
        mutableStateOf(config.preventTimedClear)
    }

    var requireHoldToClear by remember {
        mutableStateOf(config.requireHoldToClear)
    }

    var forceSpeaker by remember {
        mutableStateOf(config.forceSpeaker)
    }

    var boostVolume by remember {
        mutableStateOf(config.boostVolume)
    }

    var tone by remember {
        mutableStateOf(config.tone)
    }

    var confirmBeforeSend by remember {
        mutableStateOf(config.confirmBeforeSend)
    }

    AckDialogShell(
        title = stringResource(R.string.emergency_overrides_title),
        primaryColor = primaryColor,
        onDismiss = onDismiss
    ) {
        Text(
            text = stringResource(R.string.emergency_overlay_clearing),
            color = primaryColor,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        AckToggleRow(
            label = stringResource(R.string.emergency_prevent_timed_clear),
            enabled = preventTimedClear,
            primaryColor = primaryColor
        ) {
            preventTimedClear = !preventTimedClear
        }

        Spacer(modifier = Modifier.height(8.dp))

        AckToggleRow(
            label = stringResource(R.string.emergency_require_hold),
            enabled = requireHoldToClear,
            primaryColor = primaryColor
        ) {
            requireHoldToClear = !requireHoldToClear
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = stringResource(R.string.emergency_output_routing),
            color = primaryColor,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        AckToggleRow(
            label = stringResource(R.string.emergency_force_speaker),
            enabled = forceSpeaker,
            primaryColor = primaryColor
        ) {
            forceSpeaker = !forceSpeaker
        }

        Spacer(modifier = Modifier.height(8.dp))

        AckToggleRow(
            label = stringResource(R.string.emergency_volume_boost),
            enabled = boostVolume,
            primaryColor = primaryColor
        ) {
            boostVolume = !boostVolume
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = stringResource(R.string.emergency_alert_tone),
            color = primaryColor,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            EmergencyTone.entries.forEach { option ->
                AckSegmentButton(
                    label = stringResource(
                        when (option) {
                            EmergencyTone.OFF -> R.string.emergency_tone_off
                            EmergencyTone.TONE_1 -> R.string.emergency_tone_1
                            EmergencyTone.TONE_2 -> R.string.emergency_tone_2
                            EmergencyTone.TONE_3 -> R.string.emergency_tone_3
                        }
                    ),
                    selected = tone == option,
                    primaryColor = primaryColor,
                    modifier = Modifier.weight(1f)
                ) {
                    tone = option
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = stringResource(R.string.emergency_tap_protection),
            color = primaryColor,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        AckToggleRow(
            label = stringResource(R.string.emergency_confirm_before_sending),
            enabled = confirmBeforeSend,
            primaryColor = primaryColor
        ) {
            confirmBeforeSend = !confirmBeforeSend
        }

        Spacer(modifier = Modifier.height(18.dp))

        AckOutlineButton(
            text = stringResource(R.string.emergency_save_overrides),
            primaryColor = primaryColor,
            modifier = Modifier.fillMaxWidth()
        ) {
            onSave(
                config.copy(
                    preventTimedClear = preventTimedClear,
                    requireHoldToClear = requireHoldToClear,
                    forceSpeaker = forceSpeaker,
                    boostVolume = boostVolume,
                    tone = tone,
                    confirmBeforeSend = confirmBeforeSend
                )
            )
        }
    }
}

// Shown instead of sending straight away when CONFIRM BEFORE SENDING is on. The person, or a helper
// looking over their shoulder, can read exactly what will be said before it is. Tapping outside the
// dialog, or Back, is the same as CANCEL.
@Composable
private fun EmergencyConfirmDialog(
    slotLabel: String,
    phrase: String,
    primaryColor: Color,
    onSend: () -> Unit,
    onCancel: () -> Unit
) {
    AckDialogShell(
        title = stringResource(R.string.emergency_confirm_title),
        primaryColor = primaryColor,
        onDismiss = onCancel
    ) {
        Text(
            text = slotLabel,
            color = primaryColor,
            fontSize = 16.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(10.dp))

        Text(
            text = phrase,
            color = Color.White,
            fontSize = 20.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(24.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            AckConfirmButton(
                text = stringResource(R.string.common_cancel),
                color = Color.White,
                modifier = Modifier.weight(1f),
                onClick = onCancel
            )

            AckConfirmButton(
                text = stringResource(R.string.emergency_send),
                color = primaryColor,
                modifier = Modifier.weight(1f),
                onClick = onSend
            )
        }
    }
}

// A large button for the confirmation dialog: at least 64 dp tall (56 dp is the floor) with a big
// label, so a tap is deliberate and easy to land.
@Composable
private fun AckConfirmButton(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .heightIn(min = 64.dp)
            .border(
                width = 2.dp,
                color = color,
                shape = CutCornerShape(4.dp)
            )
            .background(
                color = color.copy(alpha = 0.14f),
                shape = CutCornerShape(4.dp)
            )
            .pointerInput(Unit) {
                detectTapGestures(
                    onTap = {
                        onClick()
                    }
                )
            }
            .padding(horizontal = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = color,
            fontSize = 18.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun EmergencyInfoDialog(
    card: EmergencyInfoCard,
    onDismiss: () -> Unit,
    onSave: (EmergencyInfoCard) -> Unit
) {
    var isEditing by remember { mutableStateOf(false) }

    AckDialogShell(
        // The card view is read by someone else, so its title is the chosen language and English; the edit form is the person's own.
        title = if (isEditing) {
            stringResource(R.string.emergency_info_edit_title)
        } else {
            EmergencyLabels.cardLabel(rememberText(), CardLabel.TITLE)
        },
        primaryColor = Color.White,
        onDismiss = onDismiss
    ) {
        if (isEditing) {
            EmergencyInfoEditForm(
                card = card,
                onCancel = { isEditing = false },
                onSave = { updated ->
                    onSave(updated)
                    isEditing = false
                }
            )
        } else {
            EmergencyInfoDisplay(card)

            Spacer(modifier = Modifier.height(18.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                AckOutlineButton(
                    text = stringResource(R.string.common_close),
                    primaryColor = Color.Gray,
                    modifier = Modifier.weight(1f)
                ) {
                    onDismiss()
                }

                AckOutlineButton(
                    text = stringResource(R.string.common_edit),
                    primaryColor = Color.White,
                    modifier = Modifier.weight(1f)
                ) {
                    isEditing = true
                }
            }
        }
    }
}

@Composable
private fun EmergencyInfoField(label: String, value: String) {
    if (value.isBlank()) return

    Column(modifier = Modifier.padding(bottom = 14.dp)) {
        Text(
            text = label,
            color = Color.White.copy(alpha = 0.6f),
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = looseSpacing(1.sp)
        )

        Spacer(modifier = Modifier.height(2.dp))

        Text(
            text = value,
            color = Color.White,
            fontSize = 15.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
    }
}

@Composable
private fun EmergencyInfoDisplay(card: EmergencyInfoCard) {
    val words = rememberText()

    Column(modifier = Modifier.fillMaxWidth()) {
        if (card.isBlank) {
            Text(
                text = stringResource(R.string.emergency_info_empty),
                color = Color.Gray,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(14.dp))
        }

        EmergencyInfoField(EmergencyLabels.cardLabel(words, CardLabel.NAME), card.fullName)
        EmergencyInfoField(EmergencyLabels.cardLabel(words, CardLabel.DATE_OF_BIRTH), card.dateOfBirth)
        EmergencyInfoField(EmergencyLabels.cardLabel(words, CardLabel.BLOOD_TYPE), card.bloodType)
        EmergencyInfoField(EmergencyLabels.cardLabel(words, CardLabel.COMMUNICATION), card.communicationNote)
        EmergencyInfoField(EmergencyLabels.cardLabel(words, CardLabel.CONDITIONS), card.conditions)
        EmergencyInfoField(EmergencyLabels.cardLabel(words, CardLabel.ALLERGIES), card.allergies)
        EmergencyInfoField(EmergencyLabels.cardLabel(words, CardLabel.MEDICATIONS), card.medications)

        card.contacts.forEachIndexed { index, contact ->
            if (!contact.isBlank) {
                EmergencyInfoField(
                    label = EmergencyLabels.cardLabel(words, if (index == 0) CardLabel.PRIMARY_CONTACT else CardLabel.EMERGENCY_CONTACT),
                    value = listOf(contact.name, contact.relationship, contact.phone)
                        .filter { it.isNotBlank() }
                        .joinToString("  //  ")
                )
            }
        }

        EmergencyInfoField(EmergencyLabels.cardLabel(words, CardLabel.NOTES), card.notes)
    }
}

@Composable
private fun EmergencyInfoEditForm(
    card: EmergencyInfoCard,
    onCancel: () -> Unit,
    onSave: (EmergencyInfoCard) -> Unit
) {
    var fullName by remember { mutableStateOf(card.fullName) }
    var dateOfBirth by remember { mutableStateOf(card.dateOfBirth) }
    var bloodType by remember { mutableStateOf(card.bloodType) }
    var communicationNote by remember { mutableStateOf(card.communicationNote) }
    var conditions by remember { mutableStateOf(card.conditions) }
    var allergies by remember { mutableStateOf(card.allergies) }
    var medications by remember { mutableStateOf(card.medications) }
    var notes by remember { mutableStateOf(card.notes) }

    val contact1 = card.contacts.getOrNull(0) ?: EmergencyContact()
    val contact2 = card.contacts.getOrNull(1) ?: EmergencyContact()

    var contact1Name by remember { mutableStateOf(contact1.name) }
    var contact1Relationship by remember { mutableStateOf(contact1.relationship) }
    var contact1Phone by remember { mutableStateOf(contact1.phone) }
    var contact2Name by remember { mutableStateOf(contact2.name) }
    var contact2Relationship by remember { mutableStateOf(contact2.relationship) }
    var contact2Phone by remember { mutableStateOf(contact2.phone) }

    Column {
        AckTextField(label = stringResource(R.string.emergency_form_full_name), value = fullName, primaryColor = Color.White) {
            fullName = it
        }

        Spacer(modifier = Modifier.height(10.dp))

        AckTextField(label = stringResource(R.string.emergency_card_dob), value = dateOfBirth, primaryColor = Color.White) {
            dateOfBirth = it
        }

        Spacer(modifier = Modifier.height(10.dp))

        AckTextField(label = stringResource(R.string.emergency_card_blood), value = bloodType, primaryColor = Color.White) {
            bloodType = it
        }

        Spacer(modifier = Modifier.height(10.dp))

        AckTextField(
            label = stringResource(R.string.emergency_form_communication_note),
            value = communicationNote,
            primaryColor = Color.White,
            singleLine = false
        ) {
            communicationNote = it
        }

        Spacer(modifier = Modifier.height(10.dp))

        AckTextField(
            label = stringResource(R.string.emergency_form_conditions),
            value = conditions,
            primaryColor = Color.White,
            singleLine = false
        ) {
            conditions = it
        }

        Spacer(modifier = Modifier.height(10.dp))

        AckTextField(
            label = stringResource(R.string.emergency_card_allergies),
            value = allergies,
            primaryColor = Color.White,
            singleLine = false
        ) {
            allergies = it
        }

        Spacer(modifier = Modifier.height(10.dp))

        AckTextField(
            label = stringResource(R.string.emergency_card_medications),
            value = medications,
            primaryColor = Color.White,
            singleLine = false
        ) {
            medications = it
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = stringResource(R.string.emergency_card_primary),
            color = Color.White,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        AckTextField(label = stringResource(R.string.emergency_card_name), value = contact1Name, primaryColor = Color.White) {
            contact1Name = it
        }

        Spacer(modifier = Modifier.height(8.dp))

        AckTextField(
            label = stringResource(R.string.emergency_form_relationship),
            value = contact1Relationship,
            primaryColor = Color.White
        ) {
            contact1Relationship = it
        }

        Spacer(modifier = Modifier.height(8.dp))

        AckTextField(label = stringResource(R.string.emergency_form_phone), value = contact1Phone, primaryColor = Color.White) {
            contact1Phone = it
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = stringResource(R.string.emergency_form_secondary),
            color = Color.White,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        AckTextField(label = stringResource(R.string.emergency_card_name), value = contact2Name, primaryColor = Color.White) {
            contact2Name = it
        }

        Spacer(modifier = Modifier.height(8.dp))

        AckTextField(
            label = stringResource(R.string.emergency_form_relationship),
            value = contact2Relationship,
            primaryColor = Color.White
        ) {
            contact2Relationship = it
        }

        Spacer(modifier = Modifier.height(8.dp))

        AckTextField(label = stringResource(R.string.emergency_form_phone), value = contact2Phone, primaryColor = Color.White) {
            contact2Phone = it
        }

        Spacer(modifier = Modifier.height(10.dp))

        AckTextField(
            label = stringResource(R.string.emergency_form_notes),
            value = notes,
            primaryColor = Color.White,
            singleLine = false
        ) {
            notes = it
        }

        Spacer(modifier = Modifier.height(18.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            AckOutlineButton(
                text = stringResource(R.string.common_cancel),
                primaryColor = Color.Gray,
                modifier = Modifier.weight(1f)
            ) {
                onCancel()
            }

            AckOutlineButton(
                text = stringResource(R.string.common_save),
                primaryColor = Color.White,
                modifier = Modifier
                    .weight(1f)
                    .testTag(AckTags.EMERGENCY_INFO_SAVE)
                    .helpTarget(AckTags.EMERGENCY_INFO_SAVE, Color.White)
            ) {
                onSave(
                    EmergencyInfoCard(
                        fullName = fullName.trim(),
                        dateOfBirth = dateOfBirth.trim(),
                        bloodType = bloodType.trim(),
                        communicationNote = communicationNote.trim(),
                        conditions = conditions.trim(),
                        allergies = allergies.trim(),
                        medications = medications.trim(),
                        contacts = listOf(
                            EmergencyContact(
                                name = contact1Name.trim(),
                                relationship = contact1Relationship.trim(),
                                phone = contact1Phone.trim()
                            ),
                            EmergencyContact(
                                name = contact2Name.trim(),
                                relationship = contact2Relationship.trim(),
                                phone = contact2Phone.trim()
                            )
                        ),
                        notes = notes.trim()
                    )
                )
            }
        }
    }
}

@Composable
private fun AckDialogShell(
    title: String,
    primaryColor: Color,
    onDismiss: () -> Unit,
    content: @Composable () -> Unit
) {
    Dialog(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 640.dp)
                .background(
                    color = Color(0xFF17191D),
                    shape = CutCornerShape(topStart = 16.dp, bottomEnd = 16.dp)
                )
                .border(
                    width = 1.dp,
                    color = primaryColor,
                    shape = CutCornerShape(topStart = 16.dp, bottomEnd = 16.dp)
                )
                .padding(18.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Text(
                text = title,
                color = primaryColor,
                fontSize = 16.sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace,
                letterSpacing = looseSpacing(1.sp)
            )

            Spacer(modifier = Modifier.height(18.dp))

            content()
        }
    }
}

@Composable
private fun AckTextField(
    label: String,
    value: String,
    primaryColor: Color,
    singleLine: Boolean = true,
    onValueChange: (String) -> Unit
) {
    Column {
        Text(
            text = label,
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(4.dp))

        BasicTextField(
            value = value,
            onValueChange = onValueChange,
            singleLine = singleLine,
            textStyle = androidx.compose.ui.text.TextStyle(
                color = Color.White,
                fontSize = 14.sp,
                fontFamily = FontFamily.Monospace
            ),
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    color = Color.Black.copy(alpha = 0.4f),
                    shape = CutCornerShape(4.dp)
                )
                .border(
                    width = 1.dp,
                    color = primaryColor.copy(alpha = 0.65f),
                    shape = CutCornerShape(4.dp)
                )
                .padding(10.dp)
        )
    }
}

@Composable
private fun AckToggleRow(
    label: String,
    enabled: Boolean,
    primaryColor: Color,
    onToggle: () -> Unit
) {
    val stateColor = if (enabled) primaryColor else Color.Gray

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = stateColor.copy(alpha = 0.75f),
                shape = CutCornerShape(4.dp)
            )
            .background(
                color = if (enabled) {
                    primaryColor.copy(alpha = 0.12f)
                } else {
                    Color.Black.copy(alpha = 0.22f)
                },
                shape = CutCornerShape(4.dp)
            )
            .pointerInput(Unit) {
                detectTapGestures(
                    onTap = {
                        onToggle()
                    }
                )
            }
            .padding(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            modifier = Modifier
                .size(14.dp)
                .border(
                    width = 1.dp,
                    color = stateColor,
                    shape = CutCornerShape(2.dp)
                )
                .background(
                    color = if (enabled) stateColor else Color.Transparent,
                    shape = CutCornerShape(2.dp)
                )
        )

        Spacer(modifier = Modifier.width(10.dp))

        Text(
            text = label,
            color = stateColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
    }
}

@Composable
private fun AckSegmentButton(
    label: String,
    selected: Boolean,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    val color = if (selected) primaryColor else Color.Gray

    Box(
        modifier = modifier
            .border(
                width = 1.dp,
                color = color,
                shape = CutCornerShape(4.dp)
            )
            .background(
                color = if (selected) {
                    primaryColor.copy(alpha = 0.16f)
                } else {
                    Color.Black.copy(alpha = 0.25f)
                },
                shape = CutCornerShape(4.dp)
            )
            .pointerInput(Unit) {
                detectTapGestures(
                    onTap = {
                        onClick()
                    }
                )
            }
            .padding(vertical = 10.dp, horizontal = 4.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = label,
            color = color,
            fontSize = 8.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun AckOutlineButton(
    text: String,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    verticalPadding: Dp = 12.dp,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .border(
                width = 1.dp,
                color = primaryColor,
                shape = CutCornerShape(4.dp)
            )
            .background(
                color = primaryColor.copy(alpha = 0.10f),
                shape = CutCornerShape(4.dp)
            )
            .pointerInput(Unit) {
                detectTapGestures(
                    onTap = {
                        onClick()
                    }
                )
            }
            .padding(vertical = verticalPadding, horizontal = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = primaryColor,
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace,
            textAlign = TextAlign.Center
        )
    }
}
