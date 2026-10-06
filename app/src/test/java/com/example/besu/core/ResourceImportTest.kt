// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * `R` is the app's generated resource class, and several libraries ship an `R` of their own. A file that says `import com.example.besu.*` (or any
 * other wildcard that brings a library's `R` in) and then writes `R.string.x` gets "None of the following candidates is applicable: class R ..."
 * from the compiler, 48 times over. An explicit `import com.example.besu.R` wins over every wildcard, so every file outside the base package that uses
 * `R.string.` or `R.drawable.` etc. must have it. (Found when DesignSystem.kt broke the build: this test could not run the compiler, so it reads the files.)
 */
class ResourceImportTest {

    @Test
    fun everyFileOutsideTheBasePackageThatUsesTheResourceClassImportsItExplicitly() {
        val root = RepoFiles.file("app/src/main/java")
        val offenders = root.walkTopDown().filter { it.isFile && it.extension == "kt" }.filter { file ->
            val text = file.readText(Charsets.UTF_8)
            val pkg = Regex("""^package\s+([\w.]+)""", RegexOption.MULTILINE).find(text)?.groupValues?.get(1).orEmpty()
            val code = text.lines().filterNot { it.trimStart().let { t -> t.startsWith("//") || t.startsWith("*") || t.startsWith("/*") } }.joinToString("\n")
            val usesR = Regex("""(?<![\w.])R\.(string|drawable|color|font|raw|array|plurals|dimen|xml|mipmap|layout|id)\b""").containsMatchIn(code)
            usesR && pkg != "com.example.besu" && !Regex("""^import com\.example\.besu\.R$""", RegexOption.MULTILINE).containsMatchIn(text)
        }.map { it.name }.toList()
        assertTrue("these files use R without `import com.example.besu.R` (a wildcard import is not enough): $offenders", offenders.isEmpty())
    }
}
