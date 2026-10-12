# SPDX-License-Identifier: GPL-3.0-or-later
"""A name or an id that ends with a line break is not a valid name or an id.

In Python a `$` at the end of a pattern also matches just before a final line break, so `^[a-z0-9-]{1,64}$` accepts `"abc\\n"`. Every check below ends with `\\Z` instead. There are
three kinds of proof: each check is shown to refuse its good sample with a line break added, a few call sites are shown to refuse it where it matters, and the source of the whole package
and the maintainers' tools is read, so a pattern that goes back to ending in `$` fails here (the reader is shown to catch the shapes it is for).
"""
import ast
import importlib.util
import sys
from pathlib import Path

import pytest

from voice_studio.core import ackimport, commands, envspec, jobs, launcher, registry, scratch, text, winshortcut

PKG = Path(__file__).resolve().parents[1]
MAINT = PKG.parent / "voice_studio_maint"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module                  # the pin maker uses dataclasses, which look their own module up by name
    spec.loader.exec_module(module)
    return module


make_lock = load("make_lock_trailing_newline", MAINT / "make_lock.py")
make_pins = load("make_pins_trailing_newline", MAINT / "make_pins.py")

CHECKS = [
    ("jobs.KIND", jobs.KIND, "train"), ("scratch.PROJECT_ID", scratch.PROJECT_ID, "voice-check"), ("commands.SAFE_NAME", commands.SAFE_NAME, "round-1_a.b"),
    ("commands.CHECKPOINT_DIR", commands.CHECKPOINT_DIR, "version_12"), ("text.LANGUAGE", text.LANGUAGE, "en"), ("text.LANGUAGE (with a region)", text.LANGUAGE, "pt-br"),
    ("envspec.SHA256", envspec.SHA256, "a" * 64), ("envspec.SAFE_LOCK_NAME", envspec.SAFE_LOCK_NAME, "training-3.12.txt"), ("envspec.SAFE_RELATIVE", envspec.SAFE_RELATIVE, "lib/x.py"),
    ("envspec.DIST_NAME", envspec.DIST_NAME, "numpy"), ("envspec.NATIVE_FILE", envspec.NATIVE_FILE, "mod.pyx"), ("envspec.NATIVE_MODULE", envspec.NATIVE_MODULE, "mod"),
    ("envspec._HASH", envspec._HASH, "--hash=sha256:" + "a" * 64), ("envspec._REQUIREMENT", envspec._REQUIREMENT, "numpy==1.26.4"),
    ("registry.SAFE_FILENAME", registry.SAFE_FILENAME, "model.onnx"), ("registry.SLUG", registry.SLUG, "amy-low"), ("registry.SHA256", registry.SHA256, "b" * 64),
    ("registry.PAGE_ADDRESS", registry.PAGE_ADDRESS, "example.test/page"), ("ackimport.NAME_RE", ackimport.NAME_RE, "my package.zip"),
    ("launcher.SAFE_PATH", launcher.SAFE_PATH, "/usr/bin/python3"), ("winshortcut.DISTRO_PATTERN", winshortcut.DISTRO_PATTERN, "Ubuntu-22.04"),
    ("winshortcut.FILE_NAME_PATTERN", winshortcut.FILE_NAME_PATTERN, "ACK Voice Studio"),
    ("make_lock.LINE", make_lock.LINE, "numpy==1.26.4"), ("make_pins.SHA256", make_pins.SHA256, "a" * 64), ("make_pins.COMMIT", make_pins.COMMIT, "b" * 40),
    ("make_pins.SLUG", make_pins.SLUG, "x-y"), ("make_pins.SAFE_FILENAME", make_pins.SAFE_FILENAME, "model.onnx"),
]


@pytest.mark.parametrize("name, pattern, good", CHECKS, ids=[c[0] for c in CHECKS])
def test_a_check_that_accepts_a_value_refuses_the_same_value_with_a_line_break_after_it(name, pattern, good):
    assert pattern.match(good), "the sample must be a good one"
    for spoiled in (good + "\n", good + "\n\n", good + "\r\n"):
        assert not pattern.match(spoiled), repr(spoiled)


