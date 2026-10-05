// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The Terminal's big text list (`/info`'s patch notes) is a Kotlin `listOf(...)` block in ui/DesignSystem.kt, which cannot be compiled without the
 * Android SDK. A missing comma between two lines is a build error there, and an edit to this list is made in nearly every release, so this checks
 * the shape of every line: one quoted line, a comma after it (not after the last), no `$` (which would start a template), no stray quote.
 * (The `/help` list used to be one too; it is built from core/TerminalText.kt now and checked by TerminalTextTest.)
 */
class TerminalTextListsShapeTest {

    private fun block(name: String): List<String> {
        val text = RepoFiles.read("app/src/main/java/com/example/besu/ui/DesignSystem.kt")
        val start = text.indexOf("private val $name = listOf(\n")
        assertTrue("$name not found", start >= 0)
        val from = text.indexOf('\n', start) + 1
        val end = text.indexOf("\n)\n", from)
        assertTrue("end of $name not found", end > from)
        return text.substring(from, end).lines()
    }

    private fun checkShape(name: String) {
        val lines = block(name)
        assertTrue("$name is empty", lines.isNotEmpty())
        lines.forEachIndexed { i, raw ->
            val line = raw.trim()
            val last = i == lines.lastIndex
            assertTrue("$name line ${i + 1} is not a quoted line: $line", line.startsWith("\"") && (line.endsWith("\",") || line.endsWith("\"")))
            if (last) {
                assertTrue("$name: the last line must not end with a comma: $line", !line.endsWith(","))
            } else {
                assertTrue("$name line ${i + 1} has no comma after it (a build error): $line", line.endsWith("\","))
            }
            val inside = line.removeSuffix(",").removePrefix("\"").removeSuffix("\"")
            assertTrue("$name line ${i + 1} has a quote inside it: $line", !inside.replace("\\\"", "").contains('"'))
            assertTrue("$name line ${i + 1} has a dollar sign (a template): $line", !inside.contains('$'))
        }
    }

    @Test
    fun theInfoPatchNotesAreWellFormed() = checkShape("PATCH_NOTES")

    @Test
    fun theHelpListIsNoLongerAKotlinListInTheScreen() {
        val text = RepoFiles.read("app/src/main/java/com/example/besu/ui/DesignSystem.kt")
        assertTrue(!text.contains("TERMINAL_HELP_LINES"))
        assertTrue(text.contains("TerminalText.helpLines(ResourceText(context))"))
    }
}
