// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.data

import android.content.Context
import android.content.res.Configuration
import android.util.Log
import com.example.besu.core.ActiveScript
import com.example.besu.core.InterfaceLanguagePolicy
import java.util.Locale

/**
 * The Android edge of INTERFACE LANGUAGE (rules and tests in core/InterfaceLanguage.kt). MainActivity calls [wrap] from `attachBaseContext`, so every
 * string resource the screens read, and the layout direction, come from the chosen language. Following the phone (DEVICE) leaves the context alone and
 * Android picks the matching `values-xx` folder itself; any named language, English included, is applied here.
 *
 * It never stops ACK from opening: if anything goes wrong it logs one fixed line and returns the context unchanged, which shows English.
 */
object InterfaceLocale {
    private const val TAG = "ACK_INTERFACE_LOCALE"

    fun wrap(base: Context): Context {
        return try {
            val setting = AssistPrefs.interfaceLanguage(base)
            val locales = base.resources.configuration.locales
            val deviceLanguage = if (locales.isEmpty) "" else locales[0].language
            val tag = InterfaceLanguagePolicy.effectiveTag(setting, deviceLanguage)
            ActiveScript.use(tag)
            if (!InterfaceLanguagePolicy.mustApply(setting)) return base

            val locale = Locale.forLanguageTag(tag)
            val configuration = Configuration(base.resources.configuration)
            configuration.setLocale(locale)
            configuration.setLayoutDirection(locale)
            base.createConfigurationContext(configuration)
        } catch (e: Exception) {
            Log.e(TAG, "could not apply the interface language, showing English", e)
            base
        }
    }
}
