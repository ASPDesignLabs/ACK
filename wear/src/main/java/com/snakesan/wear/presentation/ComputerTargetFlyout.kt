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
// to hold-confirm.
private data class FlyoutRow(
    val label: String,
    val categoryId: String,
    val nodeId: String?, // null only for a top-level category row from the picker
    val isCategory: Boolean
)

private enum class RingSlotKind { BACK, EXIT, NEXT, CATEGORY, LEAF }

// Everything ComputerRingCanvas needs to draw one ring slice -- built by
// ComputerTargetFlyout from the current page's rows plus its own
// back/next bookkeeping, so the canvas itself doesn't need to know
// anything about levels, pages, or the navigation stack.
private data class RingSlotContent(val label: String, val kind: RingSlotKind)

// Up to this many real rows show at once. Ring slots 1, 2, 4 and 5 hold
// them (slot 0 is always BACK/EXIT, slot 3 is always NEXT when there's
// more than one page) -- fixed positions regardless of how many rows are
// actually on a given page, so "4 o'clock" means the same thing page to
// page. ITEM_RING_SLOTS' order is the reading order (first row = slot 1).
private const val ITEMS_PER_PAGE = 4
private val ITEM_RING_SLOTS = listOf(1, 2, 4, 5)
private const val NEXT_RING_SLOT = 3

