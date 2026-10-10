# SPDX-License-Identifier: GPL-3.0-or-later
"""The text catalog (plan task VS-1.7, decisions D19 and D22): safe to fill in, plain in its words, and complete in both directions.

Complete means: every key the code names is in the catalog, every code the modules can raise or return has words (a failed step has all three
parts, what happened, whether anything changed, and what to do next), and no string is left that nothing uses.
"""
import ast
import json
import re
import shutil
from pathlib import Path

import pytest

from vs_fakes import (DEBIAN_12, MEM_4G, PROC_WSL1, SMI_6G, SMI_DRIVER_DOWN, UBUNTU_2004, FakeSystem, wsl2)
from voice_studio.core import describe as ds
from voice_studio.core import ackimport, diskbudget, envbuild, envspec, fetch, jobs, newproject, preflight, project, report, scratch, setupplan, setuprun, text, voicezip
from voice_studio.core.registry import load_registry
from voice_studio.core.system import CommandResult
from voice_studio.core.text import Catalog, TextError

PKG = Path(__file__).resolve().parents[1]
CAT = text.load_catalog("en")
SHIPPED_PY = sorted(p for p in (PKG / "core").glob("*.py") if p.name not in {"text.py", "describe.py"})
NAMESPACES = ("ui", "preflight", "apt", "fetch", "job", "project", "scratch", "budget", "report", "setup", "env", "newproject", "ackimport", "voicezip")
KEY = re.compile(r"^(%s)\.[a-z0-9_]+(\.[a-z0-9_]+)*$" % "|".join(NAMESPACES))


# ---------------------------------------------------------------- filling in a template

def test_a_placeholder_is_filled_and_nothing_else_in_the_value_is_ever_read_as_a_template():
    assert text.render("Hello {name}.", {"name": "Anna"}) == "Hello Anna."
    assert text.render("Hello {name}.", {"name": "{other} {{x}} {0} %s"}) == "Hello {other} {{x}} {0} %s."
    assert text.render("{{literal}} {a}{b}", {"a": 1, "b": 2}) == "{literal} 12"
    assert text.render("{memory_mib} MB", {"memory_mib": 7000}) == "7000 MB"


def test_a_value_with_attribute_tricks_is_just_text():
    class Evil:
        def __str__(self):
            return "ok"
    assert text.render("{x}", {"x": Evil()}) == "ok"
    assert text.render("{x.__class__}", {"x": 1}) == "{x.__class__}"            # not a placeholder: left exactly as it is
    assert text.placeholders("{x.__class__} {y!r} {z:>5}") == frozenset()


def test_a_missing_value_stays_visible_and_strict_mode_says_which():
    assert text.render("Hello {name}.", {}) == "Hello {name}."
    with pytest.raises(KeyError) as caught:
        text.render("Hello {name}.", {}, strict=True)
    assert caught.value.args == ("name",)


def test_placeholders_are_listed_by_name():
    assert text.placeholders("{a} and {b_2} and {{c}} and {a}") == frozenset({"a", "b_2"})
    assert text.placeholders("no placeholders") == frozenset()


def test_a_key_that_is_not_in_the_catalog_reads_as_itself_so_a_gap_shows():
    assert CAT.t("nope.not.here") == "nope.not.here" and CAT.count("nope.not.here", 2) == "nope.not.here"
    with pytest.raises(KeyError):
        CAT.strict("nope.not.here")
    assert CAT.t("preflight.os.supported", name="Ubuntu 24.04.1 LTS") == "Ubuntu 24.04.1 LTS works with this tool."


def test_plurals_use_the_number_and_one_is_exactly_one():
    assert CAT.count("preflight.packages.missing", 1) == "1 extra program needs to be installed."
    assert CAT.count("preflight.packages.missing", 0) == "0 extra programs need to be installed."
    assert CAT.count("preflight.packages.missing", 2) == "2 extra programs need to be installed."
    assert CAT.count("preflight.packages.missing", 1000) == "1000 extra programs need to be installed."
    assert text.plural_form("en", 1) == "one" and text.plural_form("en", 11) == "other"


def test_sizes_read_the_way_drives_are_labelled():
    assert text.size_text(846_000_000) == "846 MB" and text.size_text(1_692_000_000) == "1.7 GB" and text.size_text(0) == "0 B"


# ---------------------------------------------------------------- languages

