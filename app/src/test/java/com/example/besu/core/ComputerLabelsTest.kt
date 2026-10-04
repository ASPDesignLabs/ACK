// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ComputerLabelsTest {

    private val languages = listOf("es", "pt", "af", "hi", "ar")
    private val repository get() = RepoFiles.read("app/src/main/java/com/example/besu/computer/ComputerRepository.kt")

    // ---- the four seeded categories are the ones the repository seeds ----------------------------------------------------------

    private fun slugify(label: String): String = label.trim().uppercase().replace(Regex("[^A-Z0-9]+"), "_").trim('_').ifEmpty { "CATEGORY" }.take(24)

    @Test
    fun theDefaultsAreTheOnesTheRepositorySeeds_andTheIdIsTheNamesSlug() {
        assertTrue(repository.contains("private val DEFAULT_CATEGORY_LABELS = listOf(\"PEOPLE\", \"PLACES\", \"FOOD/DRINK\", \"ACTIONS\")"))
        assertEquals(listOf("PEOPLE", "PLACES", "FOOD/DRINK", "ACTIONS"), ComputerLabels.DEFAULT_CATEGORIES.map { it.second })
        for ((id, label) in ComputerLabels.DEFAULT_CATEGORIES) assertEquals(id, slugify(label))
        // The migration builds the PEOPLE category by hand with these exact words.
        assertTrue(repository.contains("id = \"PEOPLE\",\n            label = \"PEOPLE\","))
    }

    @Test
    fun theEnglishNamesInTheStringsFileAreTheSavedDefaults_soEnglishIsUnchanged() {
        for ((id, label) in ComputerLabels.DEFAULT_CATEGORIES) {
            assertEquals(label, EnglishText.get(ComputerLabels.defaultResource(id)))
            assertEquals(label, ComputerLabels.shownCategoryLabel(EnglishText, id, label))
            assertEquals(label, ComputerLabels.defaultName(EnglishText, id))
        }
    }

    // ---- shown in the chosen language, saved name untouched ----------------------------------------------------------------------

    @Test
    fun aCategoryStillNamedByItsSavedDefaultIsShownInTheChosenLanguage() {
        val es = FileText("es")
        assertEquals("PERSONAS", ComputerLabels.shownCategoryLabel(es, "PEOPLE", "PEOPLE"))
        assertEquals("LUGARES", ComputerLabels.shownCategoryLabel(es, "PLACES", "PLACES"))
        assertEquals("COMIDA/BEBIDA", ComputerLabels.shownCategoryLabel(es, "FOOD_DRINK", "FOOD/DRINK"))
        assertEquals("ACCIONES", ComputerLabels.shownCategoryLabel(es, "ACTIONS", "ACTIONS"))
        for (tag in languages) {
            val text = FileText(tag)
            for ((id, label) in ComputerLabels.DEFAULT_CATEGORIES) {
                val shown = ComputerLabels.shownCategoryLabel(text, id, label)
                assertTrue("$tag/$id: $shown", shown.isNotBlank() && shown != label && shown != ComputerLabels.defaultResource(id))
            }
        }
    }

    @Test
    fun aRenamedOrHomeMadeCategoryIsShownExactlyAsSaved_inEveryLanguage() {
        for (text in listOf<TextSource>(EnglishText) + languages.map { FileText(it) }) {
            // A default category the person renamed.
            assertEquals("FAMILY", ComputerLabels.shownCategoryLabel(text, "PEOPLE", "FAMILY"))
            assertEquals("people", ComputerLabels.shownCategoryLabel(text, "PEOPLE", "people"))
            assertEquals("", ComputerLabels.shownCategoryLabel(text, "PEOPLE", ""))
            // A category the person made, even one they happened to call PEOPLE (its id is not a default's).
            assertEquals("PEOPLE", ComputerLabels.shownCategoryLabel(text, "PEOPLE_2", "PEOPLE"))
            assertEquals("PLACES", ComputerLabels.shownCategoryLabel(text, "TOPS", "PLACES"))
            // The default name of ANOTHER default category is just text on this one.
            assertEquals("PLACES", ComputerLabels.shownCategoryLabel(text, "PEOPLE", "PLACES"))
        }
    }

    @Test
    fun defaultNameForAnIdThatIsNotADefaultIsTheIdItself() {
        assertEquals("TOPS", ComputerLabels.defaultName(EnglishText, "TOPS"))
    }

    @Test
    fun savingFromTheOptionsDialogKeepsWhatWasStoredUnlessTheNameWasChanged() {
        // Left as shown (the translated default): the stored default stays the stored default.
        assertEquals("PEOPLE", ComputerLabels.nameToSave(typed = "PERSONAS", shownAtStart = "PERSONAS", storedAtStart = "PEOPLE"))
        // Typed with stray spaces around it but otherwise untouched.
        assertEquals("PEOPLE", ComputerLabels.nameToSave(typed = "PERSONAS ", shownAtStart = "PERSONAS", storedAtStart = "PEOPLE"))
        // A name the person typed earlier, left alone.
        assertEquals("FAMILY", ComputerLabels.nameToSave("FAMILY", "FAMILY", "FAMILY"))
        // Changed: exactly what was typed.
        assertEquals("FRIENDS", ComputerLabels.nameToSave("FRIENDS", "PERSONAS", "PEOPLE"))
        assertEquals("PERSONAS 2", ComputerLabels.nameToSave("PERSONAS 2", "PERSONAS", "PEOPLE"))
    }

    // ---- a place card's days -----------------------------------------------------------------------------------------------------

    @Test
    fun theDayKeysAreTheOnesTheCardSavesHoursWith() {
        val models = RepoFiles.read("app/src/main/java/com/example/besu/computer/ComputerModels.kt")
        assertTrue(models.contains("val CONTACT_CARD_DAYS = listOf(\"MON\", \"TUE\", \"WED\", \"THU\", \"FRI\", \"SAT\", \"SUN\")"))
        assertEquals(listOf("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"), ComputerLabels.DAYS)
    }

    @Test
    fun aDayIsShownInTheChosenLanguage_andInEnglishItIsTheSavedKey() {
        for (day in ComputerLabels.DAYS) assertEquals(day, ComputerLabels.dayLabel(EnglishText, day))
        for (tag in languages) {
            val text = FileText(tag)
            val shown = ComputerLabels.DAYS.map { ComputerLabels.dayLabel(text, it) }
            assertEquals("$tag: seven different day names", 7, shown.toSet().size)
            // Really translated: at most two may read like the English key (a short name two languages share, such as Afrikaans SAT).
            assertTrue("$tag: day names are still English: $shown", shown.zip(ComputerLabels.DAYS).count { it.first != it.second } >= 5)
            for ((i, name) in shown.withIndex()) assertTrue("$tag/${ComputerLabels.DAYS[i]}: $name", name.isNotBlank() && !name.startsWith("people_day_"))
        }
    }

    @Test
    fun aDayThatIsNotOneOfTheSevenIsShownAsItIs() {
        for (text in listOf<TextSource>(EnglishText, FileText("es"))) {
            assertEquals("mon", ComputerLabels.dayLabel(text, "mon"))
            assertEquals("", ComputerLabels.dayLabel(text, ""))
            assertEquals("HOLIDAY", ComputerLabels.dayLabel(text, "HOLIDAY"))
        }
    }

    @Test
    fun copiedReadsTheSameOnEveryScreen_inEveryLanguage() {
        for (map in listOf(StringsXml.map(StringsXml.default)) + StringsXml.translations().values.map { StringsXml.map(it) }) {
            assertEquals(map.getValue("composer_copied"), map.getValue("common_copied"))
        }
    }

    @Test
    fun theNamesThatAreAlsoOnTheContactCardPanelAreNotMixedUp() {
        // The PLACES section of the contact card panel (people_places) and the default category PLACES are separate strings with the same English word.
        val english = StringsXml.map(StringsXml.default)
        assertEquals("PLACES", english.getValue("people_places"))
        assertEquals("PLACES", english.getValue("people_category_places"))
        assertFalse(english.getValue("people_places") == english.getValue("people_names"))
    }
}
