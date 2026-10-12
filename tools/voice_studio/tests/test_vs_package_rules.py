# SPDX-License-Identifier: GPL-3.0-or-later
"""Rules for the whole package, held by tests so a later change cannot quietly break them.

1. It runs on Ubuntu 22.04's Python 3.10, so nothing newer may be used.
2. core/ is plain Python: it imports no GUI toolkit (the window stays a thin edge over it).
3. Every source file says which license it is under.
"""
import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
CORE = PKG / "core"


def py_files(root=PKG):
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def parsed(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))


# ---------------------------------------------------------------- 1. Python 3.10

NEWER_IMPORTS = {   # names that exist only in a newer Python, with the version that added them
    "tomllib": "3.11", "StrEnum": "3.11", "Self": "3.11", "ExceptionGroup": "3.11", "BaseExceptionGroup": "3.11",
    "Required": "3.11", "NotRequired": "3.11", "LiteralString": "3.11", "Never": "3.11", "assert_never": "3.11",
    "override": "3.12", "batched": "3.12", "UTC": "3.11", "TaskGroup": "3.11",
}
NEWER_ATTRIBUTES = {
    ("datetime", "UTC"): "3.11", ("itertools", "batched"): "3.12", ("asyncio", "TaskGroup"): "3.11", ("asyncio", "timeout"): "3.11",
    ("typing", "Self"): "3.11", ("typing", "override"): "3.12", ("enum", "StrEnum"): "3.11",
}


def newer_python_uses(tree):
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(a.name, NEWER_IMPORTS[a.name]) for a in node.names if a.name in NEWER_IMPORTS]
        elif isinstance(node, ast.ImportFrom):
            if node.module in NEWER_IMPORTS:
                found.append((node.module, NEWER_IMPORTS[node.module]))
            found += [(a.name, NEWER_IMPORTS[a.name]) for a in node.names if a.name in NEWER_IMPORTS]
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            key = (node.value.id, node.attr)
            if key in NEWER_ATTRIBUTES:
                found.append((".".join(key), NEWER_ATTRIBUTES[key]))
    return found


def test_the_package_has_files_to_check():
    assert len(py_files()) >= 4


def test_every_file_parses_as_python_3_10():
    for p in py_files():
        parsed(p)   # raises SyntaxError for syntax newer than 3.10 (a 3.12 f-string, a type statement)


def test_nothing_newer_than_python_3_10_is_imported_or_used():
    offenders = [f"{p.relative_to(PKG)}: {name} (Python {version}+)" for p in py_files() for name, version in newer_python_uses(parsed(p))]
    assert not offenders, "Ubuntu 22.04 has Python 3.10:\n" + "\n".join(offenders)


def test_the_newer_python_check_catches_what_it_is_meant_to():   # mutation guard: the check itself must be able to fail
    bad = ast.parse("import tomllib\nfrom enum import StrEnum\nimport datetime\nx = datetime.UTC\nfrom typing import Self\n")
    assert {n for n, _ in newer_python_uses(bad)} == {"tomllib", "StrEnum", "datetime.UTC", "Self"}
    assert newer_python_uses(ast.parse("import json\nfrom pathlib import Path\n")) == []


# ---------------------------------------------------------------- 2. core/ imports no GUI toolkit

GUI_ROOTS = {"gi", "tkinter", "Tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "wx", "kivy", "pygame", "cairo"}


def imported_roots(tree):
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_imports_no_gui_toolkit():
    offenders = [f"{p.relative_to(PKG)}: {sorted(imported_roots(parsed(p)) & GUI_ROOTS)}" for p in py_files(CORE) if imported_roots(parsed(p)) & GUI_ROOTS]
    assert not offenders, "core/ is plain Python; the window is a thin edge over it:\n" + "\n".join(offenders)


def test_the_gui_import_check_catches_what_it_is_meant_to():
    assert imported_roots(ast.parse("import gi\nfrom gi.repository import Gtk\nimport os.path\n")) == {"gi", "os"}
    assert imported_roots(ast.parse("from . import x\nfrom .y import z\n")) == set()


# ---------------------------------------------------------------- 3. licensing

def test_every_source_file_says_which_license_it_is_under():
    missing = []
    for p in sorted(PKG.rglob("*")):
        if p.suffix in {".py", ".sh"} and "__pycache__" not in p.parts and p.stat().st_size:
            if "SPDX-License-Identifier: GPL-3.0-or-later" not in "\n".join(p.read_text(encoding="utf-8").splitlines()[:10]):
                missing.append(str(p.relative_to(PKG)))
    assert not missing, "add `SPDX-License-Identifier: GPL-3.0-or-later` near the top of:\n" + "\n".join(missing)
