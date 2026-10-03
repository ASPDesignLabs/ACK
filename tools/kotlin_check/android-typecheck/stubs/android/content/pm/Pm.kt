// SPDX-License-Identifier: GPL-3.0-or-later
package android.content.pm
class PackageInfo { var versionName: String? = null }
abstract class PackageManager {
    abstract fun getPackageInfo(packageName: String, flags: Int): PackageInfo
    companion object { const val PERMISSION_GRANTED = 0 }
}
object ActivityInfo { const val SCREEN_ORIENTATION_LOCKED = 14 }
