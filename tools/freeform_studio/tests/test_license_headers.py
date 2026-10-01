# SPDX-License-Identifier: GPL-3.0-or-later
"""The project is GPL-3.0-or-later, and stays that way: the license text is verbatim, every source file says so, and nothing
made by someone else is added without being listed in THIRD_PARTY_NOTICES.md.

Checks on files in the repository, so they run anywhere the whole repo is checked out and skip when this folder is on its own.
"""
import hashlib
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(not (ROOT / "LICENSE").exists() or not (ROOT / "app").exists(), reason="not inside the full ACK repository")

GPL3_SHA256 = "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"       # the FSF's text, as shipped in Debian and Ubuntu
APACHE2_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
CODE = {".kt", ".kts", ".py", ".js", ".mjs", ".html", ".css", ".sh", ".pro"}
SKIP_PARTS = {".idea", "__pycache__", "node_modules", ".gradle", "build"}
BINARY_ASSETS = {".so", ".otf", ".ttf", ".jar", ".aar", ".woff", ".woff2"}
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"


def repo_files():
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return sorted({ROOT / p for p in out.stdout.splitlines() if p and (ROOT / p).is_file()})
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(p for p in ROOT.rglob("*") if p.is_file() and not (SKIP_PARTS & set(p.relative_to(ROOT).parts)))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_the_license_file_is_the_unmodified_gpl_version_3_text():
    assert sha(ROOT / "LICENSE") == GPL3_SHA256, ("LICENSE must stay byte-for-byte the FSF's GPLv3; the copyright line belongs in "
                                                  "NOTICE, not in the license text")


def test_the_apache_text_kept_for_the_one_derived_file_is_unmodified():
    assert sha(ROOT / "LICENSES" / "Apache-2.0.txt") == APACHE2_SHA256


def test_every_source_file_says_which_license_it_is_under():
    missing = []
    for p in repo_files():
        rel = p.relative_to(ROOT)
        if p.suffix not in CODE or SKIP_PARTS & set(rel.parts) or p.stat().st_size == 0:
            continue
        head = "\n".join(p.read_text(encoding="utf-8", errors="replace").splitlines()[:10])
        if "SPDX-License-Identifier: GPL-3.0-or-later" not in head:
            missing.append(str(rel))
    assert not missing, ("add `SPDX-License-Identifier: GPL-3.0-or-later` in a comment on the first lines (after a shebang or "
                         "<!doctype>) of:\n" + "\n".join(missing))


def test_the_notice_and_readme_say_gpl_3_or_later():
    notice = " ".join((ROOT / "NOTICE").read_text().split())     # the sentence wraps across lines in the file
    assert "either version 3 of the License, or (at your option) any later version" in notice
    assert "SPDX-License-Identifier: GPL-3.0-or-later" in notice and "Copyright (C) 2026" in notice
    assert "GPL-3.0-or-later" in (ROOT / "README.md").read_text()


def test_the_script_that_follows_sherpa_onnxs_original_credits_it():
    head = "\n".join((ROOT / "tools" / "patch_voice_for_sherpa_onnx.py").read_text().splitlines()[:14])
    assert "Apache-2.0" in head and "Xiaomi Corp." in head and "LICENSES/Apache-2.0.txt" in head
    assert "Changes made here" in head, "Apache-2.0 asks that changes to a derived file are stated"
    assert "SPDX-License-Identifier: GPL-3.0-or-later AND Apache-2.0" in head


def test_every_binary_asset_in_the_repository_is_listed_in_the_third_party_notices():
    notices = NOTICES.read_text()
    unlisted = [str(p.relative_to(ROOT)) for p in repo_files() if p.suffix in BINARY_ASSETS and str(p.relative_to(ROOT)) not in notices]
    assert not unlisted, "a font or native library was added without saying where it came from and under what license:\n" + "\n".join(unlisted)


def test_every_python_requirement_of_freeform_studio_is_listed_in_the_third_party_notices():
    notices = NOTICES.read_text().lower().replace("_", "-")
    names = [re.split(r"[<>=!~\[ ;]", line.strip(), 1)[0].lower().replace("_", "-")
             for line in (ROOT / "tools" / "freeform_studio" / "requirements.txt").read_text().splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    assert names and not [n for n in names if n not in notices], f"not in THIRD_PARTY_NOTICES.md: {[n for n in names if n not in notices]}"


def test_the_notices_say_which_claims_were_not_verified():
    text = NOTICES.read_text()
    assert "not verified" in text and "How each entry was checked" in text and "not legal advice" in text