def make_language(tmp_path, code, strings, plurals=None):
    shutil.copy(text.DATA_DIR / "en.json", tmp_path / "en.json")
    (tmp_path / (code + ".json")).write_text(json.dumps({"schema": 1, "language": code, "strings": strings, "plurals": plurals or {}}), encoding="utf-8")
    return text.load_catalog(code, data_dir=tmp_path)


def test_another_language_covers_what_it_has_and_english_covers_the_rest(tmp_path):
    cat = make_language(tmp_path, "xx", {"ui.cancel": "Annuler"}, {"preflight.disk.facts": {"other": "{count} endroits"}})
    assert cat.t("ui.cancel") == "Annuler" and cat.t("ui.back") == "Back"
    assert cat.count("preflight.disk.facts", 3) == "3 endroits" and cat.count("preflight.packages.missing", 2) == "2 extra programs need to be installed."
    assert cat.has("ui.back") and cat.is_plural("preflight.packages.missing")


def test_an_unknown_or_unsafe_language_is_english_and_a_bad_file_is_an_error(tmp_path):
    shutil.copy(text.DATA_DIR / "en.json", tmp_path / "en.json")
    assert text.load_catalog("zz", data_dir=tmp_path).language == "en" and text.load_catalog("../../etc/passwd", data_dir=tmp_path).language == "en"
    (tmp_path / "bad.json").write_text("{not json")
    with pytest.raises(TextError):
        text.load_catalog("bad", data_dir=tmp_path)
    for content in ({"schema": 9, "strings": {}}, {"schema": 1}, {"schema": 1, "strings": {"a": 5}}, {"schema": 1, "strings": {}, "plurals": {"p": {"one": "x"}}},
                    {"schema": 1, "strings": {}, "plurals": {"p": {"other": "x", "weird": "y"}}}):
        (tmp_path / "bad.json").write_text(json.dumps(content))
        with pytest.raises(TextError):
            text.load_catalog("bad", data_dir=tmp_path)


def test_a_language_name_cannot_reach_a_catalog_outside_the_folder(tmp_path):
    folder = tmp_path / "text"
    folder.mkdir()
    shutil.copy(text.DATA_DIR / "en.json", folder / "en.json")
    (tmp_path / "evil.json").write_text(json.dumps({"schema": 1, "strings": {"ui.cancel": "HACKED"}}))
    assert text.load_catalog("../evil", data_dir=folder).t("ui.cancel") == "Cancel"
    assert text.load_catalog("../evil", data_dir=folder).language == "en"


def test_languages_are_listed_by_file(tmp_path):
    make_language(tmp_path, "xx", {})
    (tmp_path / "Not A Language.json").write_text("{}")
    assert text.available_languages(tmp_path) == ["en", "xx"] and "en" in text.available_languages()


def test_every_language_file_asks_for_the_same_placeholders_as_english():
    english = json.loads((text.DATA_DIR / "en.json").read_text(encoding="utf-8"))
    for lang in text.available_languages():
        other = json.loads((text.DATA_DIR / (lang + ".json")).read_text(encoding="utf-8"))
        for key, value in other["strings"].items():
            assert key in english["strings"], (lang, key)
            assert text.placeholders(value) == text.placeholders(english["strings"][key]), (lang, key)


# ---------------------------------------------------------------- wording rules

JARGON = ("checkpoint", "epoch", "venv", "tensor", "onnx", "cuda", "vram", "ckpt", "checksum", "sha256", "filesystem", "symlink", "chmod", "sudo", "apt",
          "pip", "ffmpeg", "wslg", "python", "gpu", "hash", "mount", "dataset", "cache", "daemon", "pid")
MAX_WORDS_IN_A_SENTENCE = 25
MAX_LENGTH = 300


def wording_problems(key, value):
    """Why this text is not plain enough, or []. Texts under a `.detail` key may be technical and are not checked."""
    if key.endswith(".detail"):
        return []
    problems = []
    for term in () if key.startswith("report.") else JARGON:       # the report is for whoever helps, so it may name Python and the like
        if re.search(r"\b%s\b" % re.escape(term), value, re.IGNORECASE):
            problems.append("jargon:" + term)
    for sentence in re.split(r"(?<=[.!?])\s+", value):
        if len(sentence.split()) > MAX_WORDS_IN_A_SENTENCE:
            problems.append("long_sentence")
    if value != value.strip() or "  " in value or "\n" in value or "\r" in value or "\t" in value:
        problems.append("whitespace")
    if len(value) > MAX_LENGTH:
        problems.append("long")
    if re.search(r"(?:https?|ftp)://", value):
        problems.append("web_address")
    if re.search(r"\b[A-Z]{4,}\b", value):
        problems.append("shouting")
    if re.search(r"%[sd]|%\(|\{\d|\{[^}]*[!:.\[]", value) or re.sub(r"\{\{|\}\}|\{[a-z][a-z0-9_]*\}", "", value).count("{") or re.sub(r"\{\{|\}\}|\{[a-z][a-z0-9_]*\}", "", value).count("}"):
        problems.append("template")
    if not value:
        problems.append("empty")
    return problems


