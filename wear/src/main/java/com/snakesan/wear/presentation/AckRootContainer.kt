package com.example.besu.wear

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeoutOrNull

@Composable
fun AckRootContainer(
    onTap: () -> Unit,
    onDoubleTap: () -> Unit,
    onLongPress: () -> Unit, // Re-mapped to standard Long Press (Cryo)
    onTapTapHold: () -> Unit, // THE NEW GESTURE
    content: @Composable BoxScope.() -> Unit
) {
    var lastTapTime by remember { mutableLongStateOf(0L) }
    
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(CyberBg)
            .pointerInput(Unit) {
                awaitPointerEventScope {
                    while (true) {
                        val down = awaitFirstDown()
                        val downTime = System.currentTimeMillis()
                        
                        // Check if this is the 2nd tap of a sequence
                        val isSecondTap = (downTime - lastTapTime) < 300 // 300ms window
                        
                        if (isSecondTap) {
                            // POTENTIAL TAP-TAP-HOLD
                            // Wait 500ms to see if they hold it
                            val upOrCancel = withTimeoutOrNull(500) {
                                waitForUpOrCancellation()
                            }
                            
                            if (upOrCancel == null) {
                                // Timeout reached = User is still holding = TAP-TAP-HOLD
                                onTapTapHold()
                                // Consume input until release
                                waitForUpOrCancellation()
                            } else {
                                // User lifted finger = DOUBLE TAP
                                onDoubleTap()
                            }
                            // Reset sequence
                            lastTapTime = 0L 
                            
                        } else {
                            // FIRST TAP
                            // Wait to see if it's a Long Press
                            val upOrCancel = withTimeoutOrNull(500) {
                                waitForUpOrCancellation()
                            }
                            
                            if (upOrCancel == null) {
                                // Timeout reached = LONG PRESS
                                onLongPress()
                                waitForUpOrCancellation()
                            } else {
                                // User lifted = SINGLE TAP
                                onTap()
                                lastTapTime = System.currentTimeMillis()
                            }
                        }
                    }
                }
            },
        content = content
    )
}
