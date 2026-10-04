// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color

// Stubs of two shared pieces ui/SharedComponents.kt owns (that file is not staged), written from the real signatures.
@Composable
fun DspSlider(label: String, value: Float, range: ClosedFloatingPointRange<Float>, color: Color, onValueChange: (Float) -> Unit) {}

@Composable
fun HeroButton(text: String, modifier: Modifier = Modifier, mainColor: Color, onClick: () -> Unit) {}
