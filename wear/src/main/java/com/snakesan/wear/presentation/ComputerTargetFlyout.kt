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
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.Text
import kotlinx.coroutines.delay
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

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
// to hold-confirm. The synthetic back/exit row (always ring slot 0) isn't
// represented here; ComputerTargetFlyout handles it directly by index.
private data class FlyoutRow(
    val label: String,
    val categoryId: String,
    val nodeId: String?, // null only for a top-level category row from the picker
    val isCategory: Boolean
)

// Up to this many real rows show at once, arranged around the ring
// alongside the fixed back/exit position -- see RING_SLOT_COUNT below.
// Scrolling past the last one on a page moves to the next page rather
// than paging one item at a time; see the crown handler.
private const val ITEMS_PER_PAGE = 5

// Ring slot 0 is always the synthetic back/exit control (fixed at the top,
// every page); slots 1..5 hold the current page's real rows. Fixed slot
// *angles* regardless of how many are filled on a given page, so a
// position (e.g. "2 o'clock") means the same thing page to page.
private const val RING_SLOT_COUNT = 1 + ITEMS_PER_PAGE
private const val RING_RADIUS_FRACTION = 0.38f
private const val CHIP_HIT_RADIUS_DP = 30

// Clock-position offset (px, relative to center) for ring slot 0..5, slot 0
// fixed at the top, clockwise from there. Shared by rendering and tap
// hit-testing so what's drawn and what's tappable can never drift apart.
private fun ringOffsetPx(radiusPx: Float, slotIndex: Int): Offset {
    val angleRad = Math.toRadians((slotIndex * (360 / RING_SLOT_COUNT)).toDouble())
    return Offset(
        x = (radiusPx * sin(angleRad)).toFloat(),
        y = (-radiusPx * cos(angleRad)).toFloat()
    )
}

// Ring chips only have room for a short preview -- the full label always
// shows in the center once a chip is highlighted.
private fun String.toRingLabel(): String = if (length > 8) take(7) + "…" else this