def test_a_job_with_a_kind_or_a_project_that_ends_with_a_line_break_is_refused_before_it_starts():
    ok = jobs.JobSpec("train", "voice-check", ("true",))
    jobs._check_spec(ok)
    for kind, project in (("train\n", "voice-check"), ("train", "voice-check\n")):
        with pytest.raises(jobs.JobError) as caught:
            jobs._check_spec(jobs.JobSpec(kind, project, ("true",)))
        assert caught.value.code == "bad_spec"


def test_a_language_with_a_line_break_is_not_a_language_to_load_even_if_a_file_with_that_odd_name_is_there(tmp_path):
    english = (text.DATA_DIR / "en.json").read_text(encoding="utf-8")
    (tmp_path / "en.json").write_text(english, encoding="utf-8")
    (tmp_path / "xx.json").write_text(english, encoding="utf-8")
    (tmp_path / "xx\n.json").write_text(english, encoding="utf-8")
    assert text.available_languages(tmp_path) == ["en", "xx"]
    assert text.load_catalog("xx", tmp_path).language == "xx"
    assert text.load_catalog("xx\n", tmp_path).language == "en"


def test_the_pin_makers_link_reader_still_finds_the_next_page_when_the_header_ends_with_white_space():
    assert make_pins.next_page('<example.test/next>; rel="next"') == "example.test/next"
    assert make_pins.next_page('<example.test/next>; rel="next" \r\n') == "example.test/next"
    assert make_pins.next_page('<example.test/a>; rel="prev", <example.test/b>; rel="next"\n') == "example.test/b"
    assert make_pins.next_page('<example.test/next>; rel="nextish"') is None and make_pins.next_page(None) is None


# ---------------------------------------------------------------- read the source, so it stays that way

def ends_with_dollar(pattern):
    """Does the pattern end with a `$` that is a line end, and not an escaped dollar sign (`\\$`, but `\\\\$` is an escaped backslash and then a line end)?"""
    if not pattern.endswith("$"):
        return False
    body = pattern[:-1]
    return (len(body) - len(body.rstrip("\\"))) % 2 == 0


def patterns_ending_in_dollar(source):
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "re"
                and node.func.attr in {"compile", "match", "search"} and node.args):
            continue
        first = node.args[0]
        if isinstance(first, ast.BinOp) and isinstance(first.op, ast.Mod):              # "pattern ... $" % value
            first = first.left
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str) and ends_with_dollar(first.value)):
            continue
        flags = [n for part in list(node.args[1:]) + [k.value for k in node.keywords] for n in ast.walk(part)]
        if any(isinstance(n, ast.Attribute) and n.attr in {"MULTILINE", "M"} for n in flags):
            continue                                                                       # a pattern that is meant to match line by line
        found.append(first.lineno)
    return found


def test_no_pattern_in_the_package_or_the_maintainers_tools_ends_in_a_dollar_that_a_line_break_gets_past():
    files = [p for p in sorted(PKG.rglob("*.py")) + sorted(MAINT.rglob("*.py")) if "tests" not in p.relative_to(PKG.parent).parts and "__pycache__" not in p.parts]
    assert len(files) > 40
    offenders = {str(p.relative_to(PKG.parent)): patterns_ending_in_dollar(p.read_text(encoding="utf-8")) for p in files}
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, "end the pattern with \\Z (a $ also matches before a trailing line break):\n%s" % offenders


def test_the_source_reader_can_actually_fail():
    assert patterns_ending_in_dollar('import re\nA = re.compile(r"^a$")\n') == [2]
    assert patterns_ending_in_dollar('import re\nre.match(r"^a$", x)\nre.search("a$", x)\n') == [2, 3]
    assert patterns_ending_in_dollar('import re\nA = re.compile(r"^a-%s$" % x)\n') == [2]
    assert patterns_ending_in_dollar('import re\nA = re.compile(r"^a\\\\$")\n') == [2]                              # an escaped backslash, then a line end
    assert patterns_ending_in_dollar('import re\nA = re.compile(r"^a\\Z")\nB = re.compile(r"^a\\$")\nC = re.compile(r"^a")\n') == []      # \Z, an escaped dollar sign, no dollar
    assert patterns_ending_in_dollar('import re\nA = re.compile(r"^a$", re.MULTILINE)\nB = re.compile(r"^a$", flags=re.M | re.I)\n') == []
    assert patterns_ending_in_dollar('import re\nre.sub(r"a$", "", x)\nre.fullmatch(r"a$", x)\n') == []        # these are not asked to refuse a trailing break
