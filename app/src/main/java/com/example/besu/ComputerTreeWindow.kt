package com.example.besu

import android.content.Context
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.VoidBlack

private val DangerRed = Color(0xFFFF0055)

// The drill-down/visualization screen for one root category's tree.
//
// Two independent bits of navigation state, on purpose:
//  - `expandedIds` + `addTargetNodeId` drive TREE mode (a real multi-level
//    diagram, not just "one level at a time") and double as "where does
//    + CATEGORY / + ENTRY add next."
//  - `dropdownPath` drives DROPDOWN mode's cascading selects, independent
//    of what's expanded in TREE mode, so switching modes mid-browse never
//    fights the other mode's idea of "where am I."
// Both modes call the exact same ComputerRepository mutation/selection
// functions -- only how you get there differs.
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun ComputerTreeWindow(
    context: Context,
    primaryColor: Color,
    categoryId: String,
    onDismiss: () -> Unit,
    onChanged: () -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    val category = remember(categoryId, refreshKey) {
        ComputerRepository.getCategories(context).find { it.id == categoryId }
    }

    LaunchedEffect(category) {
        if (category == null) onDismiss()
    }

    if (category == null) return

    var displayMode by remember(categoryId) { mutableStateOf("TREE") } // TREE, DROPDOWN

    var expandedIds by remember(categoryId) { mutableStateOf<Set<String>>(emptySet()) }
    var addTargetNodeId by remember(categoryId) { mutableStateOf<String?>(null) } // null = category root
    var dropdownPath by remember(categoryId) { mutableStateOf<List<String>>(emptyList()) }

    // Opening a category with an active pick expands straight to it, so
    // what's currently selected is visible without hunting for it. Runs
    // once per window (keyed on categoryId, not on every refresh).
    LaunchedEffect(categoryId) {
        val activeId = category.activeNodeId
        if (activeId != null) {
            expandedIds = ComputerRepository.findPath(category, activeId)
                .map { it.id }
                .toSet()
        }
    }

    var addDialogType by remember { mutableStateOf<ComputerNodeType?>(null) }
    var editingNode by remember { mutableStateOf<ComputerNode?>(null) }
    var showWizard by remember { mutableStateOf(false) }

    val helpManager = LocalHelpManager.current

    fun refresh() {
        refreshKey++
        onChanged()
    }

    fun selectOrClear(nodeId: String) {
        if (category.activeNodeId == nodeId) {
            ComputerRepository.clearActiveEntry(context, categoryId)
        } else {
            ComputerRepository.setActiveEntry(context, categoryId, nodeId)
        }
        refresh()
    }

    val addTargetNode = addTargetNodeId?.let { ComputerRepository.findNode(category, it) } ?: category.root

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = category.label,
        dismissLabel = "DONE"
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                modifier = Modifier
                    .testTag(AckTags.COMPUTER_TREE_WINDOW_MODE)
                    .helpTarget(AckTags.COMPUTER_TREE_WINDOW_MODE, primaryColor),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                listOf("TREE", "DROPDOWN").forEach { mode ->
                    Text(
                        text = mode,
                        color = if (displayMode == mode) primaryColor else Color.Gray,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.clickable {
                            displayMode = mode
                            helpManager?.onEvent(HelpEvent.Interacted(AckTags.COMPUTER_TREE_WINDOW_MODE))
                        }
                    )
                }
            }

            Text(
                text = "[GUIDE ME]",
                color = primaryColor,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.clickable { showWizard = true }
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        if (category.root.children.isEmpty()) {
            Text(
                text = "NOTHING HERE YET.",
                color = Color.DarkGray,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                modifier = Modifier.padding(vertical = 16.dp)
            )
        } else if (displayMode == "TREE") {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { addTargetNodeId = null }
                    .padding(vertical = 4.dp)
            ) {
                Text(
                    text = category.label.uppercase(),
                    color = if (addTargetNodeId == null) primaryColor else Color.Gray,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )
            }

            val visibleRows = remember(category, expandedIds) {
                mutableListOf<TreeVisualRow>().apply {
                    flattenVisibleTree(category.root.children, 0, emptyList(), expandedIds, this)
                }
            }

            LazyColumn(modifier = Modifier.heightIn(max = 340.dp)) {
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
                                addTargetNodeId = row.node.id
                            } else {
                                selectOrClear(row.node.id)
                            }
                        },
                        onLongPress = { editingNode = row.node }
                    )
                }
            }
        } else {
            ComputerDropdownPath(
                root = category.root,
                pathNodes = dropdownPath.mapNotNull { ComputerRepository.findNode(category, it) },
                primaryColor = primaryColor,
                onPathChanged = { newPath -> dropdownPath = newPath },
                onLeafPicked = { leafId -> selectOrClear(leafId) }
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        Text(
            text = "ADD TO: ${addTargetNode.label.uppercase()}",
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(6.dp))

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TightPanelButton("+ CATEGORY", Modifier.weight(1f), mainColor = primaryColor) {
                addDialogType = ComputerNodeType.CATEGORY
            }
            TightPanelButton("+ ENTRY", Modifier.weight(1f), mainColor = primaryColor) {
                addDialogType = ComputerNodeType.ENTRY
            }
        }
    }

    val addType = addDialogType
    if (addType != null) {
        AddTreeNodeDialog(
            primaryColor = primaryColor,
            parentLabel = addTargetNode.label,
            kind = addType,
            onDismiss = { addDialogType = null },
            onCreate = { label ->
                val created = ComputerRepository.addNode(context, categoryId, addTargetNode.id, label, addType)
                if (addType == ComputerNodeType.CATEGORY) {
                    expandedIds = expandedIds + addTargetNode.id
                    addTargetNodeId = created.id
                }
                addDialogType = null
                refresh()
            }
        )
    }

    if (showWizard) {
        ComputerWizard(
            context = context,
            primaryColor = primaryColor,
            initialCategoryId = categoryId,
            initialNodeId = addTargetNode.id,
            onDismiss = { showWizard = false },
            onChanged = { refresh() }
        )
    }

    val editing = editingNode
    if (editing != null) {
        EditTreeNodeDialog(
            node = editing,
            primaryColor = primaryColor,
            onDismiss = { editingNode = null },
            onRename = { newLabel ->
                ComputerRepository.renameNode(context, categoryId, editing.id, newLabel)
                editingNode = null
                refresh()
            },
            onDelete = {
                ComputerRepository.deleteNode(context, categoryId, editing.id)
                expandedIds = expandedIds - editing.id
                if (addTargetNodeId == editing.id) addTargetNodeId = null
                dropdownPath = dropdownPath.takeWhile { it != editing.id }
                editingNode = null
                refresh()
            }
        )
    }
}

