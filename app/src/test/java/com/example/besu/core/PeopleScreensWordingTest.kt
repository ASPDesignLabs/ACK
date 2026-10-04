// SPDX-License-Identifier: GPL-3.0-or-later
package com.example.besu.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The People and places (Target Computer) category, tree, wizard and quick-insert screens read their words from string resources, in the chosen language. They
 * cannot be compiled here, so this reads them: the old English literals are gone, every string they name exists and none is unused, a category is drawn through
 * the shown-name helper (a default name in the chosen language, anything else as saved) and never rewritten when saved, and what the screens do (modes, wizard
 * start, delete and clear flows, what is inserted) is exactly as it was. The default-name rule is in ComputerLabelsTest.
 */
class PeopleScreensWordingTest {

    private val base = "app/src/main/java/com/example/besu/computer"
    private fun noComments(text: String): String = text.lines().joinToString("\n") { line ->
        val t = line.trimStart()
        if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else line
    }
    private fun file(name: String) = noComments(RepoFiles.read("$base/$name"))
    private val english get() = StringsXml.map(StringsXml.default)
    private val translations get() = StringsXml.translations().mapValues { StringsXml.map(it.value) }
    private val screens = listOf("TargetView.kt", "ComputerTreeWindow.kt", "ComputerWizard.kt", "ManualOverrideTargetBrowser.kt", "ContactCardView.kt")
    private val newCommon = listOf("common_undo", "common_clear", "common_done", "common_back", "common_name", "common_confirm_delete", "common_copied")

