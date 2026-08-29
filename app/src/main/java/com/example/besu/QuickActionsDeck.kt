package com.example.besu

import android.content.Context
import android.content.Intent
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.VoidBlack

@Composable
fun QuickActionsDeck(
    context: Context,
    deckId: String,
    primaryColor: Color
) {
    var selectedGroupIndex by remember(deckId) {
        mutableIntStateOf(0)
    }

    var config by remember(deckId) {
        mutableStateOf(
            CommandRepository.getQuickActionsConfig(
                context = context,
                deckId = deckId
            )
        )
    }

    var editingSlot by remember {
        mutableStateOf<QuickActionSlot?>(null)
    }

    var editingGroup by remember {
        mutableStateOf<QuickActionGroup?>(null)
    }

    val activeGroup = config.groups.find {
        it.groupIndex == selectedGroupIndex
    } ?: config.groups.first()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Text(
            text = "QUICK ACTIONS",
            color = primaryColor,
            fontSize = 20.sp,
            fontWeight = FontWeight.Black,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 2.sp
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "TAP: EXECUTE  //  HOLD: EDIT",
            color = Color.Gray,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(16.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            config.groups.forEach { group ->
                val isSelected = group.groupIndex == selectedGroupIndex

                Box(
                    modifier = Modifier
                        .weight(1f)
                        .border(
                            width = 1.dp,
                            color = if (isSelected) {
                                primaryColor
                            } else {
                                Color.DarkGray
                            },
                            shape = CutCornerShape(4.dp)
                        )
                        .background(
                            color = if (isSelected) {
                                primaryColor.copy(alpha = 0.18f)
                            } else {
                                VoidBlack.copy(alpha = 0.45f)
                            },
                            shape = CutCornerShape(4.dp)
                        )
                        .clickable {
                            selectedGroupIndex = group.groupIndex
                        }
                        .padding(vertical = 10.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "G${group.groupIndex + 1}",
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        QuickActionsGroupHeader(
            group = activeGroup,
            primaryColor = primaryColor,
            onEdit = {
                editingGroup = activeGroup
            }
        )

        Spacer(modifier = Modifier.height(12.dp))

        activeGroup.slots.forEach { slot ->
            QuickActionButton(
                slot = slot,
                primaryColor = primaryColor,
                onExecute = {
                    val phrase = CommandRepository.resolveQuickAction(
                        context = context,
                        deckId = deckId,
                        groupIndex = activeGroup.groupIndex,
                        slotIndex = slot.slotIndex
                    )

                    if (phrase.isNotBlank()) {
                        context.startService(
                            Intent(context, OutputService::class.java).apply {
                                putExtra("phrase", phrase)
                                putExtra("robotic", false)
                                putExtra("source", "QUICK_ACTION")
                            }
                        )
                    }
                },
                onEdit = {
                    editingSlot = slot
                }
            )

            Spacer(modifier = Modifier.height(10.dp))
        }
    }

    editingSlot?.let { slot ->
        QuickActionEditorDialog(
            slot = slot,
            primaryColor = primaryColor,
            onDismiss = {
                editingSlot = null
            },
            onSave = { label, template, localValues ->
                CommandRepository.updateQuickActionSlot(
                    context = context,
                    deckId = deckId,
                    groupIndex = activeGroup.groupIndex,
                    slotIndex = slot.slotIndex,
                    label = label,
                    template = template,
                    localValues = localValues
                )

                config = CommandRepository.getQuickActionsConfig(
                    context = context,
                    deckId = deckId
                )

                editingSlot = null
            }
        )
    }

    editingGroup?.let { group ->
        QuickActionGroupEditorDialog(
            group = group,
            primaryColor = primaryColor,
            onDismiss = {
                editingGroup = null
            },
            onSave = { label, rootCategory ->
                CommandRepository.updateQuickActionGroup(
                    context = context,
                    deckId = deckId,
                    groupIndex = group.groupIndex,
                    label = label,
                    rootCategory = rootCategory
                )

                config = CommandRepository.getQuickActionsConfig(
                    context = context,
                    deckId = deckId
                )

                editingGroup = null
            }
        )
    }
}

@Composable
private fun QuickActionsGroupHeader(
    group: QuickActionGroup,
    primaryColor: Color,
    onEdit: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = primaryColor,
                shape = CutCornerShape(topStart = 10.dp, bottomEnd = 10.dp)
            )
            .background(
                color = VoidBlack.copy(alpha = 0.40f),
                shape = CutCornerShape(topStart = 10.dp, bottomEnd = 10.dp)
            )
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = group.label,
                color = primaryColor,
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace
            )

            Text(
                text = "ROOT: ${group.rootCategory}",
                color = Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )
        }

        NeonButton(
            text = "EDIT",
            mainColor = primaryColor
        ) {
            onEdit()
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun QuickActionButton(
    slot: QuickActionSlot,
    primaryColor: Color,
    onExecute: () -> Unit,
    onEdit: () -> Unit
) {
    val isConfigured = slot.template.isNotBlank()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = if (isConfigured) primaryColor else Color.DarkGray,
                shape = CutCornerShape(topStart = 12.dp, bottomEnd = 12.dp)
            )
            .background(
                color = if (isConfigured) {
                    primaryColor.copy(alpha = 0.12f)
                } else {
                    VoidBlack.copy(alpha = 0.35f)
                },
                shape = CutCornerShape(topStart = 12.dp, bottomEnd = 12.dp)
            )
            .combinedClickable(
                onClick = onExecute,
                onLongClick = onEdit
            )
            .padding(horizontal = 18.dp, vertical = 20.dp)
    ) {
        Text(
            text = slot.label,
            color = if (isConfigured) primaryColor else Color.Gray,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(5.dp))

        Text(
            text = if (isConfigured) {
                slot.template
            } else {
                "[HOLD TO CONFIGURE]"
            },
            color = Color.Gray,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            maxLines = 2
        )
    }
}

@Composable
private fun QuickActionEditorDialog(
    slot: QuickActionSlot,
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

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Graphite,
        title = {
            Text(
                text = "EDIT QUICK ACTION",
                color = primaryColor,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = label,
                    onValueChange = {
                        label = it
                    },
                    label = {
                        Text("BUTTON LABEL")
                    },
                    singleLine = true
                )

                Spacer(modifier = Modifier.height(12.dp))

                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = template,
                    onValueChange = {
                        template = it
                    },
                    label = {
                        Text("PHRASE TEMPLATE")
                    },
                    minLines = 3
                )

                if (tags.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(
                        text = "LOCAL VARIABLES",
                        color = primaryColor,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )

                    tags.forEachIndexed { index, tag ->
                        Spacer(modifier = Modifier.height(8.dp))

                        OutlinedTextField(
                            modifier = Modifier.fillMaxWidth(),
                            value = localValues.getOrNull(index).orEmpty(),
                            onValueChange = { value ->
                                localValues = localValues.toMutableList().apply {
                                    this[index] = value
                                }
                            },
                            label = {
                                Text(
                                    tag?.let { "VAR:$it" } ?: "VAR ${index + 1}"
                                )
                            },
                            singleLine = true
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(
                        label,
                        template,
                        localValues
                    )
                }
            ) {
                Text("SAVE")
            }
        },
        dismissButton = {
            Button(onClick = onDismiss) {
                Text("CANCEL")
            }
        }
    )
}

