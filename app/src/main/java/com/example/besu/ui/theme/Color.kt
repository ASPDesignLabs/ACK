package com.example.besu.ui.theme

import androidx.compose.ui.graphics.Color

// STATIC VOID COLORS (Always the same)
val VoidBlack = Color(0xFF050505)
val Graphite = Color(0xFF121212)
val ErrorRed = Color(0xFFFF0000)

// THE 10 NEON PRESETS (THE 'SOUL' OF THE DECKS)
object NeonPalette {
    val DEFAULT_CYAN = Color(0xFF00F3FF) // The Original ACK

    // 0-9 Index Map
    val SWATCHES = listOf(
        Color(0xFF00F3FF), // 0: Cyan (Default / Netrunner)
        Color(0xFFFF0055), // 1: Radical Red (Aggressive / Error)
        Color(0xFF00FF41), // 2: Bio Green (Military / Nature)
        Color(0xFFFF9900), // 3: Data Orange (Industrial / Construction)
        Color(0xFFBD00FF), // 4: Neon Purple (Synthwave / Royal)
        Color(0xFFFFD500), // 5: High-Vis Yellow (Hazard / Cyber)
        Color(0xFF0055FF), // 6: Deep Link Blue (Corporate / Cold)
        Color(0xFFFF00FF), // 7: Hot Magenta (Punk / Loud)
        Color(0xFFB7FF00), // 8: Toxic Lime (Acid / Glitch)
        Color(0xFFFF0099)  // 9: Laser Pink (Retro / Vapor)
    )

    fun getColor(index: Int): Color {
        return SWATCHES.getOrElse(index) { DEFAULT_CYAN }
    }
}

// Fallback aliases for legacy code if needed
val NeonCyan = NeonPalette.DEFAULT_CYAN
val NeonPink = NeonPalette.SWATCHES[1]
val NeonGreen = NeonPalette.SWATCHES[2]
val NeonAmber = NeonPalette.SWATCHES[3]
val NeonBg = VoidBlack
val NeonDark = Graphite
