package com.example.besu

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.NeonPalette
import com.example.besu.ui.theme.VoidBlack

val AtkinsonHyperlegible = FontFamily(Font(R.font.atkinson_hyperlegible_next_regular))

@OptIn(ExperimentalTextApi::class)
@Composable
fun VisualEditorView(context: Context, primaryColor: Color) {
    var refreshKey by remember { mutableIntStateOf(0) }
    var activePreset by remember(refreshKey) { mutableStateOf(VisualPresetRepository.getActivePreset(context)) }
    val allPresets = remember(refreshKey) { VisualPresetRepository.getPresets(context) }

    var currentDraft by remember(activePreset) { mutableStateOf(activePreset) }
    var demoText by remember { mutableStateOf("SYSTEM ONLINE") }

    Column(modifier = Modifier.fillMaxSize()) {
        // --- 16:9 LANDSCAPE PROPORTION PREVIEW ---
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 9f) // Ratio simulates landscape output
                .background(Color.Black.copy(alpha = 0.8f))
                .border(2.dp, primaryColor)
                .padding(8.dp),
            contentAlignment = Alignment.Center
        ) {
            Text("PREVIEW RATIO (16:9)", color = Color.DarkGray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.align(Alignment.TopStart))

            val textStyle = TextStyle(
                fontFamily = AtkinsonHyperlegible,
                fontSize = currentDraft.fontSizeSp.sp,
                fontWeight = if (currentDraft.isBold) FontWeight.Bold else FontWeight.Normal,
                fontStyle = if (currentDraft.isItalic) FontStyle.Italic else FontStyle.Normal,
                textDecoration = if (currentDraft.isUnderline) TextDecoration.Underline else TextDecoration.None,
                textAlign = TextAlign.Center
            )

            Text(
                text = demoText,
                style = textStyle.copy(drawStyle = Stroke(join = StrokeJoin.Round, width = currentDraft.outlineWidth)),
                color = Color(currentDraft.outlineColorArgb)
            )
            Text(text = demoText, style = textStyle, color = Color(currentDraft.textColorArgb))
        }

        Spacer(modifier = Modifier.height(16.dp))

        // --- DEMO TEXT INPUT ---
        OutlinedTextField(
            value = demoText,
            onValueChange = { demoText = it.uppercase() },
            placeholder = { Text("ENTER DEMO TEXT...") },
            modifier = Modifier.fillMaxWidth(),
            colors = TextFieldDefaults.colors(focusedTextColor = primaryColor, unfocusedTextColor = primaryColor, focusedContainerColor = VoidBlack, unfocusedContainerColor = VoidBlack, focusedIndicatorColor = primaryColor, unfocusedIndicatorColor = Color.DarkGray),
            textStyle = androidx.compose.ui.text.TextStyle(fontFamily = FontFamily.Monospace, fontSize = 14.sp)
        )
        Spacer(modifier = Modifier.height(16.dp))

        // --- CONTROLS ---
        LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            // Preset Controls...
            item {
                Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                    NeonButton("SAVE PRESET", Modifier.weight(1f), mainColor = primaryColor) {
                        VisualPresetRepository.savePreset(context, currentDraft); refreshKey++
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    HeroButton("SET ACTIVE", Modifier.weight(1f), mainColor = primaryColor) {
                        VisualPresetRepository.setActivePreset(context, currentDraft.id); refreshKey++
                    }
                }
            }

            // Truncation Bypass
            item {
                Row(modifier = Modifier.fillMaxWidth().border(1.dp, primaryColor, CutCornerShape(8.dp)).background(Graphite).padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text("FORCE RENDER FULL TEXT", color = primaryColor, fontSize = 12.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
                        Text("Bypasses 5-word truncation limit. May cause overflow if text size is too large.", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                    }
                    NeonButton(if (currentDraft.bypassTruncation) "ON" else "OFF", isActive = currentDraft.bypassTruncation, mainColor = primaryColor) {
                        currentDraft = currentDraft.copy(bypassTruncation = !currentDraft.bypassTruncation)
                    }
                }
            }

            // Sliders & Toggles 
            item {
                Text("SIZE: ${currentDraft.fontSizeSp.toInt()}", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = currentDraft.fontSizeSp, onValueChange = { currentDraft = currentDraft.copy(fontSizeSp = it) }, valueRange = 40f..250f, colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor))

                Text("OUTLINE THICKNESS: ${currentDraft.outlineWidth.toInt()}", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Slider(value = currentDraft.outlineWidth, onValueChange = { currentDraft = currentDraft.copy(outlineWidth = it) }, valueRange = 0f..20f, colors = SliderDefaults.colors(thumbColor = primaryColor, activeTrackColor = primaryColor))
            }
            
            // Format toggles
            item {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    NeonButton("BOLD", Modifier.weight(1f), isActive = currentDraft.isBold, mainColor = primaryColor) { currentDraft = currentDraft.copy(isBold = !currentDraft.isBold) }
                    Spacer(modifier = Modifier.width(8.dp))
                    NeonButton("ITALIC", Modifier.weight(1f), isActive = currentDraft.isItalic, mainColor = primaryColor) { currentDraft = currentDraft.copy(isItalic = !currentDraft.isItalic) }
                    Spacer(modifier = Modifier.width(8.dp))
                    NeonButton("UNDERLINE", Modifier.weight(1f), isActive = currentDraft.isUnderline, mainColor = primaryColor) { currentDraft = currentDraft.copy(isUnderline = !currentDraft.isUnderline) }
                }
            }
            // Colors
            item {
                Text("OUTLINE COLOR", color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
                Row(modifier = Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    NeonPalette.SWATCHES.forEach { col ->
                        val isAct = currentDraft.outlineColorArgb == col.value.toLong()
                        Box(modifier = Modifier.size(40.dp).background(col, CutCornerShape(4.dp)).border(2.dp, if(isAct) Color.White else Color.Transparent, CutCornerShape(4.dp)).clickable { currentDraft = currentDraft.copy(outlineColorArgb = col.value.toLong()) })
                    }
                }
            }
            item { Spacer(modifier = Modifier.height(24.dp)) }
        }
    }
}
