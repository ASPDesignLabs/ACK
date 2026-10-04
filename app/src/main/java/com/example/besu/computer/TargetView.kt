// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.computer

import com.example.besu.core.ComputerLabels
import com.example.besu.core.LabelKey
import com.example.besu.*
import com.example.besu.R
import com.example.besu.backup.*
import com.example.besu.help.*
import com.example.besu.output.*
import com.example.besu.ui.*
import com.example.besu.ui.theme.*
import android.content.Context
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.res.stringResource
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
    // categoryId to nodeId -- set from the tree window's [CARD] badge, its
    // EDIT ENTRY "OPEN CONTACT CARD" button, or a tap in the CONTACT CARDS
    // browser below. One piece of state at this level regardless of entry
    // point, so there's only ever one ContactCardDialog instantiation.
    var openContactCard by remember { mutableStateOf<Pair<String, String>?>(null) }

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
            Text(labelFor(LabelKey.TARGET_COMPUTER), color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, letterSpacing = looseSpacing(2.sp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.people_tab_categories), color = if(subMode=="CATEGORIES") primaryColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { subMode = "CATEGORIES" })
                Text("|", color = Color.DarkGray)
                Text(stringResource(R.string.people_tab_visuals), color = if(subMode=="VISUALS") primaryColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, modifier = Modifier.clickable { subMode = "VISUALS" })
            }
        }

        if (subMode == "CATEGORIES") {
            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = stringResource(R.string.people_guide_me),
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

            // Anchored below the grid (which already claims the flexible
            // space via weight(1f) above), not scrolling away with it --
            // every contact card across every category, reachable without
            // remembering which category and how deep it's nested in.
            val allCards = remember(refreshKey) { ComputerRepository.findAllContactCards(context) }
            if (allCards.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                ContactCardBrowserPanel(
                    primaryColor = primaryColor,
                    cards = allCards,
                    onOpen = { categoryId, nodeId -> openContactCard = categoryId to nodeId }
                )
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
            onChanged = { refresh() },
            onOpenContactCard = { nodeId -> openContactCard = treeCategoryId to nodeId }
        )
    }

    val cardTarget = openContactCard
    if (cardTarget != null) {
        val (cardCategoryId, cardNodeId) = cardTarget
        ContactCardDialog(
            context = context,
            primaryColor = primaryColor,
            categoryId = cardCategoryId,
            nodeId = cardNodeId,
            onDismiss = {
                openContactCard = null
                refresh()
            }
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

private data class ClearedRecord(
    val categoryId: String,
    val categoryLabel: String,
    val node: ComputerNode
)

// Opened by tapping the "COMPUTER:" status indicator in the app header.
// Lists every category's current active pick (or lack of one), with an
// inline CLEAR -- this dialog is about *current state*, not authoring, so
// it swaps RootOverrideStrip's usual EDIT button for CLEAR instead.
//
// CLEAR is gated behind a tap-to-confirm step (mirroring the two-step
// delete pattern used elsewhere in this file), and a confirmed clear leaves
// a one-tap UNDO in place until something else is cleared or the dialog is
// dismissed -- clearing a category's pick here is otherwise a single tap
// with no other recovery path.
@Composable
fun ComputerSummaryDialog(
    context: Context,
    primaryColor: Color,
    onDismiss: () -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    val categories = remember(refreshKey) { ComputerRepository.getCategories(context) }
    var confirmingClearId by remember { mutableStateOf<String?>(null) }
    var lastCleared by remember { mutableStateOf<ClearedRecord?>(null) }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = stringResource(R.string.people_summary_title),
        dismissLabel = stringResource(R.string.common_close)
    ) {
        val cleared = lastCleared

        if (cleared != null) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, primaryColor, CutCornerShape(6.dp))
                    .background(primaryColor.copy(alpha = 0.08f), CutCornerShape(6.dp))
                    .padding(horizontal = 10.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = stringResource(R.string.people_cleared, cleared.categoryLabel.uppercase(), cleared.node.label),
                    color = Color.White,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.weight(1f)
                )

                Text(
                    text = stringResource(R.string.common_undo),
                    color = primaryColor,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier
                        .heightIn(min = 44.dp)
                        .clickable {
                            ComputerRepository.setActiveEntry(context, cleared.categoryId, cleared.node.id)
                            lastCleared = null
                            refreshKey++
                        }
                        .padding(horizontal = 10.dp, vertical = 12.dp)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))
        }

        if (categories.isEmpty()) {
            Text(
                text = stringResource(R.string.people_no_categories),
                color = Color.DarkGray,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                categories.forEach { category ->
                    val activeNode = category.activeNodeId?.let { ComputerRepository.findNode(category, it) }
                    val isActive = activeNode != null
                    val isConfirming = confirmingClearId == category.id
                    // The name as shown (a default name in the chosen language); what is saved and tokens built from the id never change.
                    val shownName = categoryName(category)

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
                                text = shownName.uppercase(),
                                color = if (isActive) primaryColor else Color.Gray,
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold
                            )

                            Text(
                                text = if (isConfirming) {
                                    stringResource(R.string.people_clear_question, activeNode?.label.orEmpty())
                                } else {
                                    activeNode?.label ?: stringResource(R.string.people_nothing_selected)
                                },
                                color = if (isConfirming) DangerRed else if (isActive) Color.White else Color.DarkGray,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = if (isConfirming) FontWeight.Bold else FontWeight.Normal
                            )
                        }

                        if (isConfirming) {
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(
                                    text = stringResource(R.string.common_cancel),
                                    color = Color.Gray,
                                    fontSize = 10.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold,
                                    modifier = Modifier
                                        .heightIn(min = 44.dp)
                                        .clickable { confirmingClearId = null }
                                        .padding(horizontal = 8.dp, vertical = 12.dp)
                                )

                                Box(
                                    modifier = Modifier
                                        .heightIn(min = 44.dp)
                                        .border(1.dp, DangerRed, CutCornerShape(4.dp))
                                        .clickable {
                                            val node = activeNode
                                            if (node != null) {
                                                ComputerRepository.clearActiveEntry(context, category.id)
                                                lastCleared = ClearedRecord(category.id, shownName, node)
                                            }
                                            confirmingClearId = null
                                            refreshKey++
                                        }
                                        .padding(horizontal = 10.dp, vertical = 8.dp),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = stringResource(R.string.common_confirm),
                                        color = DangerRed,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        } else if (isActive) {
                            Box(
                                modifier = Modifier
                                    .heightIn(min = 44.dp)
                                    .border(1.dp, DangerRed, CutCornerShape(4.dp))
                                    .clickable { confirmingClearId = category.id }
                                    .padding(horizontal = 10.dp, vertical = 8.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = stringResource(R.string.common_clear),
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
            text = categoryName(category).uppercase(),
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
                text = stringResource(R.string.common_empty),
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
            text = stringResource(R.string.people_add_category_tile),
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )
    }
}

// Anchored strip below the categories grid listing every contact card
// across every category (ComputerRepository.findAllContactCards), split
// into NAMES/PLACES and sorted alphabetically -- reaching a card doesn't
// require remembering which category or how deep in its tree it lives.
// Only rendered at all once at least one card exists (see caller).
@Composable
private fun ContactCardBrowserPanel(
    primaryColor: Color,
    cards: List<ComputerRepository.ContactCardListing>,
    onOpen: (categoryId: String, nodeId: String) -> Unit
) {
    val names = remember(cards) {
        cards.filter { it.node.contactCard?.type == ContactCardType.PERSON }
            .sortedBy { it.node.label.uppercase() }
    }
    val places = remember(cards) {
        cards.filter { it.node.contactCard?.type == ContactCardType.PLACE }
            .sortedBy { listing -> (listing.node.contactCard?.name?.ifBlank { listing.node.label } ?: listing.node.label).uppercase() }
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(max = 180.dp)
            .border(1.dp, primaryColor.copy(alpha = 0.4f), CutCornerShape(8.dp))
            .background(primaryColor.copy(alpha = 0.04f), CutCornerShape(8.dp))
            .padding(10.dp)
    ) {
        Text(
            text = labelFor(LabelKey.CONTACT_CARDS),
            color = primaryColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = looseSpacing(1.sp)
        )

        Spacer(modifier = Modifier.height(6.dp))

        LazyColumn(modifier = Modifier.weight(1f, fill = false)) {
            if (names.isNotEmpty()) {
                item { ContactCardBrowserSectionLabel(stringResource(R.string.people_names)) }
                items(names, key = { it.node.id }) { listing ->
                    ContactCardBrowserRow(listing.node.label, primaryColor) {
                        onOpen(listing.categoryId, listing.node.id)
                    }
                }
            }
            if (places.isNotEmpty()) {
                item { ContactCardBrowserSectionLabel(stringResource(R.string.people_places)) }
                items(places, key = { it.node.id }) { listing ->
                    val displayName = listing.node.contactCard?.name?.ifBlank { listing.node.label } ?: listing.node.label
                    ContactCardBrowserRow(displayName, primaryColor) {
                        onOpen(listing.categoryId, listing.node.id)
                    }
                }
            }
        }
    }
}

@Composable
private fun ContactCardBrowserSectionLabel(text: String) {
    Text(
        text = text,
        color = Color.Gray,
        fontSize = 9.sp,
        fontFamily = FontFamily.Monospace,
        fontWeight = FontWeight.Bold,
        letterSpacing = looseSpacing(1.sp),
        modifier = Modifier.padding(top = 4.dp, bottom = 2.dp)
    )
}

@Composable
private fun ContactCardBrowserRow(label: String, primaryColor: Color, onTap: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 36.dp)
            .clickable(onClick = onTap)
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, color = Color.LightGray, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
        Text("›", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
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

    TightDialogSurface(onDismiss = onDismiss, primaryColor = primaryColor, title = labelFor(LabelKey.TARGET_ADD_CATEGORY)) {
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            placeholder = { Text(stringResource(R.string.people_example_category)) },
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
            TightPanelButton(stringResource(R.string.common_create), Modifier.weight(1f), isActive = isValid, mainColor = primaryColor) {
                if (isValid) onCreate(name.trim())
            }
            TightPanelButton(stringResource(R.string.common_cancel), Modifier.weight(1f), isActive = false, mainColor = primaryColor, onClick = onDismiss)
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
    // The field starts with the name as it is shown (a default name in the chosen language). Left untouched, saving keeps what was stored: a saved name is never rewritten.
    val shownAtStart = categoryName(category)
    var name by remember(category.id) { mutableStateOf(shownAtStart) }
    var persistUntilCleared by remember(category.id) { mutableStateOf(category.persistUntilCleared) }
    var confirmingDelete by remember { mutableStateOf(false) }
    val isValid = name.trim().isNotEmpty()

    TightDialogSurface(onDismiss = onDismiss, primaryColor = primaryColor, title = labelFor(LabelKey.TARGET_CATEGORY_OPTIONS)) {
        TightSectionLabel(stringResource(R.string.common_name))
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
        TightSectionLabel(stringResource(R.string.people_when_pick))
        Spacer(modifier = Modifier.height(6.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TightPanelButton(stringResource(R.string.people_keep_it), Modifier.weight(1f), isActive = persistUntilCleared, mainColor = primaryColor) {
                persistUntilCleared = true
            }
            TightPanelButton(stringResource(R.string.people_clear_after_use), Modifier.weight(1f), isActive = !persistUntilCleared, mainColor = primaryColor) {
                persistUntilCleared = false
            }
        }
        Text(
            text = stringResource(if (persistUntilCleared) R.string.people_keep_it_note else R.string.people_clear_after_use_note),
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            modifier = Modifier.padding(top = 4.dp)
        )

        Spacer(modifier = Modifier.height(16.dp))

        if (!confirmingDelete) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton(stringResource(R.string.common_save), Modifier.weight(1f), isActive = isValid, mainColor = primaryColor) {
                    if (isValid) {
                        ComputerRepository.saveCategory(
                            context,
                            category.copy(label = ComputerLabels.nameToSave(name.trim(), shownAtStart, category.label), persistUntilCleared = persistUntilCleared)
                        )
                        onChanged()
                        onDismiss()
                    }
                }
                TightPanelButton(stringResource(R.string.common_delete), Modifier.weight(1f), mainColor = DangerRed) {
                    confirmingDelete = true
                }
            }
        } else {
            Text(
                text = stringResource(R.string.people_delete_category_warning),
                color = Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(12.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton(stringResource(R.string.common_confirm_delete), Modifier.weight(1f), mainColor = DangerRed) {
                    ComputerRepository.deleteCategory(context, category.id)
                    onChanged()
                    onDismiss()
                }
                TightPanelButton(stringResource(R.string.common_cancel), Modifier.weight(1f), isActive = false, mainColor = primaryColor) {
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
        title = stringResource(R.string.people_migrated_title),
        dismissLabel = stringResource(R.string.people_migrated_ok)
    ) {
        Text(
            text = stringResource(R.string.people_migrated_body, ComputerLabels.defaultName(rememberText(), "PEOPLE")),
            color = Color.Gray,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = stringResource(R.string.people_migrated_help),
            color = Color.Gray,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TightPanelButton(stringResource(R.string.people_start_wizard), Modifier.weight(1f), mainColor = primaryColor, onClick = onStartWizard)
            TightPanelButton(stringResource(R.string.people_do_it_myself), Modifier.weight(1f), isActive = false, mainColor = primaryColor, onClick = onDismiss)
        }
    }
}
