package com.example.besu.wear

import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Typeface
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
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.Text
import kotlinx.coroutines.delay
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sqrt

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
// alongside the fixed back/exit slice -- see RING_SLOT_COUNT below.
// Scrolling past the last one on a page moves to the next page rather
// than paging one item at a time; see the crown handler.
private const val ITEMS_PER_PAGE = 5

// Ring slot 0 is always the synthetic back/exit control (fixed at the top,
// every page); slots 1..5 hold the current page's real rows. Fixed slot
// *angles* regardless of how many are filled on a given page, so a
// position (e.g. "2 o'clock") means the same thing page to page.
private const val RING_SLOT_COUNT = 1 + ITEMS_PER_PAGE
private const val SLICE_WIDTH_DEG = 360f / RING_SLOT_COUNT
private const val SLICE_GAP_DEG = 6f // leaves a visible gap between adjacent slices' bands

// Radial layout, as fractions of the screen's shorter dimension.
private const val BAND_RADIUS_FRACTION = 0.46f
private const val TEXT_OUTER_RADIUS_FRACTION = 0.405f
private const val LINE_STEP_FRACTION = 0.085f
private const val MAX_ARC_LINES = 3
private const val HIT_MIN_RADIUS_FRACTION = 0.14f
private const val HIT_MAX_RADIUS_FRACTION = 0.50f

// A slice centered in the bottom half of the circle needs its arc swept
// in the opposite direction from one in the top half, or drawTextOnPath
// would lay its letters out backwards and upside down -- see
// ComputerRingCanvas's comment for the full reasoning. slotPos here is in
// "my" angle convention: 0 = straight up, increasing clockwise.
private fun isBottomHalfSlice(slotPos: Int): Boolean {
    val angleRad = Math.toRadians((slotPos * SLICE_WIDTH_DEG).toDouble())
    return cos(angleRad) < 0.0
}

// Greedy word-wrap against a fixed pixel budget (the narrowest line's arc
// length, used for every line so no line risks overflowing its arc) --
// not a general-purpose wrapper, just enough for short entry/category
// names. A label that still doesn't fit in maxLines has its last line
// ellipsized rather than silently dropping words.
private fun wrapToArcLines(label: String, paint: Paint, maxLines: Int, budgetPx: Float): List<String> {
    val words = label.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
    if (words.isEmpty()) return emptyList()

    val lines = mutableListOf<String>()
    var current = StringBuilder()
    var wordIndex = 0

    while (wordIndex < words.size && lines.size < maxLines) {
        val word = words[wordIndex]
        val candidate = if (current.isEmpty()) word else "$current $word"
        if (current.isEmpty() || paint.measureText(candidate) <= budgetPx) {
            current = StringBuilder(candidate)
            wordIndex++
        } else {
            lines.add(current.toString())
            current = StringBuilder()
        }
    }
    if (current.isNotEmpty() && lines.size < maxLines) {
        lines.add(current.toString())
    }

    if (wordIndex < words.size && lines.isNotEmpty()) {
        var last = lines.last()
        while (last.isNotEmpty() && paint.measureText("$last…") > budgetPx) {
            last = last.dropLast(1).trimEnd()
        }
        lines[lines.lastIndex] = "$last…"
    }

    return lines
}

