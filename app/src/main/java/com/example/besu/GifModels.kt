package com.example.besu

import kotlinx.serialization.Serializable

@Serializable
data class GifCategory(
    val id: String,
    val name: String,
    val createdAt: Long = System.currentTimeMillis()
)

@Serializable
data class GifEntry(
    val id: String,
    val deckId: String,
    val title: String,
    val categoryId: String,
    val fileName: String,
    val importedAt: Long = System.currentTimeMillis(),
    val sortOrder: Long = System.currentTimeMillis()
)
