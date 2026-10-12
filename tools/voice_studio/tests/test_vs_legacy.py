# SPDX-License-Identifier: GPL-3.0-or-later
"""Finding the manual setup (plan decision D13, task VS-1.5): it only looks, and it counts what is there."""
import os

from vs_fakes import FakeSystem
from voice_studio.core.legacy import MAX_DATASETS_LISTED, detect_legacy
from voice_studio.core.system import RealSystem

H = "/home/u"


def old_setup(**over):
    out = H + "/piper-recording-studio/output"
    dirs = {out, out + "/en-US", out + "/en-US/01_story", out + "/en-US/02_news", out + "/_freeform", out + "/_freeform/en-US", out + "/_freeform/en-US/takes",
            H + "/piper1-gpl", H + "/piper1-gpl/lightning_logs", H + "/piper", H + "/piper/my-dataset", H + "/piper/freeform-dataset-1", H + "/ack-tools"}
    listings = {out: ["en-US", "_freeform", "stray.txt"], out + "/en-US": ["01_story", "02_news", "notes.txt"], out + "/_freeform": ["en-US"],
                out + "/_freeform/en-US/takes": ["t1", "t2", "t3"], H + "/piper": ["my-dataset", "freeform-dataset-1", "file.txt"]}
    present = {H + "/piper1-gpl/.venv/bin/python", H + "/freeform-studio-venv/bin/python"}
    dirs |= over.pop("dirs", set())
    listings.update(over.pop("listings", {}))
    return FakeSystem(dirs=dirs, listings=listings, present=present | over.pop("present", set()), **over)


def test_nothing_found_on_a_clean_computer():
    found = detect_legacy(FakeSystem(), H)
    assert not found.any_found and not found.has_recordings and found.prompted_languages == () and found.datasets == ()


def test_the_old_setup_is_described_with_counts():
    found = detect_legacy(old_setup(), H)
    assert found.any_found and found.has_recordings
    assert found.recorder_output == H + "/piper-recording-studio/output" and found.prompted_languages == ("en-US",)
    assert found.prompted_groups == 2 and found.freeform_takes == 3
    assert found.trainer_repo == H + "/piper1-gpl" and found.trainer_env and found.trainer_runs and found.freeform_env
    assert found.piper_folder == H + "/piper" and found.datasets == ("freeform-dataset-1", "my-dataset") and found.tools_clone == H + "/ack-tools"


def test_underscore_folders_and_loose_files_are_not_languages_or_groups():
    found = detect_legacy(old_setup(), H)
    assert "_freeform" not in found.prompted_languages and found.prompted_groups == 2


def test_a_trainer_without_an_environment_or_runs_is_reported_as_such():
    system = FakeSystem(dirs={H + "/piper1-gpl"})
    found = detect_legacy(system, H)
    assert found.trainer_repo and not found.trainer_env and not found.trainer_runs and found.any_found and not found.has_recordings


def test_only_freeform_recordings_still_count_as_recordings():
    out = H + "/piper-recording-studio/output"
    system = FakeSystem(dirs={out, out + "/_freeform", out + "/_freeform/en-US"}, listings={out: ["_freeform"], out + "/_freeform": ["en-US"], out + "/_freeform/en-US/takes": ["a"]})
    found = detect_legacy(system, H)
    assert found.prompted_groups == 0 and found.freeform_takes == 1 and found.has_recordings


def test_unreadable_folders_count_as_empty_not_as_errors():
    system = FakeSystem(dirs={H + "/piper-recording-studio/output", H + "/piper"})
    found = detect_legacy(system, H)
    assert found.recorder_output and found.prompted_groups == 0 and found.freeform_takes == 0 and found.datasets == ()


def test_the_dataset_list_is_capped_and_sorted():
    names = ["d%02d" % i for i in range(30)][::-1]
    system = FakeSystem(dirs={H + "/piper"} | {H + "/piper/" + n for n in names}, listings={H + "/piper": names})
    assert detect_legacy(system, H).datasets == tuple(sorted(names)[:MAX_DATASETS_LISTED])


def test_a_trailing_slash_on_the_home_folder_makes_no_difference():
    assert detect_legacy(old_setup(), H + "/") == detect_legacy(old_setup(), H)


def test_looking_changes_nothing_on_a_real_disk(tmp_path):
    out = tmp_path / "piper-recording-studio" / "output" / "en-US" / "01_story"
    out.mkdir(parents=True)
    (out / "0.wav").write_bytes(b"audio")
    (tmp_path / "piper1-gpl" / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / "piper1-gpl" / ".venv" / "bin" / "python").write_text("")

    def snapshot():
        return sorted((os.path.relpath(os.path.join(d, n), tmp_path), os.stat(os.path.join(d, n)).st_mtime_ns) for d, dirs, files in os.walk(tmp_path) for n in dirs + files)
    before = snapshot()
    found = detect_legacy(RealSystem(), str(tmp_path))
    assert found.prompted_groups == 1 and found.trainer_env and snapshot() == before
