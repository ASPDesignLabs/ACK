package com.example.besu

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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import java.util.UUID
import kotlinx.serialization.Serializable

@Serializable
enum class EmojiGridSize(
    val columns: Int,
    val rows: Int
) {
    THREE_BY_THREE(columns = 3, rows = 3),
    FOUR_BY_FOUR(columns = 4, rows = 4),
    FIVE_BY_FIVE(columns = 5, rows = 5);

    val slotCount: Int
        get() = columns * rows
}

@Serializable
enum class EmojiOverlayTimeout(
    val durationMs: Long
) {
    STANDARD(durationMs = 10_000L),
    EXTENDED(durationMs = 20_000L),
    NO_AUTO_CLEAR(durationMs = 0L)
}

@Serializable
data class EmojiSlot(
    val slotIndex: Int,
    val emoji: String = "",
    val label: String = "",
    val displayText: String = "",
    val opensRelatedPanel: Boolean = false,
    val relatedPanel: List<EmojiSlot> = emptyList()
)

@Serializable
data class EmojiPage(
    val pageId: String,
    val name: String,
    val slots: List<EmojiSlot> = emptyList()
)

@Serializable
data class EmojiDeckConfig(
    val deckId: String,
    val gridSize: EmojiGridSize = EmojiGridSize.FOUR_BY_FOUR,
    val pages: List<EmojiPage> = listOf(
        EmojiPage(
            pageId = "page_1",
            name = "PAGE 1"
        )
    ),
    val overlayTimeout: EmojiOverlayTimeout =
        EmojiOverlayTimeout.STANDARD
)

