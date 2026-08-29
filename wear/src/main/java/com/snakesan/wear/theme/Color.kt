package com.example.besu.wear.theme

import androidx.compose.ui.graphics.Color

// STATIC COLORS
val CyberBg = Color(0xFF050505)
val CyberDark = Color(0xFF121212)
val CyberAmber = Color(0xFFFF9900) // Keep for Lock state
val CyberGreen = Color(0xFF00FF41) // Keep for Success state

// THE DECK PALETTE (Must match Phone exactly)
object NeonPalette {
    val DEFAULT_CYAN = Color(0xFF00F3FF) 

    val SWATCHES = listOf(
        Color(0xFF00F3FF), // 0: Cyan
        Color(0xFFFF0055), // 1: Red
        Color(0xFF00FF41), // 2: Green
        Color(0xFFFF9900), // 3: Orange
        Color(0xFFBD00FF), // 4: Purple
        Color(0xFFFFD500), // 5: Yellow
        Color(0xFF0055FF), // 6: Blue
        Color(0xFFFF00FF), // 7: Magenta
        Color(0xFFB7FF00), // 8: Lime
        Color(0xFFFF0099)  // 9: Pink
    )

    fun getColor(index: Int): Color {
        return SWATCHES.getOrElse(index) { DEFAULT_CYAN }
    }
}
