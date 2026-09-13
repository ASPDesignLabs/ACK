package com.example.besu

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
// else. Both insert plain text at the caller's cursor (via onInsert) and
// never touch ComputerRepository's active-selection state -- browsing here
// never "turns the target computer on" the way using it from its own tab
// does. The browser deliberately reuses ComputerTreeWindow.kt's
// TreeVisualRow/flattenVisibleTree/ComputerTreeVisualRow/ComputerDropdownPath
// rendering pieces (widened from private to internal there) rather than
// duplicating the tree/dropdown drawing logic.

@Composable
fun TargetQuickAccessRow(
    context: Context,
    primaryColor: Color,
    onInsert: (String) -> Unit
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
                            .clickable { onInsert(node.label) }
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
    onInsert: (String) -> Unit
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

                LazyColumn(modifier = Modifier.heightIn(max = 260.dp)) {
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
                                    onInsert(row.node.label)
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
                        ComputerRepository.findNode(category, leafId)?.let { onInsert(it.label) }
                        // Deliberately does not reset dropdownPath -- the
                        // panel stays open at the same level so several
                        // entries can be inserted in a row.
                    }
                )
            }
        }
    }
}
