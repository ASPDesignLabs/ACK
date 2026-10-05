// SPDX-License-Identifier: GPL-3.0-or-later
package android.content.res
/** From the real signatures: `Configuration(Configuration)`, `setLocale(Locale)`, `setLayoutDirection(Locale)`. */
class Configuration() {
    constructor(other: Configuration) : this()
    fun setLocale(locale: java.util.Locale?) {}
    fun setLayoutDirection(locale: java.util.Locale?) {}
}
class Resources {
    val configuration: Configuration = Configuration()
    fun getIdentifier(name: String, defType: String, defPackage: String): Int = 0
    fun getQuantityString(id: Int, quantity: Int, vararg formatArgs: Any): String = ""
}
