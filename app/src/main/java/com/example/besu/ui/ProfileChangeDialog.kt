// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.ui

import com.example.besu.core.ProfileSwapText
import com.example.besu.core.ProfileWarningText
import com.example.besu.core.SlotChange
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// Shown before a profile change that would make a Matrix gesture say something different (core/ProfileSwapDiff.kt decides; MainActivity
// shows it). It lists what would change and asks. Quiet: nothing is spoken, no sound, no animation, nothing starts HELP. Leaving by the back
// button or a tap outside is STAY, so doing nothing never changes a profile. STAY is listed first and is the highlighted button; the
// checkbox writes the same setting as WARN BEFORE PROFILE CHANGES in SETTINGS.
@Composable
fun ProfileChangeDialog(
    targetProfile: String,
    changes: List<SlotChange>,
    dontShowAgain: Boolean,
    onDontShowAgainChanged: (Boolean) -> Unit,
    primaryColor: Color,
    onStay: () -> Unit,
    onChange: () -> Unit
) {
    TightDialogSurface(
        onDismiss = onStay,
        primaryColor = primaryColor,
        title = ProfileWarningText.DIALOG_TITLE,
        dismissLabel = ProfileWarningText.STAY
    ) {
        Text(
            text = ProfileSwapText.heading(changes.size, targetProfile),
            color = Color.White,
            fontSize = 14.sp,
            lineHeight = 19.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(10.dp))

        ProfileSwapText.lines(changes).forEach { line ->
            Text(
                text = line,
                color = Color.LightGray,
                fontSize = 12.sp,
                lineHeight = 17.sp,
                fontFamily = FontFamily.Monospace
            )
            Spacer(modifier = Modifier.height(6.dp))
        }

        Spacer(modifier = Modifier.height(10.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 48.dp)
                .toggleable(value = dontShowAgain, role = Role.Checkbox, onValueChange = onDontShowAgainChanged),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Checkbox(
                checked = dontShowAgain,
                onCheckedChange = null,
                colors = CheckboxDefaults.colors(
                    checkedColor = primaryColor,
                    uncheckedColor = Color.Gray,
                    checkmarkColor = Color.Black
                )
            )
            Spacer(modifier = Modifier.width(8.dp))
            androidx.compose.foundation.layout.Column {
                Text(
                    text = ProfileWarningText.DONT_SHOW_AGAIN,
                    color = Color.White,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace
                )
                Text(
                    text = ProfileWarningText.DONT_SHOW_AGAIN_NOTE,
                    color = Color.Gray,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            NeonButton(ProfileWarningText.STAY, Modifier.weight(1f), mainColor = primaryColor) { onStay() }
            NeonButton(ProfileWarningText.CHANGE, Modifier.weight(1f), mainColor = Color.White) { onChange() }
        }
    }
}