private data class TreeVisualRow(
    val node: ComputerNode,
    val depth: Int,
    val isLastChild: Boolean,
    val ancestorContinues: List<Boolean>
)

private fun flattenVisibleTree(
    children: List<ComputerNode>,
    depth: Int,
    ancestorContinues: List<Boolean>,
    expandedIds: Set<String>,
    out: MutableList<TreeVisualRow>
) {
    children.forEachIndexed { index, node ->
        val isLast = index == children.lastIndex
        out.add(TreeVisualRow(node, depth, isLast, ancestorContinues))

        if (node.type == ComputerNodeType.CATEGORY && node.id in expandedIds && node.children.isNotEmpty()) {
            flattenVisibleTree(node.children, depth + 1, ancestorContinues + !isLast, expandedIds, out)
        }
    }
}

private fun connectorPrefix(row: TreeVisualRow): String {
    val sb = StringBuilder()
    for (i in 0 until row.depth) {
        sb.append(if (row.ancestorContinues.getOrElse(i) { false }) "│  " else "   ")
    }
    sb.append(if (row.isLastChild) "└─ " else "├─ ")
    return sb.toString()
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ComputerTreeVisualRow(
    row: TreeVisualRow,
    isActive: Boolean,
    isExpanded: Boolean,
    primaryColor: Color,
    onTap: () -> Unit,
    onLongPress: () -> Unit
) {
    val node = row.node
    val isCategory = node.type == ComputerNodeType.CATEGORY

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 40.dp)
            .combinedClickable(onClick = onTap, onLongClick = onLongPress)
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = connectorPrefix(row),
            color = Color.DarkGray,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )

        Text(
            text = when {
                isCategory && isExpanded -> "▾ "
                isCategory -> "▸ "
                else -> ""
            },
            color = Color.Gray,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace
        )

        Text(
            text = node.label,
            color = if (isActive) primaryColor else if (isCategory) Color.White else Color.LightGray,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = if (isActive || isCategory) FontWeight.Bold else FontWeight.Normal,
            modifier = Modifier.weight(1f)
        )

        if (isActive) {
            Text(
                text = "ACTIVE",
                color = primaryColor,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }
    }
}

