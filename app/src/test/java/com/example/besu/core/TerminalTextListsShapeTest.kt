// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * The Terminal used to hold two big hand-written text lists (`/help` and `/info`'s patch notes) in ui/DesignSystem.kt, which cannot be compiled without the Android SDK: a missing comma between two lines was
 * a build error there, and these lists were edited in nearly every release, so this test checked the shape of every line. Both lists are string resources now (core/TerminalText.kt, core/PatchNotes.kt), compiled
 * and tested on a JVM, so what is left to guard is that nobody puts a list of lines back in the screen file, where it would be English only and unchecked.
 */
class TerminalTextListsShapeTest {

    @Test
    fun theScreenFileHoldsNoHandWrittenListOfTextLines() {
        val text = RepoFiles.read("app/src/main/java/com/example/besu/ui/DesignSystem.kt")
        // A list of lines is a `private val NAME = listOf(` that opens a block (a quoted entry on each following line), as /help and the patch notes were.
        val lists = Regex("""private val (\w+) = listOf\(\n""").findAll(text).map { it.groupValues[1] }.toList()
        assertEquals("a list of lines moved into the screen file again (use string resources and core/): $lists", emptyList<String>(), lists)
    }

    @Test
    fun theTwoListsAreBuiltFromResourcesInCore() {
        val text = RepoFiles.read("app/src/main/java/com/example/besu/ui/DesignSystem.kt")
        assertEquals(1, Regex("""TerminalText\.helpLines\(ResourceText\(context\)\)""").findAll(text).count())
        assertEquals(1, Regex("""PatchNotes\.lines\(ResourceText\(context\)\)""").findAll(text).count())
    }
}
