package com.example.besu

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

val AckHelpShape = CutCornerShape(
    topStart = 10.dp,
    topEnd = 2.dp,
    bottomStart = 2.dp,
    bottomEnd = 10.dp
)
@Composable
fun Modifier.helpTarget(
    tag: String,
    primaryColor: Color
): Modifier {
    val manager = LocalHelpManager.current
    val step = manager?.currentStep
    val isActiveTarget = step?.targetTag == tag

    if (!isActiveTarget) {
        return this
    }

    val transition = rememberInfiniteTransition(
        label = "help_target_pulse"
    )

    val alpha = transition.animateFloat(
        initialValue = 0.35f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(700),
            repeatMode = RepeatMode.Reverse
        ),
        label = "help_target_alpha"
    ).value

    return this
        .background(
            color = primaryColor.copy(alpha = 0.14f * alpha),
            shape = AckHelpShape
        )
        .border(
            width = 1.dp,
            color = primaryColor.copy(alpha = alpha),
            shape = AckHelpShape
        )
}
