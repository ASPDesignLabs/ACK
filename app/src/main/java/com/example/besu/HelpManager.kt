package com.example.besu

import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

class HelpManager(
    private val modules: List<HelpModule>
) {
    var activeModule by mutableStateOf<HelpModule?>(null)
        private set

    var currentStepIndex by mutableStateOf(0)
        private set

    var destinationRequest by mutableStateOf<HelpDestination?>(null)
        private set

    var completedCategory by mutableStateOf<HelpCategory?>(null)
        private set

    val isActive: Boolean
        get() = activeModule != null

    val currentStep: HelpStep?
        get() = activeModule?.steps?.getOrNull(currentStepIndex)

    fun start(moduleId: String) {
        val module = modules.firstOrNull { it.id == moduleId } ?: return

        completedCategory = null
        activeModule = module
        currentStepIndex = 0
        destinationRequest = currentStep?.destination ?: module.destination
    }

    fun advanceReadStep() {
        if (currentStep?.action == HelpAction.Read) {
            next()
        }
    }

    fun onEvent(event: HelpEvent) {
        // TODO(smoke test): remove this Log.d once watch gesture telemetry is confirmed landing.
        Log.d("ACK_HELP_EVENT", "onEvent: $event (active module=${activeModule?.id})")

        val step = currentStep ?: return

        if (matches(step.action, event)) {
            next()
        }
    }

    fun destinationHandled(destination: HelpDestination) {
        if (destinationRequest == destination) {
            destinationRequest = null
        }
    }

    fun completionHandled() {
        completedCategory = null
    }

    fun abort() {
        activeModule = null
        currentStepIndex = 0
        destinationRequest = null
        completedCategory = null
    }

    private fun next() {
        val module = activeModule ?: return

        if (currentStepIndex >= module.steps.lastIndex) {
            complete(module)
            return
        }

        currentStepIndex += 1
        destinationRequest = currentStep?.destination
    }

    private fun complete(module: HelpModule) {
        activeModule = null
        currentStepIndex = 0
        destinationRequest = null
        completedCategory = module.category
    }

    private fun matches(
        action: HelpAction,
        event: HelpEvent
    ): Boolean {
        return when (action) {
            HelpAction.Read -> false

            is HelpAction.Interact -> {
                event is HelpEvent.Interacted &&
                        event.targetTag == action.targetTag
            }

            is HelpAction.CommitText -> {
                event is HelpEvent.TextCommitted &&
                        event.targetTag == action.targetTag
            }

            is HelpAction.CommitFile -> {
                event is HelpEvent.FileCommitted &&
                        event.targetTag == action.targetTag
            }

            is HelpAction.OverlayCleared -> {
                event is HelpEvent.OverlayWasCleared &&
                        event.targetTag == action.targetTag
            }

            is HelpAction.WatchEvent -> {
                event is HelpEvent.WatchInput &&
                        event.eventType == action.eventType
            }

            is HelpAction.DeckSelected -> {
                event is HelpEvent.DeckWasSelected &&
                        event.targetTag == action.targetTag
            }

            is HelpAction.ProfileSelected -> {
                event is HelpEvent.ProfileWasSelected &&
                        event.targetTag == action.targetTag
            }

            is HelpAction.KeyboardDismissed -> {
                event is HelpEvent.KeyboardWasDismissed &&
                        event.targetTag == action.targetTag
            }
        }
    }
}
