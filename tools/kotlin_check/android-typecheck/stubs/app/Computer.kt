// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.computer
import android.content.Context

// Stub of computer/ComputerRepository.kt (it reads and writes storage), written from its real signatures.
object ComputerRepository {
    data class ContactCardListing(val categoryId: String, val node: ComputerNode)
    data class InitResult(val categories: List<ComputerCategory>, val didMigrate: Boolean)
    fun getCategories(context: Context): List<ComputerCategory> = emptyList()
    fun saveCategory(context: Context, category: ComputerCategory) {}
    fun createCategory(context: Context, label: String): ComputerCategory = throw NotImplementedError()
    fun deleteCategory(context: Context, categoryId: String) {}
    fun addNode(context: Context, categoryId: String, parentId: String, label: String, type: ComputerNodeType): ComputerNode = throw NotImplementedError()
    fun renameNode(context: Context, categoryId: String, nodeId: String, newLabel: String) {}
    fun deleteNode(context: Context, categoryId: String, nodeId: String) {}
    fun findNode(category: ComputerCategory, nodeId: String): ComputerNode? = null
    fun setContactCardType(context: Context, categoryId: String, nodeId: String, type: ContactCardType) {}
    fun saveContactCard(context: Context, categoryId: String, nodeId: String, card: ContactCard) {}
    fun findAllContactCards(context: Context): List<ContactCardListing> = emptyList()
    fun findPath(category: ComputerCategory, nodeId: String): List<ComputerNode> = emptyList()
    fun setActiveEntry(context: Context, categoryId: String, leafNodeId: String) {}
    fun clearActiveEntry(context: Context, categoryId: String) {}
    fun ensureInitialized(context: Context): InitResult = InitResult(emptyList(), false)
}
