package com.example.besu

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

class ProfileWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        for (appWidgetId in appWidgetIds) {
            updateAppWidget(context, appWidgetManager, appWidgetId)
        }
    }

    // Handle button clicks
    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        
        if (intent.action?.startsWith("ACTION_SET_PROFILE") == true) {
            val profile = intent.getStringExtra("PROFILE_KEY") ?: "DEFAULT"
            
            // 1. Tell the Core Service to switch (Also triggers voice)
            val serviceIntent = Intent(context, OutputService::class.java)
            serviceIntent.action = "CHANGE_PROFILE"
            serviceIntent.putExtra("NEW_PROFILE", profile)
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent)
            } else {
                context.startService(serviceIntent)
            }

            // 2. Force Widget Redraw to show active state
            val appWidgetManager = AppWidgetManager.getInstance(context)
            val ids = appWidgetManager.getAppWidgetIds(ComponentName(context, ProfileWidget::class.java))
            for (id in ids) {
                updateAppWidget(context, appWidgetManager, id)
            }
        }
    }

    companion object {
        fun updateAppWidget(context: Context, appWidgetManager: AppWidgetManager, appWidgetId: Int) {
            // Get Current Profile to highlight the correct button
            val currentProfile = CommandRepository.getActiveProfile(context)

            val views = RemoteViews(context.packageName, R.layout.widget_profile)

            // Setup buttons
            setupButton(context, views, R.id.btn_builder, "BUILDER", currentProfile)
            setupButton(context, views, R.id.btn_work, "WORK", currentProfile)
            setupButton(context, views, R.id.btn_stress, "HIGH_STRESS", currentProfile)
            setupButton(context, views, R.id.btn_social, "SOCIAL", currentProfile)
            setupButton(context, views, R.id.btn_default, "DEFAULT", currentProfile)

            appWidgetManager.updateAppWidget(appWidgetId, views)
        }

        private fun setupButton(context: Context, views: RemoteViews, viewId: Int, profileKey: String, activeProfile: String) {
            val isActive = profileKey == activeProfile
            
            // Styling Logic (Neon Flux emulation for RemoteViews)
            // We use simple shapes because RemoteViews are limited
            if (isActive) {
                views.setInt(viewId, "setBackgroundColor", 0xFF00F3FF.toInt()) // Cyan
                views.setTextColor(viewId, 0xFF050505.toInt()) // Black text
            } else {
                views.setInt(viewId, "setBackgroundColor", 0xFF121212.toInt()) // Graphite
                views.setTextColor(viewId, 0xFF00F3FF.toInt()) // Cyan text
            }

            // Click Intent
            val intent = Intent(context, ProfileWidget::class.java).apply {
                action = "ACTION_SET_PROFILE"
                putExtra("PROFILE_KEY", profileKey)
            }
            val pendingIntent = PendingIntent.getBroadcast(
                context, 
                profileKey.hashCode(), // Unique ID per button
                intent, 
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            views.setOnClickPendingIntent(viewId, pendingIntent)
        }
    }
}
