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
cp "$A/ui/OverlayStyle.kt" "$STAGE/com/example/besu/ui/"
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
cp "$A/data/ResourceText.kt" "$STAGE/com/example/besu/data/"
cp "$A/ui/ResourceText.kt" "$A/ui/BackupReminderBanner.kt" "$STAGE/com/example/besu/ui/"
cp "$A/settings/BackupWarningDialog.kt" "$STAGE/com/example/besu/settings/"
cp -r "$H/stubs/." "$STAGE/"
cd "$H"
gradle --no-daemon --console=plain -q -Pkotlin.compiler.execution.strategy=in-process compileKotlin > "$H/build/check.log" 2>&1 && status=0 || status=$?
grep -v "^Picked up JAVA_TOOL_OPTIONS" "$H/build/check.log" || true
if [ "$status" = 0 ]; then echo "TYPE-CHECK PASSED"; else echo "TYPE-CHECK FAILED (gradle exit $status)"; fi
exit $status
