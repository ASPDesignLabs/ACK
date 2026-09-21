package com.example.besu.help

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// A small, dismissible, informational nudge -- never an auto-launched
// dialog or navigation -- for pointing someone at a HELP walkthrough the
// first time they encounter a feature. Purely a pointer: dismissing it
// only hides it, it never starts anything on its own.
@Composable
fun HelpOfferBanner(
    message: String,
    primaryColor: Color,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, primaryColor.copy(alpha = 0.5f), AckHelpShape)
            .background(primaryColor.copy(alpha = 0.08f), AckHelpShape)
            .padding(10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = message,
            color = Color.LightGray,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            lineHeight = 13.sp,
            modifier = Modifier.weight(1f)
        )

        Spacer(modifier = Modifier.width(10.dp))

        Text(
            text = "[GOT IT]",
            color = primaryColor,
            fontSize = 9.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            modifier = Modifier
                .clickable(onClick = onDismiss)
                .padding(4.dp)
        )
    }
}
