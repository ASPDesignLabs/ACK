// SPDX-License-Identifier: GPL-3.0-or-later
package androidx.activity
import android.app.Activity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
open class ComponentActivity : Activity(), LifecycleOwner {
    override val lifecycle: Lifecycle get() = throw NotImplementedError()
}
