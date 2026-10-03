// SPDX-License-Identifier: GPL-3.0-or-later
package android.app
import android.content.Context
import android.content.ContextWrapper
import android.view.Window
open class Activity : ContextWrapper(null) {
    var requestedOrientation: Int = 0
    val window: Window = Window()
}
