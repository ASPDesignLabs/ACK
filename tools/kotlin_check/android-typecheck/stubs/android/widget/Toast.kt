// SPDX-License-Identifier: GPL-3.0-or-later
package android.widget
import android.content.Context
class Toast { fun show() {}; companion object { const val LENGTH_SHORT = 0; const val LENGTH_LONG = 1; fun makeText(c: Context, t: CharSequence, d: Int): Toast = Toast() } }
