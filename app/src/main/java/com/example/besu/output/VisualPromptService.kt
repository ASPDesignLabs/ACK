// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.output

import com.example.besu.*
import com.example.besu.data.*
import com.example.besu.decks.*
import com.example.besu.help.*
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Movie
import android.graphics.Paint
import android.graphics.Typeface
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.widget.TextViewCompat
import java.io.File
import kotlin.math.max
import kotlin.math.min
import android.content.pm.ActivityInfo

class VisualPromptService : Service() {


    private val handler = Handler(Looper.getMainLooper())

    private lateinit var windowManager: WindowManager

    private var overlayView: View? = null
    private var timeoutRunnable: Runnable? = null

    // Missed-message repair: if a prompt clears (timeout, tap, or hold),
    // this is left set so a small REPLAY chip can bring it right back --
    // recovering used to mean unlocking the phone and finding the right
    // row in Type view's history. Not offered when a new prompt simply
    // replaces this one, or when the phone-shake kill switch force-clears
    // (that content was a mistake, not something to offer back).
    private var replayAction: (() -> Unit)? = null
    private var replayChipView: View? = null
    private var chipTimeoutRunnable: Runnable? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()

        windowManager = getSystemService(
            Context.WINDOW_SERVICE
        ) as WindowManager
    }

    private fun resolveVisualPromptText(
        template: String,
        rootCategory: String,
        localValues: List<String>
    ): String {
        val category = rootCategory.ifBlank {
            CommandRepository.getActiveCategoryFocus(this)
        }

        val rootConfig = RootOverrideRepository.getConfig(
            context = this,
            category = category
        )

        return TemplateEngine.resolve(
            template = template,
            localValues = localValues,
            overrides = rootConfig.slots
        )
    }

    override fun onStartCommand(
        intent: Intent?,
        flags: Int,
        startId: Int
    ): Int {
        if (!Settings.canDrawOverlays(this)) {
            stopSelf(startId)
            return START_NOT_STICKY
        }

        when (intent?.action) {
            ACTION_SHOW_PROMPT -> {
                showTextPrompt(
                    template = intent.getStringExtra(EXTRA_TEXT).orEmpty(),
                    rootCategory = intent.getStringExtra(
                        EXTRA_ROOT_CATEGORY
                    ).orEmpty(),
                    localValues = intent.getStringArrayListExtra(
                        EXTRA_LOCAL_VALUES
                    ).orEmpty(),
                    preventTimedClear = intent.getBooleanExtra(
                        EXTRA_PREVENT_TIMED_CLEAR,
                        false
                    ),
                    requireHoldToClear = intent.getBooleanExtra(
                        EXTRA_REQUIRE_HOLD_TO_CLEAR,
                        false
                    )
                )
            }

            ACTION_SHOW_EMOJI -> {
                showEmojiPrompt(
                    emoji = intent.getStringExtra(EXTRA_EMOJI).orEmpty(),
                    displayText = intent.getStringExtra(
                        EXTRA_DISPLAY_TEXT
                    ).orEmpty(),
                    timeoutMs = intent.getLongExtra(
                        EXTRA_EMOJI_TIMEOUT_MS,
                        DEFAULT_EMOJI_TIMEOUT_MS
                    )
                )
            }

            ACTION_SHOW_GIF -> {
                showGifPrompt(
                    filePath = intent.getStringExtra(
                        EXTRA_GIF_FILE_PATH
                    ).orEmpty(),
                    title = intent.getStringExtra(
                        EXTRA_GIF_TITLE
                    ).orEmpty(),
                    forceLandscape = intent.getBooleanExtra(
                        EXTRA_GIF_FORCE_LANDSCAPE,
                        false
                    ),
                    showText = intent.getBooleanExtra(
                        EXTRA_GIF_SHOW_TEXT,
                        true
                    )
                )
            }

            ACTION_FORCE_CLEAR -> {
                clearOverlay()
            }
        }

        return START_NOT_STICKY
    }

    private fun resolveVisualPromptText(template: String): String {
        val category = CommandRepository.getActiveCategoryFocus(this)

        val rootConfig = RootOverrideRepository.getConfig(
            context = this,
            category = category
        )

        return TemplateEngine.resolve(
            template = template,
            localValues = emptyList(),
            overrides = rootConfig.slots
        )
    }

    private fun showTextPrompt(
        template: String,
        rootCategory: String,
        localValues: List<String>,
        preventTimedClear: Boolean,
        requireHoldToClear: Boolean
    ) {
        val text = resolveVisualPromptText(
            template = template,
            rootCategory = rootCategory,
            localValues = localValues
        )


        if (text.isBlank()) {
            clearOverlay()
            return
        }

        replayAction = {
            showTextPrompt(
                template = template,
                rootCategory = rootCategory,
                localValues = localValues,
                preventTimedClear = preventTimedClear,
                requireHoldToClear = requireHoldToClear
            )
        }

        val preset = VisualPresetRepository.getActivePreset(this)

        val content = createContentContainer()

        val textView = OutlinedTextView(this).apply {
            this.text = text
            setTextColor(preset.textColorArgb.toInt())
            outlineColor = preset.outlineColorArgb.toInt()
            outlineWidth = preset.outlineWidth

            textSize = preset.fontSizeSp
            gravity = Gravity.CENTER
            includeFontPadding = true

            typeface = Typeface.create(
                Typeface.DEFAULT,
                if (preset.isBold) Typeface.BOLD else Typeface.NORMAL
            )

            setTypeface(
                typeface,
                when {
                    preset.isBold && preset.isItalic -> Typeface.BOLD_ITALIC
                    preset.isBold -> Typeface.BOLD
                    preset.isItalic -> Typeface.ITALIC
                    else -> Typeface.NORMAL
                }
            )

            paint.isUnderlineText = preset.isUnderline

            setLineSpacing(10f, 1.0f)

            setPadding(
                CONTENT_PADDING_PX,
                CONTENT_PADDING_PX,
                CONTENT_PADDING_PX,
                CONTENT_PADDING_PX
            )
        }

        /*
         * The preset's size is the LARGEST the text may be, not a fixed size.
         * The view takes whatever height is left after the optional hint
         * (weight 1, height 0), and Android shrinks the text, a step at a time,
         * until the whole message fits inside that space. A message that
         * already fits at the preset size looks exactly as it did before.
         * Nothing here changes what is said or shown, only the size it is
         * drawn at, so the screen never shows less than was spoken.
         */
        val maxSp = preset.fontSizeSp.toInt().coerceAtLeast(FIT_MIN_SP)
        if (maxSp > FIT_MIN_SP) {
            TextViewCompat.setAutoSizeTextTypeUniformWithConfiguration(
                textView,
                FIT_MIN_SP,
                maxSp,
                FIT_STEP_SP,
                TypedValue.COMPLEX_UNIT_SP
            )
        }

        content.addView(
            textView,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )

        if (requireHoldToClear) {
            content.addView(
                createHintText(
                    text = "HOLD ANYWHERE TO CLEAR"
                )
            )
        }

        scrollIfStillOverflowing(content, textView, requireHoldToClear)

        showOverlay(
            content = content,
            requireHoldToClear = requireHoldToClear,
            landscapeLayout = true,
            fitText = true
        )

        if (!preventTimedClear) {
            scheduleClear(DEFAULT_PROMPT_TIMEOUT_MS)
        }
    }

    /*
     * Last resort for a message too long to fit even at FIT_MIN_SP. Once the
     * text has been laid out at its final size, if it is still taller than the
     * space it was given, it is moved into a ScrollView with a SCROLL FOR MORE
     * hint, so nothing is ever cut off without the person being told.
     *
     * Autosize works by choosing a size and then asking for another layout
     * pass (which throws the old text layout away), so the first callback
     * usually has no layout yet. The listener waits for the first one that
     * does, checks it once, and removes itself.
     */
    private fun scrollIfStillOverflowing(
        content: LinearLayout,
        textView: TextView,
        requireHoldToClear: Boolean
    ) {
        textView.addOnLayoutChangeListener(object : View.OnLayoutChangeListener {
            override fun onLayoutChange(
                v: View,
                left: Int,
                top: Int,
                right: Int,
                bottom: Int,
                oldLeft: Int,
                oldTop: Int,
                oldRight: Int,
                oldBottom: Int
            ) {
                val textLayout = textView.layout ?: return

                if (textView.height <= 0) {
                    return
                }

                textView.removeOnLayoutChangeListener(this)

                val availableHeight = textView.height -
                        textView.compoundPaddingTop -
                        textView.compoundPaddingBottom

                if (textLayout.height > availableHeight) {
                    // Not inside this layout pass: changing the view tree
                    // while it is being laid out is not safe.
                    handler.post {
                        swapTextIntoScrollView(content, textView, requireHoldToClear)
                    }
                }
            }
        })
    }

    private fun swapTextIntoScrollView(
        content: LinearLayout,
        textView: TextView,
        requireHoldToClear: Boolean
    ) {
        // The prompt may have been cleared or replaced before this ran.
        if (overlayView == null || textView.parent !== content) {
            return
        }

        val index = content.indexOfChild(textView)

        TextViewCompat.setAutoSizeTextTypeWithDefaults(
            textView,
            TextViewCompat.AUTO_SIZE_TEXT_TYPE_NONE
        )
        textView.setTextSize(TypedValue.COMPLEX_UNIT_SP, FIT_MIN_SP.toFloat())

        content.removeViewAt(index)

        val scroll = ScrollView(this)
        scroll.addView(
            textView,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        )

        content.addView(
            scroll,
            index,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1f
            )
        )
        content.addView(createHintText(text = "SCROLL FOR MORE"), index + 1)

        /*
         * A ScrollView swallows touches, so the tap that clears the prompt
         * would never reach the overlay's own listener. Put the same handlers
         * on the text view itself: a tap clears it, or, when hold-to-clear is
         * on (Emergency), only a long press does. Same behavior as before.
         */
        if (requireHoldToClear) {
            textView.setOnLongClickListener {
                clearOverlay(offerReplay = true)
                true
            }
        } else {
            textView.setOnClickListener {
                clearOverlay(offerReplay = true)
            }
        }
    }

    private fun showEmojiPrompt(
        emoji: String,
        displayText: String,
        timeoutMs: Long
    ) {
        if (emoji.isBlank()) {
            clearOverlay()
            return
        }

        replayAction = {
            showEmojiPrompt(
                emoji = emoji,
                displayText = displayText,
                timeoutMs = timeoutMs
            )
        }

        val content = createContentContainer()

        val emojiView = TextView(this).apply {
            text = emoji
            setTextColor(Color.WHITE)
            textSize = EMOJI_TEXT_SIZE_SP
            gravity = Gravity.CENTER
            setPadding(
                CONTENT_PADDING_PX,
                CONTENT_PADDING_PX,
                CONTENT_PADDING_PX,
                0
            )
        }

        content.addView(
            emojiView,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        )

        if (displayText.isNotBlank()) {
            val displayTextView = TextView(this).apply {
                text = displayText
                setTextColor(Color.WHITE)
                textSize = EMOJI_LABEL_TEXT_SIZE_SP
                gravity = Gravity.CENTER
                setLineSpacing(8f, 1.0f)

                setPadding(
                    CONTENT_PADDING_PX,
                    0,
                    CONTENT_PADDING_PX,
                    CONTENT_PADDING_PX
                )
            }

            content.addView(
                displayTextView,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )
            )
        }

        showOverlay(
            content = content,
            requireHoldToClear = false,
            landscapeLayout = true
        )

        /*
         * EmojiOverlayTimeout.NO_AUTO_CLEAR sends 0L.
         */
        if (timeoutMs > 0L) {
            scheduleClear(timeoutMs)
        }
    }

    private fun showGifPrompt(
        filePath: String,
        title: String,
        forceLandscape: Boolean,
        showText: Boolean
    ) {
        val gifFile = File(filePath)

        if (!gifFile.exists() || !gifFile.isFile) {
            clearOverlay()
            return
        }

        val movie = try {
            Movie.decodeFile(gifFile.absolutePath)
        } catch (_: Exception) {
            null
        }

        if (movie == null) {
            clearOverlay()
            return
        }

        replayAction = {
            showGifPrompt(
                filePath = filePath,
                title = title,
                forceLandscape = forceLandscape,
                showText = showText
            )
        }

        val content = createContentContainer()

        val gifView = VisualPromptGifMovieView(
            context = this,
            decodedMovie = movie
        ).apply {
            setBackgroundColor(Color.BLACK)
        }

        content.addView(
            gifView,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                if (forceLandscape) {
                    LANDSCAPE_GIF_HEIGHT_PX
                } else {
                    LinearLayout.LayoutParams.WRAP_CONTENT
                }
            )
        )

        if (showText && title.isNotBlank()) {
            val titleView = TextView(this).apply {
                text = title
                setTextColor(Color.WHITE)
                textSize = GIF_TITLE_TEXT_SIZE_SP
                gravity = Gravity.CENTER

                setPadding(
                    CONTENT_PADDING_PX,
                    12,
                    CONTENT_PADDING_PX,
                    CONTENT_PADDING_PX
                )
            }

            content.addView(
                titleView,
                LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )
            )
        }

        showOverlay(
            content = content,
            requireHoldToClear = false,
            landscapeLayout = true
        )

        /*
         * GIF overlays deliberately stay visible until tapped. GifDeck has no
         * timeout setting, unlike EmojiDeck.
         */
    }

    private fun createContentContainer(): LinearLayout {
        return LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(Color.argb(246, 15, 17, 21))

            setPadding(
                CONTAINER_PADDING_PX,
                CONTAINER_PADDING_PX,
                CONTAINER_PADDING_PX,
                CONTAINER_PADDING_PX
            )
        }
    }

    private fun createHintText(text: String): TextView {
        return TextView(this).apply {
            this.text = text
            setTextColor(Color.rgb(110, 235, 255))
            textSize = HOLD_HINT_TEXT_SIZE_SP
            gravity = Gravity.CENTER

            setPadding(
                CONTENT_PADDING_PX,
                12,
                CONTENT_PADDING_PX,
                4
            )
        }
    }

    // fitText: the content holds auto-sizing text, which needs a height it can
    // be measured against. In forced-rotation mode the content is otherwise
    // WRAP_CONTENT tall, which cannot bound a child that shrinks to fit. Only
    // text prompts pass true; emoji and GIF prompts keep their current layout.
    private fun showOverlay(
        content: View,
        requireHoldToClear: Boolean,
        landscapeLayout: Boolean,
        fitText: Boolean = false
    ) {
        clearOverlay(stopService = false)

        /*
         * landscapeLayout wants maximum width for large, unwrapped text. That
         * used to be done by forcing the whole device into landscape (below),
         * which destroys/recreates MainActivity and drops the user back on the
         * TERMINAL tab once the prompt clears. Instead, by default, rotate just
         * the content 90 degrees in place: it's sized as if it were landscape
         * (width = screen height, height = screen width) and then spun to fill
         * the actual (unrotated) screen bounds exactly, so device orientation
         * never changes. PROTOCOL has a toggle back to the old forced-rotation
         * behavior for anyone who prefers it.
         */
        val forceDeviceRotation = landscapeLayout &&
                OverlayDisplayPrefs.isDeviceRotationEnabled(this)

        val rotateContentInPlace = landscapeLayout && !forceDeviceRotation

        val root = FrameLayout(this).apply {
            /*
             * Opaque on purpose: no underlying app/UI should remain visible at the
             * screen edges while a visual prompt is being displayed.
             */
            setBackgroundColor(Color.BLACK)

            if (rotateContentInPlace) {
                // The rotated child is wider than this parent (its unrotated
                // width is the screen's height), so it must not be clipped to
                // the parent's own bounds before the rotation transform lands
                // it back inside the screen.
                setClipChildren(false)
            }

            val contentParams = if (rotateContentInPlace) {
                val screenBounds = windowManager.currentWindowMetrics.bounds

                content.rotation = CONTENT_FILL_ROTATION_DEGREES

                FrameLayout.LayoutParams(
                    screenBounds.height(),
                    screenBounds.width(),
                    Gravity.CENTER
                )
            } else {
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    if (fitText) {
                        FrameLayout.LayoutParams.MATCH_PARENT
                    } else {
                        FrameLayout.LayoutParams.WRAP_CONTENT
                    },
                    Gravity.CENTER
                )
            }

            addView(content, contentParams)
        }

        if (requireHoldToClear) {
            root.setOnLongClickListener {
                clearOverlay(offerReplay = true)
                true
            }

            root.isLongClickable = true
        } else {
            root.setOnClickListener {
                clearOverlay(offerReplay = true)
            }
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            overlayWindowType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_OVERSCAN,
            android.graphics.PixelFormat.OPAQUE
        ).apply {
            /*
             * Pin the overlay to the actual display origin. Do not center it inside
             * Android's orientation-transition or system-bar-adjusted bounds.
             */
            gravity = Gravity.TOP or Gravity.START
            x = 0
            y = 0

            if (forceDeviceRotation) {
                screenOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                layoutInDisplayCutoutMode =
                    WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            }
        }

        try {
            windowManager.addView(root, params)
            overlayView = root
        } catch (_: Exception) {
            overlayView = null
            stopSelf()
        }
    }



    private fun scheduleClear(timeoutMs: Long) {
        timeoutRunnable?.let(handler::removeCallbacks)

        timeoutRunnable = Runnable {
            clearOverlay(offerReplay = true)
        }

        handler.postDelayed(timeoutRunnable!!, timeoutMs)
    }

    private fun clearOverlay(stopService: Boolean = true, offerReplay: Boolean = false) {
        timeoutRunnable?.let(handler::removeCallbacks)
        timeoutRunnable = null

        // Any overlay lifecycle event tears down a stale chip first -- new
        // content replacing it, a fresh dismiss, or a force-clear all mean
        // whatever the chip would have replayed is no longer the point.
        clearReplayChip()

        val hadContent = overlayView != null

        overlayView?.let { view ->
            try {
                windowManager.removeViewImmediate(view)
            } catch (_: IllegalArgumentException) {
                /*
                 * The system may already have detached the overlay.
                 */
            } catch (_: Exception) {
                /*
                 * Overlay cleanup must never crash OutputService's display
                 * lifecycle.
                 */
            }

            // Lets MainActivity's HelpManager advance any step waiting on an
            // overlay actually clearing (e.g. EmojiDeckHelp's "clear" step).
            // Not slot-specific -- any overlay clearing is a harmless no-op
            // for a step that isn't currently expecting it.
            sendBroadcast(
                Intent("ACK_OVERLAY_CLEARED").setPackage(packageName)
            )
        }

        overlayView = null

        if (offerReplay && hadContent && replayAction != null) {
            showReplayChip()
            return
        }

        if (stopService) {
            stopSelf()
        }
    }

    private fun showReplayChip() {
        clearReplayChip()

        val chip = TextView(this).apply {
            text = "↻ REPLAY"
            setTextColor(Color.WHITE)
            textSize = 12f
            setBackgroundColor(Color.argb(230, 20, 20, 24))
            setPadding(28, 20, 28, 20)
            setOnClickListener {
                val action = replayAction
                clearReplayChip()
                action?.invoke()
            }
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            overlayWindowType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            android.graphics.PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.BOTTOM or Gravity.END
            x = 24
            y = 48
        }

        try {
            windowManager.addView(chip, params)
            replayChipView = chip
        } catch (_: Exception) {
            stopSelf()
            return
        }

        chipTimeoutRunnable = Runnable {
            clearReplayChip()
            stopSelf()
        }

        handler.postDelayed(chipTimeoutRunnable!!, REPLAY_CHIP_TIMEOUT_MS)
    }

    private fun clearReplayChip() {
        chipTimeoutRunnable?.let(handler::removeCallbacks)
        chipTimeoutRunnable = null

        replayChipView?.let { view ->
            try {
                windowManager.removeViewImmediate(view)
            } catch (_: Exception) {
                // Already detached -- nothing left to do.
            }
        }

        replayChipView = null
    }

    private fun overlayWindowType(): Int {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }
    }

    override fun onDestroy() {
        clearOverlay(stopService = false)
        super.onDestroy()
    }



    companion object {
        const val ACTION_SHOW_PROMPT = "SHOW_PROMPT"
        const val ACTION_SHOW_EMOJI = "SHOW_EMOJI"
        const val ACTION_SHOW_GIF = "SHOW_GIF"

        // Dismisses whatever is currently showing immediately, ignoring
        // preventTimedClear/requireHoldToClear -- used by the phone-shake
        // kill switch (AccelerometerTapService) to back out of a mistaken
        // output right away rather than waiting on its normal clear rules.
        const val ACTION_FORCE_CLEAR = "FORCE_CLEAR"
        const val EXTRA_ROOT_CATEGORY = "root_category"
        const val EXTRA_LOCAL_VALUES = "local_values"

        const val EXTRA_TEXT = "text"

        const val EXTRA_EMOJI = "emoji"
        const val EXTRA_DISPLAY_TEXT = "display_text"
        const val EXTRA_EMOJI_TIMEOUT_MS = "emoji_timeout_ms"

        const val EXTRA_PREVENT_TIMED_CLEAR = "prevent_timed_clear"
        const val EXTRA_REQUIRE_HOLD_TO_CLEAR = "require_hold_to_clear"

        const val EXTRA_GIF_FILE_PATH = "gif_file_path"
        const val EXTRA_GIF_TITLE = "gif_title"
        const val EXTRA_GIF_FORCE_LANDSCAPE = "gif_force_landscape"
        const val EXTRA_GIF_SHOW_TEXT = "gif_show_text"

        private const val DEFAULT_PROMPT_TIMEOUT_MS = 10_000L
        private const val DEFAULT_EMOJI_TIMEOUT_MS = 10_000L
        private const val REPLAY_CHIP_TIMEOUT_MS = 20_000L

        private const val CONTENT_PADDING_PX = 30
        private const val CONTAINER_PADDING_PX = 12
        private const val LANDSCAPE_GIF_HEIGHT_PX = 620

        private const val EMOJI_TEXT_SIZE_SP = 132f
        private const val EMOJI_LABEL_TEXT_SIZE_SP = 28f
        private const val GIF_TITLE_TEXT_SIZE_SP = 22f
        private const val HOLD_HINT_TEXT_SIZE_SP = 11f

        // Text prompts shrink from the preset's size (the largest allowed) down
        // to this, a step at a time, until the whole message fits. If it still
        // does not fit at FIT_MIN_SP it scrolls instead (SCROLL FOR MORE).
        private const val FIT_MIN_SP = 24
        private const val FIT_STEP_SP = 2

        // Rotates the in-place "fill the screen" content to read left-to-right,
        // matching the direction SCREEN_ORIENTATION_LANDSCAPE used to produce.
        private const val CONTENT_FILL_ROTATION_DEGREES = -90f
    }
}

