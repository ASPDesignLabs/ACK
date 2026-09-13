package com.example.besu

import android.content.Context
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.VoidBlack

private val DangerRed = Color(0xFFFF0055)

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun TargetView(context: Context, primaryColor: Color) {
    var subMode by remember { mutableStateOf("CATEGORIES") } // CATEGORIES, VISUALS

    val helpManager = LocalHelpManager.current

    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(HelpEvent.Interacted(tag))
    }

    var refreshKey by remember { mutableIntStateOf(0) }
    val categories = remember(refreshKey) { ComputerRepository.getCategories(context) }

    var showAddCategory by remember { mutableStateOf(false) }
    var optionsCategory by remember { mutableStateOf<ComputerCategory?>(null) }
    var openTreeCategoryId by remember { mutableStateOf<String?>(null) }
    var showMigrationNotice by remember { mutableStateOf(false) }
    var showWizard by remember { mutableStateOf(false) }
    var wizardStartCategoryId by remember { mutableStateOf<String?>(null) }
    var initialized by remember { mutableStateOf(false) }

    fun refresh() {
        refreshKey++
    }

    // Runs once per screen visit: seeds the four default categories on a
    // fresh install, or folds any still-unmigrated legacy TargetSlot data
    // into a PEOPLE category (auto-backed-up first -- see
    // ComputerRepository.migrateLegacyTargetsIfNeeded). Either way this is
    // a no-op once categories already exist.
    LaunchedEffect(Unit) {
        if (!initialized) {
            initialized = true
            val result = ComputerRepository.ensureInitialized(context)
            if (result.didMigrate) {
                showMigrationNotice = true
            }
            refresh()
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {

        // --- HEADER ---
        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Text("TARGET COMPUTER", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = 2.sp)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("CATEGORIES", color = if(subMode=="CATEGORIES") primaryColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { subMode = "CATEGORIES" })
                Text("|", color = Color.DarkGray)
                Text("VISUALS", color = if(subMode=="VISUALS") primaryColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { subMode = "VISUALS" })
            }
        }

        if (subMode == "CATEGORIES") {
            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = "[GUIDE ME]",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .testTag(AckTags.COMPUTER_GUIDE_ME)
                    .helpTarget(AckTags.COMPUTER_GUIDE_ME, primaryColor)
                    .clickable {
                        wizardStartCategoryId = null
                        showWizard = true
                        reportHelpInteraction(AckTags.COMPUTER_GUIDE_ME)
                    }
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // --- SUB-MODE: CATEGORIES ---
        if (subMode == "CATEGORIES") {
            LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.weight(1f)
            ) {
                items(categories, key = { it.id }) { category ->
                    val activeLabel = category.activeNodeId?.let { ComputerRepository.findNode(category, it)?.label }

                    TargetCategoryChip(
                        category = category,
                        activeLabel = activeLabel,
                        primaryColor = primaryColor,
                        modifier = Modifier
                            .testTag(AckTags.TARGET_SLOT)
                            .helpTarget(AckTags.TARGET_SLOT, primaryColor),
                        onTap = {
                            openTreeCategoryId = category.id
                            reportHelpInteraction(AckTags.TARGET_SLOT)
                        },
                        onLongPress = { optionsCategory = category }
                    )
                }

                item {
                    AddCategoryTile(primaryColor = primaryColor) {
                        showAddCategory = true
                        reportHelpInteraction(AckTags.COMPUTER_ADD_CATEGORY)
                    }
                }
            }
        }

        // --- SUB-MODE: VISUALS ---
        if (subMode == "VISUALS") {
            VisualEditorView(context, primaryColor)
        }
    }

    if (showAddCategory) {
        AddCategoryDialog(
            primaryColor = primaryColor,
            onDismiss = { showAddCategory = false },
            onCreate = { label ->
                ComputerRepository.createCategory(context, label)
                showAddCategory = false
                refresh()
            }
        )
    }

    val editingOptions = optionsCategory
    if (editingOptions != null) {
        CategoryOptionsDialog(
            context = context,
            category = editingOptions,
            primaryColor = primaryColor,
            onDismiss = { optionsCategory = null },
            onChanged = { refresh() }
        )
    }

    val treeCategoryId = openTreeCategoryId
    if (treeCategoryId != null) {
        ComputerTreeWindow(
            context = context,
            primaryColor = primaryColor,
            categoryId = treeCategoryId,
            onDismiss = { openTreeCategoryId = null },
            onChanged = { refresh() }
        )
    }

    if (showWizard) {
        ComputerWizard(
            context = context,
            primaryColor = primaryColor,
            initialCategoryId = wizardStartCategoryId,
            onDismiss = { showWizard = false },
            onChanged = { refresh() }
        )
    }

    if (showMigrationNotice) {
        MigrationNoticeDialog(
            primaryColor = primaryColor,
            onDismiss = { showMigrationNotice = false },
            onStartWizard = {
                showMigrationNotice = false
                wizardStartCategoryId = "PEOPLE"
                showWizard = true
            }
        )
    }
}