    @Test
    fun everyStringTheScreensNameExists_andNoneIsLeftUnused() {
        val sources = screens.map { file(it) } + file("CategoryNames.kt")
        val referenced = sources.flatMap { Regex("""R\.string\.((?:people_[a-z0-9_]+)|(?:common_[a-z_]+))""").findAll(it).map { m -> m.groupValues[1] }.toList() }.toSet()
        // Names the screens write as plain strings (the delete-count plural), and the four default category names built from their ids by ComputerLabels.
        val named = Regex(""""(people_[a-z0-9_]+)"""").findAll(sources.joinToString("\n")).map { it.groupValues[1] }.toSet() +
            ComputerLabels.DEFAULT_CATEGORIES.map { ComputerLabels.defaultResource(it.first) } + ComputerLabels.DAYS.map { "people_day_${it.lowercase()}" }
        val used = referenced + named
        val definedPeople = english.keys.filter { it.startsWith("people_") }.toSet() + StringsXml.plurals(StringsXml.default).keys.filter { it.startsWith("people_") }
        val missing = referenced.filter { it !in english.keys && it !in definedPeople }
        assertEquals("named but not defined: $missing", emptyList<String>(), missing)
        val unused = definedPeople - used
        assertTrue("defined but never used: $unused", unused.isEmpty())
        for (name in newCommon) assertTrue("$name is not used by a screen", name in used)
    }

    @Test
    fun theOldEnglishLiteralsAreNoLongerDrawn() {
        val gone = mapOf(
            "TargetView.kt" to listOf(
                "\"CATEGORIES\",", "\"VISUALS\",", "\"[GUIDE ME]\"", "\"TARGET COMPUTER STATUS\"", "\"CLOSE\"", "\"UNDO\"", "\"NO CATEGORIES YET.\"", "\"NOTHING SELECTED\"", "\"CANCEL\"",
                "\"CONFIRM\"", "\"CLEAR\"", "\"EMPTY\"", "\"+ ADD", "\"NAMES\"", "\"PLACES\"", "\"E.G. FEELINGS\"", "\"CREATE\"", "\"NAME\"", "\"WHEN A PICK IS MADE\"", "\"KEEP IT\"",
                "\"CLEAR AFTER USE\"", "Stays active until you clear it", "\"SAVE\"", "\"DELETE\"", "This removes the whole category", "\"CONFIRM DELETE\"", "\"TARGETS MOVED\"", "\"LOOKS GOOD\"",
                "Your previously saved targets", "Want help organizing", "\"START WIZARD\"", "I'LL DO IT MYSELF", "CLEARED \${", "\"CLEAR \${",
            ),
            "ComputerTreeWindow.kt" to listOf(
                "\"DONE\"", "\"[GUIDE ME]\"", "\"NOTHING HERE YET.\"", "\"ADD TO: ", "\"+ CATEGORY\"", "\"+ ENTRY\"", "\"[CARD]\"", "\"ACTIVE\"", "\"LEVEL \${", "\"SELECT...\"", "\"ADD ENTRY\"",
                "\"UNDER: ", "\"E.G. FRIENDS\"", "\"E.G. MOM\"", "\"CREATE\"", "\"CANCEL\"", "\"EDIT CATEGORY\"", "\"EDIT ENTRY\"", "\"CONTACT CARD\"", "\"PERSON\"", "\"PLACE\"", "\"OPEN CONTACT CARD\"",
                "\"SAVE\"", "\"DELETE\"", "\"CONFIRM DELETE\"", "item(s) nested inside it", "\"This cannot be undone.\"", "text = mode,",
            ),
            "ComputerWizard.kt" to listOf(
                "\"GUIDED SETUP\"", "\"FINISH\"", "Pick a category to build", "\"+ NEW CATEGORY\"", "\"NAME THE NEW CATEGORY\"", "\"E.G. FEELINGS\"", "\"ADDING TO: ", "\"+ ADD SUBCATEGORY HERE\"",
                "\"+ ADD ENTRY HERE\"", "\"↑ UP ONE LEVEL\"", "\"NAME THE NEW SUBCATEGORY\"", "\"NAME THE NEW ENTRY\"", "\"E.G. FRIENDS\"", "\"E.G. MOM\"", "\"CREATE\"", "\"BACK\"", "\"IN \${",
            ),
            "ManualOverrideTargetBrowser.kt" to listOf(
                "\"NO ACTIVE TARGETS", "\"NO CATEGORIES YET.", "\"PICK A CATEGORY\"", "\"← CATEGORIES\"", "text = mode,", "\"NOTHING HERE YET.\"", "\"QUICK INSERT MODE\"", "\"CLOSE THE KEYBOARD",
                "\"[HIDE FULL BROWSER]\"", "\"[BROWSE ALL ENTRIES]\"",
            ),
        )
        for ((name, literals) in gone) {
            val text = file(name)
            for (literal in literals) assertFalse("$name still holds $literal", text.contains(literal))
            assertTrue("$name needs an explicit R import outside the base package", text.contains("import com.example.besu.R"))
        }
        assertTrue("ComputerTreeWindow uses testTag and must import it", file("ComputerTreeWindow.kt").contains("import androidx.compose.ui.platform.testTag"))
    }

    // ---- the contact card ----------------------------------------------------------------------------------------------------------

    @Test
    fun theContactCardReadsItsWordsFromResources_andItsToastsThroughTheContext() {
        val card = file("ContactCardView.kt")
        val gone = listOf(
            "\"PLACE CARD\"", "\"PERSON CARD\"", "\"[DONE EDITING]\"", "\"[EDIT]\"", "label = \"NAME\"", "TightSectionLabel(\"NAME\")", "label = \"PHONE\"", "label = \"ADDRESS\"",
            "TightSectionLabel(\"HOURS\")", "label = \"EMAIL\"", "E.G. TOPS FRIENDLY MARKETS",
            "E.G. (555) 555-1234", "E.G. 123 MAIN ST", "E.G. NAME@EXAMPLE.COM", "E.G. @HANDLE", "\"E.G. HANDLE\"", "\"OPEN\")", "\"CLOSE\")", "\"NO APP AVAILABLE FOR THIS ACTION\"", "Toast.makeText(context, \"COPIED\"",
            "label = day.day",
        )
        for (literal in gone) assertFalse("ContactCardView.kt still holds $literal", card.contains(literal))
        // A toast is not in a composable lambda: it reads through the context.
        assertTrue(card.contains("Toast.makeText(context, context.getString(R.string.people_no_app), Toast.LENGTH_SHORT).show()"))
        assertTrue(card.contains("Toast.makeText(context, context.getString(R.string.common_copied), Toast.LENGTH_SHORT).show()"))
        assertFalse(Regex("""Toast\.makeText\([^)]*stringResource""").containsMatchIn(card))
        assertTrue(card.contains("label = dayName(day.day),"))
        // The two titles are the right way round, and a phone opens the dialer, an address the map, an email the mail app.
        assertTrue(card.contains("title = stringResource(if (localCard.type == ContactCardType.PLACE) R.string.people_place_card else R.string.people_person_card),"))
        assertTrue(card.contains("Intent(Intent.ACTION_DIAL, Uri.parse(\"tel:"))
        assertTrue(card.contains("Intent(Intent.ACTION_VIEW, Uri.parse(\"geo:0,0?q="))
        assertTrue(card.contains("Intent(Intent.ACTION_SENDTO, Uri.parse(\"mailto:"))
        assertTrue(card.contains("HourTimeField(day.open, primaryColor, stringResource(R.string.people_hours_open))"))
        assertTrue(card.contains("HourTimeField(day.close, primaryColor, stringResource(R.string.people_hours_close))"))
    }

    @Test
    fun theBrandNamesAndWhatACardDoesAreUnchanged() {
        val card = file("ContactCardView.kt")
        // X, FACEBOOK and LINKEDIN are names of services, not words; the keys the profile link is built from are logic.
        for (brand in listOf("label = \"X\",", "label = \"FACEBOOK\",", "label = \"LINKEDIN\",")) assertTrue(brand, card.contains(brand))
        assertTrue(card.contains("\"X\" -> \"https://x.com/\$handle\""))
        assertTrue(card.contains("\"FACEBOOK\" -> \"https://facebook.com/\$handle\""))
        assertTrue(card.contains("\"LINKEDIN\" -> \"https://linkedin.com/in/\$handle\""))
        // The actions a tap or a long press does, and the label the clipboard is given, are as they were.
        assertTrue(card.contains("Uri.parse(\"tel:\${Uri.encode(phone)}\")"))
        assertTrue(card.contains("Uri.parse(\"geo:0,0?q=\${Uri.encode(address)}\")"))
        assertTrue(card.contains("Uri.parse(\"mailto:\${Uri.encode(email)}\")"))
        assertTrue(card.contains("onCopy = { copyToClipboard(context, \"NAME\", card.name) }"))
        assertTrue(card.contains("onCopy = { copyToClipboard(context, \"PHONE\", card.phone) }"))
        assertTrue(card.contains("intent.putExtra(\"source\", \"COMPUTER/CONTACT\")"))
        // An hours checkbox changes the saved flag of the day it is for, whatever the day is called on screen.
        assertTrue(card.contains("updated[index] = day.copy(enabled = !day.enabled)"))
        assertTrue(card.contains("onCopy = { copyToClipboard(context, \"EMAIL\", card.email) }"))
    }

    @Test
    fun opensAndClosesAreDifferentWordsInEveryLanguage_asAreThePersonAndPlaceCards() {
        for (map in listOf(english) + translations.values) {
            assertTrue(map.getValue("people_hours_open") != map.getValue("people_hours_close"))
            assertTrue(map.getValue("people_person_card") != map.getValue("people_place_card"))
            assertTrue(map.getValue("people_person") != map.getValue("people_place"))
        }
    }

    // ---- a category is drawn through the shown-name helper and never rewritten by it ------------------------------------------------

    @Test
    fun everyPlaceACategoryNameIsDrawnUsesTheShownNameHelper() {
        val view = file("TargetView.kt")
        assertTrue(view.contains("text = categoryName(category).uppercase(),"))      // the chip
        assertTrue(view.contains("val shownName = categoryName(category)"))           // the status dialog
        assertTrue(view.contains("text = shownName.uppercase(),"))
        assertTrue(view.contains("ClearedRecord(category.id, shownName, node)"))
        val tree = file("ComputerTreeWindow.kt")
        assertTrue(tree.contains("val categoryShown = categoryName(category)"))
        assertTrue(tree.contains("title = categoryShown,"))
        assertTrue(tree.contains("text = categoryShown.uppercase(),"))
        assertTrue(tree.contains("val addTargetShown = if (addTargetNode.id == category.root.id) categoryShown else addTargetNode.label"))
        assertTrue(tree.contains("parentLabel = addTargetShown,"))
        val wizard = file("ComputerWizard.kt")
        assertTrue(wizard.contains("WizardOptionRow(label = categoryName(cat), primaryColor = primaryColor) {"))
        assertTrue(wizard.contains("categoryName(it).uppercase()"))
        assertTrue(wizard.contains("if (currentNode.id == category.root.id) categoryName(category) else currentNode.label"))
        val browser = file("ManualOverrideTargetBrowser.kt")
        assertTrue(browser.contains("text = categoryName(category).uppercase(),"))
        assertTrue(browser.contains("text = categoryName(cat),"))
        // No screen still draws a category's own label directly.
        for ((name, text) in screens.map { it to file(it) }) {
            assertFalse("$name draws category.label directly", Regex("""text = category\.label""").containsMatchIn(text))
            assertFalse("$name draws cat.label directly", text.contains("cat.label"))
        }
    }

    @Test
    fun theOptionsDialogStartsFromTheShownNameAndSavesWhatWasStoredIfLeftAlone() {
        val view = file("TargetView.kt")
        assertTrue(view.contains("val shownAtStart = categoryName(category)\n    var name by remember(category.id) { mutableStateOf(shownAtStart) }"))
        assertTrue(view.contains("category.copy(label = ComputerLabels.nameToSave(name.trim(), shownAtStart, category.label), persistUntilCleared = persistUntilCleared)"))
        assertFalse("the field must not start from the stored text", view.contains("mutableStateOf(category.label)"))
    }

    @Test
    fun theMigrationNoticeNamesTheCategoryItNamesOnScreen() {
        val view = file("TargetView.kt")
        assertTrue(view.contains("stringResource(R.string.people_migrated_body, ComputerLabels.defaultName(rememberText(), \"PEOPLE\"))"))
        // The wizard it offers still starts in the saved PEOPLE category (an id, never a word).
        assertTrue(view.contains("wizardStartCategoryId = \"PEOPLE\""))
        assertEquals(listOf("%1\$s"), StringsXml.placeholders(english.getValue("people_migrated_body")))
    }

    // ---- what the screens do is exactly as it was ------------------------------------------------------------------------------

    @Test
    fun theModesTheFlowsAndWhatIsInsertedAreUnchanged() {
        val view = file("TargetView.kt")
        assertTrue(view.contains("subMode == \"CATEGORIES\""))
        assertTrue(view.contains("subMode = \"VISUALS\""))
        assertTrue(view.contains("ComputerRepository.deleteCategory(context, category.id)"))
        assertTrue(view.contains("ComputerRepository.clearActiveEntry(context, category.id)"))
        assertTrue(view.contains("ComputerRepository.setActiveEntry(context, cleared.categoryId, cleared.node.id)"))
        assertTrue("a delete still needs its second tap", view.contains("if (!confirmingDelete) {") && view.contains("confirmingDelete = true"))
        assertTrue(view.contains("ComputerRepository.createCategory(context, label)"))
        val tree = file("ComputerTreeWindow.kt")
        assertTrue(tree.contains("displayMode == \"TREE\""))
        assertTrue(tree.contains("listOf(\"TREE\", \"DROPDOWN\").forEach { mode ->"))
        assertTrue(tree.contains("ComputerRepository.deleteNode(context, categoryId, editing.id)"))
        assertTrue(tree.contains("ComputerRepository.renameNode(context, categoryId, editing.id, newLabel)"))
        assertTrue("a node delete still needs its second tap", tree.contains("if (!confirmingDelete) {") && tree.contains("confirmingDelete = true"))
        // The warning counts nested items only when there are some; the second tap's two buttons are the confirm (which deletes) and the cancel (which does not).
        assertTrue(tree.contains("text = if (descendantCount > 0) {\n                    rememberText().count(\"people_delete_nested\", descendantCount)\n                } else {\n                    stringResource(R.string.people_cannot_undo)\n                },"))
        assertTrue(tree.contains("TightPanelButton(stringResource(R.string.common_confirm_delete), Modifier.weight(1f), mainColor = DangerRed, onClick = onDelete)"))
        assertTrue(view.contains("TightPanelButton(stringResource(R.string.common_confirm_delete), Modifier.weight(1f), mainColor = DangerRed) {\n                    ComputerRepository.deleteCategory(context, category.id)"))
        // A name must not be empty to be saved or created: every save and create is behind its isValid guard.
        assertTrue(view.contains("if (isValid) {\n                        ComputerRepository.saveCategory("))
        assertTrue(view.contains("if (isValid) onCreate(name.trim())"))
        assertTrue(tree.contains("if (isValid) onCreate(name.trim())"))
        assertTrue(tree.contains("if (isValid) onSave(name.trim(), cardType)"))
        assertTrue(file("ComputerWizard.kt").contains("if (isValid) onCreate(name.trim())"))
        val browser = file("ManualOverrideTargetBrowser.kt")
        // What lands in the text field is the entry's own label, as typed: never a translated word.
        assertTrue(browser.contains("onClick = { onInsert(category.id, node.label) },"))
        assertTrue(browser.contains("onInsert(category.id, row.node.label)"))
        assertTrue(browser.contains("ComputerRepository.findNode(category, leafId)?.let { onInsert(category.id, it.label) }"))
        assertTrue(browser.contains("displayMode == \"TREE\""))
        val names = file("CategoryNames.kt")
        assertTrue(names.contains("stringResource(if (mode == \"TREE\") R.string.people_mode_tree else R.string.people_mode_dropdown)"))
    }

    // ---- the safety sentences hold in every language --------------------------------------------------------------------------

    @Test
    fun theDeleteWarningsAndTheUndoAreInEveryLanguage_andKeepTheirPlaceholders() {
        for ((tag, map) in translations) {
            for (name in listOf("people_delete_category_warning", "people_cannot_undo", "people_clear_after_use_note", "people_keep_it_note", "people_migrated_body")) {
                val text = map.getValue(name)
                assertTrue("$tag/$name is not a real sentence: $text", text.length >= 12 && text != english.getValue(name))
            }
            assertTrue(tag, map.getValue("people_clear_question").contains("%1\$s"))
            assertTrue(tag, map.getValue("people_cleared").let { it.contains("%1\$s") && it.contains("%2\$s") })
            assertTrue(tag, map.getValue("people_add_to").contains("%1\$s"))
            assertTrue("$tag: CONFIRM DELETE must not read as CANCEL", map.getValue("common_confirm_delete") != map.getValue("common_cancel"))
            assertTrue("$tag: UNDO must not read as CLEAR", map.getValue("common_undo") != map.getValue("common_clear"))
            assertTrue("$tag: KEEP IT must not read as CLEAR AFTER USE", map.getValue("people_keep_it") != map.getValue("people_clear_after_use"))
        }
        assertEquals("CLEARED %1\$s: %2\$s", english.getValue("people_cleared"))
    }

    @Test
    fun theNestedItemWarningKeepsItsNumberAndTheEnglishWordingIsUnchanged() {
        val plurals = StringsXml.plurals(StringsXml.default).getValue("people_delete_nested")
        assertEquals("This also removes %d item(s) nested inside it. This cannot be undone.", plurals.getValue("one"))
        assertEquals(plurals.getValue("one"), plurals.getValue("other"))
        assertEquals("This also removes 3 item(s) nested inside it. This cannot be undone.", EnglishText.count("people_delete_nested", 3))
    }
}
