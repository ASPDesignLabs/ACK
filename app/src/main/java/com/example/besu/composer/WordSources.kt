// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.composer

import android.content.Context
import com.example.besu.computer.ComputerNode
import com.example.besu.computer.ComputerNodeType
import com.example.besu.computer.ComputerRepository
import com.example.besu.core.ExtraWords
import com.example.besu.data.CommandRepository
import com.example.besu.data.RootOverrideRepository
import com.example.besu.decks.POSE_CATEGORIES

/**
 * The names the person already keeps, offered as word suggestions alongside the learned words (core/ExtraWords.kt splits and caps them).
 *
 * **Read-only and live.** Nothing here writes: these words are never copied into the learned words (LearnedWordsRepository), so renaming a
 * contact changes what is offered and deleting one stops it, with nothing left behind. Only the entry NAMES in Target Computer are read, not
 * the contact cards (phone numbers, addresses, emails), and only the Shared Root Variable slots that are switched on and filled in.
 */
internal object WordSources {

    fun collect(context: Context): List<String> {
        val texts = ArrayList<String>()

        // Target Computer: the name of every entry, in every category (a category's own name is a heading, not a name).
        fun walk(node: ComputerNode) {
            if (node.type == ComputerNodeType.ENTRY) texts.add(node.label)
            node.children.forEach { walk(it) }
        }
        ComputerRepository.getCategories(context).forEach { walk(it.root) }

        // Shared Root Variables: A, B and C of each fixed pose and each custom layer, where the slot is on and has a value.
        val groupings = POSE_CATEGORIES + CommandRepository.getCustomContextEntries(context).map { it.name }
        groupings.distinct().forEach { grouping ->
            RootOverrideRepository.getConfig(context, grouping).slots.values.forEach { slot ->
                if (slot.enabled && slot.value.isNotBlank()) texts.add(slot.value)
            }
        }

        return ExtraWords.fromTexts(texts)
    }
}
