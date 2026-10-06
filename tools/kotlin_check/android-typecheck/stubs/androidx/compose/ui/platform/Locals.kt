// SPDX-License-Identifier: GPL-3.0-or-later
package androidx.compose.ui.platform
import android.content.Context
import android.content.res.Configuration
import androidx.compose.runtime.staticCompositionLocalOf
// Android's own composition locals (not in Compose Multiplatform's common code), with their real types.
val LocalContext = staticCompositionLocalOf<Context> { error("stub") }
val LocalConfiguration = staticCompositionLocalOf<Configuration> { error("stub") }
