package com.example.besu

import android.content.Context
import androidx.appcompat.app.AppCompatDelegate

object ThemeManager {
    private const val PREF_THEME = "app_theme_mode"

    fun applyTheme(context: Context) {
        val prefs = context.getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        val isNight = prefs.getBoolean(PREF_THEME, false) // Default to Day (false)

        if (isNight) {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES)
        } else {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO)
        }
    }

    fun isNightMode(context: Context): Boolean {
        val prefs = context.getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        return prefs.getBoolean(PREF_THEME, false)
    }

    fun setNightMode(context: Context, isNight: Boolean) {
        val prefs = context.getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        prefs.edit().putBoolean(PREF_THEME, isNight).apply()

        if (isNight) {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_YES)
        } else {
            AppCompatDelegate.setDefaultNightMode(AppCompatDelegate.MODE_NIGHT_NO)
        }
    }
}