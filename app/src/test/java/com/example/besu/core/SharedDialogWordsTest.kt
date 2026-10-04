// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The shared dialog surface (ui/OverlayStyle.kt: TightDialogSurface) draws "[CLOSE]" in its header for every dialog that does not name its own word, about fifty of them.
 * That default is now the resource for CLOSE, so those dialogs say it in the chosen language too. It cannot be compiled here, so this reads it.
 */
class SharedDialogWordsTest {

    private val overlay get() = RepoFiles.read("app/src/main/java/com/example/besu/ui/OverlayStyle.kt").lines().filterNot { it.trimStart().startsWith("//") }.joinToString("\n")
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }

    @Test
    fun theDefaultCloseWordIsTheResource_andNotALiteral() {
        assertTrue(overlay.contains("dismissLabel: String = stringResource(R.string.common_close),"))
        assertFalse("the literal default is gone", overlay.contains("dismissLabel: String = \"CLOSE\""))
        assertTrue("an explicit R import outside the base package", overlay.contains("import com.example.besu.R"))
        assertTrue(overlay.contains("import androidx.compose.ui.res.stringResource"))
        // The header still shows the word in brackets and a tap on it still dismisses.
        assertTrue(overlay.contains("text = \"[\$dismissLabel]\","))
        assertTrue(Regex("""text = "\[\${'$'}dismissLabel\]"[\s\S]{0,400}?\.clickable\(onClick = onDismiss\)""").containsMatchIn(overlay))
    }

    @Test
    fun closeIsRealAndDifferentFromCancelAndDone_inEveryLanguage() {
        assertEquals("CLOSE", english.getValue("common_close"))
        for ((tag, map) in translations) {
            assertNotEquals("$tag: still English", "CLOSE", map.getValue("common_close"))
            assertNotEquals("$tag: CLOSE reads like CANCEL", map.getValue("common_cancel"), map.getValue("common_close"))
            assertNotEquals("$tag: CLOSE reads like DELETE", map.getValue("common_delete"), map.getValue("common_close"))
        }
    }
}
