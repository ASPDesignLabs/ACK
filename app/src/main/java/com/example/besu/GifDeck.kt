package com.example.besu

import android.content.Context
import android.content.Intent
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.PagerState
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CutCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.besu.ui.theme.Graphite
import com.example.besu.ui.theme.VoidBlack
import kotlinx.coroutines.launch
import kotlin.math.abs

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun GifDeck(
    context: Context,
    deckId: String,
    primaryColor: Color
) {
    var selectedCategoryId by remember {
        mutableStateOf<String?>(null)
    }

    var showCategoryMenu by remember {
        mutableStateOf(false)
    }

    var showImportDialog by remember {
        mutableStateOf(false)
    }

    var pendingUri by remember {
        mutableStateOf<android.net.Uri?>(null)
    }

    var refreshToken by remember {
        mutableIntStateOf(0)
    }

    var forceLandscapeOverlay by remember(deckId) {
        mutableStateOf(
            GifRepository.shouldForceLandscapeOverlay(
                context = context,
                deckId = deckId
            )
        )
    }

    val coroutineScope = rememberCoroutineScope()

    val helpManager = LocalHelpManager.current

    fun reportHelpInteraction(tag: String) {
        helpManager?.onEvent(HelpEvent.Interacted(tag))
    }

    val categories = remember(deckId, refreshToken) {
        GifRepository.getCategories(context, deckId)
    }

    val activeCategory = categories.firstOrNull { category ->
        category.id == selectedCategoryId
    } ?: categories.firstOrNull()

    val gifs = remember(
        deckId,
        activeCategory?.id,
        refreshToken
    ) {
        GifRepository.getEntries(
            context = context,
            deckId = deckId,
            categoryId = activeCategory?.id
        )
    }

    /*
     * The wheel has a huge virtual number of pages. Every page is mapped to
     * a real GIF with modulo arithmetic, so the user can swipe indefinitely.
     */
    val virtualPageCount = if (gifs.isEmpty()) {
        0
    } else {
        1_000_000
    }

    /*
     * Start in the middle so there is plenty of virtual space in both swipe
     * directions. Aligning to gifs.size means the first visible GIF is index 0.
     */
    val virtualMiddlePage = if (gifs.isEmpty()) {
        0
    } else {
        val rawMiddle = virtualPageCount / 2
        rawMiddle - (rawMiddle % gifs.size)
    }

    val pagerState = rememberPagerState(
        initialPage = virtualMiddlePage,
        pageCount = { virtualPageCount }
    )

    val selectedGifIndex = if (gifs.isEmpty()) {
        0
    } else {
        pagerState.currentPage % gifs.size
    }

    val selectedGif = gifs.getOrNull(selectedGifIndex)

    /*
     * Category changes and new imports re-center the virtual wheel. This keeps
     * the selected page stable and avoids eventually reaching its artificial
     * boundaries.
     */
    LaunchedEffect(
        activeCategory?.id,
        gifs.size,
        refreshToken
    ) {
        if (gifs.isNotEmpty()) {
            pagerState.scrollToPage(virtualMiddlePage)
        }
    }

    val importLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) {
            pendingUri = uri
            showImportDialog = true
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "GIF // LOCAL LIBRARY",
                color = primaryColor,
                fontSize = 15.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black,
                letterSpacing = 1.sp
            )

            NeonOutlineAction(
                text = "+ IMPORT",
                color = primaryColor,
                modifier = Modifier
                    .testTag(AckTags.GIF_IMPORT)
                    .helpTarget(AckTags.GIF_IMPORT, primaryColor)
            ) {
                importLauncher.launch(arrayOf("image/gif"))
                reportHelpInteraction(AckTags.GIF_IMPORT)
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        Box {
            NeonOutlineAction(
                text = buildString {
                    append("CATEGORY: ")
                    append(activeCategory?.name ?: "NO GIFS")
                    append(if (showCategoryMenu) " ▲" else " ▼")
                },
                color = primaryColor,
                enabled = categories.isNotEmpty(),
                modifier = Modifier
                    .testTag(AckTags.GIF_CATEGORY)
                    .helpTarget(AckTags.GIF_CATEGORY, primaryColor)
            ) {
                showCategoryMenu = !showCategoryMenu
                reportHelpInteraction(AckTags.GIF_CATEGORY)
            }

            if (showCategoryMenu) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 42.dp)
                        .background(VoidBlack)
                        .border(
                            width = 1.dp,
                            color = primaryColor,
                            shape = CutCornerShape(4.dp)
                        )
                        .padding(8.dp)
                ) {
                    categories.forEach { category ->
                        Text(
                            text = category.name,
                            color = if (category.id == activeCategory?.id) {
                                Color.White
                            } else {
                                primaryColor
                            },
                            fontSize = 13.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    selectedCategoryId = category.id
                                    showCategoryMenu = false
                                }
                                .padding(10.dp)
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(VoidBlack)
                .border(
                    width = 1.dp,
                    color = primaryColor,
                    shape = CutCornerShape(8.dp)
                ),
            contentAlignment = Alignment.Center
        ) {
            if (selectedGif == null) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "NO GIFS IN THIS CATEGORY",
                        color = Color.Gray,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        fontSize = 13.sp
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    Text(
                        text = "IMPORT A LOCAL GIF TO BEGIN",
                        color = primaryColor.copy(alpha = 0.7f),
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp
                    )
                }
            } else {
                GifSwipeWheel(
                    gifs = gifs,
                    pagerState = pagerState,
                    context = context,
                    forceLandscapeOverlay = forceLandscapeOverlay
                )
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        Text(
            text = selectedGif?.title ?: "---",
            color = Color.White,
            fontSize = 14.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(8.dp))

        NeonOutlineAction(
            text = if (forceLandscapeOverlay) {
                "OVERLAY: LANDSCAPE [ON]"
            } else {
                "OVERLAY: LANDSCAPE [OFF]"
            },
            color = if (forceLandscapeOverlay) {
                primaryColor
            } else {
                Color.Gray
            },
            modifier = Modifier
                .fillMaxWidth()
                .testTag(AckTags.GIF_LANDSCAPE_TOGGLE)
                .helpTarget(AckTags.GIF_LANDSCAPE_TOGGLE, primaryColor)
        ) {
            forceLandscapeOverlay = !forceLandscapeOverlay

            GifRepository.setForceLandscapeOverlay(
                context = context,
                deckId = deckId,
                enabled = forceLandscapeOverlay
            )

            reportHelpInteraction(AckTags.GIF_LANDSCAPE_TOGGLE)
        }

        Spacer(modifier = Modifier.height(10.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            NeonOutlineAction(
                text = "◀ PREV",
                color = primaryColor,
                enabled = gifs.size > 1
            ) {
                coroutineScope.launch {
                    pagerState.animateScrollToPage(
                        page = pagerState.currentPage - 1
                    )
                }
            }

            Text(
                text = if (gifs.isEmpty()) {
                    "0 / 0"
                } else {
                    "${selectedGifIndex + 1} / ${gifs.size}"
                },
                color = primaryColor,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )

            NeonOutlineAction(
                text = "NEXT ▶",
                color = primaryColor,
                enabled = gifs.size > 1
            ) {
                coroutineScope.launch {
                    pagerState.animateScrollToPage(
                        page = pagerState.currentPage + 1
                    )
                }
            }
        }

        if (selectedGif != null) {
            Spacer(modifier = Modifier.height(8.dp))

            NeonOutlineAction(
                text = "DISPLAY FULL SCREEN",
                color = primaryColor,
                modifier = Modifier.fillMaxWidth()
            ) {
                showGifOverlay(
                    context = context,
                    entry = selectedGif,
                    forceLandscape = forceLandscapeOverlay
                )
            }
        }
    }

    if (showImportDialog && pendingUri != null) {
        GifImportDialog(
            context = context,
            deckId = deckId,
            uri = pendingUri!!,
            primaryColor = primaryColor,
            onDismiss = {
                pendingUri = null
                showImportDialog = false
            },
            onImported = { entry ->
                selectedCategoryId = entry.categoryId
                refreshToken++
                pendingUri = null
                showImportDialog = false
            }
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun GifSwipeWheel(
    gifs: List<GifEntry>,
    pagerState: PagerState,
    context: Context,
    forceLandscapeOverlay: Boolean
) {
    /*
     * HorizontalPager already uses pager-aware fling and snap behavior by
     * default. We deliberately keep that native behavior rather than adding
     * a LazyList snapping API, which is incompatible with PagerState.
     */
    HorizontalPager(
        state = pagerState,
        beyondViewportPageCount = 1,
        modifier = Modifier.fillMaxSize()
    ) { page ->
        val gifIndex = page % gifs.size
        val entry = gifs[gifIndex]

        /*
         * Neighbour pages fade slightly as they move away from center. This
         * gives the wheel a calm visual falloff while preserving legibility.
         */
        val pageOffset = (
            pagerState.currentPage - page
        ) + pagerState.currentPageOffsetFraction

        val distanceFromCenter = abs(pageOffset)

        val pageAlpha = (
            1f - (distanceFromCenter * 0.30f)
        ).coerceIn(
            minimumValue = 0.55f,
            maximumValue = 1f
        )

        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(8.dp)
                .alpha(pageAlpha)
        ) {
            AnimatedGifPlayer(
                file = GifRepository.getGifFile(context, entry),
                modifier = Modifier
                    .fillMaxSize()
                    .clickable {
                        showGifOverlay(
                            context = context,
                            entry = entry,
                            forceLandscape = forceLandscapeOverlay
                        )
                    }
            )
        }
    }
}

@Composable
private fun NeonOutlineAction(
    text: String,
    color: Color,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    onClick: () -> Unit
) {
    val effectiveColor = if (enabled) {
        color
    } else {
        Color.Gray.copy(alpha = 0.45f)
    }

    Box(
        modifier = modifier
            .border(
                width = 1.dp,
                color = effectiveColor,
                shape = CutCornerShape(4.dp)
            )
            .then(
                if (enabled) {
                    Modifier.clickable(onClick = onClick)
                } else {
                    Modifier
                }
            )
            .padding(horizontal = 10.dp, vertical = 8.dp)
    ) {
        Text(
            text = text,
            color = effectiveColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
    }
}

@Composable
private fun GifImportDialog(
    context: Context,
    deckId: String,
    uri: android.net.Uri,
    primaryColor: Color,
    onDismiss: () -> Unit,
    onImported: (GifEntry) -> Unit
) {
    var title by remember {
        mutableStateOf(getSuggestedGifTitle(context, uri))
    }

    var categoryName by remember {
        mutableStateOf("")
    }

    var errorMessage by remember {
        mutableStateOf("")
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Graphite,
        title = {
            Text(
                text = "IMPORT GIF",
                color = primaryColor,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Black
            )
        },
        text = {
            Column {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = {
                        Text(
                            text = "TITLE",
                            fontFamily = FontFamily.Monospace
                        )
                    },
                    singleLine = true
                )

                Spacer(modifier = Modifier.height(12.dp))

                OutlinedTextField(
                    value = categoryName,
                    onValueChange = { categoryName = it },
                    label = {
                        Text(
                            text = "CATEGORY",
                            fontFamily = FontFamily.Monospace
                        )
                    },
                    placeholder = {
                        Text(
                            text = "REACTIONS",
                            fontFamily = FontFamily.Monospace
                        )
                    },
                    singleLine = true
                )

                if (errorMessage.isNotBlank()) {
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(
                        text = errorMessage,
                        color = Color.Red,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp
                    )
                }
            }
        },
        confirmButton = {
            val helpManager = LocalHelpManager.current

            NeonOutlineAction(
                text = "IMPORT",
                color = primaryColor,
                modifier = Modifier
                    .testTag(AckTags.GIF_IMPORT_COMMIT)
                    .helpTarget(AckTags.GIF_IMPORT_COMMIT, primaryColor)
            ) {
                val category = GifRepository.createCategory(
                    context = context,
                    name = categoryName
                )

                GifRepository.importGif(
                    context = context,
                    deckId = deckId,
                    sourceUri = uri,
                    title = title,
                    categoryId = category.id
                ).onSuccess { entry ->
                    onImported(entry)
                    helpManager?.onEvent(
                        HelpEvent.FileCommitted(AckTags.GIF_IMPORT_COMMIT)
                    )
                }.onFailure { error ->
                    errorMessage = error.message ?: "GIF IMPORT FAILED"
                }
            }
        },
        dismissButton = {
            NeonOutlineAction(
                text = "CANCEL",
                color = Color.Red
            ) {
                onDismiss()
            }
        }
    )
}

private fun getSuggestedGifTitle(
    context: Context,
    uri: android.net.Uri
): String {
    val cursor = context.contentResolver.query(
        uri,
        null,
        null,
        null,
        null
    )

    cursor?.use {
        val nameIndex = it.getColumnIndex(OpenableColumns.DISPLAY_NAME)

        if (nameIndex >= 0 && it.moveToFirst()) {
            return it.getString(nameIndex)
                .removeSuffix(".gif")
                .replace('_', ' ')
                .replace('-', ' ')
                .uppercase()
        }
    }

    return "UNTITLED GIF"
}

private fun showGifOverlay(
    context: Context,
    entry: GifEntry,
    forceLandscape: Boolean
) {
    context.startService(
        Intent(context, VisualPromptService::class.java).apply {
            action = VisualPromptService.ACTION_SHOW_GIF

            putExtra(
                VisualPromptService.EXTRA_GIF_FILE_PATH,
                GifRepository.getGifFile(context, entry).absolutePath
            )

            putExtra(
                VisualPromptService.EXTRA_GIF_TITLE,
                entry.title
            )

            putExtra(
                VisualPromptService.EXTRA_GIF_FORCE_LANDSCAPE,
                forceLandscape
            )
        }
    )
}
