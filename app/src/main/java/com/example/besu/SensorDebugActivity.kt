package com.example.besu

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.android.gms.wearable.MessageClient
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.Wearable
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.nio.charset.StandardCharsets

// Simple data structure for the graph
@Serializable
data class DebugSample(
    val t: Long,
    val ax: Float, val ay: Float, val az: Float,
    val gx: Float, val gy: Float, val gz: Float
)

@Serializable
data class DebugBatch(val samples: List<DebugSample>)

class SensorDebugActivity : ComponentActivity(), MessageClient.OnMessageReceivedListener {

    // Store the last 2000 points
    private val maxPoints = 2000
    private val dataPoints = mutableStateListOf<DebugSample>()

    // Toggle visualization
    private var showAccel by mutableStateOf(true)
    private var showGyro by mutableStateOf(true)
    private var isConnected by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Wearable.getMessageClient(this).addListener(this)

        setContent {
            MaterialTheme(colors = darkColors()) {
                Column(modifier = Modifier.fillMaxSize().background(Color.Black)) {
                    // Header Controls
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(8.dp).background(Color(0xFF222222)),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Sensor Stream", color = Color.White, fontWeight = FontWeight.Bold, modifier = Modifier.padding(8.dp))
                        Row {
                            ToggleButton("Accel", showAccel) { showAccel = it }
                            Spacer(modifier = Modifier.width(8.dp))
                            ToggleButton("Gyro", showGyro) { showGyro = it }
                            Spacer(modifier = Modifier.width(8.dp))
                            Button(
                                onClick = { dataPoints.clear() },
                                colors = ButtonDefaults.buttonColors(backgroundColor = Color.Red)
                            ) { Text("Clear", color = Color.White) }
                        }
                    }

                    if (dataPoints.isEmpty()) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("Waiting for Watch Stream...\n(Enable via Watch)", color = Color.Gray)
                        }
                    } else {
                        // The Scrolling Graph
                        // We make the canvas width dynamic based on data size so we can scroll
                        val scrollState = rememberScrollState()
                        val pointWidth = 3f // Pixels per data point
                        val canvasWidth = maxOf(1000.dp, (dataPoints.size * pointWidth).dp)

                        // Auto-scroll to end if at the end
                        LaunchedEffect(dataPoints.size) {
                            if (scrollState.maxValue > 0 && scrollState.value > scrollState.maxValue - 200) {
                                scrollState.animateScrollTo(scrollState.maxValue)
                            }
                        }

                        Box(modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth()
                            .horizontalScroll(scrollState)
                        ) {
                            SensorGraph(
                                data = dataPoints,
                                showAccel = showAccel,
                                showGyro = showGyro,
                                modifier = Modifier.height(600.dp).width(canvasWidth)
                            )
                        }

                        // Time Scrubber Readout
                        Text(
                            "Samples: ${dataPoints.size} | Last: ${dataPoints.lastOrNull()?.t ?: 0}ms",
                            color = Color.DarkGray,
                            modifier = Modifier.padding(4.dp)
                        )
                    }
                }
            }
        }
    }

    override fun onMessageReceived(event: MessageEvent) {
        if (event.path == "/besu/sensor_debug") {
            try {
                val json = String(event.data, StandardCharsets.UTF_8)
                val batch = Json.decodeFromString<DebugBatch>(json)

                runOnUiThread {
                    isConnected = true
                    dataPoints.addAll(batch.samples)
                    // Trim old data to prevent OOM
                    if (dataPoints.size > maxPoints) {
                        dataPoints.removeRange(0, dataPoints.size - maxPoints)
                    }
                }
            } catch (e: Exception) { e.printStackTrace() }
        }
    }

    override fun onDestroy() {
        Wearable.getMessageClient(this).removeListener(this)
        super.onDestroy()
    }
}

@Composable
fun SensorGraph(data: List<DebugSample>, showAccel: Boolean, showGyro: Boolean, modifier: Modifier) {
    Canvas(modifier = modifier) {
        val height = size.height
        val width = size.width
        val midY = height / 2
        val stepX = width / data.size.coerceAtLeast(1)

        // Scale factors:
        // Accel typically -20 to 20.
        // Gyro typically -10 to 10 (radians).
        val scaleAccel = height / 40f
        val scaleGyro = height / 20f

        val pathAX = Path(); val pathAY = Path(); val pathAZ = Path()
        val pathGX = Path(); val pathGY = Path(); val pathGZ = Path()

        if (data.isNotEmpty()) {
            pathAX.moveTo(0f, midY - (data[0].ax * scaleAccel))
            pathAY.moveTo(0f, midY - (data[0].ay * scaleAccel))
            pathAZ.moveTo(0f, midY - (data[0].az * scaleAccel))
            pathGX.moveTo(0f, midY - (data[0].gx * scaleGyro))
            pathGY.moveTo(0f, midY - (data[0].gy * scaleGyro))
            pathGZ.moveTo(0f, midY - (data[0].gz * scaleGyro))

            data.forEachIndexed { i, p ->
                val x = i * stepX
                if (showAccel) {
                    pathAX.lineTo(x, midY - (p.ax * scaleAccel))
                    pathAY.lineTo(x, midY - (p.ay * scaleAccel))
                    pathAZ.lineTo(x, midY - (p.az * scaleAccel))
                }
                if (showGyro) {
                    pathGX.lineTo(x, midY - (p.gx * scaleGyro))
                    pathGY.lineTo(x, midY - (p.gy * scaleGyro))
                    pathGZ.lineTo(x, midY - (p.gz * scaleGyro))
                }
            }

            // Draw Paths
            if (showAccel) {
                drawPath(pathAX, Color.Red, style = Stroke(2f)) // X = Red
                drawPath(pathAY, Color.Green, style = Stroke(2f)) // Y = Green
                drawPath(pathAZ, Color.Blue, style = Stroke(2f)) // Z = Blue
            }
            if (showGyro) {
                drawPath(pathGX, Color.Cyan, style = Stroke(1f)) // GX
                drawPath(pathGY, Color.Magenta, style = Stroke(1f)) // GY
                drawPath(pathGZ, Color.Yellow, style = Stroke(1f)) // GZ
            }

            // Draw Zero Line
            drawLine(Color.DarkGray, start = Offset(0f, midY), end = Offset(width, midY))
        }
    }
}

@Composable
fun ToggleButton(text: String, active: Boolean, onClick: (Boolean) -> Unit) {
    Button(
        onClick = { onClick(!active) },
        colors = ButtonDefaults.buttonColors(
            backgroundColor = if(active) Color.Gray else Color.DarkGray
        )
    ) {
        Text(text, color = if(active) Color.White else Color.LightGray)
    }
}