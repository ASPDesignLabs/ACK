package com.example.besu

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.VoidBlack

@Composable
fun HelpMenuDialog(
    modules: List<HelpModule>,
    context: HelpContext,
    primaryColor: Color,
    initialCategory: HelpCategory? = null,
    onDismiss: () -> Unit,
    onLaunch: (HelpModule) -> Unit
) {
    var selectedCategory by remember(
        context.deckType,
        initialCategory
    ) {
        mutableStateOf(
            initialCategory ?: defaultHelpCategory(context)
        )
    }

    val visibleModules: List<HelpModule> = modules.filter { module ->
        module.category == selectedCategory
    }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(
            usePlatformDefaultWidth = false
        )
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            contentAlignment = Alignment.Center
        ) {
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .widthIn(max = 680.dp)
                    .border(
                        width = 1.dp,
                        color = primaryColor,
                        shape = AckHelpShape
                    ),
                color = Graphite,
                shape = AckHelpShape
            ) {
                Column {
                    HelpHeader(
                        title = "ACK // HELP SYSTEM",
                        subtitle = "TRAINING MODULES AND REFERENCE PROTOCOLS",
                        primaryColor = primaryColor,
                        rightLabel = "[CLOSE]",
                        onRightClick = onDismiss
                    )

                    HorizontalDivider(
                        color = primaryColor.copy(alpha = 0.35f)
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    Text(
                        text = "SELECT MODULE FAMILY",
                        color = Color.Gray,
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace,
                        letterSpacing = 1.sp,
                        modifier = Modifier.padding(horizontal = 14.dp)
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    LazyRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(
                            horizontal = 14.dp
                        )
                    ) {
                        items<HelpCategory>(
                            items = HelpCategory.values().toList()
                        ) { category: HelpCategory ->
                            HelpCategoryChip(
                                category = category,
                                isSelected = category == selectedCategory,
                                primaryColor = primaryColor,
                                onClick = {
                                    selectedCategory = category
                                }
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(VoidBlack.copy(alpha = 0.45f))
                            .padding(horizontal = 14.dp, vertical = 10.dp)
                    ) {
                        Text(
                            text = selectedCategory.title,
                            color = primaryColor,
                            fontSize = 11.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            letterSpacing = 1.sp
                        )

                        Spacer(modifier = Modifier.height(4.dp))

                        Text(
                            text = selectedCategory.subtitle,
                            color = Color.Gray,
                            fontSize = 9.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }

                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 380.dp)
                            .padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        if (visibleModules.isEmpty()) {
                            item {
                                HelpEmptyState(primaryColor)
                            }
                        }

                        items(
                            items = visibleModules,
                            key = { module -> module.id }
                        ) { module ->
                            HelpModuleMenuItem(
                                module = module,
                                primaryColor = primaryColor,
                                onClick = {
                                    onLaunch(module)
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun HelpHeader(
    title: String,
    subtitle: String,
    primaryColor: Color,
    rightLabel: String,
    onRightClick: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(14.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                color = primaryColor,
                fontSize = 15.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black,
                letterSpacing = 1.5.sp
            )

            Spacer(modifier = Modifier.height(5.dp))

            Text(
                text = subtitle,
                color = Color.Gray,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 0.8.sp
            )
        }

        Text(
            text = rightLabel,
            color = Color.Gray,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            modifier = Modifier
                .clickable(onClick = onRightClick)
                .padding(start = 12.dp, top = 4.dp)
        )
    }
}

@Composable
private fun HelpCategoryChip(
    category: HelpCategory,
    isSelected: Boolean,
    primaryColor: Color,
    onClick: () -> Unit
) {
    val borderColor = if (isSelected) Color.White else primaryColor.copy(
        alpha = 0.5f
    )

    val textColor = if (isSelected) Color.White else primaryColor

    Box(
        modifier = Modifier
            .border(
                width = 1.dp,
                color = borderColor,
                shape = AckHelpShape
            )
            .background(
                color = if (isSelected) {
                    primaryColor.copy(alpha = 0.16f)
                } else {
                    Color.Transparent
                },
                shape = AckHelpShape
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 8.dp)
    ) {
        Text(
            text = category.title.substringAfter("// ").trim(),
            color = textColor,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 0.5.sp
        )
    }
}

@Composable
private fun HelpModuleMenuItem(
    module: HelpModule,
    primaryColor: Color,
    onClick: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = primaryColor.copy(alpha = 0.65f),
                shape = AckHelpShape
            )
            .background(
                color = primaryColor.copy(alpha = 0.04f),
                shape = AckHelpShape
            )
            .clickable(onClick = onClick)
            .padding(12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = module.title,
                color = primaryColor,
                fontSize = 11.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.8.sp,
                modifier = Modifier.weight(1f)
            )

            Spacer(modifier = Modifier.width(8.dp))

            Text(
                text = "[RUN]",
                color = Color.White,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
        }

        Spacer(modifier = Modifier.height(6.dp))

        Text(
            text = module.summary,
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "${module.steps.size} STEPS // " +
                (module.destination?.viewMode ?: "CURRENT VIEW"),
            color = primaryColor.copy(alpha = 0.7f),
            fontSize = 8.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun HelpEmptyState(primaryColor: Color) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .border(
                width = 1.dp,
                color = Color.DarkGray,
                shape = AckHelpShape
            )
            .padding(14.dp)
    ) {
        Text(
            text = "NO MODULES DEPLOYED",
            color = primaryColor.copy(alpha = 0.65f),
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(4.dp))

        Text(
            text = "THIS KNOWLEDGE FAMILY HAS NO ACTIVE HELP PROTOCOLS.",
            color = Color.Gray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

private fun defaultHelpCategory(
    context: HelpContext
): HelpCategory {
    return when (context.deckType) {
        DeckType.MATRIX,
        DeckType.QUICK_ACTIONS,
        DeckType.EMERGENCY,
        DeckType.EMOJI,
        DeckType.GIF -> HelpCategory.USING_DECKS
    }
}
