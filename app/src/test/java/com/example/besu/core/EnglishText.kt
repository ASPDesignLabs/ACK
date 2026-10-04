// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale

/**
 * The tests' [TextSource]: the real English strings file, so a test of a warning or a confirmation reads the words a person sees. A plurals entry is chosen
 * by English's own rule (one for 1, otherwise other).
 */
object EnglishText : TextSource {
    private val strings: Map<String, String> by lazy { StringsXml.map(StringsXml.default) }
    private val plurals: Map<String, Map<String, String>> by lazy { StringsXml.plurals(StringsXml.default) }

    override fun get(name: String, vararg args: Any): String {
        val text = strings[name] ?: return name
        return if (args.isEmpty()) text else String.format(Locale.ROOT, text, *args)
    }

    override fun count(name: String, quantity: Int): String {
        val forms = plurals[name] ?: return name
        val text = if (quantity == 1) forms["one"] ?: forms.getValue("other") else forms.getValue("other")
        return String.format(Locale.ROOT, text, quantity)
    }
}