def all_texts():
    data = json.loads((text.DATA_DIR / "en.json").read_text(encoding="utf-8"))
    yield from data["strings"].items()
    for key, forms in data["plurals"].items():
        for form, value in forms.items():
            yield key + "#" + form, value


def test_every_text_is_plain_short_and_safe_to_fill_in():
    bad = {key: wording_problems(key, value) for key, value in all_texts() if wording_problems(key, value)}
    assert not bad, bad


def test_the_wording_rules_can_actually_fail():          # mutation guards: each rule is shown to catch what it is for
    assert "jargon:checkpoint" in wording_problems("a.b", "The checkpoint was saved.") and "jargon:gpu" in wording_problems("a.b", "Your GPU is busy.")
    assert wording_problems("a.b.detail", "The checkpoint was saved by python on the GPU.") == []
    assert wording_problems("report.label.python", "Python") == [] and "jargon:python" in wording_problems("a.b", "Python")
    assert "long_sentence" in wording_problems("a.b", " ".join(["word"] * 26) + ".") and wording_problems("a.b", " ".join(["word"] * 25) + ".") == []
    assert "whitespace" in wording_problems("a.b", "two  spaces") and "whitespace" in wording_problems("a.b", "trailing ") and "whitespace" in wording_problems("a.b", "a\nb")
    assert "web_address" in wording_problems("a.b", "see https://example.org") and "shouting" in wording_problems("a.b", "STOP NOW")
    assert wording_problems("a.b", "WSL and USB are fine") == []
    assert "template" in wording_problems("a.b", "100%s done") and "template" in wording_problems("a.b", "{0} items") and "template" in wording_problems("a.b", "{x!r}")
    assert "template" in wording_problems("a.b", "stray { brace") and wording_problems("a.b", "{{literal}} {name}") == []
    assert "long" in wording_problems("a.b", "x" * 301) and "empty" in wording_problems("a.b", "")


def test_the_three_parts_of_a_failure_are_not_the_same_sentence_and_the_middle_one_says_what_happened_to_the_files():
    says_something_about_change = ("nothing", "kept", "deleted", "left", "no project", "not opened", "not changed", "not saved")
    for ns, codes in (("fetch", fetch.ERROR_CODES), ("job", jobs.ERROR_CODES), ("project", project.ERROR_CODES), ("env", envbuild.ERROR_CODES), ("newproject", newproject.ERROR_CODES), ("ackimport", ackimport.ERROR_CODES), ("voicezip", voicezip.ERROR_CODES)):
        for code in codes:
            parts = ds.error_text(CAT, ns, code)
            assert len({parts.what, parts.changed, parts.next}) == 3 and all(p and "." in p for p in (parts.what, parts.changed, parts.next)), (ns, code)
            assert any(w in parts.changed.lower() for w in says_something_about_change), (ns, code, parts.changed)
            assert parts.as_paragraph().count(". ") >= 2


# ---------------------------------------------------------------- complete in both directions

def code_keys():
    """Every catalog key the code names: written out as a string, or built from a list of codes."""
    keys = set()
    for path in SHIPPED_PY:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and KEY.match(node.value):
                keys.add(node.value)
    for item in load_registry().items:
        keys.add(item.why_key)
    return keys


