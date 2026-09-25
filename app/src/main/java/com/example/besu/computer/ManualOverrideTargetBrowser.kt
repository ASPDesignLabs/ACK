package com.example.besu.computer

import com.example.besu.*
import com.example.besu.help.*
import com.example.besu.ui.*
import android.content.Context
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// Manual Override's Target Computer integration: a quick-tap row of
// currently-active picks, plus a full tree/dropdown browser for anything
// else. Neither touches ComputerRepository's active-selection state --
// browsing here never "turns the target computer on" the way using it from
// its own tab does. The browser deliberately reuses ComputerTreeWindow.kt's
// TreeVisualRow/flattenVisibleTree/ComputerTreeVisualRow/ComputerDropdownPath
// rendering pieces (widened from private to internal there) rather than
// duplicating the tree/dropdown drawing logic.
//
// onInsert hands back BOTH the picked category's id and the node's label --
// deliberately, so the caller decides what actually lands in the text field.
// Legacy Manual Override (TypeView) ignores the id and splices the literal
// label, exactly as it always has. The statement composer instead builds a
// [COMPUTER:id] token from the id, the same syntax TemplateEngine already
// resolves for Matrix/Quick Actions phrases -- so the SAME picker UI here
// serves both a "type it now" screen and a "save it for later, resolved
// live" screen without forking the browsing code.
//
// A chip in the quick row always represents the category's CURRENTLY
// ACTIVE entry, which is exactly what a [COMPUTER:id] token resolves to --
// so a tap there is the one place in this file safe to insert a token by
// default. TargetBrowsePanel below can browse to any entry, active or not,
// so a token from there could silently resolve to something other than
// what was picked; callers that want a live reference from a chip should
// build it from onInsert's categoryId, and literal text from anywhere
// else in this file.
//
// onLongPress (optional, default no-op) opens whatever the caller wants
// for retargeting a category's active entry -- e.g. the statement composer
// opens ComputerTreeWindow, the SAME dialog the Target Computer tab itself
// uses, so a long-press changes the active entry for real, across the
// whole app, not a composer-local copy of it. Left null, chips behave
// exactly as before (tap-to-insert only).

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun TargetQuickAccessRow(
    context: Context,
    primaryColor: Color,
    onInsert: (categoryId: String, label: String) -> Unit,
    onLongPress: ((categoryId: String) -> Unit)? = null
) {
    // No refresh key: this screen is recomposed fresh each time the user
    // navigates into Manual Override (switching tabs disposes/recreates it),
    // which is the only time active picks can realistically have changed --
    // this panel itself never sets one.
    val activePicks = remember {
        ComputerRepository.getCategories(context).mapNotNull { category ->
            val activeId = category.activeNodeId ?: return@mapNotNull null
            val node = ComputerRepository.findNode(category, activeId) ?: return@mapNotNull null
            category to node
        }
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AckTags.MANUAL_TARGET_QUICK_ROW)
            .helpTarget(AckTags.MANUAL_TARGET_QUICK_ROW, primaryColor)
    ) {
        TightSectionLabel("TARGET COMPUTER")
        Spacer(modifier = Modifier.height(6.dp))

        if (activePicks.isEmpty()) {
            Text(
                text = "NO ACTIVE TARGETS -- BROWSE TARGETS TO PICK ONE.",
                color = Color.DarkGray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace
            )
        } else {
            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                activePicks.forEach { (category, node) ->
                    Box(
                        modifier = Modifier
                            .widthIn(max = 140.dp)
                            .heightIn(min = 44.dp)
                            .border(1.dp, primaryColor, CutCornerShape(4.dp))
                            .background(primaryColor.copy(alpha = 0.10f), CutCornerShape(4.dp))
                            // Insertion always uses the full node.label --
                            // only the on-screen chip text below truncates.
                            .combinedClickable(
                                onClick = { onInsert(category.id, node.label) },
                                onLongClick = onLongPress?.let { callback ->
                                    { callback(category.id) }
                                }
                            )
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                        contentAlignment = Alignment.CenterStart
                    ) {
                        Column {
                            Text(
                                text = category.label.uppercase(),
                                color = primaryColor.copy(alpha = 0.7f),
                                fontSize = 8.sp,
                                fontFamily = FontFamily.Monospace,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            Text(
                                text = node.label,
                                color = primaryColor,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun TargetBrowsePanel(
    context: Context,
    primaryColor: Color,
    onInsert: (categoryId: String, label: String) -> Unit,
    // Threaded straight onto the TREE mode's own LazyColumn (not an outer
    // wrapper) so the caller can tighten the bound -- e.g. the header
    // takeover, which shares its vertical budget with the keyboard --
    // without risking the unbounded-height crash an indirect wrapper can.
    treeMaxHeight: androidx.compose.ui.unit.Dp = 260.dp
) {
    val categories = remember { ComputerRepository.getCategories(context) }
    var browseCategoryId by remember { mutableStateOf<String?>(null) }
    var displayMode by remember { mutableStateOf("TREE") } // TREE, DROPDOWN
    var expandedIds by remember { mutableStateOf<Set<String>>(emptySet()) }
    var dropdownPath by remember { mutableStateOf<List<String>>(emptyList()) }

    val category = browseCategoryId?.let { id -> categories.find { it.id == id } }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor.copy(alpha = 0.4f), CutCornerShape(8.dp))
            .background(primaryColor.copy(alpha = 0.04f), CutCornerShape(8.dp))
            .padding(10.dp)
    ) {
        if (category == null) {
            if (categories.isEmpty()) {
                Text(
                    text = "NO CATEGORIES YET. ADD SOME FROM THE TARGET COMPUTER TAB.",
                    color = Color.DarkGray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )
            } else {
                TightSectionLabel("PICK A CATEGORY")
                Spacer(modifier = Modifier.height(8.dp))

                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    categories.forEach { cat ->
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 44.dp)
                                .border(1.dp, primaryColor, CutCornerShape(6.dp))
                                .background(primaryColor.copy(alpha = 0.06f), CutCornerShape(6.dp))
                                .clickable {
                                    browseCategoryId = cat.id
                                    expandedIds = emptySet()
                                    dropdownPath = emptyList()
                                }
                                .padding(horizontal = 12.dp, vertical = 10.dp),
                            contentAlignment = Alignment.CenterStart
                        ) {
                            Text(
                                text = cat.label,
                                color = primaryColor,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        } else {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "← CATEGORIES",
                    color = Color.Gray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.clickable { browseCategoryId = null }
                )

                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    listOf("TREE", "DROPDOWN").forEach { mode ->
                        Text(
                            text = mode,
                            color = if (displayMode == mode) primaryColor else Color.Gray,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.clickable { displayMode = mode }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = category.label.uppercase(),
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(6.dp))

            if (category.root.children.isEmpty()) {
                Text(
                    text = "NOTHING HERE YET.",
                    color = Color.DarkGray,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(vertical = 12.dp)
                )
            } else if (displayMode == "TREE") {
                val visibleRows = remember(category, expandedIds) {
                    mutableListOf<TreeVisualRow>().apply {
                        flattenVisibleTree(category.root.children, 0, emptyList(), expandedIds, this)
                    }
                }

                LazyColumn(modifier = Modifier.heightIn(max = treeMaxHeight)) {
                    items(visibleRows, key = { it.node.id }) { row ->
                        ComputerTreeVisualRow(
                            row = row,
                            isActive = row.node.id == category.activeNodeId,
                            isExpanded = row.node.id in expandedIds,
                            primaryColor = primaryColor,
                            onTap = {
                                if (row.node.type == ComputerNodeType.CATEGORY) {
                                    expandedIds = if (row.node.id in expandedIds) {
                                        expandedIds - row.node.id
                                    } else {
                                        expandedIds + row.node.id
                                    }
                                } else {
                                    onInsert(category.id, row.node.label)
                                }
                            },
                            // Browse-and-insert only here -- editing stays
                            // exclusive to the Target Computer's own tab.
                            onLongPress = {}
                        )
                    }
                }
            } else {
                ComputerDropdownPath(
                    root = category.root,
                    pathNodes = dropdownPath.mapNotNull { ComputerRepository.findNode(category, it) },
                    primaryColor = primaryColor,
                    onPathChanged = { newPath -> dropdownPath = newPath },
                    onLeafPicked = { leafId ->
                        ComputerRepository.findNode(category, leafId)?.let { onInsert(category.id, it.label) }
                        // Deliberately does not reset dropdownPath -- the
                        // panel stays open at the same level so several
                        // entries can be inserted in a row.
                    }
                )
            }
        }
    }
}

// Takes over the app's whole header container (MainActivity's bordered
// ACK/DECK/PROFILE/COMPUTER box) while the software keyboard is visible on
// the Manual Override screen -- the header sits above the keyboard, so it's
// the one part of the screen guaranteed reachable without scrolling while
// typing. MainActivity swaps this in for the normal header content based on
// WindowInsets.isImeVisible && viewMode == "TYPE", and swaps back the
// instant the keyboard closes -- nothing here decides that, it only renders
// once asked to.
@Composable
fun ManualOverrideHeaderTakeover(
    context: Context,
    primaryColor: Color,
    onInsert: (categoryId: String, label: String) -> Unit,
    onLongPress: ((categoryId: String) -> Unit)? = null
) {
    var browseExpanded by remember { mutableStateOf(false) }
    val helpManager = LocalHelpManager.current

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AckTags.MANUAL_HEADER_TAKEOVER)
            .helpTarget(AckTags.MANUAL_HEADER_TAKEOVER, primaryColor)
    ) {
        Text(
            text = "QUICK INSERT MODE",
            color = primaryColor,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp
        )
        Text(
            text = "CLOSE THE KEYBOARD TO RETURN TO THE HEADER.",
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(10.dp))

        TargetQuickAccessRow(
            context = context,
            primaryColor = primaryColor,
            onInsert = onInsert,
            onLongPress = onLongPress
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = if (browseExpanded) "[HIDE FULL BROWSER]" else "[BROWSE ALL ENTRIES]",
            color = primaryColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            modifier = Modifier
                .testTag(AckTags.MANUAL_HEADER_BROWSE_TOGGLE)
                .helpTarget(AckTags.MANUAL_HEADER_BROWSE_TOGGLE, primaryColor)
                .clickable {
                    browseExpanded = !browseExpanded
                    helpManager?.onEvent(HelpEvent.Interacted(AckTags.MANUAL_HEADER_BROWSE_TOGGLE))
                }
        )

        if (browseExpanded) {
            Spacer(modifier = Modifier.height(8.dp))
            // Tighter cap than the below-field panel's default 260dp -- the
            // header shares its vertical budget with the keyboard and the
            // text field itself, not a whole screen on its own.
            TargetBrowsePanel(
                context = context,
                primaryColor = primaryColor,
                onInsert = onInsert,
                treeMaxHeight = 180.dp
            )
        }
    }
}
