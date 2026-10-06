// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

/**
 * The words of the HELP walkthroughs (module titles and summaries, step titles and bodies), moved to string resources one family at a time. Plain Kotlin (no `android.*`) so the
 * decisions are tested on a JVM; the Android edge only reads the words and speaks them.
 *
 * **A walkthrough's text is a resource name, or still its own English.** A `HelpStep`'s `title` and `body` and a `HelpModule`'s `title` and `summary` hold a name such as
 * `helpmod_geo_protocol_intro_body` once their family has moved, and [read] finds the words in the chosen language. A family that has not moved yet still holds its English text,
 * and [read] gives it back unchanged (a text that is not a resource reads as itself, see [TextSource.get]), so the families can move one commit at a time and nothing shows a key.
 * The names follow one rule ([moduleTitle], [moduleSummary], [stepTitle], [stepBody]) and `HelpWalkthroughWordingTest` holds each family to it.
 *
 * **Placeholders.** English keeps its `{{KEY:Original}}` placeholders exactly as the walkthrough always read (so English is word for word what it was, and an Original that is
 * not the label's own word is still allowed there). A translation uses the bare `{{KEY}}`, which `helpText()` fills with the language's own word for that label, or the everyday
 * one under PLAIN WORDS. A translation never carries an English Original.
 *
 * **What is spoken.** The coach panel speaks each step aloud. A voice that is not speaking the language of the words reads them as nonsense, so [speaksInterfaceLanguage] says
 * when the translated step may be spoken: only when SPEECH LANGUAGE follows the phone and the screens are in the phone's own language (the same language the speech engine is
 * asked for). Every other case speaks the English step, exactly what was spoken before the steps were translated.
 */
object HelpWalkthroughText {
    /** Every walkthrough string's name starts with this, so none can collide with the HELP chrome's `help_*` names. */
    const val PREFIX = "helpmod_"

    private val NAME = Regex("^helpmod_[a-z0-9_]+$")

    /** True for a resource name this system owns (not an English sentence). */
    fun isName(value: String): Boolean = NAME.matches(value)

    fun moduleTitle(moduleId: String): String = "${PREFIX}${moduleId}_title"
    fun moduleSummary(moduleId: String): String = "${PREFIX}${moduleId}_summary"
    fun stepTitle(moduleId: String, stepId: String): String = "${PREFIX}${moduleId}_${stepId}_title"
    fun stepBody(moduleId: String, stepId: String): String = "${PREFIX}${moduleId}_${stepId}_body"

    /** The words for [nameOrText]: the resource's text in the chosen language, or the text itself when it is not a resource name (a family not moved yet). */
    fun read(text: TextSource, nameOrText: String): String = text.get(nameOrText)

    /**
     * Whether the translated step may be spoken. [interfaceTag] is the language the screens are really in (`ActiveScript.tag`), [deviceLanguage] the phone's own language code
     * (`Locale.getDefault().language`). English is never "translated", and a phone whose language is not the screens' language gets the English step.
     */
    fun speaksInterfaceLanguage(speech: SpeechLanguage, interfaceTag: String, deviceLanguage: String): Boolean {
        if (speech != SpeechLanguage.DEVICE) return false
        val tag = interfaceTag.trim().lowercase()
        if (tag.isEmpty() || tag == "en") return false
        return tag == deviceLanguage.trim().lowercase()
    }
}
