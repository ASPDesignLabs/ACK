package com.example.besu.wear

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.Text
import kotlinx.coroutines.delay
import kotlin.math.abs

// One screen of the flyout's navigation stack: either the top-level
// category picker (only ever the first screen, and only when the active
// Quick Actions deck's slots reference more than one Target Computer
// category -- see MainActivity's tap-tap-hold handler) or a specific
// position within one category's tree, identified by its parentId ("" =
// that category's own top level).
private sealed class FlyoutLevel {
    object CategoryPicker : FlyoutLevel()
    data class NodeLevel(
        val categoryId: String,
        val parentId: String,
        val levelLabel: String
    ) : FlyoutLevel()
}

// One rotary/tap-selectable row at the current level -- a category to
// enter (from the picker), a subcategory to drill into, or a leaf entry
// to hold-confirm. The synthetic back/exit row (always slot 0) isn't
// represented here; ComputerTargetFlyout handles it directly by index.
private data class FlyoutRow(
    val label: String,
    val categoryId: String,
    val nodeId: String?, // null only for a top-level category row from the picker
    val isCategory: Boolean
)

// Watch-side Target Computer picker, opened by tap-tap-hold when the
// active deck is Quick Actions (see wear MainActivity.kt). Lets the user
// change which entry is active for a category one of that deck's slots
// references via [COMPUTER:X], without unlocking the phone. Deliberately
// pick-only: onSelect just updates ComputerRepository's active pick (via
// WearListenerService's /sys/req_computer_pick) -- it never speaks
// anything itself, matching the "pick only, fire separately via the
// existing pose+twist gesture" decision this feature was scoped to.
//
// Mirrors TargetSelectionOverlay's interaction language on purpose (same
// crown/tap-half scrolling, same long-press-to-confirm, same 5s
// inactivity dismiss, same Cyberpunk palette) rather than inventing a new
// one -- this app's watch overlays share one gesture vocabulary. The one
// addition TargetSelectionOverlay's flat 9-slot ring never needed is
// depth: a synthetic "‹ BACK" / "‹ EXIT" row always occupies slot 0, and
// entering a category or subcategory pushes a new level rather than
// picking anything -- only a long-press on an actual leaf entry commits.
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun ComputerTargetFlyout(
    onSelect: (categoryId: String, nodeId: String) -> Unit,
    onDismiss: () -> Unit
) {
    // Defensive only -- the tap-tap-hold handler that shows this already
    // checks there's at least one synced category first.
    if (ComputerCategoryCache.categories.isEmpty()) {
        LaunchedEffect(Unit) { onDismiss() }
        return
    }

    val stack = remember {
        mutableStateListOf<FlyoutLevel>().apply {
            val categories = ComputerCategoryCache.categories.values.toList()
            add(
                if (categories.size == 1) {
                    val only = categories.first()
                    FlyoutLevel.NodeLevel(only.id, "", only.label)
                } else {
                    FlyoutLevel.CategoryPicker
                }
            )
        }
    }

    var selectionIndex by remember { mutableIntStateOf(0) }
    var lastInteraction by remember { mutableLongStateOf(System.currentTimeMillis()) }

    LaunchedEffect(lastInteraction) {
        delay(5000) // Same inactivity window as TargetSelectionOverlay.
        onDismiss()
    }

    fun rowsFor(level: FlyoutLevel): List<FlyoutRow> = when (level) {
        is FlyoutLevel.CategoryPicker -> ComputerCategoryCache.categories.values.map { category ->
            FlyoutRow(label = category.label, categoryId = category.id, nodeId = null, isCategory = true)
        }
        is FlyoutLevel.NodeLevel -> ComputerCategoryCache.childrenOf(level.categoryId, level.parentId).map { node ->
            FlyoutRow(label = node.label, categoryId = level.categoryId, nodeId = node.id, isCategory = node.isCategory)
        }
    }

    val currentLevel = stack.last()
    val isRoot = stack.size == 1
    val rows = rowsFor(currentLevel)
    val slotCount = rows.size + 1 // + the synthetic back/exit row at index 0
    val selectedRow = rows.getOrNull(selectionIndex - 1)

    // Deliberately re-reads stack/selectionIndex/ComputerCategoryCache
    // itself rather than closing over the rows/selectedRow/isRoot vals
    // above: this is only ever invoked from the onLongPress handler inside
    // pointerInput(currentLevel) below, whose coroutine (and therefore
    // whatever it captured at launch) only restarts when currentLevel
    // changes -- not on every crown/tap scroll, which only changes
    // selectionIndex. Reading the outer vals here would silently act on
    // whatever was selected when the level was first entered instead of
    // wherever the user actually scrolled to.
    fun activate() {
        val level = stack.last()
        val rowsNow = rowsFor(level)
        val isRootNow = stack.size == 1

        if (selectionIndex == 0) {
            if (isRootNow) {
                onDismiss()
            } else {
                stack.removeAt(stack.lastIndex)
                selectionIndex = 0
                TechSynth.play(TechSynth.Sfx.TICK)
            }
            return
        }

        val row = rowsNow.getOrNull(selectionIndex - 1) ?: return
        if (row.isCategory) {
            stack.add(FlyoutLevel.NodeLevel(row.categoryId, row.nodeId ?: "", row.label))
            selectionIndex = 0
            TechSynth.play(TechSynth.Sfx.TICK)
        } else if (row.nodeId != null) {
            // Haptic + LOCK tone for the actual commit happens in
            // MainActivity's onSelect implementation, same split as
            // TargetSelectionOverlay's onSelect -- this composable only
            // plays its own audio for the in-place navigation it handles
            // entirely by itself (drill-in/back above).
            onSelect(row.categoryId, row.nodeId)
            onDismiss()
        }
    }

    val focusRequester = remember { FocusRequester() }
    var scrollAccumulator by remember { mutableFloatStateOf(0f) }
    val crownThreshold = 40f

    LaunchedEffect(Unit) { focusRequester.requestFocus() }

    val infiniteTransition = rememberInfiniteTransition()
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.5f, targetValue = 1.0f,
        animationSpec = infiniteRepeatable(tween(500, easing = LinearEasing), RepeatMode.Reverse)
    )

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.95f)),
        contentAlignment = Alignment.Center
    ) {
        val midPointPx = constraints.maxWidth / 2f

        Box(
            modifier = Modifier
                .fillMaxSize()
                .onRotaryScrollEvent {
                    lastInteraction = System.currentTimeMillis()
                    scrollAccumulator += it.verticalScrollPixels

                    if (abs(scrollAccumulator) > crownThreshold) {
                        val direction = if (scrollAccumulator > 0) 1 else -1
                        val next = selectionIndex + direction
                        selectionIndex = when {
                            next >= slotCount -> 0
                            next < 0 -> slotCount - 1
                            else -> next
                        }
                        TechSynth.playNavTone(selectionIndex)
                        scrollAccumulator = 0f
                    }
                    true
                }
                .focusRequester(focusRequester)
                // Keyed on the current level (not Unit) -- rows/slotCount
                // are plain vals recomputed each recomposition, not a
                // MutableState, so the gesture coroutine needs restarting
                // with a fresh closure whenever the level (and therefore
                // rows) actually changes, or a stale drill-in/back would
                // keep acting on the level it was launched under.
                .pointerInput(currentLevel) {
                    detectTapGestures(
                        onTap = { offset ->
                            lastInteraction = System.currentTimeMillis()
                            selectionIndex = if (offset.x < midPointPx) {
                                if (selectionIndex - 1 < 0) slotCount - 1 else selectionIndex - 1
                            } else {
                                if (selectionIndex + 1 >= slotCount) 0 else selectionIndex + 1
                            }
                            TechSynth.playNavTone(selectionIndex)
                        },
                        onLongPress = {
                            lastInteraction = System.currentTimeMillis()
                            activate()
                        }
                    )
                }
        ) {
            val isBackRow = selectionIndex == 0
            val displayLabel = if (isBackRow) {
                if (isRoot) "‹ EXIT" else "‹ BACK"
            } else {
                selectedRow?.label ?: ""
            }
            val isLeafSelected = !isBackRow && selectedRow?.isCategory == false
            val baseColor = when {
                isBackRow -> CyberAmber
                selectedRow?.isCategory == true -> CyberCyan
                else -> CyberGreen
            }
            val levelLabel = when (val level = currentLevel) {
                is FlyoutLevel.CategoryPicker -> "TARGET COMPUTER"
                is FlyoutLevel.NodeLevel -> level.levelLabel
            }
            val footerHint = when {
                isBackRow && isRoot -> "HOLD TO EXIT"
                isBackRow -> "HOLD TO GO BACK"
                selectedRow?.isCategory == true -> "HOLD TO OPEN"
                isLeafSelected -> "HOLD TO SELECT"
                else -> ""
            }

            Canvas(modifier = Modifier.fillMaxSize()) {
                val displayColor = if (isLeafSelected) baseColor else baseColor.copy(alpha = 0.7f)
                val bgAlpha = if (isLeafSelected) 0.2f else 0.05f
                val ringWidth = if (isLeafSelected) 4f else 2f

                drawCircle(displayColor.copy(alpha = bgAlpha), radius = size.minDimension / 2.2f)
                drawCircle(displayColor, radius = size.minDimension / 2.2f, style = Stroke(width = ringWidth))

                drawLine(displayColor.copy(alpha = 0.3f), start = Offset(size.width / 2, 10f), end = Offset(size.width / 2, 30f), strokeWidth = 2f)
                drawLine(displayColor.copy(alpha = 0.3f), start = Offset(size.width / 2, size.height - 10f), end = Offset(size.width / 2, size.height - 30f), strokeWidth = 2f)
            }

            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.align(Alignment.Center)) {
                Text(levelLabel.uppercase(), color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = displayLabel.uppercase(),
                    color = if (isLeafSelected) baseColor else baseColor.copy(alpha = pulseAlpha),
                    fontSize = if (displayLabel.length > 10) 16.sp else 22.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(4.dp))

                if (!isBackRow) {
                    val typeLabel = if (selectedRow?.isCategory == true) "CATEGORY" else "ENTRY"
                    Text(
                        "$typeLabel  ${selectionIndex} / ${rows.size}",
                        color = baseColor.copy(alpha = 0.5f),
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            Box(modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 30.dp)) {
                Text(footerHint, color = Color.DarkGray, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
            }

            Box(modifier = Modifier.align(Alignment.CenterStart).padding(start = 10.dp)) {
                Text("<", color = Color.Gray.copy(alpha = 0.5f), fontSize = 12.sp)
            }
            Box(modifier = Modifier.align(Alignment.CenterEnd).padding(end = 10.dp)) {
                Text(">", color = Color.Gray.copy(alpha = 0.5f), fontSize = 12.sp)
            }
        }
    }
}
