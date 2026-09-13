package com.example.besu

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CutCornerShape
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
import com.example.besu.ui.theme.VoidBlack

// The guided counterpart to manually editing a tree in ComputerTreeWindow --
// same underlying ComputerRepository calls, just sequenced so the user is
// always offered "what's next" instead of having to re-navigate after every
// add. Adding a subcategory travels into it (build a branch depth-first);
// adding an entry stays put (add several siblings in a row). Reachable with
// or without a starting category already chosen, so it works both as the
// first-run migration follow-up and as an anytime "GUIDE ME" entry point.
@Composable
fun ComputerWizard(
    context: Context,
    primaryColor: Color,
    initialCategoryId: String?,
    // Lets a "GUIDE ME" launched from inside ComputerTreeWindow continue
    // from wherever the user was already focused, instead of always
    // restarting at that category's root.
    initialNodeId: String? = null,
    onDismiss: () -> Unit,
    onChanged: () -> Unit
) {
    var refreshKey by remember { mutableIntStateOf(0) }
    var categoryId by remember { mutableStateOf(initialCategoryId) }
    var pathStack by remember {
        mutableStateOf(
            run {
                if (initialCategoryId == null || initialNodeId == null) return@run emptyList<String>()
                val startCategory = ComputerRepository.getCategories(context).find { it.id == initialCategoryId }
                    ?: return@run emptyList<String>()
                ComputerRepository.findPath(startCategory, initialNodeId).drop(1).map { it.id }
            }
        )
    }
    var pendingAddType by remember { mutableStateOf<ComputerNodeType?>(null) }
    var newCategoryMode by remember { mutableStateOf(false) }

    val categories = remember(refreshKey) { ComputerRepository.getCategories(context) }
    val category = categoryId?.let { id -> categories.find { it.id == id } }

    fun refresh() {
        refreshKey++
        onChanged()
    }

    TightDialogSurface(
        onDismiss = onDismiss,
        primaryColor = primaryColor,
        title = "GUIDED SETUP",
        subtitle = category?.let { "IN ${it.label.uppercase()}" },
        dismissLabel = "FINISH"
    ) {
        if (category == null) {
            // --- STEP: PICK OR CREATE A CATEGORY TO START ---
            if (!newCategoryMode) {
                Text(
                    text = "Pick a category to build, or start a new one.",
                    color = Color.Gray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(12.dp))

                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    categories.forEach { cat ->
                        WizardOptionRow(label = cat.label, primaryColor = primaryColor) {
                            categoryId = cat.id
                            pathStack = emptyList()
                        }
                    }

                    WizardOptionRow(label = "+ NEW CATEGORY", primaryColor = primaryColor) {
                        newCategoryMode = true
                    }
                }
            } else {
                WizardNameStep(
                    primaryColor = primaryColor,
                    prompt = "NAME THE NEW CATEGORY",
                    placeholder = "E.G. FEELINGS",
                    onCancel = { newCategoryMode = false },
                    onCreate = { label ->
                        val created = ComputerRepository.createCategory(context, label)
                        categoryId = created.id
                        pathStack = emptyList()
                        newCategoryMode = false
                        refresh()
                    }
                )
            }
        } else {
            val currentNode = pathStack.lastOrNull()
                ?.let { ComputerRepository.findNode(category, it) }
                ?: category.root

            if (pendingAddType == null) {
                // --- STEP: WHAT'S NEXT AT THE CURRENT LEVEL ---
                Text(
                    text = "ADDING TO: ${currentNode.label.uppercase()}",
                    color = Color.Gray,
                    fontSize = 10.sp,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(12.dp))

                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    WizardOptionRow(label = "+ ADD SUBCATEGORY HERE", primaryColor = primaryColor) {
                        pendingAddType = ComputerNodeType.CATEGORY
                    }
                    WizardOptionRow(label = "+ ADD ENTRY HERE", primaryColor = primaryColor) {
                        pendingAddType = ComputerNodeType.ENTRY
                    }
                    if (pathStack.isNotEmpty()) {
                        WizardOptionRow(label = "↑ UP ONE LEVEL", primaryColor = primaryColor) {
                            pathStack = pathStack.dropLast(1)
                        }
                    }
                }
            } else {
                val addType = pendingAddType

                WizardNameStep(
                    primaryColor = primaryColor,
                    prompt = if (addType == ComputerNodeType.CATEGORY) "NAME THE NEW SUBCATEGORY" else "NAME THE NEW ENTRY",
                    placeholder = if (addType == ComputerNodeType.CATEGORY) "E.G. FRIENDS" else "E.G. MOM",
                    onCancel = { pendingAddType = null },
                    onCreate = { label ->
                        val created = ComputerRepository.addNode(
                            context,
                            category.id,
                            currentNode.id,
                            label,
                            addType!!
                        )

                        if (addType == ComputerNodeType.CATEGORY) {
                            pathStack = pathStack + created.id
                        }

                        pendingAddType = null
                        refresh()
                    }
                )
            }
        }
    }
}

@Composable
private fun WizardOptionRow(label: String, primaryColor: Color, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .border(1.dp, primaryColor, CutCornerShape(6.dp))
            .background(primaryColor.copy(alpha = 0.08f), CutCornerShape(6.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        contentAlignment = Alignment.CenterStart
    ) {
        Text(
            text = label,
            color = primaryColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
    }
}

@Composable
private fun WizardNameStep(
    primaryColor: Color,
    prompt: String,
    placeholder: String,
    onCancel: () -> Unit,
    onCreate: (String) -> Unit
) {
    var name by remember { mutableStateOf("") }
    val isValid = name.trim().isNotEmpty()

    TightSectionLabel(prompt)

    Spacer(modifier = Modifier.height(8.dp))

    OutlinedTextField(
        value = name,
        onValueChange = { name = it },
        placeholder = { Text(placeholder) },
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
        TightPanelButton("BACK", Modifier.weight(1f), isActive = false, mainColor = primaryColor, onClick = onCancel)
    }
}
