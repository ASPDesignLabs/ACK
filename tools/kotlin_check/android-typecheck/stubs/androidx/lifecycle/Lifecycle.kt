// SPDX-License-Identifier: GPL-3.0-or-later
package androidx.lifecycle
abstract class Lifecycle {
    enum class Event { ON_CREATE, ON_START, ON_RESUME, ON_PAUSE, ON_STOP, ON_DESTROY, ON_ANY }
    abstract fun addObserver(observer: LifecycleObserver)
    abstract fun removeObserver(observer: LifecycleObserver)
}
interface LifecycleObserver
fun interface LifecycleEventObserver : LifecycleObserver { fun onStateChanged(source: LifecycleOwner, event: Lifecycle.Event) }
interface LifecycleOwner { val lifecycle: Lifecycle }
