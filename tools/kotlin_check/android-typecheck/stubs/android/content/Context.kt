// SPDX-License-Identifier: GPL-3.0-or-later
package android.content
import android.content.pm.PackageManager
import android.content.res.Resources
import java.io.File
abstract class Context {
    abstract val filesDir: File
    abstract val cacheDir: File
    abstract val applicationContext: Context
    abstract val packageManager: PackageManager
    abstract val packageName: String
    abstract val contentResolver: ContentResolver
    abstract val resources: Resources
    abstract fun getString(id: Int): String
    abstract fun getString(id: Int, vararg formatArgs: Any): String
    abstract fun getSharedPreferences(name: String, mode: Int): SharedPreferences
    abstract fun startService(intent: Intent): Any?
    abstract fun startActivity(intent: Intent)
    abstract fun getSystemService(name: String): Any?
    /** The real one is abstract (`Context.createConfigurationContext(Configuration)`); a default keeps the other stubs compiling. */
    open fun createConfigurationContext(overrideConfiguration: android.content.res.Configuration): Context = this
    companion object { const val MODE_PRIVATE = 0; const val CLIPBOARD_SERVICE = "clipboard" }
}
open class ContextWrapper(base: Context?) : Context() {
    open val baseContext: Context? = base
    override val filesDir: File get() = baseContext!!.filesDir
    override val cacheDir: File get() = baseContext!!.cacheDir
    override val applicationContext: Context get() = baseContext!!.applicationContext
    override val packageManager: PackageManager get() = baseContext!!.packageManager
    override val packageName: String get() = baseContext!!.packageName
    override val contentResolver: ContentResolver get() = baseContext!!.contentResolver
    override val resources: Resources get() = baseContext!!.resources
    override fun getString(id: Int): String = baseContext!!.getString(id)
    override fun getString(id: Int, vararg formatArgs: Any): String = baseContext!!.getString(id, *formatArgs)
    override fun getSharedPreferences(name: String, mode: Int): SharedPreferences = baseContext!!.getSharedPreferences(name, mode)
    override fun startService(intent: Intent): Any? = baseContext!!.startService(intent)
    override fun startActivity(intent: Intent) = baseContext!!.startActivity(intent)
    override fun getSystemService(name: String): Any? = baseContext!!.getSystemService(name)
}