// Watch-side Target Computer picker, opened by tap-tap-hold when the
// active deck is Quick Actions (see wear MainActivity.kt). Lets the user
// change which entry is active for a category one of that deck's slots
// references via [COMPUTER:X], without unlocking the phone. Deliberately
// pick-only: onSelect just updates ComputerRepository's active pick (via
// WearListenerService's /sys/req_computer_pick) -- it never speaks
// anything itself, matching the "pick only, fire separately via the
// existing pose+twist gesture" decision this feature was scoped to.
//
// Radial menu, modeled on Overseer's watch-face rim bands rather than a
// single-focus ring: every sibling on the current page gets its own
// colored arc slice with its full (word-wrapped, up to 3 lines) label
// curving along the rim, all visible at once -- not cycled through blind.
// Crown rotation AND a direct tap on a visible slice both move the
// highlight; only a long-press (anywhere, not scoped to a specific slice)
// confirms/activates it, so a stray tap never commits anything. A
// synthetic BACK/EXIT slice always occupies the top position; entering a
// category or subcategory pushes a new level rather than picking anything
// -- only a long-press on an actual leaf entry commits.
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
        val minDimPx = minOf(constraints.maxWidth, constraints.maxHeight).toFloat()

        Box(
            modifier = Modifier
                .fillMaxSize()
                .onRotaryScrollEvent {
                    lastInteraction = System.currentTimeMillis()
                    scrollAccumulator += it.verticalScrollPixels

                    if (kotlin.math.abs(scrollAccumulator) > crownThreshold) {
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

                            val cx = size.width / 2f
                            val cy = size.height / 2f
                            val dx = offset.x - cx
                            val dy = offset.y - cy
                            val dist = sqrt(dx * dx + dy * dy)
                            val minR = HIT_MIN_RADIUS_FRACTION * minOf(size.width, size.height)
                            val maxR = HIT_MAX_RADIUS_FRACTION * minOf(size.width, size.height)

                            if (dist in minR..maxR) {
                                // atan2(dx, -dy): 0 = straight up, increasing
                                // clockwise -- matches the slot-angle
                                // convention used everywhere else here.
                                var angleDeg = Math.toDegrees(atan2(dx.toDouble(), -dy.toDouble()))
                                if (angleDeg < 0) angleDeg += 360.0
                                val nearestSlot = (((angleDeg + SLICE_WIDTH_DEG / 2) / SLICE_WIDTH_DEG).toInt()) % RING_SLOT_COUNT

                                if (nearestSlot == 0 || nearestSlot - 1 < pageItemsNow.size) {
                                    selectionIndex = if (nearestSlot == 0) 0 else pageStartNow + nearestSlot
                                    TechSynth.playNavTone(selectionIndex)
                                }
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
            val isLeafSelected = !isBackHighlighted && selectedRow?.isCategory == false
            val levelLabel = when (val level = currentLevel) {
                is FlyoutLevel.CategoryPicker -> "TARGET COMPUTER"
                is FlyoutLevel.NodeLevel -> level.levelLabel
            }
            val highlightedLabel = if (isBackHighlighted) {
                if (isRoot) "EXIT" else "BACK"
            } else {
                selectedRow?.label ?: ""
            }
            val highlightColor = when {
                isBackHighlighted -> CyberAmber
                selectedRow?.isCategory == true -> CyberCyan
                else -> CyberGreen
            }
            val footerHint = when {
                isBackHighlighted && isRoot -> "HOLD TO EXIT"
                isBackHighlighted -> "HOLD TO GO BACK"
                selectedRow?.isCategory == true -> "HOLD TO OPEN"
                isLeafSelected -> "HOLD TO SELECT"
                else -> ""
            }

            ComputerRingCanvas(
                minDimPx = minDimPx,
                pageItems = pageItems,
                highlightSlot = highlightSlot,
                isRoot = isRoot
            )

            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.align(Alignment.Center)) {
                Text(levelLabel.uppercase(), color = Color.Gray, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
                Spacer(modifier = Modifier.height(4.dp))

                Text(
                    text = highlightedLabel.uppercase(),
                    color = if (isLeafSelected) highlightColor else highlightColor.copy(alpha = pulseAlpha),
                    fontSize = if (highlightedLabel.length > 12) 11.sp else 13.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )

                if (pageCount > 1) {
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        "PAGE ${page + 1}/$pageCount",
                        color = Color.Gray,
                        fontSize = 8.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            Box(modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 18.dp)) {
                Text(footerHint, color = Color.DarkGray, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
            }
        }
    }
}

// Draws the 6 rim slices -- a colored arc band plus its curved, word-
// wrapped label -- via the native Android Canvas (Path.addArc +
// Canvas.drawTextOnPath). Compose has no built-in curved-text primitive,
// so this drops to nativeCanvas for text only; the band itself could use
// Compose's own drawArc, but keeping both draw calls on the same
// native-canvas pass avoids mixing two drawing APIs for one visual unit.
//
// The one genuinely fiddly part: drawTextOnPath lays a string out along
// the path's direction of travel, orienting each glyph "upright" relative
// to that direction. Sweep a slice's arc the same way (start-angle
// increasing) all the way around a full circle, and the bottom half comes
// out backwards and upside down -- the second half of the string ends up
// on the left, and the whole thing reads like it's reflected through the
// slice's own center. Reversing the sweep direction (start from the
// opposite edge, negative sweep) for any slice centered in the bottom
// half fixes both problems in one step; isBottomHalfSlice picks out which
// slices need it. This is the one piece of this file that's hardest to
// fully verify without seeing it rendered -- if a bottom slice's text
// comes out backwards or upside down on-device, flipping the sweep-sign
// branch below (swap the two addArc calls' start/sweep) is the fix.
@Composable
private fun ComputerRingCanvas(
    minDimPx: Float,
    pageItems: List<FlyoutRow>,
    highlightSlot: Int,
    isRoot: Boolean
) {
    val bandRadius = minDimPx * BAND_RADIUS_FRACTION
    val textOuterRadius = minDimPx * TEXT_OUTER_RADIUS_FRACTION
    val lineStep = minDimPx * LINE_STEP_FRACTION
    val bandStrokeWidth = minDimPx * 0.018f
    val textSizePx = minDimPx * 0.052f

    val paint = remember {
        Paint().apply {
            isAntiAlias = true
            typeface = Typeface.MONOSPACE
            // LEFT, not CENTER -- Paint.Align.CENTER is not reliably
            // honored by drawTextOnPath across Android/Skia versions (this
            // is a known, documented pitfall of that API combination); the
            // draw loop below computes an explicit left-aligned start
            // offset instead, so centering doesn't depend on it.
            textAlign = Paint.Align.LEFT
            style = Paint.Style.FILL
        }
    }
    val bandPaint = remember {
        Paint().apply {
            isAntiAlias = true
            style = Paint.Style.STROKE
        }
    }

    Canvas(modifier = Modifier.fillMaxSize()) {
        val cx = size.width / 2f
        val cy = size.height / 2f

        drawIntoCanvas { canvas ->
            val nativeCanvas = canvas.nativeCanvas
            paint.textSize = textSizePx
            bandPaint.strokeWidth = bandStrokeWidth

            for (slotPos in 0 until RING_SLOT_COUNT) {
                val row = if (slotPos == 0) null else pageItems.getOrNull(slotPos - 1)
                if (slotPos != 0 && row == null) continue

                val isHighlighted = slotPos == highlightSlot
                val color = when {
                    slotPos == 0 -> CyberAmber
                    row?.isCategory == true -> CyberCyan
                    else -> CyberGreen
                }
                val label = if (slotPos == 0) {
                    if (isRoot) "EXIT" else "BACK"
                } else {
                    row!!.label.uppercase()
                }

                val displayColor = if (isHighlighted) color else color.copy(alpha = 0.45f)
                val argb = displayColor.toArgb()

                val sliceCenterDeg = slotPos * SLICE_WIDTH_DEG
                val halfWidthDeg = (SLICE_WIDTH_DEG - SLICE_GAP_DEG) / 2f
                val androidCenterDeg = sliceCenterDeg - 90f
                val reversed = isBottomHalfSlice(slotPos)

                // --- Rim band ---
                bandPaint.color = argb
                val bandRect = RectF(cx - bandRadius, cy - bandRadius, cx + bandRadius, cy + bandRadius)
                if (!reversed) {
                    nativeCanvas.drawArc(bandRect, androidCenterDeg - halfWidthDeg, halfWidthDeg * 2, false, bandPaint)
                } else {
                    nativeCanvas.drawArc(bandRect, androidCenterDeg + halfWidthDeg, -(halfWidthDeg * 2), false, bandPaint)
                }

                // --- Curved label, word-wrapped to fit the slice's arc ---
                paint.color = argb
                paint.isFakeBoldText = isHighlighted

                val innermostRadius = textOuterRadius - (MAX_ARC_LINES - 1) * lineStep
                val budgetPx = innermostRadius * Math.toRadians((halfWidthDeg * 2).toDouble()).toFloat() * 0.85f
                val lines = wrapToArcLines(label, paint, MAX_ARC_LINES, budgetPx)

                lines.forEachIndexed { lineIndex, line ->
                    val lineRadius = textOuterRadius - lineIndex * lineStep
                    val path = Path()
                    val rect = RectF(cx - lineRadius, cy - lineRadius, cx + lineRadius, cy + lineRadius)
                    val arcLenPx = lineRadius * Math.toRadians((halfWidthDeg * 2).toDouble()).toFloat()

                    // Explicit left-aligned start offset, chosen so the
                    // text's own measured width centers it within the
                    // slice's arc -- see the paint.textAlign comment above
                    // for why this isn't just left to Align.CENTER.
                    // Clamped to 0 so a line that (despite the word-wrap
                    // budget) still measures wider than the arc starts at
                    // the slice's near edge instead of before it, rather
                    // than trying to center something too wide to fit.
                    val textWidthPx = paint.measureText(line)
                    val hOffset = ((arcLenPx - textWidthPx) / 2f).coerceAtLeast(0f)

                    if (!reversed) {
                        path.addArc(rect, androidCenterDeg - halfWidthDeg, halfWidthDeg * 2)
                    } else {
                        path.addArc(rect, androidCenterDeg + halfWidthDeg, -(halfWidthDeg * 2))
                    }

                    nativeCanvas.drawTextOnPath(line, path, hOffset, 0f, paint)
                }
            }
        }
    }
}
