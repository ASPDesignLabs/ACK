// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import com.example.besu.data.*
import com.example.besu.decks.*
import com.example.besu.help.*
import com.example.besu.ui.theme.*
import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// Moved here, unchanged, from DesignSystem.kt so the dialogs can be type-checked without the rest of that file (see tools/kotlin_check).

// --- MANAGE CONTEXT ---
//
// IDENTITY, DEFEND, and CONNECT are the three immutable poses -- they can
// never be renamed, reassigned, reordered, or removed here. Everything below
// them is a custom context layer the wearer added: additional expression
// riding on top of one of those same three physical gestures.
@Composable
fun ManageContextDialog(
    context: Context,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onChanged: () -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    var entries by remember(refreshKey) {
        mutableStateOf(CommandRepository.getCustomContextEntries(context))
    }

    var showAddDialog by remember { mutableStateOf(false) }
    var renamingEntry by remember { mutableStateOf<CustomContextEntry?>(null) }
    var reassigningEntry by remember { mutableStateOf<CustomContextEntry?>(null) }
    var deletingEntry by remember { mutableStateOf<CustomContextEntry?>(null) }

    fun refresh() {
        refreshKey++
        onChanged()
    }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "MANAGE CONTEXT",
        dismissLabel = "DONE"
    ) {
                Text(
                    text = "The three base poses are permanent. Custom " +
                            "context layers ride on top of one pose's " +
                            "gestures and can be reordered, reassigned, " +
                            "renamed, or removed.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(12.dp))

                LazyColumn(
                    modifier = Modifier.heightIn(max = 420.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(POSE_CATEGORIES) { pose ->
                        ImmutablePoseRow(pose = pose, primaryColor = primaryColor)
                    }

                    items(entries, key = { it.name }) { entry ->
                        val index = entries.indexOf(entry)

                        CustomContextRow(
                            entry = entry,
                            primaryColor = primaryColor,
                            canMoveUp = index > 0,
                            canMoveDown = index < entries.lastIndex,
                            onMoveUp = {
                                CommandRepository.moveCustomContextEntry(
                                    context, entry.name, -1
                                )
                                refresh()
                            },
                            onMoveDown = {
                                CommandRepository.moveCustomContextEntry(
                                    context, entry.name, 1
                                )
                                refresh()
                            },
                            onRename = { renamingEntry = entry },
                            onReassign = { reassigningEntry = entry },
                            onDelete = { deletingEntry = entry }
                        )
                    }

                    item {
                        Spacer(modifier = Modifier.height(4.dp))

                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 44.dp)
                                .border(1.dp, primaryColor, AckHelpShape)
                                .background(
                                    primaryColor.copy(alpha = 0.12f),
                                    AckHelpShape
                                )
                                .clickable { showAddDialog = true }
                                .padding(vertical = 12.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "+ ADD CONTEXT",
                                color = primaryColor,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                letterSpacing = looseSpacing(1.sp)
                            )
                        }
                    }
                }
    }

    if (showAddDialog) {
        AddContextDialog(
            primaryColor = primaryColor,
            existingNames = entries.map { it.name },
            onDismiss = { showAddDialog = false },
            onCreate = { name, basePose ->
                if (CommandRepository.addCustomContextEntry(context, name, basePose)) {
                    refresh()
                    showAddDialog = false
                }
            }
        )
    }

    val renaming = renamingEntry

    if (renaming != null) {
        RenameContextDialog(
            entry = renaming,
            primaryColor = primaryColor,
            existingNames = entries.map { it.name },
            onDismiss = { renamingEntry = null },
            onConfirm = { newName ->
                if (
                    CommandRepository.renameCustomContextEntry(
                        context, renaming.name, newName
                    )
                ) {
                    refresh()
                    renamingEntry = null
                }
            }
        )
    }

    val reassigning = reassigningEntry

    if (reassigning != null) {
        ReassignPoseDialog(
            entry = reassigning,
            primaryColor = primaryColor,
            onDismiss = { reassigningEntry = null },
            onConfirm = { newPose ->
                CommandRepository.reassignCustomContextPose(
                    context, reassigning.name, newPose
                )
                refresh()
                reassigningEntry = null
            }
        )
    }

    val deleting = deletingEntry

    if (deleting != null) {
        TightDialogSurface(
            onDismiss = { deletingEntry = null },
            primaryColor = RadicalRed,
            title = "CONFIRM DELETE",
            dismissLabel = "ABORT"
        ) {
            Text(
                text = "Permanently remove context layer " +
                        "\"${deleting.name}\"? Every phrase, variable, " +
                        "and shared override saved under it will be " +
                        "deleted across every deck and profile. This " +
                        "cannot be undone -- consider exporting a " +
                        "backup first.",
                color = Color.White,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(16.dp))

            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton(
                    text = "DELETE PERMANENTLY",
                    modifier = Modifier.fillMaxWidth(),
                    mainColor = RadicalRed
                ) {
                    CommandRepository.removeCustomContextEntry(context, deleting.name)
                    refresh()
                    deletingEntry = null
                }

                TightPanelButton(
                    text = "CANCEL",
                    modifier = Modifier.fillMaxWidth(),
                    isActive = false,
                    mainColor = primaryColor
                ) {
                    deletingEntry = null
                }
            }
        }
    }
}