// Opened by tapping the "COMPUTER:" status indicator in the app header.
// Lists every category's current active pick (or lack of one), with an
// inline CLEAR -- this dialog is about *current state*, not authoring, so
// it swaps RootOverrideStrip's usual EDIT button for CLEAR instead.
@Composable
fun ComputerSummaryDialog(
    context: Context,
    primaryColor: Color,
    onDismiss: () -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    val categories = remember(refreshKey) { ComputerRepository.getCategories(context) }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "TARGET COMPUTER STATUS",
        dismissLabel = "CLOSE"
    ) {
        if (categories.isEmpty()) {
            Text(
                text = "NO CATEGORIES YET.",
                color = Color.DarkGray,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                categories.forEach { category ->
                    val activeNode = category.activeNodeId?.let { ComputerRepository.findNode(category, it) }
                    val isActive = activeNode != null

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 52.dp)
                            .border(
                                1.dp,
                                if (isActive) primaryColor else Color.DarkGray,
                                CutCornerShape(6.dp)
                            )
                            .background(
                                if (isActive) primaryColor.copy(alpha = 0.08f) else Color.Transparent,
                                CutCornerShape(6.dp)
                            )
                            .padding(horizontal = 10.dp, vertical = 8.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = category.label.uppercase(),
                                color = if (isActive) primaryColor else Color.Gray,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold
                            )

                            Text(
                                text = activeNode?.label ?: "NOTHING SELECTED",
                                color = if (isActive) Color.White else Color.DarkGray,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace
                            )
                        }

                        if (isActive) {
                            Box(
                                modifier = Modifier
                                    .heightIn(min = 44.dp)
                                    .border(1.dp, DangerRed, CutCornerShape(4.dp))
                                    .clickable {
                                        ComputerRepository.clearActiveEntry(context, category.id)
                                        refreshKey++
                                    }
                                    .padding(horizontal = 10.dp, vertical = 8.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = "CLEAR",
                                    color = DangerRed,
                                    fontSize = 10.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun TargetCategoryChip(
    category: ComputerCategory,
    activeLabel: String?,
    primaryColor: Color,
    modifier: Modifier = Modifier,
    onTap: () -> Unit,
    onLongPress: () -> Unit
) {
    val isSet = activeLabel != null
    val borderColor = if (isSet) primaryColor else Color.DarkGray
    val bg = if (isSet) primaryColor.copy(alpha = 0.1f) else Color.Transparent

    Box(
        modifier = modifier
            .height(80.dp)
            .background(bg, CutCornerShape(8.dp))
            .border(1.dp, borderColor, CutCornerShape(8.dp))
            .combinedClickable(onClick = onTap, onLongClick = onLongPress)
            .padding(12.dp)
    ) {
        Text(
            text = category.label.uppercase(),
            color = Color.Gray,
            fontSize = 8.sp,
            fontFamily = FontFamily.Monospace,
            modifier = Modifier.align(Alignment.TopStart)
        )

        if (isSet) {
            Text(
                text = activeLabel!!.uppercase(),
                color = primaryColor,
                fontSize = 14.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.align(Alignment.Center)
            )
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
private fun AddCategoryTile(primaryColor: Color, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .height(80.dp)
            .fillMaxWidth()
            .testTag(AckTags.COMPUTER_ADD_CATEGORY)
            .helpTarget(AckTags.COMPUTER_ADD_CATEGORY, primaryColor)
            .border(1.dp, primaryColor.copy(alpha = 0.6f), CutCornerShape(8.dp))
            .background(primaryColor.copy(alpha = 0.06f), CutCornerShape(8.dp))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = "+ ADD\nCATEGORY",
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )
    }
}

@Composable
private fun AddCategoryDialog(
    primaryColor: Color,
    onDismiss: () -> Unit,
    onCreate: (String) -> Unit
) {
    var name by remember { mutableStateOf("") }
    val isValid = name.trim().isNotEmpty()

    TightDialogSurface(onDismiss = onDismiss, primaryColor = primaryColor, title = "ADD CATEGORY") {
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            placeholder = { Text("E.G. FEELINGS") },
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

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TightPanelButton("CREATE", Modifier.weight(1f), isActive = isValid, mainColor = primaryColor) {
                if (isValid) onCreate(name.trim())
            }
            TightPanelButton("CANCEL", Modifier.weight(1f), isActive = false, mainColor = primaryColor, onClick = onDismiss)
        }
    }
}

@Composable
private fun CategoryOptionsDialog(
    context: Context,
    category: ComputerCategory,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onChanged: () -> Unit
) {
    var name by remember(category.id) { mutableStateOf(category.label) }
    var persistUntilCleared by remember(category.id) { mutableStateOf(category.persistUntilCleared) }
    var confirmingDelete by remember { mutableStateOf(false) }
    val isValid = name.trim().isNotEmpty()

    TightDialogSurface(onDismiss = onDismiss, primaryColor = primaryColor, title = "CATEGORY OPTIONS") {
        TightSectionLabel("NAME")
        Spacer(modifier = Modifier.height(6.dp))
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
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
        TightSectionLabel("WHEN A PICK IS MADE")
        Spacer(modifier = Modifier.height(6.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TightPanelButton("KEEP IT", Modifier.weight(1f), isActive = persistUntilCleared, mainColor = primaryColor) {
                persistUntilCleared = true
            }
            TightPanelButton("CLEAR AFTER USE", Modifier.weight(1f), isActive = !persistUntilCleared, mainColor = primaryColor) {
                persistUntilCleared = false
            }
        }
        Text(
            text = if (persistUntilCleared) "Stays active until you clear it." else "Automatically clears the next time it's used.",
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            modifier = Modifier.padding(top = 4.dp)
        )

        Spacer(modifier = Modifier.height(16.dp))

        if (!confirmingDelete) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton("SAVE", Modifier.weight(1f), isActive = isValid, mainColor = primaryColor) {
                    if (isValid) {
                        ComputerRepository.saveCategory(
                            context,
                            category.copy(label = name.trim(), persistUntilCleared = persistUntilCleared)
                        )
                        onChanged()
                        onDismiss()
                    }
                }
                TightPanelButton("DELETE", Modifier.weight(1f), mainColor = DangerRed) {
                    confirmingDelete = true
                }
            }
        } else {
            Text(
                text = "This removes the whole category and everything in it. This cannot be undone.",
                color = Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(12.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton("CONFIRM DELETE", Modifier.weight(1f), mainColor = DangerRed) {
                    ComputerRepository.deleteCategory(context, category.id)
                    onChanged()
                    onDismiss()
                }
                TightPanelButton("CANCEL", Modifier.weight(1f), isActive = false, mainColor = primaryColor) {
                    confirmingDelete = false
                }
            }
        }
    }
}

@Composable
private fun MigrationNoticeDialog(
    primaryColor: Color,
    onDismiss: () -> Unit,
    onStartWizard: () -> Unit
) {
    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "TARGETS MOVED",
        dismissLabel = "LOOKS GOOD"
    ) {
        Text(
            text = "Your previously saved targets are now entries under PEOPLE. " +
                "Nothing was deleted, and a backup was taken automatically before " +
                "anything moved.",
            color = Color.Gray,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "Want help organizing them into subcategories?",
            color = Color.Gray,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TightPanelButton("START WIZARD", Modifier.weight(1f), mainColor = primaryColor, onClick = onStartWizard)
            TightPanelButton("I'LL DO IT MYSELF", Modifier.weight(1f), isActive = false, mainColor = primaryColor, onClick = onDismiss)
        }
    }
}
