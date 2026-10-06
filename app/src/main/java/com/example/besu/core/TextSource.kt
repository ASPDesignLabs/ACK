// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * Where a decision's words come from. The decisions that say what a confirmation or a warning contains (core/ExportContents.kt, core/BackupReminderText.kt)
 * stay in plain Kotlin and are tested on a JVM; the words themselves are string resources, so they are in the chosen language. The app's TextSource reads
 * Android resources (ui/ResourceText.kt); the tests' reads the English strings file, so every test of the wording still reads the real English text.
 */
interface TextSource {
    /** The text named [name] (a string resource), with [args] filled in the way a format string does. A name that does not exist reads as itself, so a gap shows. */
    fun get(name: String, vararg args: Any): String

    /** The text named [name] (a plurals resource) in the word form that fits [quantity], with the quantity filled in. */
    fun count(name: String, quantity: Int): String

    /**
     * Like [count], for a plural sentence that also holds other arguments: [args] follow the quantity, so `%1$d` is the quantity and `%2$s` the first of [args]. The real sources override it;
     * a source that does not simply ignores the extra arguments and reads as [count].
     */
    fun count(name: String, quantity: Int, vararg args: Any): String = count(name, quantity)

    /** The language these words are in (a BCP 47 tag such as "es" or "ar-EG"), so a date can use that language's month names. English unless the source says otherwise. */
    val languageTag: String get() = "en"
}
