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


def test_an_entry_with_no_source_is_allowed():
    raw = copy.deepcopy(GOOD)
    raw["source"], raw["patches"] = None, []
    assert es.parse_environments(doc(raw))[0].source is None


BAD = [
    ("id", "Not A Slug", "bad or repeated id"), ("id", "", "bad or repeated id"), ("why_key", None, "why_key"),
    ("python_min", [3], "python_min"), ("python_min", [3, "10"], "python_min"), ("python_min", [True, 10], "python_min"), ("python_min", "3.10", "python_min"),
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


def test_the_shipped_trainer_workarounds_are_the_guides_and_are_one_line_each():
    training = next(s for s in SHIPPED if s.id == "training")
    joined = "\n".join(training.prelude)
    assert "PosixPath" in joined and "dynamo=False" in joined
    assert training.source.native_build == "build_monotonic_align.sh" and training.source.install
    assert training.python_min == (3, 10)
