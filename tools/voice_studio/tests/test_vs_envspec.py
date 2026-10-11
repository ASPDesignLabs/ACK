# SPDX-License-Identifier: GPL-3.0-or-later
"""The list of environments (plan task VS-1.9) and the rules a lock file must meet: pinned, checksummed, and nothing that could fetch from elsewhere."""
import copy
import json

import pytest

from voice_studio.core import envspec as es
from voice_studio.core.registry import Item, Registry, load_registry

H1, H2 = "a" * 64, "b" * 64
GOOD_LOCK = "# made on a real machine\nnumpy==1.26.4 \\\n    --hash=sha256:%s \\\n    --hash=sha256:%s\nQuart==0.20.0 --hash=sha256:%s\n" % (H1, H2, H1)

GOOD = {
    "id": "demo", "why_key": "env.why.demo", "python_min": [3, 10], "approx_size_bytes": 1000,
    "lock": {"filename": "demo.lock.txt", "sha256": None},
    "source": {"item_id": "demo-source", "install": True, "dist": "demo-dist", "native_build": "build.sh", "native_artifact": "src/core*.so"},
    "prelude": ["import os"], "patches": [{"id": "fix-it", "file": "src/a.py", "old": "x", "new": "y"}],
    "probes": [{"id": "imports", "code": "import os", "needs_gpu": False}],
}


def doc(*envs):
    return json.dumps({"schema": 1, "environments": list(envs)})


def parse_one(**changes):
    raw = copy.deepcopy(GOOD)
    raw.update(changes)
    return es.parse_environments(doc(raw))[0]


# ---------------------------------------------------------------- the lock file

def test_a_good_lock_is_read_into_pins_with_their_checksums():
    pins, problems = es.parse_lock(GOOD_LOCK)
    assert problems == []
    assert [(p.name, p.version, p.hashes) for p in pins] == [("numpy", "1.26.4", (H1, H2)), ("quart", "0.20.0", (H1,))]


def test_names_are_compared_the_way_python_compares_them():
    assert es.normalise_name("Typing_Extensions") == es.normalise_name("typing-extensions") == "typing-extensions"
    assert es.normalise_name("zope.interface") == "zope-interface" and es.normalise_name("A__B..C") == "a-b-c"


@pytest.mark.parametrize("line, fragment", [
    ("numpy>=1.26 --hash=sha256:%s" % H1, "not a pinned"),
    ("numpy~=1.26 --hash=sha256:%s" % H1, "not a pinned"),
    ("numpy==1.* --hash=sha256:%s" % H1, "not a pinned"),
    ("numpy --hash=sha256:%s" % H1, "not a pinned"),
    ("numpy==1.26.4", "no checksum"),
    ("numpy==1.26.4 --hash=sha256:short", "option --hash"),
    ("numpy==1.26.4 --hash=md5:%s" % ("a" * 32), "option --hash"),
    ("numpy==1.26.4 --hash=sha256:%s" % ("G" * 64), "option --hash"),
    ("-e .", "not a pinned"),
    ("--index-url x", "option --index-url"),
    ("--extra-index-url x", "option --extra-index-url"),
    ("--find-links x", "option --find-links"),
    ("--trusted-host x", "option --trusted-host"),
    ("-r other.txt", "not a pinned"),
    ("numpy @ file:///tmp/numpy.whl --hash=sha256:%s" % H1, "not a pinned"),
    ("git+file:///tmp/x#egg=x --hash=sha256:%s" % H1, "not a pinned"),
    ("./local.whl --hash=sha256:%s" % H1, "not a pinned"),
])
def test_anything_that_could_fetch_from_elsewhere_or_float_is_a_problem(line, fragment):
    pins, problems = es.parse_lock(line + "\n")
    assert pins == [] and any(fragment in p for p in problems), problems


