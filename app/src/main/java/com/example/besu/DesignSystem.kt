package com.example.besu

import android.content.Context
import android.content.Intent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalDensity


data class VariableEditRequest(
    val nodePath: String,
    val nodeLabel: String,
    val index: Int,
    val currentValue: String
)

data class MatrixVariableDisplay(
    val index: Int,
    val tag: String?,
    val localValue: String,
    val displayValue: String,
    val isOverridden: Boolean
)
// --- NEON FLUX PALETTE (DEFINITIONS) ---
val FluxCyan = Color(0xFF00F3FF)
val RadicalRed = Color(0xFFFF0055)
val BioGreen = Color(0xFF00FF41)
val DataOrange = Color(0xFFFF9900)

// ==========================================
//        ATOMIC COMPONENTS (BUTTONS)
// ==========================================

@Composable
fun NeonButton(
    text: String,
    modifier: Modifier = Modifier,
    isActive: Boolean = true,
    mainColor: Color = NeonPalette.DEFAULT_CYAN,
    onClick: () -> Unit
) {
    val haptic = LocalHapticFeedback.current
    val containerColor = Graphite
    
    // VISUALS: Dim if inactive, Bright if active
    val contentColor = if(isActive) mainColor else mainColor.copy(alpha=0.4f)
    val borderColor = if(isActive) mainColor else mainColor.copy(alpha=0.2f)

    Button(
        onClick = { 
            // Always provide haptic feedback, logic check is up to caller
            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
            onClick() 
        },
        modifier = modifier.height(40.dp),
        shape = CutCornerShape(8.dp),
        colors = ButtonDefaults.buttonColors(containerColor = containerColor, contentColor = contentColor),
        border = BorderStroke(1.dp, borderColor),
        contentPadding = PaddingValues(horizontal = 16.dp),
        // FIX: Button is always enabled so we can click it to switch tabs
        enabled = true 
    ) {
        Text(text.uppercase(), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp, fontSize = 12.sp)
    }
}



@Composable
fun PulsingStatusBox(color: Color) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val alpha by infiniteTransition.animateFloat(initialValue = 1f, targetValue = 0.2f, animationSpec = infiniteRepeatable(tween(800), RepeatMode.Reverse), label = "alpha")
    Box(modifier = Modifier.size(16.dp).border(1.dp, color, CutCornerShape(4.dp)).padding(3.dp).alpha(alpha).background(color, CutCornerShape(2.dp)))
}

@Composable
fun RowScope.ThemeOption(
    id: Int, 
    label: String, 
    current: Int, 
    activeColor: Color = FluxCyan, 
    onClick: () -> Unit
) {
    val active = id == current
    val haptic = LocalHapticFeedback.current
    Box(
        modifier = Modifier.weight(1f).height(40.dp)
            .background(if(active) activeColor.copy(alpha=0.1f) else Color.Transparent)
            .border(1.dp, if(active) activeColor else Color.DarkGray, CutCornerShape(8.dp))
            .clickable { haptic.performHapticFeedback(HapticFeedbackType.TextHandleMove); onClick() },
        contentAlignment = Alignment.Center
    ) {
        Text(label, color = if(active) activeColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
    }
}

// ==========================================
//            COMPLEX SCREENS
// ==========================================

// --- TERMINAL VIEW ---
@Composable
fun TerminalView(logs: List<LogEntry>, context: Context) {
    LazyColumn(modifier = Modifier.fillMaxSize().padding(12.dp)) {
        items(logs) { log ->
            val typeColor = when(log.type) {
                "ERR" -> RadicalRed
                "WARN" -> DataOrange
                "EMERGENCY" -> RadicalRed
                "SYS" -> BioGreen
                "OUT" -> FluxCyan
                else -> Color.White
            }
            // Only an actual communicated phrase carries replayText (see
            // OutputService.processSpeech) -- status/system log lines never
            // do, so they render plain with no tap affordance.
            val replayText = log.replayText
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 2.dp)
                    .then(
                        if (replayText != null) {
                            Modifier
                                .background(FluxCyan.copy(alpha = 0.08f))
                                .clickable {
                                    val intent = Intent(context, OutputService::class.java)
                                    intent.putExtra("phrase", replayText)
                                    intent.putExtra("robotic", false)
                                    intent.putExtra("source", "LOG/REPLAY")
                                    // An emergency message's own boost/tone
                                    // settings aren't in the log, but its
                                    // core safety properties -- audible and
                                    // not auto-clearing -- shouldn't be lost
                                    // just because it's being replayed.
                                    if (log.type == "EMERGENCY") {
                                        intent.putExtra("emergency_mode", true)
                                        intent.putExtra("emergency_force_speaker", true)
                                        intent.putExtra("emergency_prevent_timed_clear", true)
                                    }
                                    context.startService(intent)
                                }
                        } else {
                            Modifier
                        }
                    )
            ) {
                Text(
                    if (replayText != null) "▶" else " ",
                    color = FluxCyan,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 12.sp,
                    modifier = Modifier.width(14.dp)
                )
                Text("[${log.time}]", color = Color.DarkGray, fontFamily = FontFamily.Monospace, fontSize = 12.sp, modifier = Modifier.width(70.dp))
                Text(log.type, color = typeColor, fontFamily = FontFamily.Monospace, fontSize = 12.sp, fontWeight = FontWeight.Bold, modifier = Modifier.width(40.dp))
                Text(" :: ${log.msg}", color = Color.White, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
            }
        }
    }
}

