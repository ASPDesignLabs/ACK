package com.example.besu.help

import com.example.besu.AckTags

// Voice recordings span three different owners (Quick Actions slots,
// Quick-Access keys, and Matrix nodes) plus a fourth, owner-agnostic
// screen (MANAGE RECORDINGS), which doesn't map cleanly onto a single
// guided walkthrough. Broken into three real modules instead -- fanned
// out from a single chooser entry point, same shape as
// FieldOpsHelp.poseTrainingEntryModule + PoseSelectorDialog.
object VoiceRecordingsHelp {

    val recordingModule = HelpModule(
        id = "voice_rec_recording",
        category = HelpCategory.VOICE_RECORDINGS,
        title = "RECORDING A VOICE PROMPT",
        summary = "RECORD, PREVIEW, AND ACCEPT YOUR OWN VOICE FOR ANY PROMPT.",
        destination = HelpDestination.MATRIX,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "VOICE RECORDINGS",
                body = "Any Quick Actions slot, Quick-Access key, or Matrix node can play " +
                    "your own recorded voice instead of synthesized speech. The record, " +
                    "preview, and accept flow is identical everywhere it shows up -- this " +
                    "walkthrough uses a Quick Actions slot as the example."
            ),
            HelpStep(
                id = "open_slot",
                title = "OPEN A SLOT",
                body = "Hold a Quick Actions slot to open its editor.",
                action = HelpAction.Interact(AckTags.QUICK_ACTION_SLOT),
                targetTag = AckTags.QUICK_ACTION_SLOT
            ),
            HelpStep(
                id = "find_section",
                title = "VOICE RECORDING SECTION",
                body = "Scroll down past the phrase template to the VOICE RECORDING section."
            ),
            HelpStep(
                id = "record",
                title = "RECORD",
                body = "Tap RECORD. The first time, you'll be asked to allow microphone access.",
                action = HelpAction.Interact(AckTags.VOICE_REC_RECORD_BTN),
                targetTag = AckTags.VOICE_REC_RECORD_BTN
            ),
            HelpStep(
                id = "stop",
                title = "STOP",
                body = "Tap STOP when you're done talking. ACK automatically reduces " +
                    "background noise and trims dead air from both ends -- you don't need " +
                    "to leave silence around your words.",
                action = HelpAction.Interact(AckTags.VOICE_REC_STOP_BTN),
                targetTag = AckTags.VOICE_REC_STOP_BTN
            ),
            HelpStep(
                id = "preview",
                title = "PREVIEW IT",
                body = "Tap PLAY to hear exactly what will play back. Not happy with it? " +
                    "DISCARD and record again -- nothing is saved yet.",
                action = HelpAction.Interact(AckTags.VOICE_REC_PLAY_BTN),
                targetTag = AckTags.VOICE_REC_PLAY_BTN
            ),
            HelpStep(
                id = "accept",
                title = "ACCEPT",
                body = "Tap ACCEPT to save it. This slot now plays your recording instead " +
                    "of synthesized speech.",
                action = HelpAction.Interact(AckTags.VOICE_REC_ACCEPT_BTN),
                targetTag = AckTags.VOICE_REC_ACCEPT_BTN
            ),
            HelpStep(
                id = "complete",
                title = "RECORDING COMPLETE",
                body = "That's the whole flow, and it's the same wherever you see a VOICE " +
                    "RECORDING section. REMOVE clears a saved recording and falls back to " +
                    "synthesized speech; RE-RECORD (in MANAGE RECORDINGS) replaces one " +
                    "without deleting it first."
            )
        )
    )

    val matrixModule = HelpModule(
        id = "voice_rec_matrix",
        category = HelpCategory.VOICE_RECORDINGS,
        title = "MATRIX VOICE ENTRIES",
        summary = "RECORD OVER A TEMPLATE, SET A VISUAL OVERRIDE, AND HANDLE LATER EDITS.",
        destination = HelpDestination.MATRIX,
        requiresMatrixDeck = true,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "MATRIX VOICE ENTRIES",
                body = "A Matrix node can play a recording instead of resolving its " +
                    "template. Nothing about the template or its variables is touched -- " +
                    "remove the recording and the node goes right back to normal."
            ),
            HelpStep(
                id = "open_node",
                title = "OPEN A NODE",
                body = "Tap any node's row to open its Live-Save Editor.",
                action = HelpAction.Interact(AckTags.MATRIX_ROW_TARGET),
                targetTag = AckTags.MATRIX_ROW_TARGET
            ),
            HelpStep(
                id = "variables_caveat",
                title = "VARIABLES GO QUIET",
                body = "If this node's template has {VAR} tokens or [COMPUTER:] tags, " +
                    "attaching a recording plays it back exactly as recorded and ignores " +
                    "them while it's active. Their values are kept, not deleted -- remove " +
                    "the recording later and they're right where you left them. You'll see " +
                    "an ATTACH VOICE RECORDING button and a one-time confirmation first if " +
                    "this applies.",
                targetTag = AckTags.VOICE_REC_MATRIX_ATTACH_BTN
            ),
            HelpStep(
                id = "record",
                title = "RECORD",
                body = "Tap RECORD (or ATTACH VOICE RECORDING first, then RECORD, if this " +
                    "node has variables).",
                action = HelpAction.Interact(AckTags.VOICE_REC_RECORD_BTN),
                targetTag = AckTags.VOICE_REC_RECORD_BTN
            ),
            HelpStep(
                id = "stop",
                title = "STOP",
                body = "Tap STOP when you're done.",
                action = HelpAction.Interact(AckTags.VOICE_REC_STOP_BTN),
                targetTag = AckTags.VOICE_REC_STOP_BTN
            ),
            HelpStep(
                id = "accept",
                title = "ACCEPT",
                body = "Preview it with PLAY if you'd like, then tap ACCEPT.",
                action = HelpAction.Interact(AckTags.VOICE_REC_ACCEPT_BTN),
                targetTag = AckTags.VOICE_REC_ACCEPT_BTN
            ),
            HelpStep(
                id = "visual_override",
                title = "VISUAL PROMPT OVERRIDE",
                body = "With a recording active, VISUAL PROMPT OVERRIDE controls what shows " +
                    "on the overlay and in the log while it plays -- handy since the raw " +
                    "template can carry unresolved {VAR} tokens once a recording takes " +
                    "over. Leave it blank to show the raw template as-is.",
                targetTag = AckTags.VOICE_REC_MATRIX_OVERRIDE_FIELD
            ),
            HelpStep(
                id = "re_enable",
                title = "IF THE TEMPLATE CHANGES LATER",
                body = "Editing this node's text after a recording is attached disables " +
                    "the recording (not deletes it) so old audio can't play against new " +
                    "text. A RE-ENABLE button appears the next time you open this node -- " +
                    "tap it once the recording still matches, or record fresh audio instead.",
                targetTag = AckTags.VOICE_REC_MATRIX_REENABLE_BTN
            ),
            HelpStep(
                id = "complete",
                title = "MATRIX RECORDING COMPLETE",
                body = "Template, variables, and the recording all coexist -- removing the " +
                    "recording is always enough to get back to today's normal resolved " +
                    "behavior."
            )
        )
    )

    val manageModule = HelpModule(
        id = "voice_rec_manage",
        category = HelpCategory.VOICE_RECORDINGS,
        title = "MANAGING RECORDINGS",
        summary = "BROWSE, PLAY, RE-RECORD, AND DELETE EVERY RECORDING IN ONE PLACE.",
        destination = HelpDestination.SETTINGS,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "MANAGE RECORDINGS",
                body = "Every recording you've made -- Quick Actions, Quick-Access keys, " +
                    "and Matrix nodes alike -- lives in one browsable tree under PROTOCOL."
            ),
            HelpStep(
                id = "open",
                title = "OPEN IT",
                body = "Tap MANAGE RECORDINGS.",
                action = HelpAction.Interact(AckTags.VOICE_REC_MANAGE_BTN),
                targetTag = AckTags.VOICE_REC_MANAGE_BTN
            ),
            HelpStep(
                id = "tree",
                title = "DRILL DOWN",
                body = "Recordings are grouped by how they're used: Deck > Group > Slot for " +
                    "Quick Actions, a flat list for Quick-Access keys, and Deck > Profile > " +
                    "Pose > Slot for Matrix. Tap a branch row to expand or collapse it.",
                targetTag = AckTags.VOICE_REC_MANAGE_TREE
            ),
            HelpStep(
                id = "leaf",
                title = "WHAT A RECORDING SHOWS",
                body = "Each recording shows the text that would actually reach the " +
                    "overlay if it played right now, its play time, and its file size on " +
                    "disk.",
                targetTag = AckTags.VOICE_REC_MANAGE_LEAF
            ),
            HelpStep(
                id = "actions",
                title = "PLAY, RE-RECORD, DELETE",
                body = "PLAY previews it in place. RE-RECORD replaces the audio without " +
                    "touching whatever it's bound to. DELETE removes it -- whatever it was " +
                    "bound to falls back to synthesized speech (or, for Matrix, its normal " +
                    "resolved text).",
                targetTag = AckTags.VOICE_REC_MANAGE_LEAF
            ),
            HelpStep(
                id = "overlay_toggle",
                title = "OVERLAY ON PLAY",
                body = "Tap the OVERLAY toggle in the top corner. When on, tapping PLAY " +
                    "also shows that recording's own text on screen -- a second way to " +
                    "confirm you found the right one.",
                action = HelpAction.Interact(AckTags.VOICE_REC_MANAGE_OVERLAY_TOGGLE),
                targetTag = AckTags.VOICE_REC_MANAGE_OVERLAY_TOGGLE
            ),
            HelpStep(
                id = "complete",
                title = "MANAGE RECORDINGS COMPLETE",
                body = "One tree, every recording, no need to remember where each one lives."
            )
        )
    )

    data class VoiceRecOption(
        val moduleId: String,
        val label: String,
        val hint: String
    )

    val options = listOf(
        VoiceRecOption(
            recordingModule.id,
            "RECORDING A VOICE PROMPT",
            "The record, preview, and accept flow -- wherever it shows up."
        ),
        VoiceRecOption(
            matrixModule.id,
            "MATRIX VOICE ENTRIES",
            "Variables, the visual override, and edits after the fact."
        ),
        VoiceRecOption(
            manageModule.id,
            "MANAGING RECORDINGS",
            "Browse, play, re-record, and delete from one tree."
        )
    )

    // Not a guided walkthrough by itself -- MainActivity intercepts this
    // module's id before calling HelpManager.start() and opens
    // VoiceRecordingsHelpSelectorDialog instead. Picking an option there
    // starts the matching real module above.
    val entryModule = HelpModule(
        id = "voice_recordings_training",
        category = HelpCategory.VOICE_RECORDINGS,
        title = "VOICE RECORDINGS",
        summary = "PICK A TOPIC: RECORDING, MATRIX ENTRIES, OR MANAGING WHAT YOU'VE SAVED.",
        steps = listOf(
            HelpStep(
                id = "select",
                title = "VOICE RECORDINGS",
                body = "Choose a topic."
            )
        )
    )

    // The three real modules stay registered for HelpManager lookup but
    // are hidden from the menu list in favor of entryModule -- see
    // MainActivity's filtered HelpMenuDialog modules list.
    val hiddenModuleIds: Set<String> = setOf(
        recordingModule.id,
        matrixModule.id,
        manageModule.id
    )

    val modules = listOf(recordingModule, matrixModule, manageModule, entryModule)
}
