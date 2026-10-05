// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.content.res.Configuration
import com.example.besu.core.ActiveScript
import com.example.besu.core.TextSource
import java.util.Locale

/**
 * The app's [TextSource]: string resources, in the language of the [context] (the main screen's context has the chosen interface language applied,
 * data/InterfaceLocale.kt). A name that is not a resource reads as itself, so a gap is visible rather than a crash or a blank.
 */
class ResourceText(private val context: Context) : TextSource {
    /** The language the words are really in (the chosen one, or the phone's if ACK has it, otherwise English), not the phone's own setting. */
    override val languageTag: String get() = ActiveScript.tag

    override fun get(name: String, vararg args: Any): String {
        val id = context.resources.getIdentifier(name, "string", context.packageName)
        if (id == 0) return name
        return if (args.isEmpty()) context.getString(id) else context.getString(id, *args)
    }

    override fun count(name: String, quantity: Int): String {
        val id = context.resources.getIdentifier(name, "plurals", context.packageName)
        if (id == 0) return name
        return context.resources.getQuantityString(id, quantity, quantity)
    }

    override fun count(name: String, quantity: Int, vararg args: Any): String {
        val id = context.resources.getIdentifier(name, "plurals", context.packageName)
        if (id == 0) return name
        return context.resources.getQuantityString(id, quantity, quantity, *args)
    }
}

/**
 * A context whose string resources are English (the base `values/` folder) whatever language the screens are in, for the one place that must read English on purpose: the
 * spoken guide, when the voice is not speaking the screens' language (core/HelpWalkthroughText.kt). It never throws; if the configuration cannot be made it returns [base].
 */
object EnglishResources {
    fun context(base: Context): Context = try {
        val configuration = Configuration(base.resources.configuration)
        configuration.setLocale(Locale.ENGLISH)
        configuration.setLayoutDirection(Locale.ENGLISH)
        base.createConfigurationContext(configuration)
    } catch (e: Exception) {
        base
    }
}
