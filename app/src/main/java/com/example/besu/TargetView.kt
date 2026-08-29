package com.example.besu

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack

@Composable
fun TargetView(context: Context, primaryColor: Color) {
    var subMode by remember { mutableStateOf("SLOTS") } // SLOTS, TRAINING, VISUALS

    val helpManager = LocalHelpManager.current

    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(
            HelpEvent.Interacted(tag)
        )
    }

    fun reportTextCommit(tag: String) {
        helpManager?.onEvent(
            HelpEvent.TextCommitted(tag)
        )
    }

    // Data States
    var refreshKey by remember { mutableIntStateOf(0) }
    val targets = remember(refreshKey) { TargetRepository.getTargets(context) }
    val rules = remember(refreshKey) { TargetRepository.getSyntaxRules(context) }
    val matrix = remember { CommandRepository.getMatrix(context) }

    // Edit Dialog State
    var editingSlotIndex by remember { mutableStateOf<Int?>(null) }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        
        // --- HEADER ---
        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Text("TARGET COMPUTER", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("SLOTS", color = if(subMode=="SLOTS") primaryColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { subMode = "SLOTS" })
                Text("|", color = Color.DarkGray)
                Text("VISUALS", color = if(subMode=="VISUALS") primaryColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { subMode = "VISUALS" })
            }
        }
        Spacer(modifier = Modifier.height(16.dp))

        // --- SUB-MODE: SLOTS ---
        if (subMode == "SLOTS") {
            LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.weight(1f)
            ) {
                // Render 8 Slots (0 to 7)
                items(8) { index ->
                    val data = targets.find { it.index == index }
                    TargetSlotCard(
                        index = index,
                        data = data,
                        primaryColor = primaryColor,
                        modifier = Modifier
                            .testTag(AckTags.TARGET_SLOT)
                            .helpTarget(AckTags.TARGET_SLOT, primaryColor)
                    ) {
                        editingSlotIndex = index
                        reportHelpInteraction(AckTags.TARGET_SLOT)
                    }
                }
            }
        }

        // --- SUB-MODE: TRAINING ---
        if (subMode == "TRAINING") {
            Text("SYNTAX OVERRIDES", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
            Spacer(modifier = Modifier.height(8.dp))
            
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(matrix) { (node, phrase) ->
                    val currentRule = rules[node.path] ?: "AUTO"
                    
                    TrainingRow(node.label, phrase, currentRule, primaryColor) { nextRule ->
                        TargetRepository.setSyntaxRule(context, node.path, nextRule)
                        refreshKey++
                    }
                }
            }
        }

        // --- SUB-MODE: VISUALS ---
                if (subMode == "VISUALS") {
                        VisualEditorView(context, primaryColor)
                    }
    }

    // --- DIALOG: EDIT SLOT ---
    if (editingSlotIndex != null) {
        val idx = editingSlotIndex!!
        val existing = targets.find { it.index == idx }
        var tempName by remember { mutableStateOf(existing?.label ?: "") }
        var tempStrategy by remember { mutableStateOf(existing?.defaultStrategy ?: "POST") }

        AlertDialog(
            onDismissRequest = { editingSlotIndex = null },
            containerColor = Graphite,
            title = { Text("CONFIG SLOT $idx", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace) },
            text = {
                Column {
                    OutlinedTextField(
                        value = tempName, 
                        onValueChange = { tempName = it },
                        placeholder = { Text("TARGET NAME (e.g. SARAH)") },
                        colors = TextFieldDefaults.colors(focusedTextColor = primaryColor, unfocusedTextColor = primaryColor, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = primaryColor),
                        singleLine = true
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("DEFAULT PLACEMENT:", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        // Strategy Toggles
                        NeonButton(
                            "PREPEND",
                            Modifier
                                .weight(1f)
                                .helpTarget(AckTags.TARGET_STRATEGY, primaryColor),
                            isActive = tempStrategy == "PRE",
                            mainColor = primaryColor
                        ) {
                            tempStrategy = "PRE"
                            reportHelpInteraction(AckTags.TARGET_STRATEGY)
                        }

                        NeonButton(
                            "APPEND",
                            Modifier
                                .weight(1f)
                                .helpTarget(AckTags.TARGET_STRATEGY, primaryColor),
                            isActive = tempStrategy == "POST",
                            mainColor = primaryColor
                        ) {
                            tempStrategy = "POST"
                            reportHelpInteraction(AckTags.TARGET_STRATEGY)
                        }
                    }
                    if (tempStrategy == "PRE") Text("Ex: \"Sarah, Accepted.\"", color = Color.Gray, fontSize = 10.sp, modifier = Modifier.padding(top=4.dp))
                    else Text("Ex: \"Accepted, Sarah.\"", color = Color.Gray, fontSize = 10.sp, modifier = Modifier.padding(top=4.dp))
                }
            },
            confirmButton = {
                Row {
                   if (existing != null) {
                       Text("[CLEAR]", color = Color.Red, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable {
                           TargetRepository.clearTarget(context, idx)
                           refreshKey++
                           editingSlotIndex = null
                           WatchSync.sendTargetList(context)
                       }.padding(horizontal = 16.dp, vertical = 8.dp))
                   }
                    NeonButton(
                        "SAVE",
                        Modifier
                            .testTag(AckTags.TARGET_SLOT_SAVE)
                            .helpTarget(AckTags.TARGET_SLOT_SAVE, primaryColor),
                        mainColor = primaryColor
                    ) {
                        if (tempName.isNotEmpty()) {
                            TargetRepository.saveTarget(
                                context,
                                TargetSlot(
                                    index = idx,
                                    label = tempName,
                                    defaultStrategy = tempStrategy
                                )
                            )

                            refreshKey++
                            editingSlotIndex = null
                            WatchSync.sendTargetList(context)

                            reportTextCommit(AckTags.TARGET_SLOT_SAVE)
                        }
                    }
                }
            }
        )
    }
}

