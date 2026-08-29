package com.example.besu

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.graphics.Rect
import android.graphics.YuvImage
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.example.besu.ui.theme.NeonPalette
import java.io.ByteArrayOutputStream
import java.util.Base64
import java.util.concurrent.Executors
import kotlin.math.pow
import kotlin.math.sqrt

class MosaicScannerActivity : ComponentActivity() {

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) startCamera() else finish()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            requestPermissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startCamera() {
        setContent {
            MosaicScannerScreen(onCodeFound = { rawPayload ->
                val success = TransferManager.restoreBackup(this, rawPayload)
                runOnUiThread {
                    if (success) {
                        Toast.makeText(this, "PROTOCOL IMPORTED", Toast.LENGTH_LONG).show()
                        finish()
                    } else {
                        Toast.makeText(this, "INTEGRITY CHECK FAILED", Toast.LENGTH_SHORT).show()
                    }
                }
            })
        }
    }
}

data class ProcessResult(
    val successPayload: String?, 
    val scanPoints: List<Offset>, 
    val status: String,
    val headerMatch: Boolean
)

@Composable
fun MosaicScannerScreen(onCodeFound: (String) -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val cameraProviderFuture = remember { ProcessCameraProvider.getInstance(context) }
    
    // DEBUG & PAUSE
    var debugInfo by remember { mutableStateOf<ProcessResult?>(null) }
    var isPaused by remember { mutableStateOf(false) }
    var currentBitmap by remember { mutableStateOf<Bitmap?>(null) }
    
    // DATA STREAM BUFFER
    val chunkBuffer = remember { mutableStateMapOf<Int, String>() }
    var totalChunksExpected by remember { mutableIntStateOf(0) }

    Box(modifier = Modifier.fillMaxSize().background(androidx.compose.ui.graphics.Color.Black)) {
        AndroidView(
            factory = { ctx ->
                val previewView = PreviewView(ctx)
                val executor = Executors.newSingleThreadExecutor()
                
                val preview = Preview.Builder().build().apply {
                    setSurfaceProvider(previewView.surfaceProvider)
                }

                val analyzer = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .apply {
                        setAnalyzer(executor) { imageProxy ->
                            if (!isPaused) {
                                val bmp = imageProxy.toBitmap()
                                currentBitmap = bmp // Store for debug view
                                
                                if (bmp != null) {
                                    processImage(bmp) { result -> 
                                        debugInfo = result // Update live status
                                        
                                        if (result.successPayload != null && result.headerMatch) {
                                            // Format: "INDEX|TOTAL|PAYLOAD"
                                            val parts = result.successPayload.split("|")
                                            if (parts.size == 3) {
                                                try {
                                                    val idx = parts[0].toInt()
                                                    val total = parts[1].toInt()
                                                    val data = parts[2]
                                                    
                                                    totalChunksExpected = total
                                                    chunkBuffer[idx] = data
                                                    
                                                    // Check Completion
                                                    if (chunkBuffer.size == total) {
                                                        val finalBase64 = stitchChunks(chunkBuffer, total)
                                                        imageProxy.close()
                                                        onCodeFound(finalBase64)
                                                        return@processImage
                                                    }
                                                } catch (e: Exception) { }
                                            }
                                        }
                                    }
                                }
                            }
                            imageProxy.close()
                        }
                    }

                try {
                    val cameraProvider = cameraProviderFuture.get()
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(
                        lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analyzer
                    )
                } catch (e: Exception) { Log.e("ACK_CAM", "Camera Fail", e) }
                
                previewView
            },
            modifier = Modifier.fillMaxSize()
        )

        // HUD Overlay
        Canvas(modifier = Modifier.fillMaxSize()) {
            val w = size.width
            val h = size.height
            
            // GEOMETRY (16:9)
            val safeW = w * 0.85f 
            val safeH = h * 0.85f
            val targetRatio = 16f / 9f

            var boxW = safeW
            var boxH = boxW / targetRatio

            if (boxH > safeH) {
                boxH = safeH
                boxW = boxH * targetRatio
            }

            val left = (w - boxW) / 2
            val top = (h - boxH) / 2

            // Dim background
            drawRect(color = androidx.compose.ui.graphics.Color.Black.copy(alpha = 0.6f))
            drawRect(
                color = androidx.compose.ui.graphics.Color.Transparent,
                topLeft = Offset(left, top), size = Size(boxW, boxH),
                blendMode = BlendMode.Clear
            )
            
            // Guide Corners
            val strokeColor = if(chunkBuffer.isNotEmpty()) androidx.compose.ui.graphics.Color.Green else NeonPalette.DEFAULT_CYAN
            drawRect(
                color = if(isPaused) androidx.compose.ui.graphics.Color.Red else strokeColor,
                topLeft = Offset(left, top), size = Size(boxW, boxH),
                style = Stroke(width = 4.dp.toPx())
            )

            // DEBUG DOTS
            if (isPaused && debugInfo != null && currentBitmap != null) {
                // We map bitmap coords to screen coords approximately for visualization
                // Note: This is imperfect without exact scale logic but helps seeing grid alignment
                val scaleX = boxW / (currentBitmap!!.width * 0.85f) // Approximate mapping
                
                // Only draw if header matched to reduce clutter
                if (debugInfo!!.headerMatch) {
                    debugInfo!!.scanPoints.forEach { point ->
                       // (Simplified viz logic would go here)
                    }
                }
            }
        }
        
        // STATUS HUD
        Box(modifier = Modifier.align(Alignment.BottomCenter).padding(32.dp)) {
            if (totalChunksExpected > 0) {
                val collected = chunkBuffer.size
                Text(
                    text = "ACQUIRED: $collected / $totalChunksExpected",
                    color = if(collected == totalChunksExpected) androidx.compose.ui.graphics.Color.Green else NeonPalette.DEFAULT_CYAN,
                    fontSize = 24.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    style = androidx.compose.ui.text.TextStyle(shadow = androidx.compose.ui.graphics.Shadow(color = androidx.compose.ui.graphics.Color.Black, blurRadius = 10f))
                )
            } else {
                Box(
                    modifier = Modifier
                        .border(1.dp, NeonPalette.DEFAULT_CYAN, CutCornerShape(8.dp))
                        .background(androidx.compose.ui.graphics.Color.Black.copy(alpha=0.8f))
                        .clickable { isPaused = !isPaused }
                        .padding(16.dp)
                ) {
                    Text(
                        text = if(isPaused) "RESUME" else "FREEZE FRAME",
                        color = if(isPaused) androidx.compose.ui.graphics.Color.Red else NeonPalette.DEFAULT_CYAN,
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }
        
        // LIVE DEBUG TEXT
        if (debugInfo != null) {
             Text(
                text = debugInfo!!.status,
                color = androidx.compose.ui.graphics.Color.White,
                fontSize = 10.sp,
                fontFamily = FontFamily.Monospace,
                modifier = Modifier.align(Alignment.TopCenter).padding(top = 48.dp)
            )
        }
    }
}

// --- SCANNER LOGIC (PCB / MONOCHROME) ---

fun processImage(bitmap: Bitmap, onResult: (ProcessResult) -> Unit) {
    val w = bitmap.width
    val h = bitmap.height
    
    // CROP LOGIC (Matches UI)
    val safeW = w * 0.85f; val safeH = h * 0.85f; val targetRatio = 16f / 9f
    var boxW = safeW; var boxH = boxW / targetRatio
    if (boxH > safeH) { boxH = safeH; boxW = boxH * targetRatio }
    val cropX = ((w - boxW) / 2).toInt(); val cropY = ((h - boxH) / 2).toInt()
    val cropWidth = boxW.toInt(); val cropHeight = boxH.toInt()

    if (cropX < 0 || cropY < 0 || cropX + cropWidth > w || cropY + cropHeight > h) {
        onResult(ProcessResult(null, emptyList(), "BOUNDS ERROR", false)); return
    }

    // 1. DYNAMIC THRESHOLDING
    // Sample the crop area to find average brightness
    val threshold = calculateLuminanceThreshold(bitmap, cropX, cropY, cropWidth, cropHeight)

    // 2. MULTI-SCALE SCAN
    // PCB Mode (1 bit/pixel) needs wider scan range.
    // 500 bytes = 4000 bits. ~84x48.
    // We scan 50 to 130 columns.
    
    for (attemptedCols in 50..130 step 2) {
        val attemptedRows = (attemptedCols / targetRatio).toInt()
        val cellW = cropWidth / attemptedCols
        val cellH = cropHeight / attemptedRows
        
        val bits = mutableListOf<Int>()
        val points = mutableListOf<Offset>() // For debug visualization
        
        for (r in 0 until attemptedRows) {
            for (c in 0 until attemptedCols) {
                // Sample CENTER of cell
                val pxX = cropX + (c * cellW) + (cellW / 2)
                val pxY = cropY + (r * cellH) + (cellH / 2)
                
                points.add(Offset(pxX.toFloat(), pxY.toFloat()))
                
                if (pxX < w && pxY < h) {
                    val px = bitmap.getPixel(pxX, pxY)
                    // Luminance check
                    val lum = (Color.red(px) + Color.green(px) + Color.blue(px)) / 3
                    bits.add(if (lum > threshold) 1 else 0)
                } else {
                    bits.add(0)
                }
            }
        }
        
        if (checkHeader(bits)) {
            // HEADER FOUND! (0xAC 0x55)
            // Reconstruct Bytes
            val idx = bitsToByte(bits, 2) // Byte 2
            val total = bitsToByte(bits, 3) // Byte 3
            
            // Payload starts at bit 32 (4 bytes * 8)
            // Decode remaining bits
            val payloadBits = bits.drop(32)
            val payloadB64 = bitsToBase64(payloadBits)
            
            onResult(ProcessResult("$idx|$total|$payloadB64", points, "LOCK: ${attemptedCols}x${attemptedRows}", true))
            return 
        }
    }
    
    onResult(ProcessResult(null, emptyList(), "SCANNING (LUM:$threshold)...", false))
}

// --- HELPER FUNCTIONS ---

fun calculateLuminanceThreshold(bitmap: Bitmap, x: Int, y: Int, w: Int, h: Int): Int {
    var sum = 0L
    val samples = 20
    val stepX = w / samples
    val stepY = h / samples
    var count = 0
    
    for (i in 0 until samples) {
        for (j in 0 until samples) {
            val pxX = x + i*stepX
            val pxY = y + j*stepY
            if (pxX < bitmap.width && pxY < bitmap.height) {
                val px = bitmap.getPixel(pxX, pxY)
                sum += (Color.red(px) + Color.green(px) + Color.blue(px)) / 3
                count++
            }
        }
    }
    // Return average, or default 128
    return if (count > 0) (sum / count).toInt() else 128
}

fun checkHeader(bits: List<Int>): Boolean {
    if (bits.size < 32) return false
    val b0 = bitsToByte(bits, 0)
    val b1 = bitsToByte(bits, 1)
    // 0xAC (172) & 0x55 (85)
    return b0 == 172 && b1 == 85
}

fun bitsToByte(bits: List<Int>, byteIndex: Int): Int {
    var value = 0
    val start = byteIndex * 8
    if (start + 8 > bits.size) return 0
    
    for (i in 0 until 8) {
        if (bits[start + i] == 1) {
            // Reconstruct MSB First (matching web)
            value = value or (1 shl (7 - i))
        }
    }
    return value
}

fun bitsToBase64(bits: List<Int>): String {
    val byteCount = bits.size / 8
    val byteArray = ByteArray(byteCount)
    
    for (i in 0 until byteCount) {
        var value = 0
        for (b in 0 until 8) {
            if (bits[i * 8 + b] == 1) {
                value = value or (1 shl (7 - b))
            }
        }
        byteArray[i] = value.toByte()
    }
    return Base64.getEncoder().encodeToString(byteArray)
}

fun stitchChunks(buffer: Map<Int, String>, total: Int): String {
    val fullBytes = ByteArrayOutputStream()
    for (i in 0 until total) {
        val chunkB64 = buffer[i] ?: return ""
        try {
            fullBytes.write(Base64.getDecoder().decode(chunkB64))
        } catch(e: Exception) { return "" }
    }
    return Base64.getEncoder().encodeToString(fullBytes.toByteArray())
}

fun ImageProxy.toBitmap(): Bitmap? {
    val yBuffer = planes[0].buffer; val uBuffer = planes[1].buffer; val vBuffer = planes[2].buffer
    val ySize = yBuffer.remaining(); val uSize = uBuffer.remaining(); val vSize = vBuffer.remaining()
    val nv21 = ByteArray(ySize + uSize + vSize)
    yBuffer.get(nv21, 0, ySize); vBuffer.get(nv21, ySize, vSize); uBuffer.get(nv21, ySize + vSize, uSize)
    val yuvImage = YuvImage(nv21, ImageFormat.NV21, this.width, this.height, null)
    val out = ByteArrayOutputStream()
    yuvImage.compressToJpeg(Rect(0, 0, yuvImage.width, yuvImage.height), 100, out)
    val imageBytes = out.toByteArray()
    val bmp = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
    if (this.imageInfo.rotationDegrees != 0) {
        val matrix = Matrix(); matrix.postRotate(this.imageInfo.rotationDegrees.toFloat())
        return Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, matrix, true)
    }
    return bmp
}
