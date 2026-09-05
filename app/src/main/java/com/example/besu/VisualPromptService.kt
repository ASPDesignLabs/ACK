package com.example.besu

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
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import java.io.File
import kotlin.math.max
import kotlin.math.min
import android.content.pm.ActivityInfo

class VisualPromptService : Service() {


    private val handler = Handler(Looper.getMainLooper())

    private lateinit var windowManager: WindowManager

    private var overlayView: View? = null
    private var timeoutRunnable: Runnable? = null

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

        content.addView(
            textView,
            LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
        )

        if (requireHoldToClear) {
            content.addView(
                createHintText(
                    text = "HOLD ANYWHERE TO CLEAR"
                )
            )
        }

        showOverlay(
            content = content,
            requireHoldToClear = requireHoldToClear,
            landscapeLayout = true
        )

        if (!preventTimedClear) {
            scheduleClear(DEFAULT_PROMPT_TIMEOUT_MS)
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

    private fun showOverlay(
        content: View,
        requireHoldToClear: Boolean,
        landscapeLayout: Boolean
    ) {
        clearOverlay(stopService = false)

        val root = FrameLayout(this).apply {
            /*
             * Opaque on purpose: no underlying app/UI should remain visible at the
             * screen edges while a visual prompt is being displayed.
             */
            setBackgroundColor(Color.BLACK)

            addView(
                content,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.WRAP_CONTENT,
                    Gravity.CENTER
                )
            )
        }

        if (requireHoldToClear) {
            root.setOnLongClickListener {
                clearOverlay()
                true
            }

            root.isLongClickable = true
        } else {
            root.setOnClickListener {
                clearOverlay()
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

            if (landscapeLayout) {
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
            clearOverlay()
        }

        handler.postDelayed(timeoutRunnable!!, timeoutMs)
    }

    private fun clearOverlay(stopService: Boolean = true) {
        timeoutRunnable?.let(handler::removeCallbacks)
        timeoutRunnable = null

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

        if (stopService) {
            stopSelf()
        }
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

        private const val CONTENT_PADDING_PX = 30
        private const val CONTAINER_PADDING_PX = 12
        private const val LANDSCAPE_GIF_HEIGHT_PX = 620

        private const val EMOJI_TEXT_SIZE_SP = 132f
        private const val EMOJI_LABEL_TEXT_SIZE_SP = 28f
        private const val GIF_TITLE_TEXT_SIZE_SP = 22f
        private const val HOLD_HINT_TEXT_SIZE_SP = 11f
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