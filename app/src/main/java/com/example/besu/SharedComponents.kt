package com.example.besu

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite

// --- ATOMIC UI COMPONENTS ---

@Composable
fun SpeakerButton(isActive: Boolean, mainColor: Color, onClick: () -> Unit) {
    Box(
        modifier = Modifier.width(50.dp).height(40.dp).background(Graphite, CutCornerShape(8.dp))
            .border(1.dp, if(isActive) mainColor else mainColor.copy(alpha=0.2f), CutCornerShape(8.dp))
            .clickable { onClick() },
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.size(16.dp)) {
            val p = Path()
            p.moveTo(0f, size.height/3); p.lineTo(size.width/3, size.height/3); p.lineTo(size.width, 0f)
            p.lineTo(size.width, size.height); p.lineTo(size.width/3, size.height*2/3); p.lineTo(0f, size.height*2/3); p.close()
            drawPath(p, if(isActive) mainColor else mainColor.copy(alpha=0.5f))
        }
    }
}

@Composable
fun DeckItem(name: String, color: Color, isActive: Boolean, onClick: () -> Unit) {
    Row(modifier = Modifier.fillMaxWidth().clickable { onClick() }.padding(vertical=4.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(modifier = Modifier.size(12.dp).background(color, CutCornerShape(2.dp)))
        Spacer(modifier = Modifier.width(8.dp))
        Text(name, color = if(isActive) color else Color.Gray, fontWeight = if(isActive) FontWeight.Bold else FontWeight.Normal, fontFamily = FontFamily.Monospace)
        if(isActive) Text(" [ACTIVE]", color = color, fontSize = 8.sp, fontFamily = FontFamily.Monospace)
    }
}

@Composable
fun DspSlider(label: String, value: Float, range: ClosedFloatingPointRange<Float>, color: Color, onValueChange: (Float) -> Unit) {
    Column {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(label, color = Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
            Text(String.format("%.2f", value), color = color, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        }
        Slider(
            value = value, valueRange = range, onValueChange = onValueChange,
            colors = SliderDefaults.colors(thumbColor = color, activeTrackColor = color, inactiveTrackColor = Color.DarkGray)
        )
        Spacer(modifier = Modifier.height(4.dp))
    }
}

@Composable
fun ThemeOption(id: Int, label: String, current: Int, activeColor: Color, onClick: () -> Unit) {
    val active = id == current
    Box(
        modifier = Modifier.width(60.dp).height(40.dp)
            .background(if(active) activeColor.copy(alpha=0.1f) else Color.Transparent)
            .border(1.dp, if(active) activeColor else Color.DarkGray, CutCornerShape(8.dp))
            .clickable { onClick() },
        contentAlignment = Alignment.Center
    ) {
        Text(label, color = if(active) activeColor else Color.Gray, fontSize = 10.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun HeroButton(text: String, modifier: Modifier = Modifier, mainColor: Color, onClick: () -> Unit) {
    Button(
        onClick = { onClick() },
        modifier = modifier.height(50.dp),
        shape = CutCornerShape(topStart = 20.dp, bottomEnd = 20.dp),
        colors = ButtonDefaults.buttonColors(containerColor = Graphite, contentColor = mainColor),
        border = BorderStroke(2.dp, mainColor)
    ) {
        Text(text.uppercase(), fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Black, letterSpacing = 4.sp, fontSize = 12.sp)
    }
}
