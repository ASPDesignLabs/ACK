// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the QUICK ACTIONS deck says that is decided, not just drawn: the hint under the title, the name a slot or a group is shown with, the short name on a group's tab and the
 * "POSE: .. // ROOT: .." line. Plain Kotlin (no `android.*`) so it is tested without a phone; the words are string resources (`qa_*`, in the chosen language) read through a [TextSource].
 *
 * **A saved name is never rewritten.** A slot is created named `ACTION 1`..`ACTION 4` and a group `GROUP 1`..`GROUP 3` (decks/QuickActionsModels.kt). Those are saved text. A slot or group
 * still carrying its saved default name is *shown* in the chosen language; a name the person typed is shown exactly as typed; and opening an editor and saving without touching the name
 * saves what was stored ([labelToSave]). The same rule the Emergency deck uses for its buttons (core/EmergencyLabels.kt).
 */
object QuickActionLabels {
    /** What a slot is saved with until the person names it. Must equal `QuickActionSlot`'s default (a test reads the source). */
    fun storedDefaultSlotLabel(slotIndex: Int): String = "ACTION ${slotIndex + 1}"

    /** What a group is saved with until the person names it. Must equal `QuickActionGroup`'s default (a test reads the source). */
    fun storedDefaultGroupLabel(groupIndex: Int): String = "GROUP ${groupIndex + 1}"

    /** The name to show for a slot: the default in the chosen language, anything the person typed exactly as typed. */
    fun shownSlotLabel(text: TextSource, stored: String, slotIndex: Int): String =
        if (stored == storedDefaultSlotLabel(slotIndex)) text.get("qa_slot_default", slotIndex + 1) else stored

    /** The name to show for a group: the default in the chosen language, anything the person typed exactly as typed. */
    fun shownGroupLabel(text: TextSource, stored: String, groupIndex: Int): String =
        if (stored == storedDefaultGroupLabel(groupIndex)) text.get("qa_group_default", groupIndex + 1) else stored

    /** What to save from an editor: the name as it was stored if the field was left as shown, otherwise what was typed. */
    fun labelToSave(typed: String, shownAtStart: String, storedAtStart: String): String =
        if (typed == shownAtStart) storedAtStart else typed

    /** "TAP: EXECUTE  //  HOLD: EDIT": two parts in the chosen language, joined by the app's own separator (a resource would collapse the double spaces). */
    fun hint(text: TextSource): String = text.get("qa_hint_tap") + "  //  " + text.get("qa_hint_hold")

    /** A group's tab: "G1" in the language's own letter. */
    fun groupTab(text: TextSource, groupIndex: Int): String = text.get("qa_group_short", groupIndex + 1)

    /**
     * A pose's short name under a group's tab and on the pose buttons: three letters in English (IDE, DEF, CON), and the language's own short word where three letters would not read. The
     * saved pose name is never changed; a name that is not one of the three poses is cut to three letters as it always was.
     */
    fun poseShort(text: TextSource, storedPose: String): String = when (storedPose) {
        "IDENTITY" -> text.get("qa_pose_short_identity")
        "DEFEND" -> text.get("qa_pose_short_defend")
        "CONNECT" -> text.get("qa_pose_short_connect")
        else -> storedPose.take(3)
    }

    /**
     * "POSE: IDENTITY  //  ROOT: IDENTITY" under a group's name. [poseWord] is the POSE label (it follows PLAIN WORDS), [poseName] and [rootName] are the names as the Matrix screen
     * words them (a custom layer's own name as typed). The two halves are joined by the app's double-spaced separator.
     */
    fun poseRootLine(text: TextSource, poseWord: String, poseName: String, rootName: String): String =
        text.get("qa_pose_part", poseWord, poseName) + "  //  " + text.get("qa_root_part", rootName)
}
