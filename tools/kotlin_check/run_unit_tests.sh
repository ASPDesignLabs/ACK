#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Runs the unit tests of the plain-Kotlin packages (capture/ and core/) with plain Gradle (no Android SDK). Needs a JDK 17+ and Gradle 8+; fetches from Maven Central.
# Optional: ACK_KOTLIN_PACKAGES=<folder> makes PackageWriterTest also write sample packages there for
# tools/freeform_studio/tests/test_kotlin_package_contract.py to open.
set -e
cd "$(dirname "$0")/unit-tests"
mkdir -p build
gradle --no-daemon --console=plain -q -Pkotlin.compiler.execution.strategy=in-process cleanTest test
python3 - <<'PY'
import glob, xml.etree.ElementTree as ET
tests = fails = 0
for f in sorted(glob.glob("build/test-results/test/*.xml")):
    r = ET.parse(f).getroot()
    tests += int(r.get("tests")); fails += int(r.get("failures")) + int(r.get("errors"))
print(f"{tests} tests, {fails} failed")
raise SystemExit(1 if fails else 0)
PY
