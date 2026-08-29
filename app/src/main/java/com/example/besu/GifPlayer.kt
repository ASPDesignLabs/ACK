package com.example.besu

import android.content.Context
import android.graphics.Canvas
import android.graphics.Movie
import android.graphics.Paint
import android.os.SystemClock
import android.view.View
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import java.io.File
import kotlin.math.min

@Composable
fun AnimatedGifPlayer(
    file: File,
    modifier: Modifier = Modifier
) {
    AndroidView(
        modifier = modifier,
        factory = { context ->
            GifMovieView(context)
        },
        update = { view ->
            view.setGifFile(file)
        }
    )
}

private class GifMovieView(
    context: Context
) : View(context) {

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)

    private var movie: Movie? = null
    private var animationStartMs = 0L
    private var currentFilePath: String? = null

    fun setGifFile(file: File) {
        val newPath = file.absolutePath

        if (currentFilePath == newPath) {
            return
        }

        currentFilePath = newPath
        movie = Movie.decodeFile(newPath)
        animationStartMs = SystemClock.uptimeMillis()

        requestLayout()
        invalidate()
    }

    override fun onMeasure(
        widthMeasureSpec: Int,
        heightMeasureSpec: Int
    ) {
        val decodedMovie = movie

        if (decodedMovie == null) {
            setMeasuredDimension(
                resolveSize(0, widthMeasureSpec),
                resolveSize(0, heightMeasureSpec)
            )
            return
        }

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

        val decodedMovie = movie ?: return

        val movieWidth = decodedMovie.width().coerceAtLeast(1)
        val movieHeight = decodedMovie.height().coerceAtLeast(1)

        val durationMs = decodedMovie.duration().takeIf { it > 0 } ?: 1_000
        val elapsedMs = (
                SystemClock.uptimeMillis() - animationStartMs
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