@Composable
private fun QuickActionGroupEditorDialog(
    group: QuickActionGroup,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (
        label: String,
        rootCategory: String
    ) -> Unit
) {
    var label by remember(group.groupIndex) {
        mutableStateOf(group.label)
    }

    var rootCategory by remember(group.groupIndex) {
        mutableStateOf(group.rootCategory)
    }

    val categories = listOf("IDENTITY", "DEFEND", "CONNECT")

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Graphite,
        title = {
            Text(
                text = "EDIT GROUP",
                color = primaryColor,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = label,
                    onValueChange = {
                        label = it
                    },
                    label = {
                        Text("GROUP LABEL")
                    },
                    singleLine = true
                )

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "ROOT OVERRIDE SOURCE",
                    color = primaryColor,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    categories.forEach { category ->
                        Button(
                            onClick = {
                                rootCategory = category
                            },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (rootCategory == category) {
                                    primaryColor.copy(alpha = 0.22f)
                                } else {
                                    VoidBlack
                                },
                                contentColor = if (rootCategory == category) {
                                    primaryColor
                                } else {
                                    Color.Gray
                                }
                            )
                        ) {
                            Text(
                                text = category.take(3),
                                fontFamily = FontFamily.Monospace,
                                fontSize = 10.sp
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(label, rootCategory)
                }
            ) {
                Text("SAVE")
            }
        },
        dismissButton = {
            Button(onClick = onDismiss) {
                Text("CANCEL")
            }
        }
    )
}
