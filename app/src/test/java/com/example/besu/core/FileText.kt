// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import java.util.Locale

/**
 * A [TextSource] that reads one real translation file (`values-<tag>/strings.xml`), so a test can check what a screen would say in Spanish, Arabic and the rest.
 * Plurals use the "other" form (a test of a plural's forms is TranslationsTest's job).
 */
class FileText(override val languageTag: String) : TextSource {
    private val file = StringsXml.translations().getValue(languageTag)
    private val strings: Map<String, String> by lazy { StringsXml.map(file) }
    private val plurals: Map<String, Map<String, String>> by lazy { StringsXml.plurals(file) }

    override fun get(name: String, vararg args: Any): String {
        val text = strings[name] ?: return name
        return if (args.isEmpty()) text else String.format(Locale.ROOT, text, *args)
    }

    override fun count(name: String, quantity: Int): String {
        val forms = plurals[name] ?: return name
        return String.format(Locale.ROOT, forms.getValue("other"), quantity)
    }
}
