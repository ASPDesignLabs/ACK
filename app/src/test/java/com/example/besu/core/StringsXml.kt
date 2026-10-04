// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Reads Android string resources (the strings.xml files under res) on a JVM, so the label table, its translations and the placeholders in them can be
 * checked without the Android SDK. Test-only: the app itself reads resources through Android.
 */
object StringsXml {
    class Entry(val name: String, val text: String, val translatable: Boolean)

    /** Every `<string>` of [file], in file order, with Android's escapes (`\'`, `\"`, `\n`, `\\`, `\@`, `\?`, `\uXXXX`) resolved. */
    fun read(file: File): List<Entry> {
        require(file.isFile) { "missing strings file: ${file.path}" }
        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file)
        val nodes = doc.getElementsByTagName("string")
        return (0 until nodes.length).map { i ->
            val node = nodes.item(i)
            val name = node.attributes.getNamedItem("name").nodeValue
            val translatable = node.attributes.getNamedItem("translatable")?.nodeValue != "false"
            Entry(name, unescape(node.textContent.trim()), translatable)
        }
    }

    fun map(file: File): Map<String, String> = read(file).associate { it.name to it.text }

    fun unescape(raw: String): String {
        val out = StringBuilder()
        var i = 0
        while (i < raw.length) {
            val c = raw[i]
            if (c == '\\' && i + 1 < raw.length) {
                when (val n = raw[i + 1]) {
                    'n' -> { out.append('\n'); i += 2 }
                    't' -> { out.append('\t'); i += 2 }
                    'u' -> {
                        out.append(raw.substring(i + 2, i + 6).toInt(16).toChar())
                        i += 6
                    }
                    else -> { out.append(n); i += 2 }
                }
            } else {
                out.append(c)
                i++
            }
        }
        return out.toString()
    }

    /** The `%1$s`-style format placeholders of a string, in order of appearance (`%%` is not one). */
    fun placeholders(text: String): List<String> =
        Regex("""%(?:\d+\$)?[sdf]""").findAll(text.replace("%%", "")).map { it.value }.toList()

    private val resRoot get() = RepoFiles.file("app/src/main/res")

    /** The default (English) strings file. */
    val default: File get() = File(resRoot, "values/strings.xml")

    /** Every translated strings file, by locale folder suffix (`es`, `pt`, ...). */
    fun translations(): Map<String, File> =
        (resRoot.listFiles() ?: emptyArray())
            .filter { it.isDirectory && Regex("""values-[a-z]{2,3}""").matches(it.name) }
            .map { it.name.removePrefix("values-") to File(it, "strings.xml") }
            .filter { it.second.isFile }
            .toMap()
}
