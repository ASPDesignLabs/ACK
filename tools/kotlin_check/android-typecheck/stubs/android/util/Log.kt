// SPDX-License-Identifier: GPL-3.0-or-later
package android.util
object Log {
    fun i(tag: String, msg: String): Int = 0
    fun w(tag: String, msg: String): Int = 0
    fun e(tag: String, msg: String): Int = 0
    fun e(tag: String, msg: String, t: Throwable?): Int = 0
}
