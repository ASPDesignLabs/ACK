package com.example.besu.wear

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.material.Text
import kotlinx.coroutines.delay
import kotlin.math.abs

@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun TargetSelectionOverlay(
    activeTargetIndex: Int,
    onSelect: (Int, Boolean) -> Unit, // Returns Index + Sticky Mode
    onDismiss: () -> Unit
) {
    // 0..7 are slots, 8 is "CLEAR TARGET"
    var selectionIndex by remember { mutableIntStateOf(if(activeTargetIndex == -1) 0 else activeTargetIndex) }
    
    // Toggle for Latching Mode (Single Use vs Locked)
    var isSticky by remember { mutableStateOf(false) }
    
    // TIMEOUT LOGIC
    var lastInteraction by remember { mutableLongStateOf(System.currentTimeMillis()) }
    
    LaunchedEffect(lastInteraction) {
        delay(5000) // 5 Second Inactivity Timeout
        onDismiss()
    }

    val focusRequester = remember { FocusRequester() }
    var scrollAccumulator by remember { mutableFloatStateOf(0f) }
    val crownThreshold = 40f

    LaunchedEffect(Unit) { focusRequester.requestFocus() }

    val infiniteTransition = rememberInfiniteTransition()
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.5f, targetValue = 1.0f,
        animationSpec = infiniteRepeatable(tween(500, easing = LinearEasing), RepeatMode.Reverse)
    )

    // Outer box provides constraints for split-screen tap logic
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.95f)),
        contentAlignment = Alignment.Center
    ) {
        val midPointPx = constraints.maxWidth / 2f

        // Inner Box handles Inputs
        Box(
            modifier = Modifier
                .fillMaxSize()
                .onRotaryScrollEvent {
                    lastInteraction = System.currentTimeMillis()
                    scrollAccumulator += it.verticalScrollPixels
                    
                    if (abs(scrollAccumulator) > crownThreshold) {
                        val direction = if (scrollAccumulator > 0) 1 else -1
                        val next = selectionIndex + direction
                        
                        // Wrap 0-8
                        selectionIndex = if (next > 8) 0 else if (next < 0) 8 else next
                        
                        // AUDIO GUIDE: Rising/Falling Pitch
                        TechSynth.playNavTone(selectionIndex)
                        
                        scrollAccumulator = 0f
                    }
                    true
                }
                .focusRequester(focusRequester)
                .pointerInput(Unit) {
                    detectTapGestures(
                        onTap = { offset ->
                            lastInteraction = System.currentTimeMillis()
                            
                            var changed = false
                            // Left Half = Previous, Right Half = Next
                            if (offset.x < midPointPx) {
                                val next = selectionIndex - 1
                                selectionIndex = if (next < 0) 8 else next
                                changed = true
                            } else {
                                val next = selectionIndex + 1
                                selectionIndex = if (next > 8) 0 else next
                                changed = true
                            }
                            
                            if (changed) {
                                TechSynth.playNavTone(selectionIndex)
                            }
                        },
                        onDoubleTap = {
                            // Toggle Sticky Mode (unless clearing)
                            if (selectionIndex != 8) {
                                isSticky = !isSticky
                                TechSynth.play(TechSynth.Sfx.MODIFIER) // Confirm toggle
                            }
                        },
                        onLongPress = {
                            // Confirm Selection
                            if (selectionIndex == 8) onSelect(-1, false) 
                            else onSelect(selectionIndex, isSticky)
                        }
                    )
                }
        ) {
            // --- VISUALS ---
            
            // Reticle
            Canvas(modifier = Modifier.fillMaxSize()) {
                val baseColor = if(selectionIndex == 8) CyberAmber else CyberGreen
                
                // Visuals update based on Sticky Mode
                val displayColor = if(isSticky) baseColor else baseColor.copy(alpha=0.7f)
                val bgAlpha = if(isSticky) 0.2f else 0.05f
                val ringWidth = if(isSticky) 4f else 2f
                
                // Background Glow
                drawCircle(displayColor.copy(alpha=bgAlpha), radius = size.minDimension/2.2f)
                
                // Main Ring
                drawCircle(displayColor, radius = size.minDimension/2.2f, style = Stroke(width = ringWidth))
                
                // Paging Ticks (Vertical Hints)
                drawLine(displayColor.copy(alpha=0.3f), start = Offset(size.width/2, 10f), end = Offset(size.width/2, 30f), strokeWidth = 2f)
                drawLine(displayColor.copy(alpha=0.3f), start = Offset(size.width/2, size.height-10f), end = Offset(size.width/2, size.height-30f), strokeWidth = 2f)
                
                // Crosshairs (Only visible when Locked/Sticky)
                if (isSticky) {
                    val r = size.minDimension/2.2f
                    val cx = size.width/2
                    val cy = size.height/2
                    // Horizontal
                    drawLine(displayColor, start = Offset(cx - r, cy), end = Offset(cx + r, cy), strokeWidth = 1f)
                    // Vertical
                    drawLine(displayColor, start = Offset(cx, cy - r), end = Offset(cx, cy + r), strokeWidth = 1f)
                }
            }

            // Text Info
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.align(Alignment.Center)) {
                Text("TARGET LINK", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Spacer(modifier = Modifier.height(8.dp))
                
                val isClearOption = selectionIndex == 8
                val label = if (isClearOption) "CLEAR LOCK" else TargetCache.getLabel(selectionIndex)
                val color = if (isClearOption) CyberAmber else CyberGreen
                
                // Main Label
                Text(
                    text = label.uppercase(),
                    color = if(isSticky) color else color.copy(alpha = pulseAlpha),
                    fontSize = if(label.length > 8) 16.sp else 24.sp,
                    fontWeight = FontWeight.Bold,
                    fontFamily = FontFamily.Monospace
                )
                
                Spacer(modifier = Modifier.height(4.dp))
                
                // Subtext
                if (!isClearOption) {
                    val modeText = if(isSticky) "LOCKED" else "ONCE"
                    Text("SLOT ${selectionIndex + 1} [$modeText]", color = color.copy(alpha=0.5f), fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                } else {
                    Text("DISENGAGE", color = color.copy(alpha=0.5f), fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                }
            }
            
            // Footer Hint
            Box(modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 30.dp)) {
                Text("HOLD TO CONFIRM", color = Color.DarkGray, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
            }
            
            // Paging Arrows Hints
            Box(modifier = Modifier.align(Alignment.CenterStart).padding(start=10.dp)) {
                Text("<", color = Color.Gray.copy(alpha=0.5f), fontSize = 12.sp)
            }
            Box(modifier = Modifier.align(Alignment.CenterEnd).padding(end=10.dp)) {
                Text(">", color = Color.Gray.copy(alpha=0.5f), fontSize = 12.sp)
            }
        }
    }
}
