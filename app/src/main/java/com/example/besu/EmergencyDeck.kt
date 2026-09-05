package com.example.besu

import android.content.Context
import android.content.Intent
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.content.MediaType.Companion.Text
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.text.BasicTextField
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
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
    val preventTimedClear: Boolean = false,
    val requireHoldToClear: Boolean = false,
    val forceSpeaker: Boolean = false,
    val boostVolume: Boolean = false,
    val tone: EmergencyTone = EmergencyTone.OFF
)

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

    val helpManager = LocalHelpManager.current

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

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Text(
            text = "EMERGENCY",
            color = primaryColor,
            fontSize = 20.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 2.sp
        )

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = "TAP: EXECUTE  //  HOLD: CONFIGURE",
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
            text = "CONFIGURE OVERRIDES",
            primaryColor = primaryColor,
            modifier = Modifier
                .fillMaxWidth()
                .testTag(AckTags.EMERGENCY_OVERRIDES)
                .helpTarget(AckTags.EMERGENCY_OVERRIDES, primaryColor)
        ) {
            showOverrides = true
            reportHelpInteraction(AckTags.EMERGENCY_OVERRIDES)
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
}

@Composable
private fun EmergencyStatusStrip(
    config: EmergencyDeckConfig,
    primaryColor: Color
) {
    val states = buildList {
        if (config.preventTimedClear) add("PERSIST")
        if (config.requireHoldToClear) add("HOLD CLEAR")
        if (config.forceSpeaker) add("SPEAKER")
        if (config.boostVolume) add("BOOST")
        if (config.tone != EmergencyTone.OFF) add(config.tone.name)
    }

    Text(
        text = if (states.isEmpty()) {
            "OVERRIDES: STANDARD"
        } else {
            "OVERRIDES: ${states.joinToString(" // ")}"
        },
        color = if (states.isEmpty()) Color.Gray else primaryColor,
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
            text = slot.label,
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
                "READY"
            } else {
                "HOLD TO SET"
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
    var label by remember(slot.slotIndex) {
        mutableStateOf(slot.label)
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
        title = "CONFIGURE E${slot.slotIndex + 1}",
        primaryColor = primaryColor,
        onDismiss = onDismiss
    ) {
        AckTextField(
            label = "BUTTON LABEL",
            value = label,
            primaryColor = primaryColor,
            onValueChange = {
                label = it
            }
        )

        Spacer(modifier = Modifier.height(12.dp))

        AckTextField(
            label = "EMERGENCY PHRASE",
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
                text = "LOCAL VARIABLES",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )

            tags.forEachIndexed { index, tag ->
                Spacer(modifier = Modifier.height(8.dp))

                AckTextField(
                    label = tag?.let { "VAR:$it" } ?: "VARIABLE ${index + 1}",
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
                text = "CANCEL",
                primaryColor = Color.Gray,
                modifier = Modifier.weight(1f)
            ) {
                onDismiss()
            }

            AckOutlineButton(
                text = "SAVE",
                primaryColor = primaryColor,
                modifier = Modifier.weight(1f)
            ) {
                onSave(
                    label,
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

    AckDialogShell(
        title = "EMERGENCY OVERRIDES",
        primaryColor = primaryColor,
        onDismiss = onDismiss
    ) {
        Text(
            text = "OVERLAY CLEARING",
            color = primaryColor,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        AckToggleRow(
            label = "PREVENT TIMED CLEAR",
            enabled = preventTimedClear,
            primaryColor = primaryColor
        ) {
            preventTimedClear = !preventTimedClear
        }

        Spacer(modifier = Modifier.height(8.dp))

        AckToggleRow(
            label = "REQUIRE HOLD TO CLEAR",
            enabled = requireHoldToClear,
            primaryColor = primaryColor
        ) {
            requireHoldToClear = !requireHoldToClear
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "OUTPUT ROUTING",
            color = primaryColor,
            fontSize = 10.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        AckToggleRow(
            label = "FORCE DEVICE SPEAKER",
            enabled = forceSpeaker,
            primaryColor = primaryColor
        ) {
            forceSpeaker = !forceSpeaker
        }

        Spacer(modifier = Modifier.height(8.dp))

        AckToggleRow(
            label = "EMERGENCY VOLUME BOOST",
            enabled = boostVolume,
            primaryColor = primaryColor
        ) {
            boostVolume = !boostVolume
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "ALERT TONE",
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
                    label = option.name.replace('_', ' '),
                    selected = tone == option,
                    primaryColor = primaryColor,
                    modifier = Modifier.weight(1f)
                ) {
                    tone = option
                }
            }
        }

        Spacer(modifier = Modifier.height(18.dp))

        AckOutlineButton(
            text = "SAVE OVERRIDES",
            primaryColor = primaryColor,
            modifier = Modifier.fillMaxWidth()
        ) {
            onSave(
                config.copy(
                    preventTimedClear = preventTimedClear,
                    requireHoldToClear = requireHoldToClear,
                    forceSpeaker = forceSpeaker,
                    boostVolume = boostVolume,
                    tone = tone
                )
            )
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
        ) {
            Text(
                text = title,
                color = primaryColor,
                fontSize = 16.sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 1.sp
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
            .padding(vertical = 12.dp, horizontal = 10.dp),
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
