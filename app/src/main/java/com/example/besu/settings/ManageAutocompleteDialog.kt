package com.example.besu.settings

import com.example.besu.AckTags
import com.example.besu.data.*
import com.example.besu.decks.*
import com.example.besu.help.*
import com.example.besu.ui.*
import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// PROTOCOL -> "MANAGE AUTOCOMPLETE": every remembered autocomplete value in
// the app -- Matrix local variables, Quick Actions local variables, and
// Shared Root Variables -- browsed as a drill-down tree (same ASCII-
// connector style as MANAGE RECORDINGS), grouped by how each field type is
// actually scoped: Matrix as Deck > Profile > Pose > Node > Variable, Quick
// Actions as Deck > Group > Slot > Variable, Shared Root Variables as
// Category > Tag (no deck/profile level -- those values are already global,
// matching how they resolve today). A leaf lists its remembered values as
// removable rows, plus a "clear this field's history" action; a broad
// clear-everything action sits below the tree, same one PROTOCOL's old
// AUTOCOMPLETE section offered directly.

private sealed class AcTreeNode {
    abstract val id: String
    abstract val label: String
}

private data class AcBranch(
    override val id: String,
    override val label: String,
    val children: List<AcTreeNode>
) : AcTreeNode()

private data class AcLeaf(
    override val id: String,
    override val label: String,
    val scopeKey: String,
    val scope: AutocompleteScope
) : AcTreeNode()

private data class AcTreeVisualRow(
    val node: AcTreeNode,
    val depth: Int,
    val isLastChild: Boolean,
    val ancestorContinues: List<Boolean>
)

private fun flattenVisibleAutocompleteTree(
    nodes: List<AcTreeNode>,
    expandedIds: Set<String>,
    depth: Int = 0,
    ancestorContinues: List<Boolean> = emptyList()
): List<AcTreeVisualRow> {
    val rows = mutableListOf<AcTreeVisualRow>()
    nodes.forEachIndexed { index, node ->
        val isLast = index == nodes.lastIndex
        rows.add(AcTreeVisualRow(node, depth, isLast, ancestorContinues))
        if (node is AcBranch && node.id in expandedIds) {
            rows.addAll(
                flattenVisibleAutocompleteTree(node.children, expandedIds, depth + 1, ancestorContinues + !isLast)
            )
        }
    }
    return rows
}

private fun acConnectorPrefix(row: AcTreeVisualRow): String {
    val sb = StringBuilder()
    for (i in 0 until row.depth) {
        sb.append(if (row.ancestorContinues.getOrElse(i) { false }) "│  " else "   ")
    }
    sb.append(if (row.isLastChild) "└─ " else "├─ ")
    return sb.toString()
}