// One dropdown per depth level of the currently-chosen path, stacked
// vertically -- picking a category reveals the next level's dropdown,
// picking an entry commits it. Styled per the existing DropdownMenu
// precedent in GeoProtocolView.kt (Graphite background, primaryColor text).
@Composable
private fun ComputerDropdownPath(
    root: ComputerNode,
    pathNodes: List<ComputerNode>,
    primaryColor: Color,
    onPathChanged: (List<String>) -> Unit,
    onLeafPicked: (String) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        var parent = root

        for (level in 0..pathNodes.size) {
            if (parent.children.isEmpty()) break

            val selected = pathNodes.getOrNull(level)

            ComputerDropdownLevel(
                label = "LEVEL ${level + 1}",
                options = parent.children,
                selected = selected,
                primaryColor = primaryColor,
                onSelect = { node ->
                    if (node.type == ComputerNodeType.CATEGORY) {
                        onPathChanged(pathNodes.take(level).map { it.id } + node.id)
                    } else {
                        onLeafPicked(node.id)
                    }
                }
            )

            if (selected == null) break
            parent = selected
        }
    }
}

@Composable
private fun ComputerDropdownLevel(
    label: String,
    options: List<ComputerNode>,
    selected: ComputerNode?,
    primaryColor: Color,
    onSelect: (ComputerNode) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }

    Column {
        Text(text = label, color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace)

        Spacer(modifier = Modifier.height(4.dp))

        Box {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 44.dp)
                    .border(1.dp, primaryColor, CutCornerShape(6.dp))
                    .background(primaryColor.copy(alpha = 0.08f), CutCornerShape(6.dp))
                    .clickable { expanded = true }
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = selected?.label?.uppercase() ?: "SELECT...",
                    color = if (selected != null) primaryColor else Color.DarkGray,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold
                )

                Text(text = "▾", color = primaryColor, fontSize = 10.sp)
            }

            DropdownMenu(
                expanded = expanded,
                onDismissRequest = { expanded = false },
                modifier = Modifier.background(Graphite)
            ) {
                options.forEach { option ->
                    DropdownMenuItem(
                        text = {
                            val suffix = if (option.type == ComputerNodeType.CATEGORY) " >" else ""
                            Text(
                                text = "${option.label}$suffix",
                                color = primaryColor,
                                fontFamily = FontFamily.Monospace
                            )
                        },
                        onClick = {
                            expanded = false
                            onSelect(option)
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun AddTreeNodeDialog(
    primaryColor: Color,
    parentLabel: String,
    kind: ComputerNodeType,
    onDismiss: () -> Unit,
    onCreate: (label: String) -> Unit
) {
    var name by remember { mutableStateOf("") }
    val isValid = name.trim().isNotEmpty()

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = if (kind == ComputerNodeType.CATEGORY) "ADD CATEGORY" else "ADD ENTRY",
        subtitle = "UNDER: ${parentLabel.uppercase()}"
    ) {
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            placeholder = { Text(if (kind == ComputerNodeType.CATEGORY) "E.G. FRIENDS" else "E.G. MOM") },
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
private fun EditTreeNodeDialog(
    node: ComputerNode,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onRename: (String) -> Unit,
    onDelete: () -> Unit
) {
    var name by remember(node.id) { mutableStateOf(node.label) }
    var confirmingDelete by remember { mutableStateOf(false) }
    val isValid = name.trim().isNotEmpty()

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = if (node.type == ComputerNodeType.CATEGORY) "EDIT CATEGORY" else "EDIT ENTRY"
    ) {
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

        if (!confirmingDelete) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton("SAVE NAME", Modifier.weight(1f), isActive = isValid, mainColor = primaryColor) {
                    if (isValid) onRename(name.trim())
                }
                TightPanelButton("DELETE", Modifier.weight(1f), mainColor = DangerRed, onClick = { confirmingDelete = true })
            }
        } else {
            val descendantCount = countDescendants(node)

            Text(
                text = if (descendantCount > 0) {
                    "This also removes $descendantCount item(s) nested inside it. This cannot be undone."
                } else {
                    "This cannot be undone."
                },
                color = Color.Gray,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(12.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton("CONFIRM DELETE", Modifier.weight(1f), mainColor = DangerRed, onClick = onDelete)
                TightPanelButton("CANCEL", Modifier.weight(1f), isActive = false, mainColor = primaryColor) {
                    confirmingDelete = false
                }
            }
        }
    }
}

private fun countDescendants(node: ComputerNode): Int {
    var count = 0
    for (child in node.children) {
        count += 1 + countDescendants(child)
    }
    return count
}