@Composable
fun TargetSlotCard(
    index: Int,
    data: TargetSlot?,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    val isSet = data != null
    val borderColor = if (isSet) primaryColor else Color.DarkGray
    val bg = if (isSet) primaryColor.copy(alpha = 0.1f) else Color.Transparent

    Box(
        modifier = modifier
            .height(80.dp)
            .background(bg, CutCornerShape(8.dp))
            .border(1.dp, borderColor, CutCornerShape(8.dp))
            .clickable(onClick = onClick)
            .padding(12.dp)
    ) {
        Text(
            text = "SLOT $index",
            color = Color.Gray,
            fontSize = 8.sp,
            fontFamily = FontFamily.Monospace,
            modifier = Modifier.align(Alignment.TopStart)
        )

        if (isSet) {
            Column(modifier = Modifier.align(Alignment.Center)) {
                Text(
                    text = data!!.label.uppercase(),
                    color = primaryColor,
                    fontSize = 14.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )

                Text(
                    text = if (data.defaultStrategy == "PRE") {
                        "[PRE] < MSG"
                    } else {
                        "MSG > [APP]"
                    },
                    color = primaryColor.copy(alpha = 0.6f),
                    fontSize = 8.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        } else {
            Text(
                text = "EMPTY",
                color = Color.DarkGray,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                modifier = Modifier.align(Alignment.Center)
            )
        }
    }
}

@Composable
fun TrainingRow(label: String, phrase: String, rule: String, primaryColor: Color, onToggle: (String) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).background(Graphite).padding(8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(label, color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
            Text(if(phrase.length>25) phrase.take(22)+"..." else phrase, color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        }
        
        // Tri-State Toggle
        val (txt, col) = when(rule) {
            "PRE" -> "PRE" to NeonPalette.SWATCHES[3] // Orange
            "POST" -> "APP" to NeonPalette.SWATCHES[2] // Green
            else -> "AUTO" to Color.Gray
        }
        
        Box(
            modifier = Modifier
                .width(50.dp)
                .border(1.dp, col, CutCornerShape(4.dp))
                .clickable {
                    // Cycle: AUTO -> PRE -> POST -> AUTO
                    val next = when(rule) {
                        "AUTO" -> "PRE"
                        "PRE" -> "POST"
                        else -> "AUTO"
                    }
                    onToggle(next)
                }
                .padding(vertical = 6.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(txt, color = col, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
        }
    }
}
