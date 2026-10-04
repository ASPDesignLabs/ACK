// SPDX-License-Identifier: GPL-3.0-or-later
package androidx.compose.ui.res

import androidx.compose.runtime.Composable

/** Stub of Android's `stringResource` (Compose Multiplatform has a different resource API). Same shape: an id and optional format arguments. */
@Composable
fun stringResource(id: Int, vararg formatArgs: Any): String = "stub:$id"