// Deck > Profile > Pose > Node > Variable (Matrix), Deck > Group > Slot >
// Variable (Quick Actions), Category > Tag (Shared Root Variables). Only
// branches that actually lead to a remembered value are built -- same
// "browser for what exists" convention as MANAGE RECORDINGS' tree.
private fun buildAutocompleteTree(
    context: Context,
    scopes: List<Pair<String, AutocompleteScope>>
): List<AcTreeNode> {
    val kinds = mutableListOf<AcTreeNode>()

    val matrixScopes = scopes.filter { it.second.info.fieldType == AutocompleteScopeInfo.TYPE_MATRIX }
    if (matrixScopes.isNotEmpty()) {
        val deckBranches = matrixScopes.groupBy { it.second.info.deckId ?: "DEFAULT" }.map { (deckId, deckScopes) ->
            val deckName = CommandRepository.getDeckName(context, deckId)
            val profileBranches = deckScopes.groupBy { it.second.info.profile ?: "DEFAULT" }.map { (profile, profileScopes) ->
                val poseBranches = profileScopes.groupBy { (_, scope) ->
                    scope.info.storagePath?.let { CommandRepository.findMatrixNode(context, it)?.category } ?: "UNKNOWN"
                }.map { (pose, poseScopes) ->
                    val nodeBranches = poseScopes.groupBy { it.second.info.storagePath ?: "" }.map { (path, nodeScopes) ->
                        val nodeLabel = CommandRepository.findMatrixNode(context, path)?.label ?: "UNKNOWN NODE"
                        val tags = TemplateEngine.getVariableTags(
                            CommandRepository.getPhrase(context, path, deckId, profile)
                        )
                        val varLeaves = nodeScopes.map { (scopeKey, scope) ->
                            val slotIndex = scope.info.slotIndex ?: 0
                            val tag = tags.getOrNull(slotIndex)
                            val label = if (tag == null) {
                                "VARIABLE ${slotIndex + 1}"
                            } else {
                                "VARIABLE ${slotIndex + 1} // ROOT $tag"
                            }
                            AcLeaf(id = "leaf_$scopeKey", label = label, scopeKey = scopeKey, scope = scope)
                        }.sortedBy { it.label }
                        AcBranch(id = "mtx_node_${deckId}_${profile}_$path", label = nodeLabel, children = varLeaves)
                    }.sortedBy { it.label }
                    AcBranch(id = "mtx_${deckId}_${profile}_$pose", label = pose, children = nodeBranches)
                }.sortedBy { it.label }
                AcBranch(id = "mtx_${deckId}_$profile", label = profile, children = poseBranches)
            }.sortedBy { it.label }
            AcBranch(id = "mtx_deck_$deckId", label = deckName, children = profileBranches)
        }.sortedBy { it.label }
        kinds.add(AcBranch(id = "kind_mtx", label = "MATRIX (${matrixScopes.size})", children = deckBranches))
    }

    val qaScopes = scopes.filter { it.second.info.fieldType == AutocompleteScopeInfo.TYPE_QUICK_ACTION }
    if (qaScopes.isNotEmpty()) {
        val deckBranches = qaScopes.groupBy { it.second.info.deckId ?: "DEFAULT" }.map { (deckId, deckScopes) ->
            val deckName = CommandRepository.getDeckName(context, deckId)
            val config = CommandRepository.getQuickActionsConfig(context, deckId)
            val groupBranches = deckScopes.groupBy { it.second.info.groupIndex ?: 0 }.map { (groupIndex, groupScopes) ->
                val group = config.groups.find { it.groupIndex == groupIndex }
                val groupLabel = group?.label ?: "G${groupIndex + 1}"
                val slotBranches = groupScopes.groupBy { it.second.info.slotIndex ?: 0 }.map { (slotIndex, slotScopes) ->
                    val slot = group?.slots?.find { it.slotIndex == slotIndex }
                    val slotLabel = slot?.label ?: "SLOT ${slotIndex + 1}"
                    val tags = TemplateEngine.getVariableTags(slot?.template.orEmpty())
                    val tagLeaves = slotScopes.map { (scopeKey, scope) ->
                        val tagIndex = scope.info.tagIndex ?: 0
                        val tag = tags.getOrNull(tagIndex)
                        val label = tag?.let { "VAR:$it" } ?: "VAR ${tagIndex + 1}"
                        AcLeaf(id = "leaf_$scopeKey", label = label, scopeKey = scopeKey, scope = scope)
                    }.sortedBy { it.label }
                    AcBranch(id = "qa_slot_${deckId}_${groupIndex}_$slotIndex", label = slotLabel, children = tagLeaves)
                }.sortedBy { it.label }
                AcBranch(id = "qa_${deckId}_g$groupIndex", label = groupLabel, children = slotBranches)
            }.sortedBy { it.label }
            AcBranch(id = "qa_deck_$deckId", label = deckName, children = groupBranches)
        }.sortedBy { it.label }
        kinds.add(AcBranch(id = "kind_qa", label = "QUICK ACTIONS (${qaScopes.size})", children = deckBranches))
    }

    val rootScopes = scopes.filter { it.second.info.fieldType == AutocompleteScopeInfo.TYPE_ROOT_OVERRIDE }
    if (rootScopes.isNotEmpty()) {
        val categoryBranches = rootScopes.groupBy { it.second.info.category ?: "UNKNOWN" }.map { (category, catScopes) ->
            val tagLeaves = catScopes.map { (scopeKey, scope) ->
                val tag = scope.info.tag ?: "?"
                AcLeaf(id = "leaf_$scopeKey", label = "TAG $tag", scopeKey = scopeKey, scope = scope)
            }.sortedBy { it.label }
            AcBranch(id = "root_$category", label = category, children = tagLeaves)
        }.sortedBy { it.label }
        kinds.add(
            AcBranch(id = "kind_root", label = "SHARED ROOT VARIABLES (${rootScopes.size})", children = categoryBranches)
        )
    }

    return kinds
}

