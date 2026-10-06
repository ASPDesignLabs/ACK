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
     * The code from the first `{` after [signature] to its matching `}`, with `//` comments removed so that a word in an
     * explanatory comment is never mistaken for a call. For the source-reading guards of Android-only files (they cannot run on a
     * JVM). Only for bodies with no `//` inside a string.
     */
    fun functionBody(source: String, signature: String): String {
        val start = source.indexOf(signature)
        check(start >= 0) { "$signature not found" }
        val open = source.indexOf('{', start)
        check(open >= 0) { "no body after $signature" }
        var depth = 0
        for (i in open until source.length) {
            when (source[i]) {
                '{' -> depth++
                '}' -> {
                    depth--
                    if (depth == 0) return withoutLineComments(source.substring(open, i + 1))
                }
            }
        }
        error("unbalanced braces after $signature")
    }

    private fun withoutLineComments(code: String): String = code.lines().joinToString("\n") { it.substringBefore("//") }
}