@Composable
private fun ImmutablePoseRow(pose: String, primaryColor: Color) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, Color.DarkGray, AckHelpShape)
            .padding(horizontal = 10.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "ROOT :: $pose",
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )

        Text(
            text = "[IMMUTABLE]",
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun CustomContextRow(
    entry: CustomContextEntry,
    primaryColor: Color,
    canMoveUp: Boolean,
    canMoveDown: Boolean,
    onMoveUp: () -> Unit,
    onMoveDown: () -> Unit,
    onRename: () -> Unit,
    onReassign: () -> Unit,
    onDelete: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor.copy(alpha = 0.5f), AckHelpShape)
            .background(primaryColor.copy(alpha = 0.05f), AckHelpShape)
            .padding(10.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = entry.name,
                    color = primaryColor,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )

                Text(
                    text = "BASED ON: ${entry.basePose}",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )
            }

            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                ContextRowIconButton(
                    text = "▲",
                    enabled = canMoveUp,
                    primaryColor = primaryColor,
                    onClick = onMoveUp
                )

                ContextRowIconButton(
                    text = "▼",
                    enabled = canMoveDown,
                    primaryColor = primaryColor,
                    onClick = onMoveDown
                )
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            ContextRowActionButton(
                text = "REASSIGN",
                primaryColor = primaryColor,
                modifier = Modifier.weight(1f),
                onClick = onReassign
            )

            ContextRowActionButton(
                text = "RENAME",
                primaryColor = primaryColor,
                modifier = Modifier.weight(1f),
                onClick = onRename
            )

            ContextRowActionButton(
                text = "DELETE",
                primaryColor = RadicalRed,
                modifier = Modifier.weight(1f),
                onClick = onDelete
            )
        }
    }
}

@Composable
private fun ContextRowIconButton(
    text: String,
    enabled: Boolean,
    primaryColor: Color,
    onClick: () -> Unit
) {
    val color = if (enabled) primaryColor else Color.DarkGray

    Box(
        modifier = Modifier
            .size(44.dp)
            .border(1.dp, color, AckHelpShape)
            .then(
                if (enabled) Modifier.clickable { onClick() } else Modifier
            ),
        contentAlignment = Alignment.Center
    ) {
        Text(text = text, color = color, fontSize = 12.sp)
    }
}

