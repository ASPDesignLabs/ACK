// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.io.File

/**
 * Finds the repository's source files from the test's working directory (the `app` module folder under Android's unit-test
 * run and under tools/kotlin_check), the same walk-upwards approach capture/Vectors.kt uses. Lets a test read the app's own
 * source, which is how the drift guards (ExportContentsTest, StorageCatalogueTest) notice a new field or storage area.
 */
object RepoFiles {
    private const val MARKER = "app/src/main/java/com/example/besu/backup/AckBackup.kt"

    val root: File by lazy {
        var d: File? = File(System.getProperty("user.dir")).absoluteFile
        while (d != null && !File(d, MARKER).isFile) d = d.parentFile
        d ?: error("can't find $MARKER above ${System.getProperty("user.dir")}")
    }

    fun file(relativePath: String): File = File(root, relativePath)

    fun read(relativePath: String): String = file(relativePath).readText(Charsets.UTF_8)

    /** The app's Kotlin source folder. */
    val appSource: File get() = file("app/src/main/java")

    /**
     * The whole declaration of `fun [name](` in an object whose members are indented four spaces: from the `fun` to the line before the next member.
     * Unlike a brace-matching helper it also holds for an expression body (`fun x() = y`), which has no braces of its own to match; a brace
     * matcher run on one silently reads the NEXT function's body, and a test built on it passes or fails by accident.
     */
    fun declarationOf(text: String, name: String): String {
        val at = text.indexOf("fun $name(")
        check(at >= 0) { "fun $name( not found" }
        val next = Regex("""\n    (/\*\*|//|fun |private fun |internal fun |@|val |private val |const |private const )""").find(text, at + 1)
        return text.substring(at, next?.range?.first ?: text.length)
    }
}