def derived_keys():
    keys = set()
    for ns, codes in (("fetch", fetch.ERROR_CODES), ("job", jobs.ERROR_CODES), ("project", project.ERROR_CODES), ("env", envbuild.ERROR_CODES), ("newproject", newproject.ERROR_CODES), ("ackimport", ackimport.ERROR_CODES), ("voicezip", voicezip.ERROR_CODES)):
        keys |= {"%s.error.%s.%s" % (ns, code, part) for code in codes for part in ("what", "changed", "next")}
    keys |= {"scratch.refuse." + c for c in scratch.REFUSAL_CODES} | {"scratch.warn." + c for c in scratch.WARNING_CODES}
    keys |= {"scratch.speed." + c for c in scratch.SPEED_CODES} | {"job.status." + s.value for s in jobs.JobStatus}
    keys |= {"budget.level." + l.value for l in diskbudget.Level} | {"budget.watch." + w.value for w in diskbudget.Watch}
    keys |= {"project.consent.missing." + c for c in project.CONSENT_PROBLEM_CODES} | {"project.how_given." + h for h in project.HOW_GIVEN}
    keys |= {"setup.tag." + s.value for s in preflight.Status}
    keys |= {"newproject.problem.%s.%s" % pair for pair in newproject.PROBLEMS}
    keys |= {"voicezip.problem." + c for c in voicezip.PROBLEM_CODES}
    keys |= {"ackimport.state." + s for s in ("new", "already", "aborted")} | {"ackimport.mode." + m for m in ("script", "free")}
    keys |= {"setup.refuse." + c for c in setuprun.REFUSAL_CODES} | {"setup.status." + s for s in setuprun.STATUSES}
    keys |= {"setup.problem." + p for p in ("not_ready", "broken")} | {"setup.kind." + k for k in setupplan.KINDS}
    keys |= {"env.step." + a for a in envbuild.ACTION_IDS} | {"env.state." + s for s in envbuild.INSPECTION_STATES}
    for spec in envspec.load_environments():
        keys |= {spec.why_key} | {"env.probe." + probe.id for probe in spec.probes}
    keys |= {"report.label." + n for n in report.LABELS} | {"report.section." + s for s in report.SECTIONS} | {"report.platform." + p.value for p in preflight.Platform}
    return keys


def catalog_keys():
    data = json.loads((text.DATA_DIR / "en.json").read_text(encoding="utf-8"))
    return set(data["strings"]) | set(data["plurals"])


def test_a_key_is_either_a_sentence_or_a_plural_never_both():
    data = json.loads((text.DATA_DIR / "en.json").read_text(encoding="utf-8"))
    assert not set(data["strings"]) & set(data["plurals"])


def test_every_key_the_code_names_has_words():
    missing = sorted((code_keys() | derived_keys()) - catalog_keys())
    assert not missing, "in the code but not in data/text/en.json:\n" + "\n".join(missing)


def test_no_string_is_left_that_nothing_uses():
    used = code_keys() | derived_keys()
    unused = sorted(k for k in catalog_keys() if k not in used and not k.startswith("ui.") and not (k.endswith(".detail") and k[:-len(".detail")] in used))
    assert not unused, "in data/text/en.json but not used by any code:\n" + "\n".join(unused)


def test_a_detail_text_belongs_to_a_key_that_exists():
    for key in catalog_keys():
        if key.endswith(".detail"):
            assert key[:-len(".detail")] in catalog_keys(), key