@Composable
fun ManageAutocompleteDialog(
    context: Context,
    primaryColor: Color,
    onDismiss: () -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    val scopes = remember(refreshKey) { AutocompleteHistoryRepository.listAllScopes(context) }
    val tree = remember(refreshKey) { buildAutocompleteTree(context, scopes) }

    var expandedIds by remember { mutableStateOf<Set<String>>(emptySet()) }
    var confirmingClearKey by remember { mutableStateOf<String?>(null) }
    var confirmingClearAll by remember { mutableStateOf(false) }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "MANAGE AUTOCOMPLETE",
        subtitle = "${scopes.size} FIELD${if (scopes.size == 1) "" else "S"} REMEMBERED"
    ) {
        if (scopes.isEmpty()) {
            Text(
                "NOTHING REMEMBERED YET. START TYPING INTO A MATRIX NODE'S VARIABLE, A QUICK ACTIONS SLOT'S VARIABLE, OR A SHARED ROOT VARIABLE -- ACK REMEMBERS IT HERE.",
                color = Color.DarkGray,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )
        } else {
            Column(
                modifier = Modifier
                    .heightIn(max = 460.dp)
                    .testTag(AckTags.AUTOCOMPLETE_MANAGE_TREE)
                    .helpTarget(AckTags.AUTOCOMPLETE_MANAGE_TREE, primaryColor)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                flattenVisibleAutocompleteTree(tree, expandedIds).forEach { row ->
                    when (val node = row.node) {
                        is AcBranch -> {
                            val isExpanded = node.id in expandedIds
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        expandedIds = if (isExpanded) expandedIds - node.id else expandedIds + node.id
                                    }
                                    .padding(vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = acConnectorPrefix(row) + (if (isExpanded) "▾ " else "▸ ") + node.label,
                                    color = if (isExpanded) primaryColor else Color.LightGray,
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = if (row.depth == 0) FontWeight.Bold else FontWeight.Normal
                                )
                            }
                        }
                        is AcLeaf -> {
                            AcTreeLeafCard(
                                row = row,
                                leaf = node,
                                primaryColor = primaryColor,
                                onValueRemoved = { value ->
                                    AutocompleteHistoryRepository.removeValue(context, node.scopeKey, value)
                                    refreshKey++
                                },
                                onClearRequested = { confirmingClearKey = node.scopeKey }
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            TightPanelButton(
                text = "CLEAR ALL AUTOCOMPLETE HISTORY",
                modifier = Modifier.fillMaxWidth(),
                mainColor = RadicalRed,
                onClick = { confirmingClearAll = true }
            )
        }
    }

    val clearingKey = confirmingClearKey
    if (clearingKey != null) {
        TightDialogSurface(
            onDismiss = { confirmingClearKey = null },
            primaryColor = RadicalRed,
            title = "CLEAR FIELD HISTORY",
            dismissLabel = "CANCEL"
        ) {
            Text(
                "This removes every remembered value for this one field. Nothing else is affected. This cannot be undone.",
                color = Color.White,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton("CLEAR", Modifier.weight(1f), mainColor = RadicalRed) {
                    AutocompleteHistoryRepository.clearScope(context, clearingKey)
                    confirmingClearKey = null
                    refreshKey++
                }
                TightPanelButton("CANCEL", Modifier.weight(1f), isActive = false, mainColor = primaryColor) {
                    confirmingClearKey = null
                }
            }
        }
    }

    if (confirmingClearAll) {
        TightDialogSurface(
            onDismiss = { confirmingClearAll = false },
            primaryColor = RadicalRed,
            title = "CLEAR ALL AUTOCOMPLETE HISTORY",
            dismissLabel = "CANCEL"
        ) {
            Text(
                "This removes every remembered value for every Matrix, Quick Actions, and Shared Root Variable field. This cannot be undone.",
                color = Color.White,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TightPanelButton("CLEAR ALL", Modifier.weight(1f), mainColor = RadicalRed) {
                    AutocompleteHistoryRepository.clearAll(context)
                    confirmingClearAll = false
                    refreshKey++
                }
                TightPanelButton("CANCEL", Modifier.weight(1f), isActive = false, mainColor = primaryColor) {
                    confirmingClearAll = false
                }
            }
        }
    }
}

@Composable
private fun AcTreeLeafCard(
    row: AcTreeVisualRow,
    leaf: AcLeaf,
    primaryColor: Color,
    onValueRemoved: (String) -> Unit,
    onClearRequested: () -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = acConnectorPrefix(row) + leaf.label,
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = (row.depth * 14).dp, top = 2.dp)
                .testTag(AckTags.AUTOCOMPLETE_MANAGE_LEAF)
                .helpTarget(AckTags.AUTOCOMPLETE_MANAGE_LEAF, primaryColor)
                .border(1.dp, primaryColor.copy(alpha = 0.4f), AckHelpShape)
                .background(primaryColor.copy(alpha = 0.05f), AckHelpShape)
                .padding(10.dp)
        ) {
            leaf.scope.entries
                .sortedWith(compareByDescending<AutocompleteEntry> { it.count }.thenByDescending { it.lastUsedAt })
                .forEach { entry ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 2.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = entry.value,
                            color = Color.White,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            modifier = Modifier.weight(1f)
                        )
                        Text(
                            text = "[X]",
                            color = RadicalRed,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .padding(start = 8.dp)
                                .clickable { onValueRemoved(entry.value) }
                        )
                    }
                }

            Spacer(modifier = Modifier.height(8.dp))

            TightPanelButton(
                text = "CLEAR THIS FIELD'S HISTORY",
                modifier = Modifier.fillMaxWidth(),
                mainColor = RadicalRed,
                onClick = onClearRequested
            )
        }
    }
}
