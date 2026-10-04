// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Two lines of text with nothing joining them are not one sentence in Kotlin: the first is an unused value and only the second is used. In a
 * `when` branch that built a confirmation (ui/DesignSystem.kt, the clear-variables dialog) it quietly dropped the first sentence of the question the
 * person was being asked before a delete. Inside a `listOf(` the same slip is a build error. Neither can be seen without running the screen, and the
 * app cannot be built here, so this reads every source file and fails on a line that is only a quoted text followed by a line that starts a quoted
 * text. A real line of a longer text ends in `+` or a comma, or is a `->` branch, and none of those are matched.
 */
class AdjacentTextLinesTest {

    private val onlyAQuotedText = Regex("""^"(?:[^"\\]|\\.)*"$""")

    private fun sourceFiles() = listOf("app/src/main/java", "wear/src/main/java")
        .map { RepoFiles.file(it) }
        .filter { it.isDirectory }
        .flatMap { dir -> dir.walkTopDown().filter { it.isFile && it.extension == "kt" }.toList() }

    @Test
    fun noLineOfTextIsFollowedByAnotherWithNothingJoiningThem() {
        val offenders = mutableListOf<String>()
        for (file in sourceFiles()) {
            val lines = file.readText(Charsets.UTF_8).lines().map { it.trim() }
            for (i in 0 until lines.size - 1) {
                val a = lines[i]
                val b = lines[i + 1]
                if (a.contains("\"\"\"") || b.contains("\"\"\"")) continue
                if (onlyAQuotedText.matches(a) && b.startsWith("\"")) {
                    offenders += "${file.name}:${i + 1}  $a  //  $b"
                }
            }
        }
        assertTrue("two lines of text with nothing joining them (add a + or a comma): $offenders", offenders.isEmpty())
    }

    @Test
    fun theRuleSeesTheSlipItIsHereToCatch() {
        // The shape that was in the clear-variables dialog, and the two shapes that are fine.
        val slip = listOf("\"Clear this prompt only? \"", "\"will be preserved.\"")
        val joined = listOf("\"Clear this prompt only? \" +", "\"will be preserved.\"")
        val branches = listOf("\"VARS\" -> {", "\"A\"")
        assertTrue(onlyAQuotedText.matches(slip[0]) && slip[1].startsWith("\""))
        assertTrue(!onlyAQuotedText.matches(joined[0]))
        assertTrue(!onlyAQuotedText.matches(branches[0]))
    }
}