def codes_in_calls(path, callee):
    """Every string that can be the first argument of `callee(...)` in `path`, including either branch of `"a" if x else "b"`."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == callee and node.args:
            found |= {c.value for c in ast.walk(node.args[0]) if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return found


def test_every_error_the_modules_raise_is_in_its_list_and_every_listed_one_is_raised():
    for path, callee, listed in ((PKG / "core/fetch.py", "FetchError", fetch.ERROR_CODES), (PKG / "core/jobs.py", "JobError", jobs.ERROR_CODES),
                                 (PKG / "core/project.py", "ProjectError", project.ERROR_CODES),
                                 (PKG / "core/envbuild.py", "EnvError", envbuild.ERROR_CODES),
                                 (PKG / "core/ackimport.py", "AckImportError", ackimport.ERROR_CODES),
                                 (PKG / "core/voicezip.py", "VoiceZipError", voicezip.ERROR_CODES)):
        raised = codes_in_calls(path, callee) - {"consent_problems"}
        assert raised <= set(listed), (callee, sorted(raised - set(listed)))
        assert set(listed) <= raised, (callee, "listed but never raised", sorted(set(listed) - raised))


def test_every_label_and_section_the_report_writes_is_declared_and_every_declared_one_is_written():
    tree = ast.parse((PKG / "core/report.py").read_text())
    written = {"labelled": set(), "section": set()}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in written and node.args and isinstance(node.args[0], ast.Constant):
            written[node.func.id].add(node.args[0].value)
    assert written["labelled"] <= set(report.LABELS) and written["section"] == set(report.SECTIONS)
    assert set(report.LABELS) - written["labelled"] <= {"time"}          # the time is written as a heading line, not through labelled()


def appended_codes(path, receivers):
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "append" and isinstance(node.func.value, ast.Name) \
                and node.func.value.id in receivers and node.args and isinstance(node.args[0], ast.Constant):
            found.add(node.args[0].value)
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id in receivers and isinstance(node.value, ast.List):
            found |= {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
    return found


def test_every_refusal_warning_and_speed_code_the_place_rules_can_give_is_listed_and_every_listed_one_can_be_given():
    refused, warned = appended_codes(PKG / "core/scratch.py", {"refuse"}), appended_codes(PKG / "core/scratch.py", {"warn"})
    assert refused == set(scratch.REFUSAL_CODES) and warned == set(scratch.WARNING_CODES)
    assert appended_codes(PKG / "core/scratch.py", {"codes"}) == set(scratch.SPEED_CODES)


# ---------------------------------------------------------------- real results read as sentences

SCENARIOS = {
    "healthy": FakeSystem(),
    "wsl2, nothing installed": wsl2(installed=[], tools={"apt-get": "/usr/bin/apt-get"}, failing_probes=("import",), smi=None),
    "root": FakeSystem(euid=0),
    "wsl1": FakeSystem(proc_version=PROC_WSL1),
    "old python": FakeSystem(python=(3, 9, 1)),
    "no gpu": FakeSystem(smi=None),
    "small gpu": FakeSystem(smi=CommandResult(0, SMI_6G)),
    "gpu error": FakeSystem(smi=CommandResult(9, SMI_DRIVER_DOWN)),
    "gpu memory unreadable": FakeSystem(smi=CommandResult(0, "NVIDIA Thing, [N/A], 535.1\n")),
    "unknown os": FakeSystem(os_release=None),
    "untested os": FakeSystem(os_release=UBUNTU_2004),
    "other distribution": FakeSystem(os_release=DEBIAN_12),
    "little memory": FakeSystem(meminfo=MEM_4G),
    "memory unreadable": FakeSystem(meminfo=None),
    "home on windows": wsl2(home="/mnt/c/Users/me"),
    "no desktop": FakeSystem(environ={}),
    "no desktop on wsl": wsl2(environ={"WSL_DISTRO_NAME": "Ubuntu"}, present={"/mnt/c"}),
    "no apt": FakeSystem(tools={}),
    "no sudo": FakeSystem(installed=["git"], tools={"apt-get": "/usr/bin/apt-get"}, failing_probes=("import",)),
}


def test_every_check_preflight_can_give_reads_as_a_sentence_with_nothing_left_unfilled():
    emitted = set()
    for name, system in SCENARIOS.items():
        for check in preflight.run_preflight(system).checks:
            emitted.add(check.key)
            sentence = ds.check_text(CAT, check)
            assert sentence and "{" not in sentence and not sentence.startswith("preflight."), (name, check.key, sentence)
            if not CAT.is_plural(check.key):
                CAT.strict(check.key, **check.args)                       # every placeholder the text asks for is supplied
    catalog_preflight = {k for k in catalog_keys() if k.startswith("preflight.") and not k.endswith(".detail")}
    assert catalog_preflight == emitted, ("never produced", sorted(catalog_preflight - emitted), "no words", sorted(emitted - catalog_preflight))


def test_the_reasons_for_each_program_and_each_download_read_as_plain_sentences():
    for req in preflight.REQUIREMENTS:
        assert ds.apt_reason(CAT, req) != req.why_key and not ds.apt_reason(CAT, req).endswith(".")
    for item in load_registry().items:
        assert ds.why_text(CAT, item) != item.why_key


def test_each_code_has_its_own_distinct_sentence():
    for codes, fn in ((scratch.REFUSAL_CODES, ds.refusal_text), (scratch.WARNING_CODES, ds.warning_text), (scratch.SPEED_CODES, ds.speed_text),
                      (project.CONSENT_PROBLEM_CODES, ds.consent_problem_text), (project.HOW_GIVEN, ds.how_given_text)):
        sentences = [fn(CAT, c) for c in codes]
        assert len(set(sentences)) == len(sentences) and not any("." + c in s or s == c for s, c in zip(sentences, codes))
    assert len({ds.status_text(CAT, s) for s in jobs.JobStatus}) == len(jobs.JobStatus)
    assert len({ds.level_text(CAT, l) for l in diskbudget.Level}) == 3 and len({ds.watch_text(CAT, w) for w in diskbudget.Watch}) == 3


def test_a_real_failure_reads_as_three_parts():
    err = fetch.FetchError("checksum")
    parts = ds.error_text(CAT, "fetch", err.code)
    assert parts.what.startswith("The file that arrived") and "deleted" in parts.changed and parts.next.startswith("Try again")
