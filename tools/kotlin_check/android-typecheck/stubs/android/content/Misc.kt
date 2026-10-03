// SPDX-License-Identifier: GPL-3.0-or-later
package android.content
import android.net.Uri
import java.io.InputStream
import java.io.OutputStream
class Intent(context: Context, cls: Class<*>) {
    var action: String? = null
    fun putExtra(name: String, value: String): Intent = this
    fun putExtra(name: String, value: Boolean): Intent = this
}
interface SharedPreferences {
    fun getString(key: String, default: String?): String?
    fun getBoolean(key: String, default: Boolean): Boolean
    fun getInt(key: String, default: Int): Int
    fun edit(): Editor
    interface Editor {
        fun putString(key: String, value: String?): Editor
        fun putBoolean(key: String, value: Boolean): Editor
        fun putInt(key: String, value: Int): Editor
        fun apply()
    }
}
abstract class ContentResolver {
    abstract fun openOutputStream(uri: Uri, mode: String): OutputStream?
    abstract fun openInputStream(uri: Uri): InputStream?
}