private const val RING_SLOT_COUNT = 6
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
// single-focus ring: every row on the current page gets its own colored
// arc slice with its full (word-wrapped, up to 3 lines) label curving
// along the rim, all visible at once -- not cycled through blind. Crown
// rotation AND a direct tap on a visible slice both move the highlight;
// only a double-tap (anywhere, not scoped to a specific slice) confirms/
// activates it, so a stray tap never commits anything -- deliberately not
// a long-press, which this app already uses for tap-tap-hold and shaky-
// hands and which turned out unreliable to land consistently as this
// flyout's own entry gesture too (see AckWatchHud's TARGET button, its
// replacement). Two fixed control slices -- BACK/EXIT (top) and NEXT
// (bottom, only when there's more than one page) -- sit alongside up to 4
// real rows; entering a category or subcategory pushes a new level rather
// than picking anything, and NEXT pages within the current level rather
// than picking anything -- only a double-tap on an actual leaf entry
// commits.
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun ComputerTargetFlyout(
    onSelect: (categoryId: String, nodeId: String) -> Unit,
    onDismiss: () -> Unit,
    // Caller-configured (PROTOCOL > HARDWARE CONFIG); defaults to
    // TargetSelectionOverlay's original 5s only as a last-resort fallback
    // if somehow called without a real synced value.
    timeoutMs: Long = 5000L
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
    val pageCount = if (rows.isEmpty()) 1 else (rows.size + ITEMS_PER_PAGE - 1) / ITEMS_PER_PAGE

    // Keyed on currentLevel -- entering/leaving a level always starts back
    // on its first page, and (being remember(key), not a plain reset call)
    // this can't be forgotten at some future call site the way a manual
    // "currentPage = 0" sprinkled into activate() could be.
    var currentPage by remember(currentLevel) { mutableIntStateOf(0) }
    val pageIndex = currentPage.coerceIn(0, pageCount - 1)
    val pageStart = pageIndex * ITEMS_PER_PAGE
    val pageItems = rows.subList(pageStart, minOf(pageStart + ITEMS_PER_PAGE, rows.size))

    // selectionIndex is local to the *current page*: 0 = BACK/EXIT,
    // 1..pageItems.size = that page's rows (in ITEM_RING_SLOTS order),
    // pageItems.size+1 = NEXT (only a valid target when pageCount > 1).
    // Resetting whenever the page changes for the same reason currentPage
    // itself resets on level change -- keyed remember, not a call site to
    // forget.
    var selectionIndex by remember(currentLevel, pageIndex) { mutableIntStateOf(0) }
    val slotCountThisPage = 1 + pageItems.size + (if (pageCount > 1) 1 else 0)

    var lastInteraction by remember { mutableLongStateOf(System.currentTimeMillis()) }

    LaunchedEffect(lastInteraction, timeoutMs) {
        delay(timeoutMs)
        onDismiss()
    }

    val selectedRow = if (selectionIndex in 1..pageItems.size) pageItems[selectionIndex - 1] else null
    val isNextHighlighted = selectionIndex == pageItems.size + 1 && pageCount > 1

    // Deliberately re-reads stack/currentPage/selectionIndex/
    // ComputerCategoryCache itself rather than closing over the rows/
    // pageItems/selectedRow vals above: this is only ever invoked from
    // the onDoubleTap handler inside pointerInput(currentLevel) below,
    // whose coroutine (and therefore whatever it captured at launch) only
    // restarts when currentLevel changes -- not on every crown/tap
    // scroll, which only changes selectionIndex or currentPage. Reading
    // the outer vals here would silently act on whatever was selected
    // when the level was first entered instead of wherever the user
    // actually scrolled to. currentPage/selectionIndex themselves are
    // fine to read directly even here -- they're real MutableState, not
    // plain derived vals, so a read always sees the latest value
    // regardless of which composition's closure is doing the reading.
    fun activate() {
        val level = stack.last()
        val rowsNow = rowsFor(level)
        val isRootNow = stack.size == 1
        val pageCountNow = if (rowsNow.isEmpty()) 1 else (rowsNow.size + ITEMS_PER_PAGE - 1) / ITEMS_PER_PAGE
        val pageNow = currentPage.coerceIn(0, pageCountNow - 1)
        val pageStartNow = pageNow * ITEMS_PER_PAGE
        val itemsNow = rowsNow.subList(pageStartNow, minOf(pageStartNow + ITEMS_PER_PAGE, rowsNow.size))

        if (selectionIndex == 0) {
            if (isRootNow) {
                onDismiss()
            } else {
                stack.removeAt(stack.lastIndex)
                TechSynth.play(TechSynth.Sfx.TICK)
            }
            return
        }

        if (selectionIndex == itemsNow.size + 1 && pageCountNow > 1) {
            currentPage = (pageNow + 1) % pageCountNow
            TechSynth.play(TechSynth.Sfx.TICK)
            return
        }

        val row = itemsNow.getOrNull(selectionIndex - 1) ?: return
        if (row.isCategory) {
            stack.add(FlyoutLevel.NodeLevel(row.categoryId, row.nodeId ?: "", row.label))
            TechSynth.play(TechSynth.Sfx.TICK)
        } else if (row.nodeId != null) {
            // Haptic + LOCK tone for the actual commit happens in
            // MainActivity's onSelect implementation, same split as
            // TargetSelectionOverlay's onSelect -- this composable only
            // plays its own audio for the in-place navigation it handles
            // entirely by itself (drill-in/back/next above).
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
                            next >= slotCountThisPage -> 0
                            next < 0 -> slotCountThisPage - 1
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
                // in/back/next) would keep acting on the level it was
                // launched under. See activate()'s own comment for the
                // full reasoning.
                .pointerInput(currentLevel) {
                    detectTapGestures(
                        onTap = { offset ->
                            lastInteraction = System.currentTimeMillis()

                            val level = stack.last()
                            val rowsNow = rowsFor(level)
                            val pageCountNow = if (rowsNow.isEmpty()) 1 else (rowsNow.size + ITEMS_PER_PAGE - 1) / ITEMS_PER_PAGE
                            val pageNow = currentPage.coerceIn(0, pageCountNow - 1)
                            val pageStartNow = pageNow * ITEMS_PER_PAGE
                            val itemsNow = rowsNow.subList(
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

                                val tappedIndex = when {
                                    nearestSlot == 0 -> 0
                                    nearestSlot == NEXT_RING_SLOT -> if (pageCountNow > 1) itemsNow.size + 1 else null
                                    else -> {
                                        val itemLocalIndex = ITEM_RING_SLOTS.indexOf(nearestSlot)
                                        if (itemLocalIndex in 0 until itemsNow.size) itemLocalIndex + 1 else null
                                    }
                                }

                                if (tappedIndex != null) {
                                    selectionIndex = tappedIndex
                                    TechSynth.playNavTone(selectionIndex)
                                }
                            }
                        },
                        // Double-tap, not long-press, confirms -- this app
                        // already has several tap-and-hold gestures
                        // elsewhere (tap-tap-hold, long-press for shaky-
                        // hands) that took real practice to land reliably;
                        // a second design's confirm gesture shouldn't add
                        // another one. Position-independent on purpose,
                        // same as the long-press it replaced: it commits
                        // whatever's currently highlighted regardless of
                        // where on screen the double-tap itself lands, so
                        // a slightly-off second tap doesn't miss.
                        onDoubleTap = {
                            lastInteraction = System.currentTimeMillis()
                            activate()
                        }
                    )
                }
        ) {
            val isBackHighlighted = selectionIndex == 0
            val isLeafSelected = !isBackHighlighted && !isNextHighlighted && selectedRow?.isCategory == false
            val levelLabel = when (val level = currentLevel) {
                is FlyoutLevel.CategoryPicker -> "TARGET COMPUTER"
                is FlyoutLevel.NodeLevel -> level.levelLabel
            }
            val highlightedLabel = when {
                isBackHighlighted -> if (isRoot) "EXIT" else "BACK"
                isNextHighlighted -> "NEXT"
                else -> selectedRow?.label ?: ""
            }
            val highlightColor = when {
                isBackHighlighted || isNextHighlighted -> CyberAmber
                selectedRow?.isCategory == true -> CyberCyan
                else -> CyberGreen
            }
            val footerHint = when {
                isBackHighlighted && isRoot -> "TAP TAP TO EXIT"
                isBackHighlighted -> "TAP TAP TO GO BACK"
                isNextHighlighted -> "TAP TAP FOR NEXT PAGE"
                selectedRow?.isCategory == true -> "TAP TAP TO OPEN"
                isLeafSelected -> "TAP TAP TO SELECT"
                else -> ""
            }

            val ringContent: Map<Int, RingSlotContent> = remember(pageItems, isRoot, pageCount) {
                buildMap {
                    put(
                        0,
                        RingSlotContent(
                            if (isRoot) "EXIT" else "BACK",
                            if (isRoot) RingSlotKind.EXIT else RingSlotKind.BACK
                        )
                    )
                    pageItems.forEachIndexed { i, row ->
                        val slot = ITEM_RING_SLOTS.getOrNull(i) ?: return@forEachIndexed
                        put(slot, RingSlotContent(row.label, if (row.isCategory) RingSlotKind.CATEGORY else RingSlotKind.LEAF))
                    }
                    if (pageCount > 1) {
                        put(NEXT_RING_SLOT, RingSlotContent("NEXT", RingSlotKind.NEXT))
                    }
                }
            }
            val highlightSlot = when {
                isBackHighlighted -> 0
                isNextHighlighted -> NEXT_RING_SLOT
                selectionIndex in 1..pageItems.size -> ITEM_RING_SLOTS.getOrElse(selectionIndex - 1) { -1 }
                else -> -1
            }

            ComputerRingCanvas(
                minDimPx = minDimPx,
                ringContent = ringContent,
                highlightSlot = highlightSlot
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
                        "PAGE ${pageIndex + 1}/$pageCount",
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

// Draws the up-to-6 rim slices -- a colored arc band plus its curved,
// word-wrapped label -- via the native Android Canvas (Path.addArc +
// Canvas.drawTextOnPath). Compose has no built-in curved-text primitive,
// so this drops to nativeCanvas for text only; the band itself could use
// Compose's own drawArc, but keeping both draw calls on the same
// native-canvas pass avoids mixing two drawing APIs for one visual unit.
// Purely a renderer -- everything about which slot holds what (back/next/
// page contents) is decided by the caller and handed in as ringContent.
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
// slices need it.
@Composable
private fun ComputerRingCanvas(
    minDimPx: Float,
    ringContent: Map<Int, RingSlotContent>,
    highlightSlot: Int
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
                val content = ringContent[slotPos] ?: continue

                val isHighlighted = slotPos == highlightSlot
                val color = when (content.kind) {
                    RingSlotKind.BACK, RingSlotKind.EXIT, RingSlotKind.NEXT -> CyberAmber
                    RingSlotKind.CATEGORY -> CyberCyan
                    RingSlotKind.LEAF -> CyberGreen
                }
                val label = content.label.uppercase()

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
                    // Top-half slices read top-to-bottom on screen exactly
                    // like the radius order they're drawn in (line 0,
                    // nearest the rim, is physically highest -- read
                    // first). For a bottom-half slice that relationship
                    // inverts: "nearest the rim" is physically LOWEST on
                    // screen there, so without this, line 0 (the first
                    // word) would be read *last* by anyone scanning the
                    // slice top-to-bottom, and a 2-word label like "SPOT
                    // COFFEE" would visually read back-to-front. Mirroring
                    // the line order for reversed slices (last word
                    // nearest the rim instead of first) keeps top-to-
                    // bottom scanning correct in both hemispheres, while
                    // still anchoring the outermost line to the rim
                    // (textOuterRadius) either way.
                    val lineRadius = if (!reversed) {
                        textOuterRadius - lineIndex * lineStep
                    } else {
                        textOuterRadius - (lines.size - 1 - lineIndex) * lineStep
                    }
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
