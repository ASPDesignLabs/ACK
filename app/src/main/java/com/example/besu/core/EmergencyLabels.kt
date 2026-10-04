// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * What the Emergency deck says that is decided, not just drawn: the line that lists the overrides in force, the name a button is shown with, and the labels on
 * the info card a bystander or first responder reads. Plain Kotlin (no `android.*`) so it is tested without a phone; the words are string resources (`emergency_*`,
 * in the chosen language) read through a [TextSource].
 *
 * Three rules, two of them decided with the developer:
 *  - **A saved name is never rewritten.** A button still named by its default (`EMERGENCY 1`..`EMERGENCY 4`, what `EmergencyPromptSlot` is created with) is *shown*
 *    in the chosen language; what is saved stays the default, and a name the person typed is shown exactly as typed. Opening the editor and saving without touching
 *    the name saves what was already stored ([labelToSave]).
 *  - **The info card is read by someone else**, so on the card view each label is the chosen language followed by English ("NOMBRE // NAME"); a responder who reads
 *    either can read it. In English there is one label. The English half is fixed here, on purpose, and a test keeps it equal to the English strings file. The edit
 *    form, which only the person sees, uses the chosen language alone. What is written on the card (the person's own words) is never touched, and the saved
 *    communication note is not translated (it is saved text, not wording on a screen).
 *  - The status line and the large SEND and CANCEL buttons are the person's own: the chosen language only.
 */
object EmergencyLabels {
    const val SEPARATOR = " // "

    // ---- the hint under the title ------------------------------------------------------------------------------------------------

    private const val HINT_TAP = "emergency_hint_tap"
    private const val HINT_HOLD = "emergency_hint_hold"

    /** "TAP: EXECUTE  //  HOLD: CONFIGURE": two words in the chosen language, joined by the app's own separator (a resource would collapse the double spaces). */
    fun hint(text: TextSource): String = text.get(HINT_TAP) + "  //  " + text.get(HINT_HOLD)

    // ---- the overrides in force --------------------------------------------------------------------------------------------------

    /** The alert tone as a number: 0 for OFF, then 1 to 3. (The saved enum is mapped to this at the screen, so this file needs nothing from it.) */
    class Overrides(
        val preventTimedClear: Boolean,
        val requireHoldToClear: Boolean,
        val forceSpeaker: Boolean,
        val boostVolume: Boolean,
        val tone: Int,
        val confirmBeforeSend: Boolean,
    ) {
        /** True when nothing is changed from the standard behaviour; the screen draws that quietly. */
        val isStandard: Boolean
            get() = !preventTimedClear && !requireHoldToClear && !forceSpeaker && !boostVolume && tone !in 1..3 && !confirmBeforeSend
    }

    private const val STANDARD = "emergency_overrides_standard"
    private const val LIST = "emergency_overrides_list"

    /** "OVERRIDES: STANDARD", or "OVERRIDES: PERSIST // SPEAKER // TONE_1": each one that is on, in this fixed order. */
    fun overridesLine(text: TextSource, overrides: Overrides): String {
        if (overrides.isStandard) return text.get(STANDARD)
        val states = buildList {
            if (overrides.preventTimedClear) add(text.get("emergency_state_persist"))
            if (overrides.requireHoldToClear) add(text.get("emergency_state_hold_clear"))
            if (overrides.forceSpeaker) add(text.get("emergency_state_speaker"))
            if (overrides.boostVolume) add(text.get("emergency_state_boost"))
            if (overrides.tone in 1..3) add(text.get("emergency_state_tone_${overrides.tone}"))
            if (overrides.confirmBeforeSend) add(text.get("emergency_state_confirm"))
        }
        return text.get(LIST, states.joinToString(SEPARATOR))
    }

    // ---- a button's name -----------------------------------------------------------------------------------------------------------

    private const val SLOT_DEFAULT = "emergency_slot_default"

    /** What a button is saved with until the person names it. Must equal `EmergencyPromptSlot`'s default (a test reads the source). */
    fun storedDefaultLabel(slotIndex: Int): String = "EMERGENCY ${slotIndex + 1}"

    /** The name to show: the default in the chosen language, anything the person typed exactly as typed. */
    fun shownLabel(text: TextSource, stored: String, slotIndex: Int): String =
        if (stored == storedDefaultLabel(slotIndex)) text.get(SLOT_DEFAULT, slotIndex + 1) else stored

    /** What to save from the editor: the name as it was stored if the field was left as shown, otherwise what was typed. */
    fun labelToSave(typed: String, shownAtStart: String, storedAtStart: String): String =
        if (typed == shownAtStart) storedAtStart else typed

    // ---- the info card's labels ----------------------------------------------------------------------------------------------------

    /** A label on the card and the English that always goes with it. The English is fixed on purpose (see the class comment). */
    enum class CardLabel(val resource: String, val english: String) {
        TITLE("emergency_info_title", "EMERGENCY INFO"),
        NAME("emergency_card_name", "NAME"),
        DATE_OF_BIRTH("emergency_card_dob", "DATE OF BIRTH"),
        BLOOD_TYPE("emergency_card_blood", "BLOOD TYPE"),
        COMMUNICATION("emergency_card_communication", "COMMUNICATION"),
        CONDITIONS("emergency_card_conditions", "CONDITIONS"),
        ALLERGIES("emergency_card_allergies", "ALLERGIES"),
        MEDICATIONS("emergency_card_medications", "MEDICATIONS"),
        PRIMARY_CONTACT("emergency_card_primary", "PRIMARY CONTACT"),
        EMERGENCY_CONTACT("emergency_card_contact", "EMERGENCY CONTACT"),
        NOTES("emergency_card_notes", "NOTES"),
    }

    /** The label as the card view shows it: "<chosen language> // <English>", or just the English when they are the same (English, or a shared word). */
    fun cardLabel(text: TextSource, label: CardLabel): String {
        val local = text.get(label.resource)
        return if (local.equals(label.english, ignoreCase = true)) label.english else "$local$SEPARATOR${label.english}"
    }
}
