// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.help

import com.example.besu.*
import com.example.besu.capture.FreeSpeechNotice

// Walks through RECORD TRAINING DATA (voicecapture/*), entered from AUDIO ARCHITECT's CUSTOM VOICE section. Most steps are
// "read" steps that point at a control: the screens change as the person works (script list, editor, setup, the recording
// screen), so a highlight simply shows when its control is on screen. Only the two taps that are always possible gate a step.
object RecordTrainingDataHelp {
    val module = HelpModule(
        id = "record_training_data",
        category = HelpCategory.BASICS_PERSONALIZATION,
        title = "RECORD TRAINING DATA",
        summary = "RECORD YOUR VOICE FOR A VOICE MODEL, WITHOUT YOUR COMPUTER.",
        destination = HelpDestination.AUDIO,
        steps = listOf(
            HelpStep(
                id = "intro",
                title = "RECORD TRAINING DATA",
                body = "This gathers recordings of your voice on this phone, so you can collect them wherever you are and train a voice model " +
                    "later. You read text aloud. The phone records it, cuts it into clips, notes how each one went, and keeps them. " +
                    "Nothing is sent anywhere: the recordings stay on this phone until you save them to a file and move that file yourself."
            ),
            HelpStep(
                id = "open",
                title = "OPEN IT",
                body = "Tap RECORD TRAINING DATA, under CUSTOM VOICE.",
                action = HelpAction.Interact(AckTags.TRAIN_ENTRY_BTN),
                targetTag = AckTags.TRAIN_ENTRY_BTN
            ),
            HelpStep(
                id = "scripts",
                title = "SCRIPTS",
                body = "A script is any text you want to read aloud: a book chapter, something you wrote, a list of sentences. " +
                    "ACK splits it into cards sized to read in one go, about ten seconds each, so every card becomes one clip."
            ),
            HelpStep(
                id = "new_script",
                title = "WRITE OR PASTE A SCRIPT",
                body = "Tap + NEW SCRIPT to see where a script is written.",
                action = HelpAction.Interact(AckTags.TRAIN_NEW_SCRIPT_BTN),
                targetTag = AckTags.TRAIN_NEW_SCRIPT_BTN
            ),
            HelpStep(
                id = "title",
                title = "GIVE IT A TITLE",
                body = "A short name so you can find it again.",
                targetTag = AckTags.TRAIN_SCRIPT_TITLE,
                coachPlacement = HelpCoachPlacement.BOTTOM
            ),
            HelpStep(
                id = "text",
                title = "THE TEXT",
                body = "Type or paste the text. Write numbers and symbols the way you will say them (\"twenty twenty-six\", \"percent\"): what you " +
                    "read is what your voice model learns. Below it you can see how many cards it becomes and a warning for any card with digits " +
                    "or symbols.",
                targetTag = AckTags.TRAIN_SCRIPT_TEXT,
                coachPlacement = HelpCoachPlacement.BOTTOM
            ),
            HelpStep(
                id = "save",
                title = "SAVE IT",
                body = "SAVE keeps the script. Changing a saved script always asks you first, and leaving with unsaved changes asks too. " +
                    "Save the script (or go BACK), then continue here.",
                targetTag = AckTags.TRAIN_SCRIPT_SAVE_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "record",
                title = "RECORD A SCRIPT",
                body = "RECORD on a script starts a session. It starts at the first card you have not recorded yet, so you can read a long script " +
                    "over many days. The list shows how many cards are done.",
                targetTag = AckTags.TRAIN_SCRIPT_RECORD_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "quiet_check",
                title = "THE QUIET CHECK",
                body = "Put the phone where it will stay, such as a stand or propped on books, and keep your mouth the same distance from it all " +
                    "the time. Then run the two-second quiet check: stay silent and the phone measures the room. It tells you in words if the room " +
                    "is loud, the microphone is covered, or something interrupted it.",
                targetTag = AckTags.TRAIN_QUIET_CHECK_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "hands_free",
                title = "HANDS-FREE RECORDING",
                body = "One card shows at a time, in large text. Read it when you are ready. The phone hears when you finish, keeps the clip, " +
                    "and shows the next card by itself. You do not touch the phone. While it listens it makes no sound and no vibration, so nothing " +
                    "ends up in your recordings but your voice.",
                targetTag = AckTags.TRAIN_CARD_TEXT,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "redo",
                title = "IF YOU STUMBLE",
                body = "REDO LAST sets the clip you just recorded aside (it is kept on the phone, but not saved to a file) and shows that card " +
                    "again. PAUSE stops listening until you tap RESUME. After a clip is kept you can mark it as noise, unclear, laugh, cough or " +
                    "stumble; a mark keeps it out of training until you review it on the computer.",
                targetTag = AckTags.TRAIN_REDO_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "end",
                title = "ENDING A SESSION",
                body = "END SESSION asks first, and everything already kept stays kept. If the app closes unexpectedly, the next time you open " +
                    "RECORD TRAINING DATA it repairs what it can, and holds a repaired recording back until you listen to it and decide.",
                targetTag = AckTags.TRAIN_END_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "free",
                title = "FREE SPEECH",
                body = "To talk about anything with no script, use RECORD FREE SPEECH. The audio is kept whole, for as long as 90 minutes. The phone " +
                    "only suggests where it could be cut; the computer decides. " + FreeSpeechNotice.HELP,
                targetTag = AckTags.TRAIN_FREE_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "save_file",
                title = "SAVING TO A FILE",
                body = "SAVE ALL TO A FILE makes a package you choose where to put. The phone then reads it back and checks every recording in it; " +
                    "if anything is wrong it removes the file and tells you nothing was lost. Move the file to your computer yourself, check it " +
                    "there, and only then delete a session from the phone. The phone never deletes one because you saved it.",
                targetTag = AckTags.TRAIN_SAVE_ALL_BTN,
                coachPlacement = HelpCoachPlacement.TOP
            ),
            HelpStep(
                id = "complete",
                title = "THAT IS THE PHONE'S PART",
                body = "On the computer, Freeform Studio imports the package and does the rest: it listens again, lines the words up with the " +
                    "text you read, and lets you review every piece before anything is used for training."
            )
        )
    )
}
