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
}
