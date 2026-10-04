# Translations (INTERFACE LANGUAGE): what exists, what does not, and how to review it

**Status: five DRAFT translations, written by an AI assistant with no native speaker involved. None has been reviewed by a native speaker or a
speech-language pathologist (SLP), and none has been run on a phone.** Hindi and Arabic are the two the author is least sure of. Every
`values-xx/strings.xml` starts with a notice that says so, and the language picker says so too. Do not describe these as finished translations
anywhere, and do not remove the notice until a person who speaks the language has read the file.

| Language | Folder | Script / direction | Wording | What the author is least sure of |
|---|---|---|---|---|
| Spanish | `values-es` | Latin, left to right | Neutral, for Spain and Latin America; "computadora" for computer | Regional choices (computadora/ordenador, ajustes/configuración) |
| Portuguese | `values-pt` | Latin, left to right | **Brazilian** wording (tela, arquivo, celular, contato); European Portuguese would need its own `values-pt-rPT` review | Every Brazil/Portugal difference |
| Hindi | `values-hi` | Devanagari, left to right | Everyday Hindi with common English loan words (सेटिंग्स, बैकअप, इमोजी) | Which loan words people actually prefer; "खाली जगह" for a fill-in |
| Arabic | `values-ar` | Arabic, **right to left** | Modern Standard Arabic, no diacritics | Gender and plural agreement; "حقل" (field) for a fill-in; dialect-neutral tone |
| Afrikaans | `values-af` | Latin, left to right | Standard Afrikaans | Compounds (one word or two) and "'n" at the start of a line in capitals |

## What is translated

Only the **label table** and the words around PLAIN WORDS and INTERFACE LANGUAGE, because those are the words the developer gave the app:

- every name in `docs/PLAIN_LANGUAGE.md`, in both forms (`label_<key>` the standard name, `label_<key>_plain` the everyday name);
- the PLAIN WORDS switch, offer and explanation, and the plain-mode buttons and switches on the Terminal screen, the Type tab and in SETTINGS
  (`plain_words_*`, `plain_ctl_*`);
- the INTERFACE LANGUAGE control itself (`interface_language_*`, `common_cancel`); its heading is fixed text in all five languages so it can be found
  by someone who cannot read the current one;
- the accessibility-service description Android shows in its own settings;
- **screens, one at a time** (so each can be reviewed): the **Matrix deck screen** (group headings, ACTIVATE/ACTIVE, the shared-value strip and its dialog,
  the recorded badge, MANAGE CONTEXT), the **Matrix editor dialog** opened from a row (template, variables, target-tag fallbacks, the voice-recording panel
  text, the three CLEAR confirmations and the recording notices) the **Statement composer** (the TYPE tab: FULL SCREEN, the preview, SAVE / COPY / SPEAK, the save and new-folder dialogs, MY STATEMENTS and its row buttons) the **header row above every screen** (DECK, PROFILE, COMPUTER) and the **backup wording** (the EXPORT .JSON warning that the file is not encrypted and where not to save it,
  the backup reminder and its switch, why a backup failed, IMPORT MATRIX AS NEW DECK and the FULL RESTORE confirmation). Words used on several
  screens are `common_*`; a screen's own words are `<screen>_*` (`matrix_*`, `matrix_edit_*`, `composer_*`, `header_*`, `export_*`, `backup_*`, `data_port_*`). The decisions that choose
  those words (`core/ExportContents.kt`, `core/BackupReminderText.kt`) stay plain Kotlin and name them through a `TextSource`, so they are still tested against the real English text.
  Two things must survive translation exactly: the typed command in `export_terminal_confirm` (`/backup CONFIRM`, which the Terminal accepts) and the `%1$s` / `%2$s` placeholders. A count of days
  is a `<plurals>` entry, so each language gets the forms its grammar needs (Arabic has six). Still to come: the MANAGE CONTEXT dialog,
  the word-suggestion offer and strip (their text lives in `core/` constants), the voice picker, the DELETE DATA dialogs, the HELP menu, the Emergency deck, People and places.

## What is NOT translated (it stays English in every language, and the control says so)

HELP walkthroughs and their menu; every screen not listed above (and the MANAGE CONTEXT dialog and the deck manager); the Terminal's own text (`/help`, the patch notes, command feedback); most dialogs, toasts and settings captions;
the DELETE DATA wording and the Terminal's own replies; the visual overlay and anything spoken (that is SPEECH LANGUAGE's job); starter phrases; anything a person typed.
A Spanish screen is therefore mixed: translated names on the main screens, English in the long tail. That is the stated limit of this pass.

## How it behaves

- **An install that already existed stays English** until its owner chooses a language in SETTINGS, even on a phone set to Spanish. A **new install
  follows the phone**, and so does a phone after DELETE DATA > SETTINGS (its confirmation says so). A phone language ACK has no words for shows English.
- Choosing asks first (CANCEL is the prominent button), then saves the choice and **restarts ACK once**. Nothing is deleted. The language is applied in
  `MainActivity.attachBaseContext` (`data/InterfaceLocale.kt`); if that ever fails ACK still opens, in English.
- The choice is in EXPORT .JSON (`interfaceLanguage`, nullable: a backup that says nothing leaves your own choice alone).
- **Android 13's own per-app language screen is deliberately not offered** (no `localeConfig`): an existing install is held on English by the in-app
  setting, and a second switch would silently lose to it. A test fails if one is declared.
- **Letter spacing is dropped in Arabic** (`ui/ScriptSpacing.kt`): the app's wide spacing is a style for capital Latin letters, and it pulls an Arabic word
  apart. Every `letterSpacing = N.sp` goes through `looseSpacing(...)`; a test fails on one that does not.

## What a reviewer should do

1. Open `values-xx/strings.xml`. Each `label_<key>` is the **standard** name (ACK's own jargon, translated closely) and `label_<key>_plain` the **everyday**
   name (what a first-time user or an SLP should see). The everyday name matters most; the English reasoning is in `docs/PLAIN_LANGUAGE.md`.
2. Change the text freely. **Keep the keys, keep the `%1$s` placeholders, escape an apostrophe as `\'`.** Spanish, Portuguese and Afrikaans stay in capitals
   (the app's house style); Hindi and Arabic have none.
3. Keep the structure the tests enforce: every everyday name differs from its standard name (except `NAV_TYPE`, `DECK_TYPE_EMERGENCY`, `DECK_TYPE_EMOJI`),
   and no two buttons share an everyday name except the four same-place pairs (HISTORY, PEOPLE AND PLACES, LOCATION ALERTS, VOICE AND SOUND).
4. Remove the DRAFT notice at the top only when you have read the whole file. Run `bash tools/kotlin_check/run_unit_tests.sh` (`TranslationsTest`).

To **add a language**: add it to `InterfaceLanguage` (`core/InterfaceLanguage.kt`), add `values-xx/strings.xml`, and update `TranslationsTest`/`InterfaceLanguageTest`
(they pin the five). The control lists whatever `InterfaceLanguage` holds.

## Not verified (no Android SDK, nothing run on a phone)

The restart and the locale applied through `createConfigurationContext`; every translated screen's layout (longer words wrapping in 48 dp buttons); the
mirrored layout in Arabic; which digits appear (most numbers are built by the app with Kotlin templates and show 0 to 9, but a value written with `String.format`, such as the twist-sensitivity slider, follows the phone's own number format); how the monospace font falls back for Devanagari and Arabic glyphs; TalkBack in each language; Android's own lint for resources.
`docs/LANGUAGE_VOCABULARY_DEVICE_TEST.md` section K is the do-this-expect-that list.