@Composable
private fun ContextRowActionButton(
    text: String,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    Box(
        modifier = modifier
            .heightIn(min = 44.dp)
            .border(1.dp, primaryColor, AckHelpShape)
            .clickable(onClick = onClick)
            .padding(vertical = 8.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = text,
            color = primaryColor,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun PosePicker(
    selected: String,
    primaryColor: Color,
    onSelect: (String) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        POSE_CATEGORIES.forEach { pose ->
            val isSelected = pose == selected
            val color = if (isSelected) primaryColor else Color.Gray

            Box(
                modifier = Modifier
                    .weight(1f)
                    .heightIn(min = 44.dp)
                    .border(
                        width = if (isSelected) 2.dp else 1.dp,
                        color = color,
                        shape = AckHelpShape
                    )
                    .background(
                        if (isSelected) primaryColor.copy(alpha = 0.14f) else Color.Transparent,
                        AckHelpShape
                    )
                    .clickable { onSelect(pose) }
                    .padding(vertical = 10.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = pose,
                    color = color,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

@Composable
private fun AddContextDialog(
    primaryColor: Color,
    existingNames: List<String>,
    onDismiss: () -> Unit,
    onCreate: (name: String, basePose: String) -> Unit
) {
    var name by remember { mutableStateOf("") }
    var basePose by remember { mutableStateOf(POSE_CATEGORIES[0]) }

    val cleanName = name.trim().uppercase()
    val isValid = cleanName.isNotEmpty() &&
            cleanName !in POSE_CATEGORIES &&
            cleanName !in existingNames

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "ADD CONTEXT"
    ) {
                TightSectionLabel("CONTEXT NAME")

                Spacer(modifier = Modifier.height(6.dp))

                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it.uppercase().take(24) },
                    placeholder = { Text("E.G. SCHOOL, WORK, PLAY") },
                    shape = AckHelpShape,
                    singleLine = true,
                    colors = TextFieldDefaults.colors(
                        focusedTextColor = primaryColor,
                        unfocusedTextColor = primaryColor,
                        focusedContainerColor = VoidBlack,
                        unfocusedContainerColor = VoidBlack,
                        focusedIndicatorColor = primaryColor
                    )
                )

                Spacer(modifier = Modifier.height(16.dp))

                TightSectionLabel("ASSIGN TO POSE")

                Spacer(modifier = Modifier.height(4.dp))

                Text(
                    text = "The physical gesture that activates this " +
                            "layer's phrases when it is focused.",
                    color = Color.DarkGray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(8.dp))

                PosePicker(
                    selected = basePose,
                    primaryColor = primaryColor,
                    onSelect = { basePose = it }
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "CREATE",
                        modifier = Modifier.weight(1f),
                        isActive = isValid,
                        mainColor = primaryColor
                    ) {
                        if (isValid) {
                            onCreate(cleanName, basePose)
                        }
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        onDismiss()
                    }
                }
    }
}

@Composable
private fun RenameContextDialog(
    entry: CustomContextEntry,
    primaryColor: Color,
    existingNames: List<String>,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var name by remember(entry.name) { mutableStateOf(entry.name) }

    val cleanName = name.trim().uppercase()
    val isValid = cleanName.isNotEmpty() &&
            (cleanName == entry.name ||
                    (cleanName !in POSE_CATEGORIES && cleanName !in existingNames))

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "RENAME CONTEXT"
    ) {
                Text(
                    text = "Every saved phrase, variable, and override " +
                            "moves with the new name.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it.uppercase().take(24) },
                    shape = AckHelpShape,
                    singleLine = true,
                    colors = TextFieldDefaults.colors(
                        focusedTextColor = primaryColor,
                        unfocusedTextColor = primaryColor,
                        focusedContainerColor = VoidBlack,
                        unfocusedContainerColor = VoidBlack,
                        focusedIndicatorColor = primaryColor
                    )
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "CONFIRM RENAME",
                        modifier = Modifier.weight(1f),
                        isActive = isValid,
                        mainColor = primaryColor
                    ) {
                        if (isValid) {
                            onConfirm(cleanName)
                        }
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        onDismiss()
                    }
                }
    }
}

@Composable
private fun ReassignPoseDialog(
    entry: CustomContextEntry,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onConfirm: (String) -> Unit
) {
    var basePose by remember(entry.name) { mutableStateOf(entry.basePose) }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "REASSIGN POSE // ${entry.name}"
    ) {
                Text(
                    text = "Choose which pose's physical gesture activates " +
                            "this context layer when it is focused.",
                    color = Color.Gray,
                    fontSize = 9.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(10.dp))

                PosePicker(
                    selected = basePose,
                    primaryColor = primaryColor,
                    onSelect = { basePose = it }
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "CONFIRM",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        onConfirm(basePose)
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        onDismiss()
                    }
                }
    }
}