def test_a_marker_after_the_version_is_allowed_and_the_same_name_twice_is_not():
    text = 'numpy==1.26.4 ; python_version < "3.12" --hash=sha256:%s\nnumpy==2.0.0 ; python_version >= "3.12" --hash=sha256:%s\n' % (H1, H2)
    pins, problems = es.parse_lock(text)
    assert problems == [] and [p.version for p in pins] == ["1.26.4", "2.0.0"]
    assert [p.marker for p in pins] == ['python_version < "3.12"', 'python_version >= "3.12"']
    pins, problems = es.parse_lock("numpy==1.0 --hash=sha256:%s\nNumPy==1.0 --hash=sha256:%s\n" % (H1, H2))
    assert len(pins) == 1 and any("listed twice" in p for p in problems)


def test_comments_blank_lines_and_inline_comments_are_ignored_and_line_numbers_point_at_the_start_of_the_entry():
    text = "# top\n\nnumpy==1.0 --hash=sha256:%s # why\n   # indented comment\ntorch>=2 \\\n   --hash=sha256:%s\n" % (H1, H1)
    pins, problems = es.parse_lock(text)
    assert [p.name for p in pins] == ["numpy"] and problems == ["line 5: not a pinned name==version"]


def test_an_empty_lock_is_a_problem_not_a_success():
    for text in ("", "# only a comment\n", "\n\n"):
        assert es.parse_lock(text) == ([], ["the lock lists nothing"])


def test_a_lock_ending_in_a_continuation_is_still_read():
    pins, problems = es.parse_lock("numpy==1.0 --hash=sha256:%s \\" % H1)
    assert problems == [] and len(pins) == 1