@Composable
fun EmojiDeck(
    context: Context,
    deckId: String,
    primaryColor: Color
) {
    var config by remember(deckId) {
        mutableStateOf(
            CommandRepository.getEmojiDeckConfig(
                context = context,
                deckId = deckId
            )
        )
    }

    var activePageIndex by remember(deckId) {
        mutableIntStateOf(0)
    }

    var editingSlot by remember {
        mutableStateOf<EmojiSlot?>(null)
    }

    var viewingRelatedPanel by remember {
        mutableStateOf<EmojiSlot?>(null)
    }

    var showDeckConfig by remember {
        mutableStateOf(false)
    }

    fun reloadConfig() {
        config = CommandRepository.getEmojiDeckConfig(
            context = context,
            deckId = deckId
        )

        activePageIndex = activePageIndex.coerceIn(
            minimumValue = 0,
            maximumValue = (config.pages.size - 1).coerceAtLeast(0)
        )
    }

    fun showEmojiPrompt(slot: EmojiSlot) {
        if (slot.emoji.isBlank()) {
            return
        }

        context.startService(
            Intent(context, VisualPromptService::class.java).apply {
                action = "SHOW_EMOJI"

                putExtra("emoji", slot.emoji)
                putExtra("display_text", slot.displayText)
                putExtra(
                    "emoji_timeout_ms",
                    config.overlayTimeout.durationMs
                )
            }
        )
    }

    val activePage = config.pages.getOrNull(activePageIndex)
        ?: return

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier.weight(1f)
            ) {
                AckText(
                    text = "EMOJI // EXPRESS",
                    color = primaryColor,
                    size = 18.sp,
                    weight = FontWeight.Black,
                    letterSpacing = 2.sp
                )

                Spacer(modifier = Modifier.height(4.dp))

                AckText(
                    text = "TAP: DISPLAY  //  HOLD: CONFIGURE",
                    color = Color.Gray,
                    size = 9.sp
                )
            }

            AckTapButton(
                text = "CONFIG",
                color = primaryColor
            ) {
                showDeckConfig = true
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        EmojiPageNavigator(
            pageName = activePage.name,
            pageIndex = activePageIndex,
            pageCount = config.pages.size,
            primaryColor = primaryColor,
            onPrevious = {
                activePageIndex = (
                    activePageIndex - 1 + config.pages.size
                ) % config.pages.size
            },
            onNext = {
                activePageIndex = (
                    activePageIndex + 1
                ) % config.pages.size
            }
        )

        Spacer(modifier = Modifier.height(12.dp))

        EmojiGrid(
            page = activePage,
            gridSize = config.gridSize,
            primaryColor = primaryColor,
            onExecute = { slot ->
                if (slot.emoji.isBlank()) {
                    return@EmojiGrid
                }

                if (slot.opensRelatedPanel) {
                    viewingRelatedPanel = slot
                    return@EmojiGrid
                }

                showEmojiPrompt(slot)
            },
            onEdit = { slot ->
                editingSlot = slot
            }
        )
    }

    editingSlot?.let { slot ->
        EmojiSlotEditorDialog(
            initialSlot = slot,
            deckId = deckId,
            pageId = activePage.pageId,
            gridSize = config.gridSize,
            primaryColor = primaryColor,
            onDismiss = {
                editingSlot = null
            },
            onSave = { emoji, label, displayText, opensRelatedPanel ->
                CommandRepository.updateEmojiSlot(
                    context = context,
                    deckId = deckId,
                    pageId = activePage.pageId,
                    slotIndex = slot.slotIndex,
                    emoji = emoji,
                    label = label,
                    displayText = displayText,
                    opensRelatedPanel = opensRelatedPanel
                )

                editingSlot = null
                reloadConfig()
            },
            onSaveParentForRelated = { emoji, label, displayText ->
                CommandRepository.updateEmojiSlot(
                    context = context,
                    deckId = deckId,
                    pageId = activePage.pageId,
                    slotIndex = slot.slotIndex,
                    emoji = emoji,
                    label = label,
                    displayText = displayText,
                    opensRelatedPanel = true
                )

                reloadConfig()
            },
            onSaveRelatedSlot = { childSlotIndex, emoji, label, displayText ->
                CommandRepository.updateRelatedEmojiSlot(
                    context = context,
                    deckId = deckId,
                    pageId = activePage.pageId,
                    parentSlotIndex = slot.slotIndex,
                    childSlotIndex = childSlotIndex,
                    emoji = emoji,
                    label = label,
                    displayText = displayText
                )

                reloadConfig()
            }
        )
    }

    viewingRelatedPanel?.let { selectedParent ->
        val currentParent = config.pages
            .find { it.pageId == activePage.pageId }
            ?.slots
            ?.find { it.slotIndex == selectedParent.slotIndex }
            ?: selectedParent

        RelatedEmojiPanelViewerDialog(
            parentSlot = currentParent,
            gridSize = config.gridSize,
            primaryColor = primaryColor,
            onDismiss = {
                viewingRelatedPanel = null
            },
            onSelect = { childSlot ->
                viewingRelatedPanel = null
                showEmojiPrompt(childSlot)
            }
        )
    }

    if (showDeckConfig) {
        EmojiDeckConfigDialog(
            config = config,
            primaryColor = primaryColor,
            onDismiss = {
                showDeckConfig = false
            },
            onSave = { updated ->
                CommandRepository.saveEmojiDeckConfig(
                    context = context,
                    config = updated
                )

                showDeckConfig = false
                reloadConfig()
            }
        )
    }
}

@Composable
private fun EmojiPageNavigator(
    pageName: String,
    pageIndex: Int,
    pageCount: Int,
    primaryColor: Color,
    onPrevious: () -> Unit,
    onNext: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        AckTapButton(
            text = "<",
            color = primaryColor,
            modifier = Modifier.weight(0.18f),
            onClick = onPrevious
        )

        Box(
            modifier = Modifier
                .weight(0.64f)
                .border(
                    width = 1.dp,
                    color = primaryColor.copy(alpha = 0.7f),
                    shape = CutCornerShape(4.dp)
                )
                .padding(vertical = 9.dp, horizontal = 6.dp),
            contentAlignment = Alignment.Center
        ) {
            AckText(
                text = "$pageName // ${pageIndex + 1}/$pageCount",
                color = primaryColor,
                size = 10.sp,
                weight = FontWeight.Bold,
                align = TextAlign.Center
            )
        }

        AckTapButton(
            text = ">",
            color = primaryColor,
            modifier = Modifier.weight(0.18f),
            onClick = onNext
        )
    }
}

