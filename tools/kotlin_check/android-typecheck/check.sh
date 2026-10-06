#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Type-checks app/.../voicecapture against Compose Multiplatform and the Android stubs in ./stubs. Prints TYPE-CHECK PASSED or the errors.
set -e
H="$(cd "$(dirname "$0")" && pwd)"
A="$H/../../../app/src/main/java/com/example/besu"
STAGE="$H/build/stage"
rm -rf "$STAGE"; mkdir -p "$STAGE/com/example/besu/help" "$STAGE/com/example/besu/ui/theme"
cp -r "$A/capture" "$A/voicecapture" "$STAGE/com/example/besu/"
cp "$A/AckTags.kt" "$STAGE/com/example/besu/"
for f in HelpCore HelpManager HelpTarget HelpOfferBanner RecordTrainingDataHelp; do cp "$A/help/$f.kt" "$STAGE/com/example/besu/help/"; done
# HELP's own chrome: the menu, the coach panel and the two chooser dialogs. The walkthrough modules they list (FieldOpsHelp, VoiceRecordingsHelp) are only stubbed, for the option types
# the choosers draw (stubs/app/HelpModules.kt); helpText() is stubbed in stubs/app/AppUi.kt.
for f in HelpMenuDialog HelpCoachDialog PoseSelectorDialog VoiceRecordingsHelpSelectorDialog; do cp "$A/help/$f.kt" "$STAGE/com/example/besu/help/"; done
cp "$A/ui/OverlayStyle.kt" "$STAGE/com/example/besu/ui/"
# The profile-change warning's dialog (its words come from core/ProfileSwapDiff.kt through a TextSource, which is staged with the rest of core/).
cp "$A/ui/ProfileChangeDialog.kt" "$STAGE/com/example/besu/ui/"
# PLAIN WORDS' Terminal controls: the screen file plus the plain-Kotlin model it uses and the dialog text helper it calls.
mkdir -p "$STAGE/com/example/besu/core" "$STAGE/com/example/besu/settings"
cp "$A/core/SendFlags.kt" "$A/core/PlainLabels.kt" "$STAGE/com/example/besu/core/"
cp "$A/ui/TerminalPlainControls.kt" "$STAGE/com/example/besu/ui/"
cp "$A/settings/ConfirmDialogParts.kt" "$STAGE/com/example/besu/settings/"
# INTERFACE LANGUAGE: the section screen, its rules, and the letter-spacing helper every screen now calls.
cp "$A/core/InterfaceLanguage.kt" "$STAGE/com/example/besu/core/"
cp "$A/ui/ScriptSpacing.kt" "$STAGE/com/example/besu/ui/"
cp "$A/settings/InterfaceLanguageSection.kt" "$STAGE/com/example/besu/settings/"
# R is generated from the real strings file, so a name the screen uses that does not exist fails here.
{ echo "package com.example.besu"; echo "object R { object string {"; grep -o 'name="[A-Za-z0-9_]*"' "$A/../../../../res/values/strings.xml" | sed 's/name="\(.*\)"/    const val \1 = 0/'; echo "} }"; } > "$STAGE/com/example/besu/R.kt"
cp "$A/ui/theme/Color.kt" "$STAGE/com/example/besu/ui/theme/"
# The backup wording: the text source and the two decisions that use it, the Android edge that reads resources, and the two screens that show it.
# BackupExporter / BackupReminder are stubbed (stubs/app/Backup.kt) because they read storage; their signatures are what these screens call.
mkdir -p "$STAGE/com/example/besu/data"
cp "$A/core/TextSource.kt" "$A/core/ExportContents.kt" "$A/core/BackupReminderText.kt" "$A/core/BackupReminderPolicy.kt" "$STAGE/com/example/besu/core/"
# DELETE DATA: its decisions are plain Kotlin (all of core/ compiles without Android, as the unit tests show), and its dialogs. DataWipe is stubbed (stubs/app/DataWipe.kt).
cp -r "$A/core/." "$STAGE/com/example/besu/core/"
cp "$A/settings/ManageDataDialog.kt" "$A/settings/SafetyCopyDialogs.kt" "$A/settings/DeleteVoiceDialogs.kt" "$STAGE/com/example/besu/settings/"
# People and places: the category, tree, wizard and quick-insert screens and the models they draw. ComputerRepository, the contact card dialog and the visual editor are
# stubbed from their real signatures (stubs/app/Computer.kt).
mkdir -p "$STAGE/com/example/besu/computer"
cp "$A/computer/ComputerModels.kt" "$A/computer/CategoryNames.kt" "$A/computer/TargetView.kt" "$A/computer/ComputerTreeWindow.kt" "$A/computer/ComputerWizard.kt" "$A/computer/ManualOverrideTargetBrowser.kt" "$A/computer/ContactCardView.kt" "$STAGE/com/example/besu/computer/"
# The Emergency deck. CommandRepository and TemplateEngine are stubbed from their real signatures (stubs/app/CommandRepository.kt): they read storage and the shared variables.
mkdir -p "$STAGE/com/example/besu/decks"
cp "$A/decks/EmergencyDeck.kt" "$STAGE/com/example/besu/decks/"
# The CREATE DECK dialog (its words are string resources; DeckType is stubbed in stubs/app/Data.kt).
cp "$A/decks/CreateDeckDialog.kt" "$STAGE/com/example/besu/decks/"
# AUDIO ARCHITECT: the screen and its one-time defaults offer. Everything it calls outside the Compose-only files (the output service, the voice stores, the backup
# manager, the capture home screen) is stubbed from its real signatures (stubs/app/Audio.kt).
cp "$A/settings/AudioView.kt" "$A/settings/DefaultsPrompt.kt" "$STAGE/com/example/besu/settings/"
# WORD SUGGESTIONS: SETTINGS section and FORGET WORDS (the learned-words repository is stubbed in stubs/app/AudioData.kt).
cp "$A/settings/WordSuggestionsSection.kt" "$STAGE/com/example/besu/settings/"
# MANAGE CONTEXT: the custom context layer dialogs (moved out of DesignSystem.kt so they can be checked). The context functions are stubbed in stubs/app/CommandRepository.kt.
cp "$A/ui/ManageContextDialog.kt" "$STAGE/com/example/besu/ui/"
# MANAGE AUTOCOMPLETE: the dialog (the history repository, the Quick Actions models and the deck, node and phrase lookups are stubbed from their real signatures).
cp "$A/settings/ManageAutocompleteDialog.kt" "$STAGE/com/example/besu/settings/"
# MANAGE RECORDINGS and the voice recording panel it embeds (the recorder, the recordings store and the command lookups are stubbed from their real signatures).
mkdir -p "$STAGE/com/example/besu/output"
cp "$A/settings/ManageRecordingsDialog.kt" "$STAGE/com/example/besu/settings/"
cp "$A/output/VoiceRecordingPanel.kt" "$STAGE/com/example/besu/output/"
cp "$A/output/AudioDsp.kt" "$STAGE/com/example/besu/output/"
mkdir -p "$STAGE/com/example/besu/output"
cp "$A/data/VoiceProfile.kt" "$STAGE/com/example/besu/data/"
cp "$A/output/VoiceInfoMapping.kt" "$STAGE/com/example/besu/output/"
cp "$A/data/ResourceText.kt" "$STAGE/com/example/besu/data/"
cp "$A/ui/ResourceText.kt" "$A/ui/BackupReminderBanner.kt" "$STAGE/com/example/besu/ui/"
cp "$A/settings/BackupWarningDialog.kt" "$STAGE/com/example/besu/settings/"
# The limits statement: the one-time banner and the ABOUT section (their words and rules are core/LimitsNotice.kt, staged with the rest of core/).
cp "$A/ui/LimitsNoticeBanner.kt" "$STAGE/com/example/besu/ui/"
cp "$A/settings/AboutSection.kt" "$STAGE/com/example/besu/settings/"
# SAVE MESSAGE LOG TO A FILE: the warning dialog and its flow (the exporter is stubbed in stubs/app/LogExporter.kt; the words and the file format are core/LogExport*.kt, staged with the rest of core/).
cp "$A/settings/LogExportDialog.kt" "$STAGE/com/example/besu/settings/"
cp -r "$H/stubs/." "$STAGE/"
cd "$H"
gradle --no-daemon --console=plain -q -Pkotlin.compiler.execution.strategy=in-process compileKotlin > "$H/build/check.log" 2>&1 && status=0 || status=$?
grep -v "^Picked up JAVA_TOOL_OPTIONS" "$H/build/check.log" || true
if [ "$status" = 0 ]; then echo "TYPE-CHECK PASSED"; else echo "TYPE-CHECK FAILED (gradle exit $status)"; fi
exit $status
