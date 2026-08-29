package com.example.besu

import androidx.compose.runtime.*

class TutorialManager {
    var activeModule by mutableStateOf<List<TutorialDef>?>(null)
    var currentStepIndex by mutableStateOf(0)
    
    val currentStep: TutorialDef?
        get() = activeModule?.getOrNull(currentStepIndex)

    val isActive: Boolean
        get() = activeModule != null

    fun startModule(module: List<TutorialDef>) {
        currentStepIndex = 0
        activeModule = module
    }

    fun next() {
        if (activeModule != null && currentStepIndex < activeModule!!.size - 1) {
            currentStepIndex++
        } else {
            abort() // End of module
        }
    }

    fun abort() {
        activeModule = null
        currentStepIndex = 0
    }

    // Called by UI clicks
    fun onInteraction(tag: String) {
        if (currentStep?.action == TutAction.INTERACT && currentStep?.targetTag == tag) {
            next()
        }
    }

    // Called by Watch Listener
    fun onWatchEvent(eventType: String) {
        if (currentStep?.action == TutAction.WATCH_INPUT) {
            // Logic to match specific watch events to steps
            // Step 1 expects "ARMED" status
            // Step 3 expects "POSE_ID"
            // Step 5 expects "FIRE"
            val expected = when(currentStepIndex) {
                1 -> "ARMED"
                3 -> "POSE_ID"
                4 -> "MODIFIED"
                5 -> "FIRE"
                else -> ""
            }
            
            if (eventType == expected) {
                next()
            }
        }
    }
}
