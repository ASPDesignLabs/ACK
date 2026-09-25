package com.example.besu.composer

import com.example.besu.*
import com.example.besu.computer.*
import com.example.besu.data.*
import com.example.besu.decks.*
import com.example.besu.help.*
import com.example.besu.output.*
import com.example.besu.ui.*
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.util.UUID

// The statement composer: builds multi-sentence statements from Target
// Computer entries and Shared Root Variables, saves them, and lets them be
// copied to the clipboard or spoken via TTS. Unlike legacy Manual Override
// (TypeView in ui/DesignSystem.kt), this screen inserts TemplateEngine
// tokens ([COMPUTER:id], {VAR:A}) at the cursor instead of literal text, so
// a saved statement stays mutable -- resolving it always re-reads whatever
// the referenced Target Computer entry or Shared Root Variable currently
// holds, exactly like a Matrix/Quick Actions phrase already does.
//
// Not yet wired into MainActivity's viewMode dispatch -- that happens
// alongside relocating legacy Manual Override behind Terminal's /m command,
// so the daily-driver flow is never without a home in between.
@Composable
fun StatementComposerView(context: Context, primaryColor: Color) {
    var textFieldValue by remember { mutableStateOf(TextFieldValue("")) }
    var editingStatementId by remember { mutableStateOf<String?>(null) }
    var variableContext by remember { mutableStateOf("IDENTITY") }
    val focusRequester = remember { FocusRequester() }

    var showTargetBrowsePanel by remember { mutableStateOf(false) }
    var showVariablePicker by remember { mutableStateOf(false) }
    var showSaveDialog by remember { mutableStateOf(false) }
    var showStatementsList by remember { mutableStateOf(false) }
    var saveLabelInput by remember { mutableStateOf("") }
    var refreshKey by remember { mutableIntStateOf(0) }

    // Long-pressing a quick-access chip opens ComputerTreeWindow (the SAME
    // dialog the Target Computer tab uses) to retarget that category's
    // active entry -- a real, app-wide change via ComputerRepository, not a
    // composer-local one. targetRefreshKey forces the chip row and the live
    // preview to pick up the change immediately, since neither would
    // otherwise know that category's active entry moved out from under it.
    var openTargetCategoryTreeId by remember { mutableStateOf<String?>(null) }
    var openTargetContactCard by remember { mutableStateOf<Pair<String, String>?>(null) }
    var targetRefreshKey by remember { mutableIntStateOf(0) }

    val savedStatements by remember(refreshKey) {
        mutableStateOf(StatementRepository.getStatements(context))
    }

    val helpManager = LocalHelpManager.current
    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(HelpEvent.Interacted(tag))
    }

    fun insertTextAtCursor(text: String) {
        val selection = textFieldValue.selection
        val spliced = "$text "
        val newText = textFieldValue.text.replaceRange(selection.start, selection.end, spliced)
        val newCursor = selection.start + spliced.length
        textFieldValue = TextFieldValue(newText, TextRange(newCursor))
        focusRequester.requestFocus()
    }

    val resolvedPreview = remember(textFieldValue.text, variableContext, targetRefreshKey) {
        resolveStatementTemplate(context, textFieldValue.text, variableContext)
    }

    fun copyResolvedText(template: String, resolved: String) {
        if (resolved.isBlank()) return
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("ACK STATEMENT", resolved))
        consumeSingleUseComputerTags(context, template)
        Toast.makeText(context, "COPIED", Toast.LENGTH_SHORT).show()
    }

    fun speakResolvedText(template: String, resolved: String, sourceTag: String) {
        if (resolved.isBlank()) return
        val intent = Intent(context, OutputService::class.java)
        intent.putExtra("phrase", resolved)
        intent.putExtra("robotic", false)
        intent.putExtra("source", sourceTag)
        context.startService(intent)
        consumeSingleUseComputerTags(context, template)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text(
            "STATEMENT COMPOSER",
            color = primaryColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            letterSpacing = 2.sp
        )
        Spacer(modifier = Modifier.height(12.dp))

        TightSectionLabel("VARIABLE CONTEXT")
        Spacer(modifier = Modifier.height(6.dp))
        VariableContextRow(
            context = context,
            primaryColor = primaryColor,
            selected = variableContext,
            modifier = Modifier
                .testTag(AckTags.COMPOSER_VARIABLE_CONTEXT_ROW)
                .helpTarget(AckTags.COMPOSER_VARIABLE_CONTEXT_ROW, primaryColor),
            onSelect = { variableContext = it }
        )

        Spacer(modifier = Modifier.height(16.dp))

        OutlinedTextField(
            value = textFieldValue,
            onValueChange = { textFieldValue = it },
            modifier = Modifier
                .fillMaxWidth()
                .testTag(AckTags.COMPOSER_FIELD)
                .helpTarget(AckTags.COMPOSER_FIELD, primaryColor)
                .focusRequester(focusRequester),
            shape = AckHelpShape,
            colors = NeonTextFieldColors(primaryColor),
            textStyle = androidx.compose.ui.text.TextStyle(
                fontFamily = FontFamily.Monospace,
                fontSize = 15.sp
            ),
            placeholder = {
                Text(
                    "COMPOSE A STATEMENT...",
                    color = Color.Gray,
                    fontFamily = FontFamily.Monospace
                )
            },
            minLines = 5,
            maxLines = 12
        )

        Spacer(modifier = Modifier.height(12.dp))

        TightSectionLabel("LIVE PREVIEW")
        Spacer(modifier = Modifier.height(6.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .border(1.dp, primaryColor.copy(alpha = 0.4f), CutCornerShape(6.dp))
                .background(primaryColor.copy(alpha = 0.04f), CutCornerShape(6.dp))
                .padding(10.dp)
        ) {
            Text(
                text = resolvedPreview.ifBlank { "NOTHING TO PREVIEW YET." },
                color = if (resolvedPreview.isBlank()) Color.DarkGray else primaryColor,
                fontSize = 13.sp,
                fontFamily = FontFamily.Monospace
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // --- INSERTION AIDS ---
        // A chip is the category's CURRENTLY ACTIVE entry, so tapping it
        // inserts a live [COMPUTER:id] token -- exactly what that token
        // means. Long-pressing opens ComputerTreeWindow to retarget which
        // entry is active, for real, app-wide (see openTargetCategoryTreeId
        // below); key() forces the row to re-read activePicks once that
        // dialog reports a change, since TargetQuickAccessRow itself has no
        // refresh-key parameter of its own.
        key(targetRefreshKey) {
            TargetQuickAccessRow(
                context = context,
                primaryColor = primaryColor,
                onInsert = { categoryId, _ -> insertTextAtCursor("[COMPUTER:$categoryId]") },
                onLongPress = { categoryId -> openTargetCategoryTreeId = categoryId }
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(
                text = if (showTargetBrowsePanel) "[HIDE TARGET BROWSER]" else "[BROWSE TARGETS]",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .testTag(AckTags.COMPOSER_BROWSE_TARGETS_TOGGLE)
                    .helpTarget(AckTags.COMPOSER_BROWSE_TARGETS_TOGGLE, primaryColor)
                    .clickable {
                        showTargetBrowsePanel = !showTargetBrowsePanel
                        reportHelpInteraction(AckTags.COMPOSER_BROWSE_TARGETS_TOGGLE)
                    }
            )

            Text(
                text = if (showVariablePicker) "[HIDE VARIABLES]" else "[INSERT VARIABLE]",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .testTag(AckTags.COMPOSER_VARIABLE_TOGGLE)
                    .helpTarget(AckTags.COMPOSER_VARIABLE_TOGGLE, primaryColor)
                    .clickable {
                        showVariablePicker = !showVariablePicker
                        reportHelpInteraction(AckTags.COMPOSER_VARIABLE_TOGGLE)
                    }
            )

            Text(
                text = if (savedStatements.isNotEmpty()) {
                    "[MY STATEMENTS (${savedStatements.size})]"
                } else {
                    "[MY STATEMENTS]"
                },
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .testTag(AckTags.COMPOSER_STATEMENTS_LIST_BTN)
                    .helpTarget(AckTags.COMPOSER_STATEMENTS_LIST_BTN, primaryColor)
                    .clickable {
                        showStatementsList = true
                        reportHelpInteraction(AckTags.COMPOSER_STATEMENTS_LIST_BTN)
                    }
            )
        }

        if (showTargetBrowsePanel) {
            Spacer(modifier = Modifier.height(8.dp))
            // Browsing here can land on an entry that ISN'T the category's
            // active one, so a [COMPUTER:id] token would be wrong -- it
            // always resolves to whatever's active, not whatever was just
            // picked here. Insert the literal, already-rationalized label
            // instead, same as legacy Manual Override's own browse panel.
            TargetBrowsePanel(
                context = context,
                primaryColor = primaryColor,
                onInsert = { _, label -> insertTextAtCursor(label) }
            )
        }

        if (showVariablePicker) {
            Spacer(modifier = Modifier.height(8.dp))
            SharedVariablePicker(
                context = context,
                primaryColor = primaryColor,
                category = variableContext,
                onInsert = { tag -> insertTextAtCursor("{VAR:$tag}") }
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            TightPanelButton(
                text = "SAVE",
                modifier = Modifier
                    .weight(1f)
                    .testTag(AckTags.COMPOSER_SAVE_BTN)
                    .helpTarget(AckTags.COMPOSER_SAVE_BTN, primaryColor),
                isActive = textFieldValue.text.isNotBlank(),
                mainColor = primaryColor
            ) {
                if (textFieldValue.text.isNotBlank()) {
                    saveLabelInput = editingStatementId
                        ?.let { id -> savedStatements.firstOrNull { it.id == id } }
                        ?.label
                        ?: ""
                    showSaveDialog = true
                }
            }

            TightPanelButton(
                text = "COPY",
                modifier = Modifier
                    .weight(1f)
                    .testTag(AckTags.COMPOSER_COPY_BTN)
                    .helpTarget(AckTags.COMPOSER_COPY_BTN, primaryColor),
                isActive = resolvedPreview.isNotBlank(),
                mainColor = primaryColor
            ) {
                copyResolvedText(textFieldValue.text, resolvedPreview)
                reportHelpInteraction(AckTags.COMPOSER_COPY_BTN)
            }

            HeroButton(
                text = "SPEAK",
                modifier = Modifier
                    .weight(1f)
                    .testTag(AckTags.COMPOSER_SPEAK_BTN)
                    .helpTarget(AckTags.COMPOSER_SPEAK_BTN, primaryColor),
                mainColor = primaryColor
            ) {
                speakResolvedText(textFieldValue.text, resolvedPreview, "COMPOSER/SPEAK")
                reportHelpInteraction(AckTags.COMPOSER_SPEAK_BTN)
            }
        }
    }

    if (showSaveDialog) {
        TightDialogSurface(
            onDismiss = { showSaveDialog = false },
            primaryColor = primaryColor,
            title = "SAVE STATEMENT"
        ) {
            TightSectionLabel("LABEL")
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = saveLabelInput,
                onValueChange = { saveLabelInput = it },
                placeholder = { Text("E.G. \"ORDER AT A CAFE\"") },
                shape = AckHelpShape,
                colors = NeonTextFieldColors(primaryColor),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(16.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                TightPanelButton("SAVE", modifier = Modifier.weight(1f), mainColor = primaryColor) {
                    if (saveLabelInput.isNotBlank()) {
                        val existing = editingStatementId
                            ?.let { id -> savedStatements.firstOrNull { it.id == id } }
                        val statement = SavedStatement(
                            id = existing?.id ?: UUID.randomUUID().toString(),
                            label = saveLabelInput.trim(),
                            template = textFieldValue.text,
                            variableContext = variableContext,
                            createdAt = existing?.createdAt ?: System.currentTimeMillis(),
                            updatedAt = System.currentTimeMillis(),
                            sortOrder = System.currentTimeMillis()
                        )
                        StatementRepository.upsertStatement(context, statement)
                        editingStatementId = statement.id
                        refreshKey++
                        showSaveDialog = false
                        Toast.makeText(context, "STATEMENT SAVED", Toast.LENGTH_SHORT).show()
                        reportHelpInteraction(AckTags.COMPOSER_SAVE_BTN)
                    }
                }
                TightPanelButton(
                    "CANCEL",
                    modifier = Modifier.weight(1f),
                    isActive = false,
                    mainColor = primaryColor
                ) {
                    showSaveDialog = false
                }
            }
        }
    }

    if (showStatementsList) {
        TightDialogSurface(
            onDismiss = { showStatementsList = false },
            primaryColor = primaryColor,
            title = "MY STATEMENTS",
            dismissLabel = "CLOSE"
        ) {
            if (savedStatements.isEmpty()) {
                Text(
                    text = "NO SAVED STATEMENTS YET. COMPOSE ONE ABOVE AND TAP SAVE.",
                    color = Color.DarkGray,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace
                )
            } else {
                LazyColumn(modifier = Modifier.heightIn(max = 420.dp)) {
                    items(savedStatements, key = { it.id }) { statement ->
                        SavedStatementRow(
                            statement = statement,
                            primaryColor = primaryColor,
                            onLoad = {
                                textFieldValue = TextFieldValue(
                                    statement.template,
                                    TextRange(statement.template.length)
                                )
                                editingStatementId = statement.id
                                variableContext = statement.variableContext
                                showStatementsList = false
                                focusRequester.requestFocus()
                            },
                            onCopy = {
                                val resolved = resolveStatementTemplate(
                                    context,
                                    statement.template,
                                    statement.variableContext
                                )
                                copyResolvedText(statement.template, resolved)
                            },
                            onSpeak = {
                                val resolved = resolveStatementTemplate(
                                    context,
                                    statement.template,
                                    statement.variableContext
                                )
                                speakResolvedText(statement.template, resolved, "COMPOSER/BANK")
                            },
                            onDelete = {
                                StatementRepository.deleteStatement(context, statement.id)
                                refreshKey++
                                if (editingStatementId == statement.id) {
                                    editingStatementId = null
                                }
                            }
                        )
                    }
                }
            }
        }
    }

    // Long-press-on-chip retargeting. Reuses ComputerTreeWindow/
    // ContactCardDialog wholesale -- the exact same dialogs the Target
    // Computer tab itself opens -- rather than building a composer-local
    // picker, so this is genuinely the same "adjust the active entry"
    // surface, not a parallel one that could drift from it.
    val treeCategoryId = openTargetCategoryTreeId
    if (treeCategoryId != null) {
        ComputerTreeWindow(
            context = context,
            primaryColor = primaryColor,
            categoryId = treeCategoryId,
            onDismiss = { openTargetCategoryTreeId = null },
            onChanged = { targetRefreshKey++ },
            onOpenContactCard = { nodeId -> openTargetContactCard = treeCategoryId to nodeId }
        )
    }

    val contactCardTarget = openTargetContactCard
    if (contactCardTarget != null) {
        val (cardCategoryId, cardNodeId) = contactCardTarget
        ContactCardDialog(
            context = context,
            primaryColor = primaryColor,
            categoryId = cardCategoryId,
            nodeId = cardNodeId,
            onDismiss = {
                openTargetContactCard = null
                targetRefreshKey++
            }
        )
    }
}

// Row 1 of the composer's own variable picker: which Shared Root Variables
// grouping (a fixed pose or a custom context layer) the WHOLE statement's
// {VAR:A}/{VAR:B}/{VAR:C} tokens resolve against. Same source list Matrix's
// own /v picker and node editor use (POSE_CATEGORIES plus every custom
// context layer's name), so nothing here is invented.
@Composable
private fun VariableContextRow(
    context: Context,
    primaryColor: Color,
    selected: String,
    modifier: Modifier = Modifier,
    onSelect: (String) -> Unit
) {
    val groupings = remember {
        POSE_CATEGORIES + CommandRepository.getCustomContextEntries(context).map { it.name }
    }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        groupings.forEach { grouping ->
            val isActive = grouping == selected
            Box(
                modifier = Modifier
                    .heightIn(min = 40.dp)
                    .border(
                        1.dp,
                        if (isActive) primaryColor else Color.DarkGray,
                        CutCornerShape(6.dp)
                    )
                    .background(
                        if (isActive) primaryColor.copy(alpha = 0.12f) else Color.Transparent,
                        CutCornerShape(6.dp)
                    )
                    .clickable { onSelect(grouping) }
                    .padding(horizontal = 10.dp, vertical = 8.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = grouping.uppercase(),
                    color = if (isActive) primaryColor else Color.Gray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

// Browses the CURRENT variable context's A/B/C Shared Root Variable slots
// and inserts a {VAR:tag} TOKEN at the cursor -- deliberately not the
// slot's literal value the way Terminal's /v picker does. A saved statement
// keeps resolving this slot live, exactly like Matrix/Quick Actions phrases
// already do via TemplateEngine.
@Composable
private fun SharedVariablePicker(
    context: Context,
    primaryColor: Color,
    category: String,
    onInsert: (tag: String) -> Unit
) {
    val config = remember(category) { RootOverrideRepository.getConfig(context, category) }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor.copy(alpha = 0.4f), CutCornerShape(8.dp))
            .background(primaryColor.copy(alpha = 0.04f), CutCornerShape(8.dp))
            .padding(10.dp)
    ) {
        TightSectionLabel("${category.uppercase()} VARIABLES")
        Spacer(modifier = Modifier.height(8.dp))

        listOf("A", "B", "C").forEach { tag ->
            val slot = config.slots[tag]
            val preview = if (slot?.enabled == true && slot.value.isNotBlank()) {
                slot.value
            } else {
                "(NOT SET)"
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 6.dp)
                    .heightIn(min = 44.dp)
                    .border(1.dp, primaryColor, CutCornerShape(6.dp))
                    .background(primaryColor.copy(alpha = 0.06f), CutCornerShape(6.dp))
                    .clickable { onInsert(tag) }
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                contentAlignment = Alignment.CenterStart
            ) {
                Column {
                    Text(
                        text = "VAR $tag",
                        color = primaryColor,
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = preview,
                        color = Color.Gray,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
        }
    }
}

@Composable
private fun SavedStatementRow(
    statement: SavedStatement,
    primaryColor: Color,
    onLoad: () -> Unit,
    onCopy: () -> Unit,
    onSpeak: () -> Unit,
    onDelete: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 10.dp)
            .border(1.dp, primaryColor.copy(alpha = 0.4f), CutCornerShape(6.dp))
            .clickable { onLoad() }
            .padding(10.dp)
    ) {
        Text(
            text = statement.label,
            color = primaryColor,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            text = statement.template,
            color = Color.Gray,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis
        )
        Spacer(modifier = Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(
                "[COPY]",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.clickable { onCopy() }
            )
            Text(
                "[SPEAK]",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.clickable { onSpeak() }
            )
            Text(
                "[DELETE]",
                color = Color(0xFFFF4444),
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.clickable { onDelete() }
            )
        }
    }
}

// Resolves a statement's raw template against a specific Shared Root
// Variable grouping (SavedStatement.variableContext) plus whatever's
// currently active in any referenced Target Computer categories -- the
// exact same TemplateEngine.resolve() call Matrix/Quick Actions phrases go
// through (CommandRepository.getResolvedPhrase/resolveQuickAction), just
// with the composer's own free-standing grouping choice standing in for a
// Matrix node's category (a statement isn't anchored to a deck/node).
private fun resolveStatementTemplate(
    context: Context,
    template: String,
    variableContext: String
): String {
    if (template.isBlank()) {
        return ""
    }

    val rootConfig = RootOverrideRepository.getConfig(context, variableContext)
    val computerActiveValues = TemplateEngine.getComputerTags(template)
        .distinct()
        .associateWith { categoryId -> ComputerRepository.resolveTag(context, categoryId) }

    return TemplateEngine.resolve(
        template = template,
        localValues = emptyList(),
        overrides = rootConfig.slots,
        computerActiveValues = computerActiveValues
    )
}

// Mirrors CommandRepository.getResolvedPhrase's consumeSingleUse step --
// only called from COPY/SPEAK (a genuine commit to output), never from the
// live preview or SAVE, so previewing or saving a statement can never
// silently clear a single-use Target Computer pick.
private fun consumeSingleUseComputerTags(context: Context, template: String) {
    TemplateEngine.getComputerTags(template).distinct().forEach { categoryId ->
        ComputerRepository.consumeIfSingleUse(context, categoryId)
    }
}