// Watch-side Target Computer picker, opened by tap-tap-hold when the
// active deck is Quick Actions (see wear MainActivity.kt). Lets the user
// change which entry is active for a category one of that deck's slots
// references via [COMPUTER:X], without unlocking the phone. Deliberately
// pick-only: onSelect just updates ComputerRepository's active pick (via
// WearListenerService's /sys/req_computer_pick) -- it never speaks
// anything itself, matching the "pick only, fire separately via the
// existing pose+twist gesture" decision this feature was scoped to.
//
// Radial layout by design, not a single-focus ring like
// TargetSelectionOverlay: every sibling on the current page is visible at
// once (as short labels around the rim, full label in the center for
// whichever is highlighted), so the user sees what they're about to act
// on rather than cycling blind. Crown rotation AND a direct tap on a
// visible chip both move the highlight; only a long-press (anywhere --
// not scoped to a specific chip) confirms/activates it, so a stray tap
// never commits anything. A synthetic "‹ BACK" / "‹ EXIT" chip always
// occupies the top ring position; entering a category or subcategory
// pushes a new level rather than picking anything -- only a long-press on
// an actual leaf entry commits.
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

    // Which page selectionIndex currently falls on, and that page's real
    // rows -- pure display derivation, recomputed fresh every
    // recomposition (so, unlike the pointerInput-scoped functions below,
    // safe to read directly rather than needing its own re-read helper).
    val page = if (selectionIndex == 0) 0 else (selectionIndex - 1) / ITEMS_PER_PAGE
    val pageStart = page * ITEMS_PER_PAGE
    val pageItems = rows.subList(pageStart, minOf(pageStart + ITEMS_PER_PAGE, rows.size))
    val pageCount = if (rows.isEmpty()) 1 else (rows.size + ITEMS_PER_PAGE - 1) / ITEMS_PER_PAGE
    val highlightSlot = if (selectionIndex == 0) 0 else ((selectionIndex - 1) % ITEMS_PER_PAGE) + 1

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
        val ringRadiusPx = minOf(constraints.maxWidth, constraints.maxHeight) * RING_RADIUS_FRACTION

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
                // Keyed on the current level (not Unit) -- rows/pages are
                // plain vals recomputed each recomposition, not a
                // MutableState, so the gesture coroutine needs restarting
                // with a fresh closure whenever the level actually
                // changes, or tap hit-testing (and activate()'s drill-
                // in/back) would keep acting on the level it was launched
                // under. See activate()'s own comment for the full reasoning.
                .pointerInput(currentLevel) {
                    detectTapGestures(
                        onTap = { offset ->
                            lastInteraction = System.currentTimeMillis()

                            val level = stack.last()
                            val rowsNow = rowsFor(level)
                            val pageNow = if (selectionIndex == 0) 0 else (selectionIndex - 1) / ITEMS_PER_PAGE
                            val pageStartNow = pageNow * ITEMS_PER_PAGE
                            val pageItemsNow = rowsNow.subList(
                                pageStartNow,
                                minOf(pageStartNow + ITEMS_PER_PAGE, rowsNow.size)
                            )

                            val center = Offset(size.width / 2f, size.height / 2f)
                            val hitRadiusPx = CHIP_HIT_RADIUS_DP.dp.toPx()

                            var tappedSlot = -1
                            for (slotPos in 0 until RING_SLOT_COUNT) {
                                if (slotPos != 0 && slotPos - 1 >= pageItemsNow.size) continue
                                val chipCenter = center + ringOffsetPx(ringRadiusPx, slotPos)
                                if ((offset - chipCenter).getDistance() <= hitRadiusPx) {
                                    tappedSlot = slotPos
                                    break
                                }
                            }

                            if (tappedSlot >= 0) {
                                selectionIndex = if (tappedSlot == 0) 0 else pageStartNow + tappedSlot
                                TechSynth.playNavTone(selectionIndex)
                            }
                        },
                        onLongPress = {
                            lastInteraction = System.currentTimeMillis()
                            activate()
                        }
                    )
                }
        ) {
            val isBackHighlighted = selectionIndex == 0
            val displayLabel = if (isBackHighlighted) {
                if (isRoot) "‹ EXIT" else "‹ BACK"
            } else {
                selectedRow?.label ?: ""
            }
            val isLeafSelected = !isBackHighlighted && selectedRow?.isCategory == false
            val baseColor = when {
                isBackHighlighted -> CyberAmber
                selectedRow?.isCategory == true -> CyberCyan
                else -> CyberGreen
            }
            val levelLabel = when (val level = currentLevel) {
                is FlyoutLevel.CategoryPicker -> "TARGET COMPUTER"
                is FlyoutLevel.NodeLevel -> level.levelLabel
            }
            val footerHint = when {
                isBackHighlighted && isRoot -> "HOLD TO EXIT"
                isBackHighlighted -> "HOLD TO GO BACK"
                selectedRow?.isCategory == true -> "HOLD TO OPEN"
                isLeafSelected -> "HOLD TO SELECT"
                else -> ""
            }

            // Faint boundary ring the chips sit inside -- purely decorative,
            // matches TargetSelectionOverlay's reticle language.
            Canvas(modifier = Modifier.fillMaxSize()) {
                val displayColor = if (isLeafSelected) baseColor else baseColor.copy(alpha = 0.6f)
                drawCircle(
                    displayColor.copy(alpha = if (isLeafSelected) 0.12f else 0.04f),
                    radius = size.minDimension / 2.2f
                )
                drawCircle(
                    displayColor.copy(alpha = 0.5f),
                    radius = size.minDimension / 2.2f,
                    style = Stroke(width = 1.5f)
                )
            }

            // --- RING CHIPS (back/exit at slot 0, current page's rows at
            // slots 1..5, fixed clock positions regardless of how many are
            // actually filled) ---
            for (slotPos in 0 until RING_SLOT_COUNT) {
                val row = if (slotPos == 0) null else pageItems.getOrNull(slotPos - 1)
                if (slotPos != 0 && row == null) continue

                val isHighlighted = slotPos == highlightSlot
                val chipColor = when {
                    slotPos == 0 -> CyberAmber
                    row?.isCategory == true -> CyberCyan
                    else -> CyberGreen
                }
                val offsetPx = ringOffsetPx(ringRadiusPx, slotPos)

                Box(
                    // align(Center) first -- this Box's parent doesn't set
                    // contentAlignment, so without it the chip would place
                    // from the parent's default top-start corner and every
                    // offset below would be wrong. absoluteOffset (not
                    // offset) after it deliberately -- this is a fixed
                    // geometric clock position, not a text-direction-
                    // relative one, so it must not mirror in RTL locales.
                    modifier = Modifier
                        .align(Alignment.Center)
                        .absoluteOffset {
                            IntOffset(offsetPx.x.roundToInt(), offsetPx.y.roundToInt())
                        }
                ) {
                    Text(
                        text = if (slotPos == 0) "‹" else row!!.label.toRingLabel().uppercase(),
                        color = if (isHighlighted) chipColor else chipColor.copy(alpha = 0.45f),
                        fontSize = if (slotPos == 0) 16.sp else 9.sp,
                        fontWeight = if (isHighlighted) FontWeight.Bold else FontWeight.Normal,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            // --- CENTER: full label + context for whichever chip is
            // currently highlighted ---
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.align(Alignment.Center)) {
                Text(levelLabel.uppercase(), color = Color.Gray, fontSize = 9.sp, fontFamily = FontFamily.Monospace)
                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = displayLabel.uppercase(),
                    color = if (isLeafSelected) baseColor else baseColor.copy(alpha = pulseAlpha),
                    fontSize = if (displayLabel.length > 10) 14.sp else 18.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )

                Spacer(modifier = Modifier.height(3.dp))

                if (!isBackHighlighted) {
                    val typeLabel = if (selectedRow?.isCategory == true) "CATEGORY" else "ENTRY"
                    Text(
                        "$typeLabel $selectionIndex/${rows.size}",
                        color = baseColor.copy(alpha = 0.5f),
                        fontSize = 9.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }

                if (pageCount > 1) {
                    Text(
                        "PAGE ${page + 1}/$pageCount",
                        color = Color.Gray,
                        fontSize = 8.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            Box(modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 24.dp)) {
                Text(footerHint, color = Color.DarkGray, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
            }
        }
    }
}