private class OutlinedTextView(
    context: Context
) : androidx.appcompat.widget.AppCompatTextView(context) {

    var outlineColor: Int = Color.CYAN
    var outlineWidth: Float = 4f

    private val outlinePaint = Paint(Paint.ANTI_ALIAS_FLAG)

    override fun onDraw(canvas: Canvas) {
        if (outlineWidth > 0f) {
            outlinePaint.set(paint)
            outlinePaint.style = Paint.Style.STROKE
            outlinePaint.strokeWidth = outlineWidth
            outlinePaint.color = outlineColor
            outlinePaint.strokeJoin = Paint.Join.ROUND

            val originalColor = currentTextColor
            setTextColor(outlineColor)
            paint.style = Paint.Style.STROKE
            paint.strokeWidth = outlineWidth

            super.onDraw(canvas)

            paint.style = Paint.Style.FILL
            paint.strokeWidth = 0f
            setTextColor(originalColor)
        }

        super.onDraw(canvas)
    }
}

private class VisualPromptGifMovieView(
    context: Context,
    private val decodedMovie: Movie
) : View(context) {

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)

    private var animationStartMs = 0L

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        animationStartMs = System.currentTimeMillis()
    }

    override fun onMeasure(
        widthMeasureSpec: Int,
        heightMeasureSpec: Int
    ) {
        val movieWidth = decodedMovie.width().coerceAtLeast(1)
        val movieHeight = decodedMovie.height().coerceAtLeast(1)

        val measuredWidth = resolveSize(movieWidth, widthMeasureSpec)
        val scale = measuredWidth.toFloat() / movieWidth
        val scaledHeight = (movieHeight * scale).toInt()

        setMeasuredDimension(
            measuredWidth,
            resolveSize(scaledHeight, heightMeasureSpec)
        )
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)

        val movieWidth = decodedMovie.width().coerceAtLeast(1)
        val movieHeight = decodedMovie.height().coerceAtLeast(1)

        val durationMs = decodedMovie.duration().takeIf { it > 0 } ?: 1_000
        val elapsedMs = (
                System.currentTimeMillis() - animationStartMs
                ).toInt()

        decodedMovie.setTime(elapsedMs % durationMs)

        val scale = min(
            width.toFloat() / movieWidth,
            height.toFloat() / movieHeight
        )

        val renderedWidth = movieWidth * scale
        val renderedHeight = movieHeight * scale

        val left = (width - renderedWidth) / 2f
        val top = (height - renderedHeight) / 2f

        canvas.save()
        canvas.translate(left, top)
        canvas.scale(scale, scale)

        decodedMovie.draw(canvas, 0f, 0f, paint)

        canvas.restore()

        postInvalidateOnAnimation()
    }
}