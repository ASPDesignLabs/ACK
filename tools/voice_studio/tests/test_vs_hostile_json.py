# SPDX-License-Identifier: GPL-3.0-or-later
"""A file nested far too deep is damaged, like any other damaged file: a plain answer from the reader, never a traceback.

Python's JSON reader gives up with RecursionError, not ValueError, on a document nested a few hundred thousand levels deep. Every reader that takes a file
from outside (a voice's settings, a marker found on another drive) or a file a person may have touched (a project, the consent record, a job's notes) must
treat that as it treats a file that is not JSON at all.
"""
import pytest

from voice_studio.core import consent, jobs, project, scratch, voicezip

DEEP = "[" * 200_000
DEEP_OBJECT = '{"schema": 1, "project": ' + "[" * 200_000


def test_the_deep_document_really_does_defeat_the_json_reader():
    import json
    with pytest.raises(RecursionError):
        json.loads(DEEP)


def test_a_voices_settings_file_nested_too_deep_is_not_json_it_is_refused_in_words(tmp_path):
    assert len(DEEP) <= voicezip.MAX_CONFIG_BYTES
    assert voicezip._config_problems(DEEP.encode()) == (["config_not_json"], None)
    assert voicezip._config_problems(b'{"audio": ' + DEEP.encode()) == (["config_not_json"], None)


def test_a_project_file_nested_too_deep_is_damaged_not_a_crash():
    for text in (DEEP, DEEP_OBJECT):
        with pytest.raises(project.ProjectError) as caught:
            project.project_from_text(text)
        assert caught.value.code == "damaged"


def test_a_marker_on_a_drive_nested_too_deep_is_damaged():
    assert scratch.check_marker(DEEP, "anna") is scratch.MarkerState.DAMAGED
    assert scratch.check_marker(DEEP_OBJECT, "anna") is scratch.MarkerState.DAMAGED


def test_a_consent_record_nested_too_deep_means_nothing_is_consented_to(tmp_path):
    path = tmp_path / "consent.json"
    path.write_text(DEEP_OBJECT)
    assert consent.load_consent(path) is None


def test_a_jobs_notes_nested_too_deep_read_as_missing(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(DEEP_OBJECT)
    assert jobs.read_json(str(path)) is None
