#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Parse-only check for Kotlin files that cannot be type-checked here (they use the Android SDK): compiles them with no classpath and reports only SYNTAX errors.
# Unresolved references are expected and ignored, so this finds a missing parenthesis or brace and nothing else. Usage: run_syntax_check.sh File.kt [File2.kt ...]
# Prints "syntax errors: 0" when the files parse. Proved by breaking a copy on purpose (an unclosed parenthesis is reported at its line).
set -e
GRADLE="$(readlink -f "$(command -v gradle)")"
LIB="$(dirname "$GRADLE")/../lib"
CP=$(ls "$LIB"/kotlin-compiler-embeddable-*.jar "$LIB"/kotlin-stdlib-*.jar "$LIB"/kotlin-reflect-*.jar "$LIB"/kotlin-script-runtime-*.jar "$LIB"/kotlin-daemon-embeddable-*.jar \
    "$LIB"/annotations-*.jar "$LIB"/trove4j*.jar "$LIB"/kotlinx-coroutines-core-jvm-*.jar | tr '\n' ':')
OUT="$(mktemp -d)"; LOG="$OUT/log"
trap 'rm -rf "$OUT"' EXIT
java -cp "$CP" org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -no-stdlib -no-reflect -nowarn -d "$OUT/classes" "$@" 2>&1 | grep -v "^Picked up" > "$LOG" || true
grep -i "syntax error\|expecting\|unclosed" "$LOG" | head -20 || true
n=$(grep -ci "syntax error\|expecting\|unclosed" "$LOG" || true)
echo "syntax errors: ${n:-0}"
[ "${n:-0}" = 0 ]
