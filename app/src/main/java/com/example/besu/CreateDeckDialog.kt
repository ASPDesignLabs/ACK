package com.example.besu

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.content.MediaType.Companion.Text
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.Text
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
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack

@Composable
fun CreateDeckDialog(
    primaryColor: Color,
    onDismiss: () -> Unit,
    onCreate: (
        name: String,
        colorIndex: Int,
        type: DeckType
    ) -> Unit
) {
    var deckType by remember {
        mutableStateOf(DeckType.QUICK_ACTIONS)
    }

    var deckName by remember {
        mutableStateOf("QUICK ACTIONS")
    }

    var colorIndex by remember {
        mutableIntStateOf(0)
    }

    val helpManager = LocalHelpManager.current

    val description = when (deckType) {
        DeckType.MATRIX -> {
            "The permanent system Matrix deck."
        }

        DeckType.QUICK_ACTIONS -> {
            "Three action groups with four configurable slots per group."
        }

        DeckType.EMERGENCY -> {
            "Four immediate prompt slots with optional emergency overrides."
        }

        DeckType.EMOJI -> {
            "Visual-only emoji pages with configurable grids and optional text."
        }

        DeckType.GIF -> {
            "Local GIF library with categories, previews, and fullscreen playback."
        }
    }

    Dialog(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    color = Graphite,
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
                .padding(18.dp)
        ) {
            Text(
                text = "CREATE DECK",
                color = primaryColor,
                fontSize = 16.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black,
                letterSpacing = 1.sp
            )

            Spacer(modifier = Modifier.height(18.dp))

            CreateDeckSectionLabel(
                text = "DECK TYPE",
                color = primaryColor
            )

            Spacer(modifier = Modifier.height(8.dp))

            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    DeckTypeOption(
                        text = "QUICK ACTIONS",
                        selected = deckType == DeckType.QUICK_ACTIONS,
                        primaryColor = primaryColor,
                        modifier = Modifier.weight(1f)
                    ) {
                        deckType = DeckType.QUICK_ACTIONS

                        if (deckName.isDefaultDeckName()) {
                            deckName = "QUICK ACTIONS"
                        }
                    }

                    DeckTypeOption(
                        text = "EMERGENCY",
                        selected = deckType == DeckType.EMERGENCY,
                        primaryColor = primaryColor,
                        modifier = Modifier.weight(1f)
                    ) {
                        deckType = DeckType.EMERGENCY

                        if (deckName.isDefaultDeckName()) {
                            deckName = "EMERGENCY"
                        }
                    }
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    DeckTypeOption(
                        text = "EMOJI",
                        selected = deckType == DeckType.EMOJI,
                        primaryColor = primaryColor,
                        modifier = Modifier.weight(1f)
                    ) {
                        deckType = DeckType.EMOJI

                        if (deckName.isDefaultDeckName()) {
                            deckName = "EMOJI"
                        }
                    }

                    DeckTypeOption(
                        text = "GIF",
                        selected = deckType == DeckType.GIF,
                        primaryColor = primaryColor,
                        modifier = Modifier.weight(1f)
                    ) {
                        deckType = DeckType.GIF

                        if (deckName.isDefaultDeckName()) {
                            deckName = "GIF"
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = description,
                color = Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(18.dp))

            CreateDeckSectionLabel(
                text = "DECK NAME",
                color = primaryColor
            )

            Spacer(modifier = Modifier.height(6.dp))

            AckDeckNameField(
                value = deckName,
                primaryColor = primaryColor,
                onValueChange = {
                    deckName = it.uppercase()
                }
            )

            Spacer(modifier = Modifier.height(18.dp))

            CreateDeckSectionLabel(
                text = "DECK COLOR",
                color = primaryColor
            )

            Spacer(modifier = Modifier.height(8.dp))

            DeckColorPicker(
                selectedIndex = colorIndex,
                onSelected = {
                    colorIndex = it
                }
            )

            Spacer(modifier = Modifier.height(20.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                CreateDeckButton(
                    text = "CANCEL",
                    color = Color.Gray,
                    modifier = Modifier.weight(1f)
                ) {
                    onDismiss()
                }

                CreateDeckButton(
                    text = "CREATE",
                    color = primaryColor,
                    modifier = Modifier
                        .weight(1f)
                        .testTag(AckTags.DECK_CREATE_COMMIT)
                        .helpTarget(AckTags.DECK_CREATE_COMMIT, primaryColor)
                ) {
                    onCreate(
                        deckName.trim().ifBlank {
                            when (deckType) {
                                DeckType.MATRIX -> "DEFAULT"
                                DeckType.QUICK_ACTIONS -> "QUICK ACTIONS"
                                DeckType.EMERGENCY -> "EMERGENCY"
                                DeckType.EMOJI -> "EMOJI"
                                DeckType.GIF -> "GIF"
                            }
                        },
                        colorIndex,
                        deckType
                    )

                    helpManager?.onEvent(
                        HelpEvent.TextCommitted(AckTags.DECK_CREATE_COMMIT)
                    )
                }
            }
        }
    }
}

@Composable
private fun CreateDeckSectionLabel(
    text: String,
    color: Color
) {
    Text(
        text = text,
        color = color,
        fontSize = 10.sp,
        fontFamily = FontFamily.Monospace,
        fontWeight = FontWeight.Bold
    )
}

@Composable
private fun DeckTypeOption(
    text: String,
    selected: Boolean,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    val color = if (selected) primaryColor else Color.Gray
    val shape = CutCornerShape(5.dp)
    val helpManager = LocalHelpManager.current

    Box(
        modifier = modifier
            .testTag(AckTags.DECK_CREATE_TYPE)
            .helpTarget(AckTags.DECK_CREATE_TYPE, primaryColor)
            .border(
                width = 1.dp,
                color = color,
                shape = shape
            )
            .background(
                color = if (selected) {
                    primaryColor.copy(alpha = 0.14f)
                } else {
                    VoidBlack.copy(alpha = 0.45f)
                },
                shape = shape
            )
            .clickable {
                onClick()
                helpManager?.onEvent(
                    HelpEvent.Interacted(AckTags.DECK_CREATE_TYPE)
                )
            }
            .padding(vertical = 12.dp, horizontal = 6.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = color,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun AckDeckNameField(
    value: String,
    primaryColor: Color,
    onValueChange: (String) -> Unit
) {
    val shape = CutCornerShape(4.dp)

    BasicTextField(
        value = value,
        onValueChange = onValueChange,
        singleLine = true,
        textStyle = TextStyle(
            color = primaryColor,
            fontSize = 14.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        ),
        modifier = Modifier
            .fillMaxWidth()
            .background(
                color = VoidBlack,
                shape = shape
            )
            .border(
                width = 1.dp,
                color = primaryColor.copy(alpha = 0.75f),
                shape = shape
            )
            .padding(12.dp)
    )
}

@Composable
private fun CreateDeckButton(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    val shape = CutCornerShape(5.dp)

    Box(
        modifier = modifier
            .border(
                width = 1.dp,
                color = color,
                shape = shape
            )
            .background(
                color = color.copy(alpha = 0.12f),
                shape = shape
            )
            .clickable(onClick = onClick)
            .padding(vertical = 12.dp, horizontal = 8.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = color,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )
    }
}

private fun String.isDefaultDeckName(): Boolean {
    return isBlank() ||
            this == "MATRIX" ||
            this == "QUICK ACTIONS" ||
            this == "EMERGENCY" ||
            this == "EMOJI" ||
            this == "GIF"
}

@Composable
private fun DeckColorPicker(
    selectedIndex: Int,
    onSelected: (Int) -> Unit
) {
    val indices = NeonPalette.SWATCHES.indices.toList()

    Column(
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        indices.chunked(5).forEach { rowIndices ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                rowIndices.forEach { index ->
                    val color = NeonPalette.getColor(index)
                    val isSelected = index == selectedIndex
                    val shape = CutCornerShape(6.dp)

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(40.dp)
                            .border(
                                width = if (isSelected) 2.dp else 1.dp,
                                color = if (isSelected) {
                                    Color.White
                                } else {
                                    color
                                },
                                shape = shape
                            )
                            .background(
                                color = color.copy(
                                    alpha = if (isSelected) 0.50f else 0.15f
                                ),
                                shape = shape
                            )
                            .clickable {
                                onSelected(index)
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = if (isSelected) "●" else "$index",
                            color = color,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                repeat(5 - rowIndices.size) {
                    Spacer(
                        modifier = Modifier
                            .weight(1f)
                            .width(1.dp)
                    )
                }
            }
        }
    }
}