def test_the_lock_checksum_is_of_the_exact_bytes():
    assert es.lock_digest(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


# ---------------------------------------------------------------- the list of environments

def test_a_good_entry_is_read_completely():
    spec = parse_one()
    assert (spec.id, spec.python_min, spec.approx_size_bytes, spec.lock_filename, spec.lock_sha256) == ("demo", (3, 10), 1000, "demo.lock.txt", None)
    assert spec.source == es.SourceUse("demo-source", True, "demo-dist", "build.sh", "src/core*.so")
    assert spec.prelude == ("import os",) and spec.patches == (es.SourcePatch("fix-it", "src/a.py", "x", "y"),)
    assert spec.probes == (es.Probe("imports", "import os", False),)


GOOD_NATIVE = {"file": "core_part.pyx", "sha256": H1, "module": "core", "into": "pkg/sub"}


def test_a_native_part_is_read_completely_and_is_optional():
    assert parse_one().native is None
    native = parse_one(native=GOOD_NATIVE, source=None, patches=[]).native
    assert native == es.NativePart("core_part.pyx", H1, "core", "pkg/sub")
    assert native.artifact == "core.*so" and native.path == es.NATIVE_DIR / "core_part.pyx"
    assert parse_one(native={**GOOD_NATIVE, "file": "x" * 80 + ".pyx"}, source=None, patches=[]).native.file == "x" * 80 + ".pyx", "the longest name allowed"
    assert parse_one(native={**GOOD_NATIVE, "module": "m" * 40}, source=None, patches=[]).native.module == "m" * 40


def test_a_native_part_may_sit_beside_a_source_but_not_beside_the_sources_own_native_build():
    assert parse_one(native=GOOD_NATIVE, source={"item_id": "demo-source", "install": True, "dist": "demo-dist"}).native is not None
    with pytest.raises(es.EnvSpecError, match="two ways of the same step"):
        parse_one(native=GOOD_NATIVE)                                  # GOOD's source has a native build of its own


@pytest.mark.parametrize("change, fragment", [
    ({"file": "../x.pyx"}, "plain .pyx file name"), ({"file": "x.py"}, "plain .pyx file name"), ({"file": "a/b.pyx"}, "plain .pyx file name"),
    ({"file": ".pyx"}, "plain .pyx file name"), ({"file": "x.pyx.sh"}, "plain .pyx file name"), ({"file": "x.pyxz"}, "plain .pyx file name"), ({"file": 5}, "plain .pyx file name"), ({"file": ""}, "plain .pyx file name"), ({"file": "x" * 81 + ".pyx"}, "plain .pyx file name"),
    ({"sha256": None}, "not a checksum"), ({"sha256": "abc"}, "not a checksum"), ({"sha256": "A" * 64}, "not a checksum"), ({"sha256": 7}, "not a checksum"),
    ({"module": "a-b"}, "plain module name"), ({"module": "1x"}, "plain module name"), ({"module": ""}, "plain module name"), ({"module": "a.b"}, "plain module name"),
    ({"module": "m" * 41}, "plain module name"), ({"module": None}, "plain module name"),
    ({"into": "../x"}, "safe relative path"), ({"into": "/abs"}, "safe relative path"), ({"into": "a/../b"}, "safe relative path"), ({"into": None}, "safe relative path"),
    ({"into": "a/*"}, "plain folder"), ({"into": ".hidden/x"}, "plain folder"), ({"into": "a/b/"}, "plain folder"),
])
def test_a_native_part_with_anything_unsafe_is_refused(change, fragment):
    with pytest.raises(es.EnvSpecError, match=fragment):
        parse_one(native={**GOOD_NATIVE, **change}, source=None, patches=[])


@pytest.mark.parametrize("value", ["x", 5, ["a"], True])
def test_a_native_part_that_is_not_an_object_is_refused(value):
    with pytest.raises(es.EnvSpecError, match="native is not an object"):
        parse_one(native=value, source=None, patches=[])


def test_the_newest_python_is_optional_and_may_equal_the_oldest():
    assert parse_one().python_max is None
    assert parse_one(python_max=[3, 12]).python_max == (3, 12)
    assert parse_one(python_max=[3, 10]).python_max == (3, 10)


def test_an_entry_with_no_source_is_allowed():
    raw = copy.deepcopy(GOOD)
    raw["source"], raw["patches"] = None, []
    assert es.parse_environments(doc(raw))[0].source is None


BAD = [
    ("id", "Not A Slug", "bad or repeated id"), ("id", "", "bad or repeated id"), ("why_key", None, "why_key"),
    ("python_min", [3], "python_min"), ("python_min", [3, "10"], "python_min"), ("python_min", [True, 10], "python_min"), ("python_min", "3.10", "python_min"),
    ("python_max", [3], "python_max must be"), ("python_max", [3, "12"], "python_max must be"), ("python_max", [True, 12], "python_max must be"),
    ("python_max", "3.12", "python_max must be"), ("python_max", [3, 100], "python_max must be"), ("python_max", [3, 9], "python_max is older than python_min"),
    ("approx_size_bytes", 0, "out of range"), ("approx_size_bytes", -5, "out of range"), ("approx_size_bytes", True, "approx_size_bytes"),
    ("approx_size_bytes", 2**41, "out of range"),
    ("lock", {"filename": "../x.txt", "sha256": None}, "unsafe lock file name"), ("lock", {"filename": "/etc/x.txt", "sha256": None}, "unsafe lock file name"),
    ("lock", {"filename": "x.lock.txt", "sha256": "abc"}, "bad lock checksum"), ("lock", {"filename": "x.lock.txt", "sha256": "A" * 64}, "bad lock checksum"),
    ("lock", {"filename": "x.sh", "sha256": None}, "unsafe lock file name"), ("lock", None, "lock"),
    ("prelude", "import os", "prelude"), ("prelude", ["a\nb"], "prelude"), ("prelude", [""], "prelude"), ("prelude", ["x" * 301], "prelude"),
    ("prelude", ["import os"] * 21, "prelude"), ("prelude", ["def ("], "not valid Python"),
    ("probes", [], "no self-test"), ("probes", [{"id": "a", "code": "def ("}], "not valid Python"),
    ("probes", [{"id": "a b", "code": "pass"}], "bad or repeated probe id"),
    ("probes", [{"id": "a", "code": "pass"}, {"id": "a", "code": "pass"}], "bad or repeated probe id"),
    ("patches", [{"id": "p", "file": "../x", "old": "a", "new": "b"}], "safe relative path"),
    ("patches", [{"id": "p", "file": "/x", "old": "a", "new": "b"}], "safe relative path"),
    ("patches", [{"id": "p", "file": "a/../../x", "old": "a", "new": "b"}], "safe relative path"),
    ("patches", [{"id": "p", "file": "x", "old": "", "new": "b"}], "changes nothing"),
    ("patches", [{"id": "p", "file": "x", "old": "a", "new": "a"}], "changes nothing"),
    ("patches", [{"id": "p", "file": "x", "old": "a", "new": "b"}, {"id": "p", "file": "y", "old": "a", "new": "b"}], "bad or repeated patch id"),
    ("source", {"item_id": "Bad Id"}, "bad source id"), ("source", {"item_id": "x", "native_build": "b.sh"}, "native build needs an artifact"),
    ("source", {"item_id": "x", "native_artifact": "a*.so"}, "native build needs an artifact"),
    ("source", {"item_id": "x", "native_build": "../b.sh", "native_artifact": "a"}, "safe relative path"),
    ("source", {"item_id": "x", "dist": "bad dist!"}, "bad distribution name"), ("source", "x", "source is not an object"),
]


@pytest.mark.parametrize("key, value, fragment", BAD, ids=["%s=%s" % (k, str(v)[:30]) for k, v, _ in BAD])
def test_a_wrong_entry_is_refused_with_the_reason(key, value, fragment):
    raw = copy.deepcopy(GOOD)
    raw[key] = value
    with pytest.raises(es.EnvSpecError) as caught:
        es.parse_environments(doc(raw))
    assert fragment in str(caught.value)


def test_patches_without_a_source_are_refused():
    raw = copy.deepcopy(GOOD)
    raw["source"] = None
    with pytest.raises(es.EnvSpecError, match="patches need a source"):
        es.parse_environments(doc(raw))


def test_two_entries_with_the_same_id_and_a_wrong_document_are_refused():
    with pytest.raises(es.EnvSpecError, match="repeated"):
        es.parse_environments(doc(GOOD, GOOD))
    for text in ("not json", "[]", json.dumps({"schema": 2, "environments": []}), json.dumps({"schema": 1}), json.dumps({"schema": 1, "environments": ["x"]})):
        with pytest.raises(es.EnvSpecError):
            es.parse_environments(text)


def test_a_file_that_cannot_be_read_is_a_plain_error(tmp_path):
    with pytest.raises(es.EnvSpecError, match="cannot read"):
        es.load_environments(tmp_path / "missing.json")


# ---------------------------------------------------------------- can it be built yet

def registry_with(pinned):
    base = dict(id="demo-source", kind="source", why_key="fetch.why.x", license_id="l", approx_size_bytes=5)
    if pinned:
        base.update(url="https://github.com/o/r/archive/abc123.tar.gz", filename="r-abc123.tar.gz", revision="abc123", size_bytes=10, sha256=H1)
    return Registry((Item(**base),))


def test_an_environment_is_buildable_only_with_a_checksummed_lock_and_a_pinned_source():
    spec = parse_one()
    assert spec.pin_problems() == ["lock_unpinned"]
    assert spec.pin_problems(registry_with(False)) == ["lock_unpinned", "source_unpinned"]
    pinned = parse_one(lock={"filename": "demo.lock.txt", "sha256": H1})
    assert pinned.pin_problems() == [] and pinned.pin_problems(registry_with(True)) == []
    assert pinned.pin_problems(registry_with(False)) == ["source_unpinned"]
    assert pinned.pin_problems(Registry(())) == ["source_unknown"]


def test_an_environment_without_a_source_needs_only_its_lock():
    raw = copy.deepcopy(GOOD)
    raw["source"], raw["patches"] = None, []
    raw["lock"]["sha256"] = H1
    spec = es.parse_environments(doc(raw))[0]
    assert spec.pin_problems(Registry(())) == []


# ---------------------------------------------------------------- the shipped list

SHIPPED = es.load_environments()


def test_the_shipped_list_has_the_two_environments_and_each_names_a_registered_source():
    assert [s.id for s in SHIPPED] == ["training", "studio"]
    registry = load_registry()
    for spec in SHIPPED:
        if spec.source is not None:
            assert registry.get(spec.source.item_id).kind == "source"


def test_a_shipped_lock_that_is_pinned_exists_matches_its_checksum_and_passes_the_rules():
    for spec in SHIPPED:
        if spec.lock_sha256 is None:
            continue
        data = spec.lock_path.read_bytes()
        assert es.lock_digest(data) == spec.lock_sha256, spec.id
        assert es.parse_lock(data.decode("utf-8"))[1] == [], spec.id


def test_every_shipped_lock_file_is_listed_and_the_names_are_unique():
    names = [s.lock_filename for s in SHIPPED]
    assert len(names) == len(set(names))
    on_disk = {p.name for p in es.LOCKS_DIR.glob("*.txt")}
    assert on_disk <= set(names), "a lock file nothing lists: %s" % (on_disk - set(names))


TRAINING_LOCK = next(s for s in SHIPPED if s.id == "training")


def test_the_shipped_training_lock_is_pinned_and_covers_the_trainer_stack_as_a_published_wheel():
    """Plan VS-0.2: the builder installs with --no-deps, so a package missing here is missing in the environment. The trainer is the published
    piper-tts wheel (it carries the compiled espeak-ng part, so nothing is built from source and nothing is cloned); the compile tools that
    only the from-source route needed are gone, and Cython and setuptools (held below 82, as the guide says) are there for the one compile step."""
    assert TRAINING_LOCK.lock_sha256 is not None
    pins, problems = es.parse_lock(TRAINING_LOCK.lock_path.read_text(encoding="utf-8"))
    assert problems == []
    by_name = {p.name: p for p in pins}
    needed = ("piper-tts", "setuptools", "cython", "torch", "lightning", "pytorch-lightning", "tensorboard", "tensorboardx",
              "jsonargparse", "docstring-parser", "typeshed-client", "onnx", "onnxruntime", "pysilero-vad", "librosa", "numpy", "pathvalidate", "numba", "soxr",
              "nvidia-cudnn-cu13", "triton")
    assert [n for n in needed if n not in by_name] == []
    assert by_name["piper-tts"].version == "1.8.0" and len(by_name["piper-tts"].hashes) == 1, "one wheel: the cp39-abi3 build serves every Python the lock covers"
    assert int(by_name["setuptools"].version.split(".")[0]) < 82
    assert [n for n in ("cmake", "ninja", "scikit-build", "wheel", "distro") if n in by_name] == [], "build tools only the from-source route needed"
    assert all(p.marker == "" and p.hashes for p in pins)


def test_the_shipped_training_lock_holds_wheels_for_every_python_the_entry_allows_and_none_the_entry_refuses():
    """The lock's header says which Pythons its checksums are for; the entry's python_min / python_max must say the same, or a Python is allowed
    that pip cannot install for (a confusing hash error) or refused that would work."""
    header = [l for l in TRAINING_LOCK.lock_path.read_text(encoding="utf-8").splitlines() if l.startswith("# Python versions covered")]
    assert header == ["# Python versions covered: 3.10, 3.11, 3.12. Linux x86_64 wheels only; Python 3.13 and newer are not covered."]
    assert TRAINING_LOCK.python_min == (3, 10) and TRAINING_LOCK.python_max == (3, 12)


def test_the_shipped_native_part_is_the_alignment_source_the_published_trainer_expects():
    """The published wheel imports `.monotonic_align.core` and ships neither a compiled copy nor the source. The shipped file must be byte for byte
    the one that was checked (the developer's clone of the pinned commit: 1148 bytes), and it must land where that import looks."""
    native = TRAINING_LOCK.native
    data = native.path.read_bytes()
    assert es.lock_digest(data) == native.sha256 == "8640b303683823a4a1259179547ef476999b1cbb2e46ff656b970763cfbc1157" and len(data) == 1148
    assert b"cpdef void maximum_path_c(" in data and b"def " not in data.replace(b"cpdef", b"").replace(b"cdef", b""), "the one function the trainer imports"
    assert native.module == "core" and native.artifact == "core.*so"
    assert native.into == "piper/train/vits/monotonic_align/monotonic_align", "the folder the wheel's alignment package imports its compiled core from"


def test_every_file_in_the_native_folder_is_listed_by_an_environment_and_nothing_else_is_there():
    listed = {s.native.file for s in SHIPPED if s.native is not None}
    on_disk = {p.name for p in es.NATIVE_DIR.iterdir()}
    assert on_disk == listed, "a file nothing builds, or a listed file that is missing: %s" % (on_disk ^ listed)


def test_the_shipped_trainer_workarounds_are_the_guides_and_are_one_line_each():
    training = next(s for s in SHIPPED if s.id == "training")
    joined = "\n".join(training.prelude)
    assert "PosixPath" in joined and "dynamo=False" in joined and "val_mos" in joined
    assert training.source is None and training.native is not None, "no source archive: the trainer is the published wheel"
    assert training.python_min == (3, 10)


# ---------------------------------------------------------------- the launcher's workaround for the trainer's quality-score checkpoint

import sys
import types


def run_val_mos_workaround(monkeypatch):
    """Run the shipped launcher line against a stand-in for the checkpoint class, and hand back that class and the calls its real method got."""
    calls = []

    class ModelCheckpoint:
        def __init__(self, monitor):
            self.monitor = monitor

        def _save_topk_checkpoint(self, trainer, found):
            calls.append((self.monitor, trainer, sorted(found)))
            if self.monitor not in found:
                raise RuntimeError("could not find the monitored key")
            return "saved"

    callbacks = types.ModuleType("lightning.pytorch.callbacks")
    callbacks.ModelCheckpoint = ModelCheckpoint
    pytorch = types.ModuleType("lightning.pytorch")
    pytorch.callbacks = callbacks
    lightning = types.ModuleType("lightning")
    lightning.pytorch = pytorch
    for name, module in (("lightning", lightning), ("lightning.pytorch", pytorch), ("lightning.pytorch.callbacks", callbacks)):
        monkeypatch.setitem(sys.modules, name, module)
    line = next(l for l in TRAINING_LOCK.prelude if "val_mos" in l)
    exec(compile(line, "<prelude>", "exec"), {})
    return ModelCheckpoint, calls


def test_a_quality_score_that_was_never_logged_is_skipped_quietly_instead_of_stopping_the_round(monkeypatch):
    checkpoint, calls = run_val_mos_workaround(monkeypatch)
    assert checkpoint("val_mos")._save_topk_checkpoint("T", {"val_mel": 0.6, "epoch": 1}) is None and calls == []


def test_a_quality_score_that_was_logged_is_saved_as_before(monkeypatch):
    checkpoint, calls = run_val_mos_workaround(monkeypatch)
    assert checkpoint("val_mos")._save_topk_checkpoint("T", {"val_mos": 3.9, "val_mel": 0.6}) == "saved" and calls == [("val_mos", "T", ["val_mel", "val_mos"])]


def test_any_other_missing_key_still_stops_the_round_because_that_is_a_real_mistake(monkeypatch):
    checkpoint, calls = run_val_mos_workaround(monkeypatch)
    with pytest.raises(RuntimeError, match="monitored key"):
        checkpoint("val_mel")._save_topk_checkpoint("T", {"val_mos": 3.9})
    assert checkpoint("val_mel")._save_topk_checkpoint("T", {"val_mel": 0.6}) == "saved" and len(calls) == 2


def test_the_workaround_names_exactly_the_one_key_and_leaves_the_rest_of_the_launcher_line_alone(monkeypatch):
    line = next(l for l in TRAINING_LOCK.prelude if "val_mos" in l)
    assert line.count("val_mos") == 2 and "ModelCheckpoint._save_topk_checkpoint" in line and len(line) <= es.MAX_LINE
