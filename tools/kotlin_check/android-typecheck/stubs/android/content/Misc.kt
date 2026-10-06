// SPDX-License-Identifier: GPL-3.0-or-later
package android.content
import android.net.Uri
import java.io.InputStream
import java.io.OutputStream
class Intent {
    constructor(context: Context, cls: Class<*>)
    constructor(action: String, uri: Uri)
    companion object { const val ACTION_DIAL = "android.intent.action.DIAL"; const val ACTION_VIEW = "android.intent.action.VIEW"; const val ACTION_SENDTO = "android.intent.action.SENDTO" }
    var action: String? = null
    fun putExtra(name: String, value: String): Intent = this
    fun putExtra(name: String, value: Boolean): Intent = this
    fun putExtra(name: String, value: Float): Intent = this
}
interface SharedPreferences {
    fun getString(key: String, default: String?): String?
    fun getBoolean(key: String, default: Boolean): Boolean
    fun getInt(key: String, default: Int): Int
    fun getFloat(key: String, default: Float): Float
    fun edit(): Editor
    interface Editor {
        fun putString(key: String, value: String?): Editor
        fun putBoolean(key: String, value: Boolean): Editor
        fun putInt(key: String, value: Int): Editor
        fun putFloat(key: String, value: Float): Editor
        fun apply()
    }
}
abstract class ContentResolver {
    abstract fun openOutputStream(uri: Uri): OutputStream?
    abstract fun openOutputStream(uri: Uri, mode: String): OutputStream?
    abstract fun openInputStream(uri: Uri): InputStream?
}
class ActivityNotFoundException : RuntimeException()
class ClipData { companion object { fun newPlainText(label: CharSequence, text: CharSequence): ClipData = ClipData() } }
class ClipboardManager { fun setPrimaryClip(clip: ClipData) {} }