@Composable
private fun EmojiGrid(
    page: EmojiPage,
    gridSize: EmojiGridSize,
    primaryColor: Color,
    onExecute: (EmojiSlot) -> Unit,
    onEdit: (EmojiSlot) -> Unit
) {
    val slots = (0 until gridSize.slotCount).map { index ->
        page.slots.find { it.slotIndex == index }
            ?: EmojiSlot(slotIndex = index)
    }

    slots.chunked(gridSize.columns).forEachIndexed { rowIndex, rowSlots ->
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            rowSlots.forEach { slot ->
                EmojiSlotButton(
                    slot = slot,
                    primaryColor = primaryColor,
                    modifier = Modifier.weight(1f),
                    onExecute = {
                        onExecute(slot)
                    },
                    onEdit = {
                        onEdit(slot)
                    }
                )
            }
        }

        if (rowIndex < gridSize.rows - 1) {
            Spacer(modifier = Modifier.height(8.dp))
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun EmojiSlotButton(
    slot: EmojiSlot,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onExecute: () -> Unit,
    onEdit: () -> Unit
) {
    val configured = slot.emoji.isNotBlank()
    val hasText = slot.displayText.isNotBlank()

    val borderColor = when {
        !configured -> Color.DarkGray
        slot.opensRelatedPanel -> primaryColor
        hasText -> Color.White
        else -> primaryColor
    }

    val borderWidth = when {
        slot.opensRelatedPanel -> 2.dp
        hasText -> 2.dp
        else -> 1.dp
    }

    val shape = CutCornerShape(
        topStart = 10.dp,
        bottomEnd = 10.dp
    )

    Box(
        modifier = modifier
            .aspectRatio(1f)
            .border(
                width = borderWidth,
                color = borderColor,
                shape = shape
            )
            .background(
                color = if (configured) {
                    primaryColor.copy(alpha = 0.10f)
                } else {
                    Color.Black.copy(alpha = 0.20f)
                },
                shape = shape
            )
            .clip(shape)
            .combinedClickable(
                onClick = onExecute,
                onLongClick = onEdit
            )
            .padding(5.dp)
    ) {
        if (configured) {
            AckText(
                text = slot.emoji,
                color = Color.White,
                size = 30.sp,
                align = TextAlign.Center,
                modifier = Modifier.align(Alignment.Center)
            )

            if (hasText) {
                AckText(
                    text = "TXT",
                    color = Color.White,
                    size = 7.sp,
                    weight = FontWeight.Black,
                    letterSpacing = 1.sp,
                    modifier = Modifier.align(Alignment.BottomEnd)
                )
            }

            if (slot.opensRelatedPanel) {
                AckText(
                    text = "+",
                    color = primaryColor,
                    size = 15.sp,
                    weight = FontWeight.Black,
                    modifier = Modifier.align(Alignment.TopEnd)
                )
            }
        } else {
            AckText(
                text = "HOLD\nTO SET",
                color = Color.Gray,
                size = 8.sp,
                weight = FontWeight.Bold,
                align = TextAlign.Center,
                modifier = Modifier.align(Alignment.Center)
            )
        }
    }
}

@Composable
private fun EmojiSlotEditorDialog(
    initialSlot: EmojiSlot,
    deckId: String,
    pageId: String,
    gridSize: EmojiGridSize,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (
        emoji: String,
        label: String,
        displayText: String,
        opensRelatedPanel: Boolean
    ) -> Unit,
    onSaveParentForRelated: (
        emoji: String,
        label: String,
        displayText: String
    ) -> Unit,
    onSaveRelatedSlot: (
        childSlotIndex: Int,
        emoji: String,
        label: String,
        displayText: String
    ) -> Unit
) {
    var opensRelatedPanel by remember(initialSlot.slotIndex) {
        mutableStateOf(initialSlot.opensRelatedPanel)
    }

    var showRelatedPanelEditor by remember(initialSlot.slotIndex) {
        mutableStateOf(false)
    }

    var emoji by remember(initialSlot.slotIndex) {
        mutableStateOf(initialSlot.emoji)
    }

    var label by remember(initialSlot.slotIndex) {
        mutableStateOf(initialSlot.label)
    }

    var displayText by remember(initialSlot.slotIndex) {
        mutableStateOf(initialSlot.displayText)
    }

    var pickerOpen by remember(initialSlot.slotIndex) {
        mutableStateOf(false)
    }

    AckDialogShell(
        title = "CONFIGURE EMOJI ${initialSlot.slotIndex + 1}",
        primaryColor = primaryColor,
        onDismiss = onDismiss
    ) {
        AckInput(
            label = "CUSTOM EMOJI",
            value = emoji,
            primaryColor = primaryColor,
            onValueChange = {
                emoji = it
            }
        )

        Spacer(modifier = Modifier.height(10.dp))

        AckTapButton(
            text = if (pickerOpen) {
                "HIDE EMOJI LIBRARY"
            } else {
                "PICK FROM LIBRARY"
            },
            color = primaryColor,
            modifier = Modifier.fillMaxWidth()
        ) {
            pickerOpen = !pickerOpen
        }

        if (pickerOpen) {
            Spacer(modifier = Modifier.height(12.dp))

            EmojiLibrary(
                primaryColor = primaryColor,
                onSelect = { selected ->
                    emoji = selected
                }
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        AckInput(
            label = "LABEL // OPTIONAL",
            value = label,
            primaryColor = primaryColor,
            onValueChange = {
                label = it
            }
        )

        Spacer(modifier = Modifier.height(12.dp))

        AckInput(
            label = "OVERLAY TEXT // OPTIONAL",
            value = displayText,
            primaryColor = primaryColor,
            singleLine = false,
            onValueChange = {
                displayText = it
            }
        )

        Spacer(modifier = Modifier.height(14.dp))

        AckToggleRow(
            label = "OPEN RELATED EMOJI PANEL",
            enabled = opensRelatedPanel,
            primaryColor = primaryColor
        ) {
            opensRelatedPanel = !opensRelatedPanel
        }

        if (opensRelatedPanel) {
            Spacer(modifier = Modifier.height(8.dp))

            AckTapButton(
                text = "CONFIGURE RELATED PANEL",
                color = primaryColor,
                modifier = Modifier.fillMaxWidth()
            ) {
                /*
                 * Save the parent slot but intentionally keep this editor open.
                 * The child panel is a nested configuration screen.
                 */
                onSaveParentForRelated(
                    emoji.trim(),
                    label.trim(),
                    displayText.trim()
                )

                showRelatedPanelEditor = true
            }

            Spacer(modifier = Modifier.height(6.dp))

            AckText(
                text = "THIS SLOT OPENS A SINGLE-PAGE EMOJI PANEL.",
                color = Color.Gray,
                size = 8.sp
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            AckTapButton(
                text = "CLEAR",
                color = Color.Gray,
                modifier = Modifier.weight(1f)
            ) {
                emoji = ""
                label = ""
                displayText = ""
                opensRelatedPanel = false
            }

            AckTapButton(
                text = "SAVE",
                color = primaryColor,
                modifier = Modifier.weight(1f)
            ) {
                onSave(
                    emoji.trim(),
                    label.trim(),
                    displayText.trim(),
                    opensRelatedPanel
                )
            }
        }
    }

    if (showRelatedPanelEditor) {
        RelatedEmojiPanelEditorDialog(
            parentSlot = initialSlot.copy(
                emoji = emoji.trim(),
                label = label.trim(),
                displayText = displayText.trim(),
                opensRelatedPanel = true
            ),
            deckId = deckId,
            pageId = pageId,
            gridSize = gridSize,
            primaryColor = primaryColor,
            onDismiss = {
                showRelatedPanelEditor = false
            },
            onSaveSlot = onSaveRelatedSlot
        )
    }
}

@Composable
private fun RelatedEmojiPanelEditorDialog(
    parentSlot: EmojiSlot,
    deckId: String,
    pageId: String,
    gridSize: EmojiGridSize,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSaveSlot: (
        childSlotIndex: Int,
        emoji: String,
        label: String,
        displayText: String
    ) -> Unit
) {
    var editingChildSlot by remember(parentSlot.slotIndex) {
        mutableStateOf<EmojiSlot?>(null)
    }

    var relatedSlots by remember(parentSlot.slotIndex) {
        mutableStateOf(parentSlot.relatedPanel)
    }

    val childSlots = (0 until gridSize.slotCount).map { slotIndex ->
        relatedSlots.find { it.slotIndex == slotIndex }
            ?: EmojiSlot(slotIndex = slotIndex)
    }

    AckDialogShell(
        title = "RELATED // ${
            parentSlot.label.ifBlank {
                parentSlot.emoji.ifBlank { "PANEL" }
            }
        }",
        primaryColor = primaryColor,
        onDismiss = onDismiss
    ) {
        AckText(
            text = "HOLD A TILE TO CONFIGURE IT.",
            color = Color.Gray,
            size = 8.sp
        )

        Spacer(modifier = Modifier.height(12.dp))

        childSlots.chunked(gridSize.columns).forEachIndexed { rowIndex, row ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                row.forEach { childSlot ->
                    EmojiSlotButton(
                        slot = childSlot.copy(
                            opensRelatedPanel = false,
                            relatedPanel = emptyList()
                        ),
                        primaryColor = primaryColor,
                        modifier = Modifier.weight(1f),
                        onExecute = {},
                        onEdit = {
                            editingChildSlot = childSlot
                        }
                    )
                }
            }

            if (rowIndex < gridSize.rows - 1) {
                Spacer(modifier = Modifier.height(6.dp))
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        AckTapButton(
            text = "DONE",
            color = primaryColor,
            modifier = Modifier.fillMaxWidth()
        ) {
            onDismiss()
        }
    }

    editingChildSlot?.let { childSlot ->
        RelatedEmojiSlotEditorDialog(
            initialSlot = childSlot,
            primaryColor = primaryColor,
            onDismiss = {
                editingChildSlot = null
            },
            onSave = { emoji, label, displayText ->
                val updatedSlot = childSlot.copy(
                    emoji = emoji,
                    label = label,
                    displayText = displayText,
                    opensRelatedPanel = false,
                    relatedPanel = emptyList()
                )

                relatedSlots = (0 until gridSize.slotCount).map { slotIndex ->
                    if (slotIndex == childSlot.slotIndex) {
                        updatedSlot
                    } else {
                        relatedSlots.find { it.slotIndex == slotIndex }
                            ?: EmojiSlot(slotIndex = slotIndex)
                    }
                }

                onSaveSlot(
                    childSlot.slotIndex,
                    emoji,
                    label,
                    displayText
                )

                editingChildSlot = null
            }
        )
    }
}

@Composable
private fun RelatedEmojiPanelViewerDialog(
    parentSlot: EmojiSlot,
    gridSize: EmojiGridSize,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSelect: (EmojiSlot) -> Unit
) {
    val childSlots = (0 until gridSize.slotCount).map { slotIndex ->
        parentSlot.relatedPanel.find { it.slotIndex == slotIndex }
            ?: EmojiSlot(slotIndex = slotIndex)
    }

    AckDialogShell(
        title = "RELATED // ${
            parentSlot.label.ifBlank {
                parentSlot.emoji.ifBlank { "PANEL" }
            }
        }",
        primaryColor = primaryColor,
        onDismiss = onDismiss
    ) {
        AckText(
            text = "TAP AN EMOJI TO DISPLAY IT.",
            color = Color.Gray,
            size = 8.sp
        )

        Spacer(modifier = Modifier.height(12.dp))

        childSlots.chunked(gridSize.columns).forEachIndexed { rowIndex, row ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                row.forEach { childSlot ->
                    RelatedEmojiPanelViewerSlot(
                        slot = childSlot,
                        primaryColor = primaryColor,
                        modifier = Modifier.weight(1f),
                        onClick = {
                            if (childSlot.emoji.isNotBlank()) {
                                onSelect(childSlot)
                            }
                        }
                    )
                }
            }

            if (rowIndex < gridSize.rows - 1) {
                Spacer(modifier = Modifier.height(6.dp))
            }
        }

        Spacer(modifier = Modifier.height(14.dp))

        AckTapButton(
            text = "DONE",
            color = primaryColor,
            modifier = Modifier.fillMaxWidth()
        ) {
            onDismiss()
        }
    }
}

@Composable
private fun RelatedEmojiPanelViewerSlot(
    slot: EmojiSlot,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    val configured = slot.emoji.isNotBlank()

    val shape = CutCornerShape(
        topStart = 10.dp,
        bottomEnd = 10.dp
    )

    Box(
        modifier = modifier
            .aspectRatio(1f)
            .border(
                width = 1.dp,
                color = if (configured) primaryColor else Color.DarkGray,
                shape = shape
            )
            .background(
                color = if (configured) {
                    primaryColor.copy(alpha = 0.10f)
                } else {
                    Color.Black.copy(alpha = 0.20f)
                },
                shape = shape
            )
            .clip(shape)
            .pointerInput(slot.slotIndex, configured) {
                detectTapGestures(
                    onTap = {
                        if (configured) {
                            onClick()
                        }
                    }
                )
            }
            .padding(5.dp),
        contentAlignment = Alignment.Center
    ) {
        if (configured) {
            AckText(
                text = slot.emoji,
                color = Color.White,
                size = 30.sp,
                align = TextAlign.Center
            )

            if (slot.displayText.isNotBlank()) {
                AckText(
                    text = "TXT",
                    color = Color.White,
                    size = 7.sp,
                    weight = FontWeight.Black,
                    letterSpacing = 1.sp,
                    modifier = Modifier.align(Alignment.BottomEnd)
                )
            }
        } else {
            AckText(
                text = "—",
                color = Color.DarkGray,
                size = 16.sp,
                weight = FontWeight.Bold,
                align = TextAlign.Center
            )
        }
    }
}

@Composable
private fun RelatedEmojiSlotEditorDialog(
    initialSlot: EmojiSlot,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (
        emoji: String,
        label: String,
        displayText: String
    ) -> Unit
) {
    var emoji by remember(initialSlot.slotIndex) {
        mutableStateOf(initialSlot.emoji)
    }

    var label by remember(initialSlot.slotIndex) {
        mutableStateOf(initialSlot.label)
    }

    var displayText by remember(initialSlot.slotIndex) {
        mutableStateOf(initialSlot.displayText)
    }

    var pickerOpen by remember(initialSlot.slotIndex) {
        mutableStateOf(false)
    }

    AckDialogShell(
        title = "RELATED EMOJI ${initialSlot.slotIndex + 1}",
        primaryColor = primaryColor,
        onDismiss = onDismiss
    ) {
        AckInput(
            label = "CUSTOM EMOJI",
            value = emoji,
            primaryColor = primaryColor,
            onValueChange = {
                emoji = it
            }
        )

        Spacer(modifier = Modifier.height(10.dp))

        AckTapButton(
            text = if (pickerOpen) {
                "HIDE EMOJI LIBRARY"
            } else {
                "PICK FROM LIBRARY"
            },
            color = primaryColor,
            modifier = Modifier.fillMaxWidth()
        ) {
            pickerOpen = !pickerOpen
        }

        if (pickerOpen) {
            Spacer(modifier = Modifier.height(12.dp))

            EmojiLibrary(
                primaryColor = primaryColor,
                onSelect = { selected ->
                    emoji = selected
                }
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        AckInput(
            label = "LABEL // OPTIONAL",
            value = label,
            primaryColor = primaryColor,
            onValueChange = {
                label = it
            }
        )

        Spacer(modifier = Modifier.height(12.dp))

        AckInput(
            label = "OVERLAY TEXT // OPTIONAL",
            value = displayText,
            primaryColor = primaryColor,
            singleLine = false,
            onValueChange = {
                displayText = it
            }
        )

        Spacer(modifier = Modifier.height(16.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            AckTapButton(
                text = "CLEAR",
                color = Color.Gray,
                modifier = Modifier.weight(1f)
            ) {
                emoji = ""
                label = ""
                displayText = ""
            }

            AckTapButton(
                text = "SAVE",
                color = primaryColor,
                modifier = Modifier.weight(1f)
            ) {
                onSave(
                    emoji.trim(),
                    label.trim(),
                    displayText.trim()
                )
            }
        }
    }
}

@Composable
private fun EmojiLibrary(
    primaryColor: Color,
    onSelect: (String) -> Unit
) {
    val categories = listOf(
        "RESPONSES" to listOf("✅", "❌", "👍", "👎", "❓", "💬"),
        "BOUNDARIES" to listOf("🛑", "✋", "🚫", "🔇", "↔️", "🚪"),
        "NEEDS" to listOf("⏳", "🥤", "🍽️", "🛏️", "🚻", "💊"),
        "FEELINGS" to listOf("😀", "😐", "😖", "😢", "😡", "😵💫"),
        "REGULATION" to listOf("🧠", "🎧", "🌧️", "🌿", "🫂", "🧊"),
        "PEOPLE / PLACES" to listOf("👤", "👥", "🏠", "🚗", "🏥", "📱")
    )

    categories.forEach { (title, emojiList) ->
        AckText(
            text = title,
            color = primaryColor,
            size = 9.sp,
            weight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(5.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(5.dp)
        ) {
            emojiList.forEach { emoji ->
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .aspectRatio(1f)
                        .border(
                            width = 1.dp,
                            color = primaryColor.copy(alpha = 0.65f),
                            shape = CutCornerShape(3.dp)
                        )
                        .pointerInput(emoji) {
                            detectTapGestures(
                                onTap = {
                                    onSelect(emoji)
                                }
                            )
                        },
                    contentAlignment = Alignment.Center
                ) {
                    AckText(
                        text = emoji,
                        color = Color.White,
                        size = 18.sp,
                        align = TextAlign.Center
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(9.dp))
    }
}

@Composable
private fun EmojiDeckConfigDialog(
    config: EmojiDeckConfig,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (EmojiDeckConfig) -> Unit
) {
    var gridSize by remember {
        mutableStateOf(config.gridSize)
    }

    var timeout by remember {
        mutableStateOf(config.overlayTimeout)
    }

    var pages by remember {
        mutableStateOf(config.pages)
    }

    AckDialogShell(
        title = "EMOJI DECK CONFIG",
        primaryColor = primaryColor,
        onDismiss = onDismiss
    ) {
        AckText(
            text = "GRID SIZE",
            color = primaryColor,
            size = 10.sp,
            weight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(7.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            EmojiGridSize.entries.forEach { option ->
                AckTapButton(
                    text = "${option.columns} X ${option.rows}",
                    color = if (gridSize == option) {
                        primaryColor
                    } else {
                        Color.Gray
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    gridSize = option
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        AckText(
            text = "OVERLAY TIMEOUT",
            color = primaryColor,
            size = 10.sp,
            weight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(7.dp))

        EmojiOverlayTimeout.entries.forEach { option ->
            AckToggleRow(
                label = option.name.replace('_', ' '),
                enabled = timeout == option,
                primaryColor = primaryColor
            ) {
                timeout = option
            }

            Spacer(modifier = Modifier.height(6.dp))
        }

        Spacer(modifier = Modifier.height(10.dp))

        AckText(
            text = "PAGES // ${pages.size}",
            color = primaryColor,
            size = 10.sp,
            weight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(7.dp))

        AckTapButton(
            text = "+ ADD PAGE",
            color = primaryColor,
            modifier = Modifier.fillMaxWidth()
        ) {
            val nextNumber = pages.size + 1

            pages = pages + EmojiPage(
                pageId = "page_${UUID.randomUUID()}",
                name = "PAGE $nextNumber"
            )
        }

        Spacer(modifier = Modifier.height(14.dp))

        AckTapButton(
            text = "SAVE CONFIG",
            color = primaryColor,
            modifier = Modifier.fillMaxWidth()
        ) {
            onSave(
                config.copy(
                    gridSize = gridSize,
                    pages = pages,
                    overlayTimeout = timeout
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
                    shape = CutCornerShape(
                        topStart = 16.dp,
                        bottomEnd = 16.dp
                    )
                )
                .border(
                    width = 1.dp,
                    color = primaryColor,
                    shape = CutCornerShape(
                        topStart = 16.dp,
                        bottomEnd = 16.dp
                    )
                )
                .padding(16.dp)
        ) {
            AckText(
                text = title,
                color = primaryColor,
                size = 15.sp,
                weight = FontWeight.Black,
                letterSpacing = 1.sp
            )

            Spacer(modifier = Modifier.height(16.dp))

            content()
        }
    }
}

@Composable
private fun AckInput(
    label: String,
    value: String,
    primaryColor: Color,
    singleLine: Boolean = true,
    onValueChange: (String) -> Unit
) {
    Column {
        AckText(
            text = label,
            color = Color.Gray,
            size = 9.sp,
            weight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(4.dp))

        BasicTextField(
            value = value,
            onValueChange = onValueChange,
            singleLine = singleLine,
            textStyle = TextStyle(
                color = Color.White,
                fontSize = 14.sp,
                fontFamily = FontFamily.Monospace
            ),
            modifier = Modifier
                .fillMaxWidth()
                .border(
                    width = 1.dp,
                    color = primaryColor.copy(alpha = 0.7f),
                    shape = CutCornerShape(4.dp)
                )
                .background(
                    color = Color.Black.copy(alpha = 0.3f),
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
    val color = if (enabled) primaryColor else Color.Gray

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = color,
                shape = CutCornerShape(4.dp)
            )
            .background(
                color = if (enabled) {
                    primaryColor.copy(alpha = 0.12f)
                } else {
                    Color.Black.copy(alpha = 0.2f)
                },
                shape = CutCornerShape(4.dp)
            )
            .pointerInput(label, enabled) {
                detectTapGestures(
                    onTap = {
                        onToggle()
                    }
                )
            }
            .padding(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        AckText(
            text = if (enabled) "[X]" else "[ ]",
            color = color,
            size = 11.sp,
            weight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.width(9.dp))

        AckText(
            text = label,
            color = color,
            size = 10.sp,
            weight = FontWeight.Bold
        )
    }
}

@Composable
private fun AckTapButton(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .border(
                width = 1.dp,
                color = color,
                shape = CutCornerShape(4.dp)
            )
            .background(
                color = color.copy(alpha = 0.10f),
                shape = CutCornerShape(4.dp)
            )
            .pointerInput(text) {
                detectTapGestures(
                    onTap = {
                        onClick()
                    }
                )
            }
            .padding(vertical = 9.dp, horizontal = 7.dp),
        contentAlignment = Alignment.Center
    ) {
        AckText(
            text = text,
            color = color,
            size = 10.sp,
            weight = FontWeight.Bold,
            align = TextAlign.Center
        )
    }
}

@Composable
private fun AckText(
    text: String,
    color: Color,
    size: androidx.compose.ui.unit.TextUnit,
    weight: FontWeight = FontWeight.Normal,
    letterSpacing: androidx.compose.ui.unit.TextUnit = 0.sp,
    align: TextAlign = TextAlign.Start,
    modifier: Modifier = Modifier
) {
    androidx.compose.material3.Text(
        text = text,
        color = color,
        fontSize = size,
        fontWeight = weight,
        fontFamily = FontFamily.Monospace,
        letterSpacing = letterSpacing,
        textAlign = align,
        modifier = modifier
    )
}
