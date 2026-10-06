// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import com.example.besu.core.TextSource
import com.example.besu.data.ResourceText

/** A [ResourceText] for the current screen, rebuilt when the language changes (see data/ResourceText.kt). */
@Composable
fun rememberText(): TextSource {
    val context = LocalContext.current
    val configuration = LocalConfiguration.current
    return remember(context, configuration) { ResourceText(context) }
}
