"""Runs the plain-JavaScript logic tests (word re-alignment, edit merging) with Node, if it is installed."""
import shutil
import subprocess
from pathlib import Path

import pytest

JS_DIR = Path(__file__).resolve().parent / "js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_logic_suite_passes():
    files = sorted(str(p) for p in JS_DIR.glob("*.test.mjs"))
    assert files, "no JavaScript tests found"
    r = subprocess.run(["node", "--test", *files], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, (r.stdout + r.stderr)[-3000:]