// --- TYPE VIEW ---
@Composable
fun TypeView(context: Context, recentPhrases: androidx.compose.runtime.snapshots.SnapshotStateList<String>) {
    val primaryColor = NeonPalette.getColor(CommandRepository.getActiveColorIndex(context))
    
    var textInput by remember { mutableStateOf("") }
    var refreshKey by remember { mutableIntStateOf(0) }
    var savedPhrases by remember(refreshKey) { mutableStateOf(CommandRepository.getQuickPhrases(context)) }
    var showSaveDialog by remember { mutableStateOf(false) }
    var newTagInput by remember { mutableStateOf("") }

    fun speak(text: String, sourceTag: String) {
        if (text.isNotBlank()) {
            val intent = Intent(context, OutputService::class.java)
            intent.putExtra("phrase", text)
            intent.putExtra("robotic", false)
            intent.putExtra("source", sourceTag)
            context.startService(intent)

            if (recentPhrases.contains(text)) recentPhrases.remove(text)
            recentPhrases.add(0, text)
            if (recentPhrases.size > 10) recentPhrases.removeLast()
            textInput = ""
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        Text("MANUAL OVERRIDE", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
        Spacer(modifier = Modifier.height(12.dp))

        OutlinedTextField(
            value = textInput,
            onValueChange = { textInput = it },
            modifier = Modifier.fillMaxWidth(),
            shape = AckHelpShape,
            colors = TextFieldDefaults.colors(
                focusedTextColor = primaryColor,
                unfocusedTextColor = primaryColor,
                focusedContainerColor = VoidBlack,
                unfocusedContainerColor = VoidBlack,
                focusedIndicatorColor = primaryColor,
                unfocusedIndicatorColor = Color.DarkGray,
                cursorColor = primaryColor
            ),
            textStyle = androidx.compose.ui.text.TextStyle(fontFamily = FontFamily.Monospace, fontSize = 16.sp),
            placeholder = { Text("ENTER SEQUENCE...", color = Color.Gray, fontFamily = FontFamily.Monospace) },
            maxLines = 3
        )

        Spacer(modifier = Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            // Encode button relies on isActive for dimming, but logic check inside lambda protects it
            NeonButton("ENCODE", Modifier.weight(0.4f), isActive = textInput.isNotBlank(), mainColor = primaryColor) {
                if(textInput.isNotBlank()) showSaveDialog = true
            }
            HeroButton("TRANSMIT", Modifier.weight(0.6f), mainColor = primaryColor) {
                speak(textInput, "TERM/INPUT")
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        if (savedPhrases.isNotEmpty()) {
            Text("MEMORY BANKS [SAVED]", color = primaryColor, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
            Spacer(modifier = Modifier.height(8.dp))
            Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
                QuickAccessAccordion(
                    phrases = savedPhrases,
                    primaryColor = primaryColor,
                    onPlay = { p -> speak(p.text, "BANK/${p.tag}") },
                    onDelete = { p -> CommandRepository.deleteQuickPhrase(context, p); refreshKey++ }
                )
            }
        } else if (recentPhrases.isNotEmpty()) {
            Text("CACHE [RECENT]", color = primaryColor.copy(alpha=0.7f), fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
            Spacer(modifier = Modifier.height(8.dp))
            LazyColumn(modifier = Modifier.weight(1f)) {
                items(recentPhrases) { phrase ->
                    RecentHistoryItem(phrase) { speak(phrase, "CACHE/REPLAY") }
                }
            }
        }
    }

    if (showSaveDialog) {
        val existingTags = savedPhrases.map { it.tag }.distinct().sorted()
        TightDialogSurface(
            onDismiss = { showSaveDialog = false },
            primaryColor = primaryColor,
            title = "ENCODE TO BANK"
        ) {
                TightSectionLabel("ASSIGN A TAG")
                Spacer(modifier = Modifier.height(12.dp))
                if (existingTags.isNotEmpty()) {
                    Row(modifier = Modifier.horizontalScroll(rememberScrollState())) {
                        existingTags.forEach { tag ->
                            Box(modifier = Modifier.padding(end = 8.dp).heightIn(min = 44.dp).border(1.dp, if(newTagInput == tag) primaryColor else Color.Gray, AckHelpShape).clickable { newTagInput = tag }.padding(horizontal = 8.dp, vertical = 4.dp), contentAlignment = Alignment.Center) {
                                Text(tag, color = if(newTagInput == tag) primaryColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(12.dp))
                }
                OutlinedTextField(
                    value = newTagInput, onValueChange = { newTagInput = it.uppercase() },
                    placeholder = { Text("NEW TAG") },
                    shape = AckHelpShape,
                    colors = TextFieldDefaults.colors(focusedTextColor = primaryColor, unfocusedTextColor = primaryColor, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = primaryColor)
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton("SAVE", modifier = Modifier.weight(1f), mainColor = primaryColor) {
                        if (newTagInput.isNotEmpty()) {
                            CommandRepository.saveQuickPhrase(context, textInput, newTagInput)
                            refreshKey++
                            showSaveDialog = false
                            newTagInput = ""
                        }
                    }
                    TightPanelButton("CANCEL", modifier = Modifier.weight(1f), isActive = false, mainColor = primaryColor) { showSaveDialog = false }
                }
        }
    }
}

// --- HELPER COMPONENTS FOR TYPE VIEW ---

@Composable
fun QuickAccessAccordion(
    phrases: List<QuickPhrase>,
    primaryColor: Color,
    onPlay: (QuickPhrase) -> Unit,
    onDelete: (QuickPhrase) -> Unit
) {
    val grouped = remember(phrases) { phrases.groupBy { it.tag } }
    val expandedStates = remember { mutableStateMapOf<String, Boolean>().apply { if(grouped.isNotEmpty()) this[grouped.keys.first()] = true } }
    var deletingPhrase by remember { mutableStateOf<QuickPhrase?>(null) }

    LazyColumn {
        grouped.forEach { (tag, items) ->
            item {
                val isExpanded = expandedStates[tag] == true
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).background(if(isExpanded) primaryColor.copy(alpha=0.1f) else Graphite).border(1.dp, if(isExpanded) primaryColor else Color.Gray, CutCornerShape(4.dp)).clickable { expandedStates[tag] = !isExpanded }.padding(8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("[$tag]", color = if(isExpanded) primaryColor else Color.Gray, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, letterSpacing = 1.sp)
                    Text(if(isExpanded) "▼" else "▶", color = if(isExpanded) primaryColor else Color.Gray, fontSize = 10.sp)
                }
            }
            if (expandedStates[tag] == true) {
                items(items) { phrase ->
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(start = 12.dp, bottom = 4.dp).background(VoidBlack).border(BorderStroke(1.dp, primaryColor.copy(alpha=0.3f))).clickable { onPlay(phrase) }.padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(text = phrase.text, color = Color.White, fontFamily = FontFamily.Monospace, fontSize = 12.sp, modifier = Modifier.weight(1f))
                        Spacer(modifier = Modifier.width(8.dp))
                        Box(
                            modifier = Modifier.size(44.dp).clickable { deletingPhrase = phrase },
                            contentAlignment = Alignment.Center
                        ) {
                            Text("X", color = Color.Red, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                        }
                    }
                }
                item { Spacer(modifier = Modifier.height(8.dp)) }
            }
        }
    }

    val deleting = deletingPhrase

    if (deleting != null) {
        TightDialogSurface(
            onDismiss = { deletingPhrase = null },
            primaryColor = RadicalRed,
            title = "CONFIRM DELETE",
            dismissLabel = "ABORT"
        ) {
            Text(
                text = "Permanently remove the saved phrase " +
                        "\"${deleting.text}\"? This cannot be undone -- " +
                        "consider exporting a backup first.",
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
                    onDelete(deleting)
                    deletingPhrase = null
                }

                TightPanelButton(
                    text = "CANCEL",
                    modifier = Modifier.fillMaxWidth(),
                    isActive = false,
                    mainColor = primaryColor
                ) {
                    deletingPhrase = null
                }
            }
        }
    }
}

@Composable
fun RecentHistoryItem(phrase: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).background(Graphite, CutCornerShape(4.dp)).border(1.dp, Color.Gray.copy(alpha=0.3f), CutCornerShape(4.dp)).clickable { onClick() }.padding(12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(text = if (phrase.length > 25) phrase.take(22) + "..." else phrase, color = Color.Gray, fontFamily = FontFamily.Monospace, fontSize = 12.sp)
        Text("REPLAY", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
    }
}

// --- MATRIX EDITOR ---
@Composable
fun MatrixEditor(context: Context, deckName: String, onDialogStateChange: (Boolean) -> Unit) {
    val primaryColor = NeonPalette.getColor(CommandRepository.getActiveColorIndex(context))

    var refreshKey by remember { mutableIntStateOf(0) }
    var matrixData by remember(deckName, refreshKey) { mutableStateOf(CommandRepository.getMatrix(context)) }
    var showDialog by remember { mutableStateOf(false) }
    var showManageContextDialog by remember { mutableStateOf(false) }
    var selectedNode by remember { mutableStateOf<Triple<MatrixNode, String, String>?>(null) }
    var variableEditRequest by remember {
        mutableStateOf<VariableEditRequest?>(null)
    }

    val grouped = matrixData.groupBy { it.first.category }

    LaunchedEffect(showDialog) { onDialogStateChange(showDialog) }

    Column {
        LazyColumn(modifier = Modifier.weight(1f).padding(16.dp)) {
            item {
                Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                    Text("SEQUENCE :: $deckName", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, letterSpacing = 2.sp)
                    Text(
                        "[MANAGE CONTEXT]",
                        color = primaryColor,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier
                            .testTag(AckTags.MATRIX_CONTEXT_ADD)
                            .helpTarget(AckTags.MATRIX_CONTEXT_ADD, primaryColor)
                            .clickable { showManageContextDialog = true }
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))
            }
            grouped.forEach { (category, nodes) ->
                item {
                    if (deckName == "BUILDER") { BuilderGuideCard(category, primaryColor); Spacer(modifier = Modifier.height(12.dp)) }
                    MatrixCategory(
                        title = category,
                        nodes = nodes,
                        context = context,
                        primaryColor = primaryColor,
                        onEdit = { nodeTriple ->
                            selectedNode = nodeTriple
                            showDialog = true
                        },
                        onEditVariable = { request ->
                            variableEditRequest = request
                        },
                        onRootOverrideChanged = {
                            refreshKey++
                        }
                    )
                    Spacer(modifier = Modifier.height(24.dp))
                }
            }
        }
    }

    if (showDialog && selectedNode != null) {
        val (node, rawPhrase, _) = selectedNode!!

        var tempText by remember(node.path) {
            mutableStateOf(rawPhrase)
        }

        val tempVars = remember(node.path) {
            mutableStateListOf<String>().apply {
                val initialCount = TemplateEngine.countVariables(rawPhrase)
                val savedValues = CommandRepository.getVariableValues(
                    context,
                    node.path
                )

                repeat(initialCount) { index ->
                    add(savedValues.getOrElse(index) { "" })
                }
            }
        }

        var clearMode by remember(node.path) {
            mutableStateOf<String?>(null)
        }

        fun closeEditor() {
            // Reload matrix rows from persistent storage so subsequent edits start
            // from the saved prompt rather than the old cached rawPhrase.
            refreshKey++
            showDialog = false
        }



        val variableCount = TemplateEngine.countVariables(tempText)

        fun saveVariables() {
            CommandRepository.setVariableValues(
                context = context,
                storagePath = node.path,
                values = tempVars.toList()
            )
        }

        fun normalizeVariableSlots(newCount: Int) {
            while (tempVars.size > newCount) {
                tempVars.removeAt(tempVars.lastIndex)
            }

            while (tempVars.size < newCount) {
                tempVars.add("")
            }
        }

        fun updateTemplate(newTemplate: String) {
            tempText = newTemplate

            val newVariableCount = TemplateEngine.countVariables(newTemplate)

            // When a token is removed, its local value is removed too.
            // If a token is added later, it receives a fresh blank field.
            normalizeVariableSlots(newVariableCount)

            CommandRepository.setPhrase(
                context = context,
                storagePath = node.path,
                phrase = newTemplate
            )

            saveVariables()
        }

        fun commitEditor() {
            /*
             * updateTemplate already persists the template and normalizes/saves
             * associated variable slots. Calling it here makes COMMIT an immediate,
             * explicit final write even though typing is also live-saved.
             */
            updateTemplate(tempText)
            refreshKey++
            showDialog = false
        }

        val helpManager = LocalHelpManager.current
        val density = LocalDensity.current
        val imeBottom = WindowInsets.ime.getBottom(density)

        var macroFieldFocused by remember(node.path) {
            mutableStateOf(false)
        }

        var macroKeyboardOpened by remember(node.path) {
            mutableStateOf(false)
        }

        LaunchedEffect(
            macroFieldFocused,
            macroKeyboardOpened,
            imeBottom
        ) {
            if (macroFieldFocused && imeBottom > 0) {
                macroKeyboardOpened = true
            }

            if (
                macroFieldFocused &&
                macroKeyboardOpened &&
                imeBottom == 0
            ) {
                helpManager?.onEvent(
                    HelpEvent.KeyboardWasDismissed(
                        AckTags.MACRO_TEMPLATE_INPUT
                    )
                )

                macroFieldFocused = false
                macroKeyboardOpened = false
            }
        }

        TightDialogSurface(
            onDismiss = {
                closeEditor()
            },
            primaryColor = primaryColor,
            title = node.label,
            subtitle = "LIVE-SAVE EDITOR",
            surfaceModifier = Modifier.testTag(AckTags.EDIT_NODE_DIALOG)
        ) {
                Column {
                    TightSectionLabel("MACRO TEMPLATE")

                    Spacer(modifier = Modifier.height(6.dp))

                    OutlinedTextField(
                        value = tempText,
                        onValueChange = { newText ->
                            updateTemplate(newText)
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag(AckTags.MACRO_TEMPLATE_INPUT)
                            .helpTarget(AckTags.MACRO_TEMPLATE_INPUT, primaryColor)
                            .onFocusChanged { state ->
                                if (state.isFocused) {
                                    macroFieldFocused = true
                                }
                            },
                        shape = AckHelpShape,
                        minLines = 3,
                        maxLines = 4,
                        placeholder = {
                            Text(
                                text = "ENTER OUTPUT PHRASE...",
                                color = Color.DarkGray,
                                fontFamily = FontFamily.Monospace
                            )
                        },
                        textStyle = androidx.compose.ui.text.TextStyle(
                            color = primaryColor,
                            fontFamily = FontFamily.Monospace
                        ),
                        colors = TextFieldDefaults.colors(
                            focusedContainerColor = VoidBlack,
                            unfocusedContainerColor = VoidBlack,
                            focusedIndicatorColor = primaryColor,
                            unfocusedIndicatorColor = Color.DarkGray,
                            focusedTextColor = primaryColor,
                            unfocusedTextColor = primaryColor,
                            cursorColor = primaryColor
                        )
                    )

                    Spacer(modifier = Modifier.height(10.dp))

                    TightSectionLabel("INSERT VARIABLE TOKEN")

                    Spacer(modifier = Modifier.height(6.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        TightPanelButton(
                            text = "+ VAR",
                            modifier = Modifier.weight(1f),
                            mainColor = primaryColor
                        ) {
                            updateTemplate("$tempText {VAR}")
                        }

                        TightPanelButton(
                            text = "+ A",
                            modifier = Modifier.weight(1f),
                            mainColor = primaryColor
                        ) {
                            updateTemplate("$tempText {VAR:A}")
                        }

                        TightPanelButton(
                            text = "+ B",
                            modifier = Modifier.weight(1f),
                            mainColor = primaryColor
                        ) {
                            updateTemplate("$tempText {VAR:B}")
                        }

                        TightPanelButton(
                            text = "+ C",
                            modifier = Modifier.weight(1f),
                            mainColor = primaryColor
                        ) {
                            updateTemplate("$tempText {VAR:C}")
                        }
                    }

                    if (variableCount > 0) {
                        Spacer(modifier = Modifier.height(14.dp))

                        Text(
                            text = "LOCAL VARIABLE DATA",
                            color = NeonPalette.SWATCHES[3],
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )

                        Spacer(modifier = Modifier.height(4.dp))

                        Text(
                            text = "Saved immediately. Tagged A/B/C values can be "
                                    + "replaced by enabled root overrides.",
                            color = Color.Gray,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )

                        Spacer(modifier = Modifier.height(8.dp))

                        repeat(variableCount) { index ->
                            val tag = TemplateEngine
                                .getVariableTags(tempText)
                                .getOrNull(index)

                            val label = if (tag == null) {
                                "VARIABLE ${index + 1}"
                            } else {
                                "VARIABLE ${index + 1} // ROOT $tag"
                            }

                            OutlinedTextField(
                                value = tempVars[index],
                                onValueChange = { newValue ->
                                    tempVars[index] = newValue
                                    saveVariables()
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 52.dp),
                                shape = AckHelpShape,
                                singleLine = true,
                                label = {
                                    Text(
                                        text = label,
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 10.sp
                                    )
                                },
                                placeholder = {
                                    Text(
                                        text = "ENTER LOCAL FALLBACK...",
                                        color = Color.DarkGray,
                                        fontFamily = FontFamily.Monospace
                                    )
                                },
                                textStyle = androidx.compose.ui.text.TextStyle(
                                    color = Color.White,
                                    fontFamily = FontFamily.Monospace
                                ),
                                colors = TextFieldDefaults.colors(
                                    focusedContainerColor = VoidBlack,
                                    unfocusedContainerColor = VoidBlack,
                                    focusedIndicatorColor = NeonPalette.SWATCHES[3],
                                    unfocusedIndicatorColor = Color.DarkGray,
                                    focusedTextColor = Color.White,
                                    unfocusedTextColor = Color.White,
                                    cursorColor = NeonPalette.SWATCHES[3]
                                )
                            )

                            if (index < variableCount - 1) {
                                Spacer(modifier = Modifier.height(8.dp))
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    TightSectionLabel("DESTRUCTIVE CONTROLS", color = RadicalRed)

                    Spacer(modifier = Modifier.height(6.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        TightPanelButton(
                            text = "CLEAR VARS",
                            modifier = Modifier.weight(1f),
                            isActive = false,
                            mainColor = RadicalRed
                        ) {
                            clearMode = "VARS"
                        }

                        TightPanelButton(
                            text = "CLEAR PROMPT",
                            modifier = Modifier.weight(1f),
                            isActive = false,
                            mainColor = RadicalRed
                        ) {
                            clearMode = "PROMPT"
                        }
                    }

                    Spacer(modifier = Modifier.height(6.dp))

                    TightPanelButton(
                        text = "CLEAR ALL",
                        modifier = Modifier.fillMaxWidth(),
                        isActive = false,
                        mainColor = RadicalRed
                    ) {
                        clearMode = "ALL"
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "COMMIT",
                        modifier = Modifier
                            .weight(1f)
                            .testTag(AckTags.MATRIX_COMMIT_BUTTON)
                            .helpTarget(AckTags.MATRIX_COMMIT_BUTTON, primaryColor),
                        mainColor = primaryColor
                    ) {
                        commitEditor()

                        helpManager?.onEvent(
                            HelpEvent.Interacted(AckTags.MATRIX_COMMIT_BUTTON)
                        )
                    }

                    TightPanelButton(
                        text = "CLOSE",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        closeEditor()
                    }
                }
        }

        val mode = clearMode

        if (mode != null) {
            val confirmationText = when (mode) {
                "VARS" -> {
                    "Clear every local variable value for this phrase? "
                     "The prompt will remain."
                }

                "PROMPT" -> {
                    "Clear this prompt only? Existing local variable values "
                     "will be preserved."
                }

                else -> {
                    "Clear both the prompt and every local variable value? "
                     "This cannot be undone from this dialog."
                }
            }

            TightDialogSurface(
                onDismiss = {
                    clearMode = null
                },
                primaryColor = RadicalRed,
                title = "CONFIRM CLEAR",
                dismissLabel = "ABORT"
            ) {
                Text(
                    text = confirmationText,
                    color = Color.White,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "CONFIRM",
                        modifier = Modifier.weight(1f),
                        mainColor = RadicalRed
                    ) {
                        when (mode) {
                            "VARS" -> {
                                repeat(tempVars.size) { index ->
                                    tempVars[index] = ""
                                }

                                saveVariables()
                            }

                            "PROMPT" -> {
                                // Prompt-only intentionally preserves the
                                // variable bank for a future replacement prompt.
                                tempText = ""

                                CommandRepository.setPhrase(
                                    context = context,
                                    storagePath = node.path,
                                    phrase = ""
                                )
                            }

                            "ALL" -> {
                                tempText = ""
                                tempVars.clear()

                                CommandRepository.setPhrase(
                                    context = context,
                                    storagePath = node.path,
                                    phrase = ""
                                )

                                saveVariables()
                            }
                        }

                        clearMode = null
                        refreshKey++
                    }

                    TightPanelButton(
                        text = "CANCEL",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        clearMode = null
                    }
                }
            }
        }
    }

    if (variableEditRequest != null) {
        val request = variableEditRequest!!
        var value by remember(request.nodePath, request.index) {
            mutableStateOf(request.currentValue)
        }

        TightDialogSurface(
            onDismiss = { variableEditRequest = null },
            primaryColor = primaryColor,
            title = "${request.nodeLabel} // VAR ${request.index + 1}",
            dismissLabel = "ABORT"
        ) {
                Column {
                    TightSectionLabel("LIVE VARIABLE VALUE")

                    Spacer(modifier = Modifier.height(8.dp))

                    OutlinedTextField(
                        value = value,
                        onValueChange = { value = it },
                        modifier = Modifier.fillMaxWidth(),
                        shape = AckHelpShape,
                        singleLine = true,
                        placeholder = {
                            Text(
                                text = "ENTER VALUE",
                                fontFamily = FontFamily.Monospace
                            )
                        },
                        textStyle = androidx.compose.ui.text.TextStyle(
                            color = primaryColor,
                            fontFamily = FontFamily.Monospace
                        ),
                        colors = TextFieldDefaults.colors(
                            focusedContainerColor = VoidBlack,
                            unfocusedContainerColor = VoidBlack,
                            focusedIndicatorColor = primaryColor,
                            unfocusedIndicatorColor = Color.DarkGray,
                            focusedTextColor = primaryColor,
                            unfocusedTextColor = primaryColor,
                            cursorColor = primaryColor
                        )
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "UPDATE",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        val existingValues = CommandRepository.getVariableValues(
                            context,
                            request.nodePath
                        ).toMutableList()

                        while (existingValues.size <= request.index) {
                            existingValues.add("")
                        }

                        existingValues[request.index] = value

                        CommandRepository.setVariableValues(
                            context,
                            request.nodePath,
                            existingValues
                        )

                        refreshKey++
                        variableEditRequest = null
                    }

                    TightPanelButton(
                        text = "ABORT",
                        modifier = Modifier.weight(1f),
                        isActive = false,
                        mainColor = primaryColor
                    ) {
                        variableEditRequest = null
                    }
                }
        }
    }

    if (showManageContextDialog) {
        ManageContextDialog(
            context = context,
            primaryColor = primaryColor,
            onDismiss = { showManageContextDialog = false },
            onChanged = { refreshKey++ }
        )
    }
}

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
                                letterSpacing = 1.sp
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

@Composable
fun MatrixCategory(
    title: String,
    nodes: List<Triple<MatrixNode, String, String>>,
    context: Context,
    primaryColor: Color,
    onEdit: (Triple<MatrixNode, String, String>) -> Unit,
    onEditVariable: (VariableEditRequest) -> Unit,
    onRootOverrideChanged: () -> Unit
) {
    val activeCat =
        remember(title) { mutableStateOf(CommandRepository.getActiveCategoryFocus(context)) }
    val isFocused = activeCat.value == title
    val canFocus = title != "DEFEND" && title != "CONNECT"
    val helpManager = LocalHelpManager.current

    Column {
        val headerModifier = if (title == "IDENTITY") {
            Modifier
                .testTag(AckTags.MATRIX_ROOT_IDENTITY)
                .helpTarget(AckTags.MATRIX_ROOT_IDENTITY, primaryColor)
        } else {
            Modifier
        }



        Row(
            modifier = headerModifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(10.dp)
                        .background(
                            color = if (isFocused) {
                                primaryColor
                            } else {
                                Color.Gray
                            },
                            shape = CutCornerShape(2.dp)
                        )
                )

                Spacer(modifier = Modifier.width(8.dp))

                Text(
                    text = "ROOT :: $title",
                    color = if (isFocused) primaryColor else Color.Gray,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 2.sp
                )
            }

            if (canFocus) {
                Box(
                    modifier = Modifier
                        .heightIn(min = 44.dp)
                        .border(
                            width = 1.dp,
                            color = if (isFocused) {
                                primaryColor
                            } else {
                                Color.Gray
                            },
                            shape = CutCornerShape(4.dp)
                        )
                        .clickable {
                            CommandRepository.setActiveCategoryFocus(
                                context,
                                title
                            )

                            activeCat.value = title

                            Intent("ACK_LOG").apply {
                                setPackage(context.packageName)
                                putExtra("msg", "CONTEXT FOCUS: $title")
                                putExtra("type", "SYS")
                                context.sendBroadcast(this)
                            }
                        }
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = if (isFocused) "ACTIVE" else "ACTIVATE",
                        color = if (isFocused) primaryColor else Color.Gray,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        RootOverrideStrip(
            category = title,
            context = context,
            primaryColor = primaryColor,
            onChanged = onRootOverrideChanged
        )

        Spacer(modifier = Modifier.height(10.dp))

        Box(modifier = Modifier.padding(start = 3.dp)) {
            Column(
                modifier = Modifier.border(
                    BorderStroke(1.dp, Color.DarkGray),
                    androidx.compose.ui.graphics.RectangleShape
                ).padding(start = 16.dp, top = 8.dp)
            ) {
                // <-- UPDATED LOOP TO DESTRUCTURE THE TRIPLE -->
                nodes.forEach { (node, rawPhrase, resolvedPhrase) ->
                    val isTarget = node.category == "IDENTITY" && node.label.contains("Twist 0")
                    val itemMod = if (isTarget) Modifier
                        .testTag(AckTags.MATRIX_ROW_TARGET)
                        .helpTarget(AckTags.MATRIX_ROW_TARGET, primaryColor)
                    else Modifier

                    val variableCount = TemplateEngine.countVariables(rawPhrase)
                    val savedValues = CommandRepository.getVariableValues(context, node.path)

                    val variableValues = List(variableCount) { index ->
                        savedValues.getOrElse(index) { "" }
                    }

                    MatrixNodeItem(
                        label = node.label,
                        phrase = resolvedPhrase,
                        variableValues = variableValues,
                        modifier = itemMod,
                        playModifier = if (isTarget) Modifier
                            .testTag(AckTags.MATRIX_PLAY_BUTTON)
                            .helpTarget(AckTags.MATRIX_PLAY_BUTTON, primaryColor)
                        else Modifier,
                        primaryColor = primaryColor,
                        onPlay = {
                            if (isTarget) {
                                helpManager?.onEvent(
                                    HelpEvent.Interacted(AckTags.MATRIX_PLAY_BUTTON)
                                )
                            }
                            val debug = CommandRepository.debugResolvedPhrase(
                                context = context,
                                storagePath = node.path
                            )

                            context.sendBroadcast(
                                Intent("ACK_LOG").apply {
                                    setPackage(context.packageName)
                                    putExtra("type", "SYS")
                                    putExtra("msg", debug.replace("\n", " | "))
                                }
                            )

                            val finalPhrase = CommandRepository.getResolvedPhrase(
                                context = context,
                                storagePath = node.path
                            )

                            val intent = Intent(context, OutputService::class.java).apply {
                                putExtra("phrase", finalPhrase)
                                putExtra("robotic", false)
                                putExtra("source", "MTX/${title.uppercase()}")
                            }

                            context.startService(intent)
                        },
                        onClick = {
                            if (isTarget) {
                                helpManager?.onEvent(
                                    HelpEvent.Interacted(AckTags.MATRIX_ROW_TARGET)
                                )
                            }
                            onEdit(Triple(node, rawPhrase, resolvedPhrase))
                        },
                        onEditVariable = { index ->
                            onEditVariable(
                                VariableEditRequest(
                                    nodePath = node.path,
                                    nodeLabel = node.label,
                                    index = index,
                                    currentValue = variableValues[index]
                                )
                            )
                        }
                    )
                }
            }
        }
    }
}

@Composable
fun RootOverrideStrip(
    category: String,
    context: Context,
    primaryColor: Color,
    onChanged: () -> Unit
) {
    var config by remember(category) {
        mutableStateOf(
            RootOverrideRepository.getConfig(context, category)
        )
    }

    // Stored per category/pose, so toggling this block never affects any
    // other pose's or custom layer's own collapsed/expanded state.
    var collapsed by remember(category) {
        mutableStateOf(RootOverrideRepository.isSectionCollapsed(context, category))
    }

    var editingTag by remember { mutableStateOf<String?>(null) }

    fun updateSlot(
        tag: String,
        transform: (RootOverrideValue) -> RootOverrideValue
    ) {
        val currentSlot = config.slots[tag] ?: RootOverrideValue()

        config = config.copy(
            slots = config.slots.toMutableMap().apply {
                put(tag, transform(currentSlot))
            }
        )

        RootOverrideRepository.saveConfig(
            context = context,
            category = category,
            config = config
        )

        onChanged()
    }

    fun toggleCollapsed() {
        collapsed = !collapsed
        RootOverrideRepository.setSectionCollapsed(context, category, collapsed)
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = primaryColor.copy(alpha = 0.45f),
                shape = CutCornerShape(8.dp)
            )
            .background(
                color = primaryColor.copy(alpha = 0.04f),
                shape = CutCornerShape(8.dp)
            )
            .padding(10.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { toggleCollapsed() },
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "SHARED ROOT VARIABLES",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp
            )

            Text(
                text = if (collapsed) "[EXPAND ▼]" else "[COLLAPSE ▲]",
                color = primaryColor,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }

        AnimatedVisibility(
            visible = collapsed,
            enter = expandVertically(),
            exit = shrinkVertically()
        ) {
            Column {
                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    listOf("A", "B", "C").forEach { tag ->
                        val slot = config.slots[tag] ?: RootOverrideValue()

                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .height(40.dp)
                                .border(
                                    width = 1.dp,
                                    color = if (slot.enabled) {
                                        primaryColor
                                    } else {
                                        Color.Gray
                                    },
                                    shape = CutCornerShape(4.dp)
                                )
                                .background(
                                    color = if (slot.enabled) {
                                        primaryColor.copy(alpha = 0.18f)
                                    } else {
                                        Color.Transparent
                                    },
                                    shape = CutCornerShape(4.dp)
                                )
                                .clickable {
                                    updateSlot(tag) { current ->
                                        current.copy(enabled = !current.enabled)
                                    }
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "$tag: ${if (slot.enabled) "ON" else "OFF"}",
                                color = if (slot.enabled) {
                                    primaryColor
                                } else {
                                    Color.Gray
                                },
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        }

        AnimatedVisibility(
            visible = !collapsed,
            enter = expandVertically(),
            exit = shrinkVertically()
        ) {
            Column {
            Spacer(modifier = Modifier.height(4.dp))

            Text(
                text = "Enabled tags replace matching {VAR:A}, {VAR:B}, or {VAR:C}.",
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(10.dp))

            listOf("A", "B", "C").forEach { tag ->
                val slot = config.slots[tag] ?: RootOverrideValue()
                val valueText = slot.value.ifBlank { "NO SHARED VALUE SET" }

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 56.dp)
                        .border(
                            width = 1.dp,
                            color = if (slot.enabled) {
                                primaryColor
                            } else {
                                Color.DarkGray
                            },
                            shape = CutCornerShape(6.dp)
                        )
                        .background(
                            color = if (slot.enabled) {
                                primaryColor.copy(alpha = 0.10f)
                            } else {
                                Color.Transparent
                            },
                            shape = CutCornerShape(6.dp)
                        )
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(width = 52.dp, height = 44.dp)
                            .border(
                                width = 1.dp,
                                color = if (slot.enabled) {
                                    primaryColor
                                } else {
                                    Color.Gray
                                },
                                shape = CutCornerShape(4.dp)
                            )
                            .background(
                                color = if (slot.enabled) {
                                    primaryColor.copy(alpha = 0.18f)
                                } else {
                                    Color.Transparent
                                },
                                shape = CutCornerShape(4.dp)
                            )
                            .clickable {
                                updateSlot(tag) { current ->
                                    current.copy(enabled = !current.enabled)
                                }
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = tag,
                                color = if (slot.enabled) {
                                    primaryColor
                                } else {
                                    Color.Gray
                                },
                                fontSize = 14.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold
                            )

                            Text(
                                text = if (slot.enabled) "ON" else "OFF",
                                color = if (slot.enabled) {
                                    primaryColor
                                } else {
                                    Color.Gray
                                },
                                fontSize = 8.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    }

                    Spacer(modifier = Modifier.width(10.dp))

                    Column(
                        modifier = Modifier.weight(1f)
                    ) {
                        Text(
                            text = "ROOT $tag",
                            color = if (slot.enabled) primaryColor else Color.Gray,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )

                        Spacer(modifier = Modifier.height(3.dp))

                        Text(
                            text = valueText,
                            color = if (slot.value.isBlank()) {
                                Color.DarkGray
                            } else {
                                Color.White
                            },
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1
                        )
                    }

                    Spacer(modifier = Modifier.width(8.dp))

                    Box(
                        modifier = Modifier
                            .size(width = 64.dp, height = 44.dp)
                            .border(
                                width = 1.dp,
                                color = primaryColor.copy(alpha = 0.75f),
                                shape = CutCornerShape(4.dp)
                            )
                            .clickable {
                                editingTag = tag
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "EDIT",
                            color = primaryColor,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                if (tag != "C") {
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }
            }
        }
    }

    val tag = editingTag

    if (tag != null) {
        RootOverrideValueDialog(
            tag = tag,
            category = category,
            initialValue = config.slots[tag]?.value.orEmpty(),
            primaryColor = primaryColor,
            onDismiss = {
                editingTag = null
            },
            onSave = { newValue: String ->
                updateSlot(tag) { current ->
                    current.copy(value = newValue)
                }

                editingTag = null
            }
        )
    }
}

@Composable
fun RootOverrideValueDialog(
    tag: String,
    category: String,
    initialValue: String,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onSave: (String) -> Unit
) {
    var value by remember(tag, initialValue) {
        mutableStateOf(initialValue)
    }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "ROOT $category // TAG $tag",
        dismissLabel = "ABORT"
    ) {
                TightSectionLabel("SHARED OVERRIDE VALUE")

                Spacer(modifier = Modifier.height(8.dp))

                OutlinedTextField(
                    value = value,
                    onValueChange = { value = it },
                    modifier = Modifier.fillMaxWidth(),
                    shape = AckHelpShape,
                    singleLine = true,
                    placeholder = {
                        Text(
                            text = "ENTER VALUE",
                            fontFamily = FontFamily.Monospace
                        )
                    },
                    textStyle = androidx.compose.ui.text.TextStyle(
                        color = primaryColor,
                        fontFamily = FontFamily.Monospace
                    ),
                    colors = TextFieldDefaults.colors(
                        focusedTextColor = primaryColor,
                        unfocusedTextColor = primaryColor,
                        focusedContainerColor = VoidBlack,
                        unfocusedContainerColor = VoidBlack,
                        focusedIndicatorColor = primaryColor,
                        unfocusedIndicatorColor = Color.DarkGray,
                        cursorColor = primaryColor
                    )
                )

                Spacer(modifier = Modifier.height(16.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    TightPanelButton(
                        text = "COMMIT",
                        modifier = Modifier.weight(1f),
                        mainColor = primaryColor
                    ) {
                        onSave(value)
                    }

                    TightPanelButton(
                        text = "ABORT",
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
fun MatrixNodeItem(
    label: String,
    phrase: String,
    variableValues: List<String>,
    modifier: Modifier = Modifier,
    playModifier: Modifier = Modifier,
    primaryColor: Color,
    onPlay: () -> Unit,
    onClick: () -> Unit,
    onEditVariable: (Int) -> Unit
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = "├─",
            color = Color.DarkGray,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.width(8.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .border(
                    1.dp,
                    primaryColor.copy(alpha = 0.3f),
                    CutCornerShape(bottomEnd = 8.dp)
                )
                .background(Graphite)
                .padding(4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .clickable { onClick() }
                    .padding(4.dp)
            ) {
                Text(
                    text = label,
                    color = primaryColor,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )

                Text(
                    text = if (phrase.length > 20) {
                        phrase.take(17) + "..."
                    } else {
                        phrase
                    },
                    color = Color.White,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )

                if (variableValues.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(6.dp))

                    Row(
                        modifier = Modifier.horizontalScroll(
                            rememberScrollState()
                        ),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        variableValues.forEachIndexed { index, value ->
                            val displayValue = value.ifBlank { "EMPTY" }

                            Box(
                                modifier = Modifier
                                    .border(
                                        1.dp,
                                        color = NeonPalette.SWATCHES[3],
                                        CutCornerShape(4.dp)
                                    )
                                    .background(
                                        NeonPalette.SWATCHES[3].copy(
                                            alpha = 0.08f
                                        ),
                                        CutCornerShape(4.dp)
                                    )
                                    .clickable {
                                        onEditVariable(index)
                                    }
                                    .padding(
                                        horizontal = 6.dp,
                                        vertical = 4.dp
                                    )
                            ) {
                                Text(
                                    text = "V${index + 1}: $displayValue",
                                    color = NeonPalette.SWATCHES[3],
                                    fontSize = 9.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.width(8.dp))

            Box(
                modifier = playModifier
                    .size(32.dp)
                    .background(
                        Color.DarkGray.copy(alpha = 0.3f),
                        CutCornerShape(4.dp)
                    )
                    .clickable { onPlay() }
                    .border(1.dp, primaryColor, CutCornerShape(4.dp)),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "▶",
                    color = primaryColor,
                    fontSize = 10.sp
                )
            }
        }
    }
}

@Composable
fun BuilderGuideCard(category: String, primaryColor: Color) {
    val (title, body) = when(category) {
        "IDENTITY" -> "POSE: ARM RAISED UP" to "Use for: Status reporting."
        "DEFEND" -> "POSE: ARM FLAT / PALM DOWN" to "Use for: Boundaries, stops."
        "CONNECT" -> "POSE: HANDSHAKE / SIDEWAYS" to "Use for: Social protocols."
        else -> "UNKNOWN" to "No data available."
    }
    Column(modifier = Modifier.fillMaxWidth().border(1.dp, primaryColor, CutCornerShape(8.dp)).background(primaryColor.copy(alpha = 0.05f)).padding(12.dp)) {
        Text("// TACTICAL GUIDE: $title", color = primaryColor, fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
        Spacer(modifier = Modifier.height(4.dp))
        Text(body, color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
    }
}
