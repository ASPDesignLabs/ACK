# SPDX-License-Identifier: GPL-3.0-or-later
"""Carrying on when the connection drops (core/connection.py): telling a drop from a real failure, and how long to wait.

The transcripts in tests/data/pip_transcripts are what pip 22.0.2 and 24.0 really printed against a local server that refused, reset, stalled,
cut a download in half and presented an untrusted certificate. The classifier is held to those, not to what anyone remembers pip saying.
"""
from pathlib import Path

import pytest

from voice_studio.core import connection as cn

DATA = Path(__file__).parent / "data" / "pip_transcripts"


def transcript(name):
    return (DATA / (name + ".txt")).read_text(encoding="utf-8")


# ---------------------------------------------------------------- what a failed pip was about

def test_a_connection_that_could_not_be_made_is_a_drop():
    assert cn.classify_pip(transcript("connection_refused")) == cn.PipOutcome("lost")


def test_a_connection_reset_in_the_middle_of_a_file_is_a_drop():
    assert cn.classify_pip(transcript("reset_during_download")) == cn.PipOutcome("lost")


def test_a_connection_that_goes_quiet_in_the_middle_of_a_file_is_a_drop():
    assert cn.classify_pip(transcript("stalled_download")) == cn.PipOutcome("lost")


def test_a_download_cut_in_half_looks_like_a_mismatch_and_carries_what_came_out():
    outcome = cn.classify_pip(transcript("cut_download_pip22"))
    assert outcome.kind == "mismatch"
    assert outcome.signature == ("1d62f08f0e846718c190ca0d89834db74887cef0b7400c5e8b5d239c5e5eb69e",)


@pytest.mark.parametrize("name", ["cut_download_pip26", "reset_download_pip26", "stalled_download_pip26"])
def test_the_newer_pip_names_an_interrupted_download_and_it_is_a_drop(name):
    text = transcript(name)
    assert "incomplete-download" in text and "Retrying" not in text and "HASHES" not in text          # none of the older signs is there
    assert cn.classify_pip(text) == cn.PipOutcome("lost")


def test_an_untrusted_certificate_is_never_waited_for_though_pip_prints_the_same_retry_lines():
    text = transcript("certificate_not_trusted")
    assert "Retrying (Retry(" in text                       # the trap: this alone would say "dropped connection"
    assert cn.classify_pip(text) == cn.PipOutcome("other")


def test_a_missing_package_with_no_sign_of_trouble_on_the_way_is_a_real_failure():
    assert cn.classify_pip("Collecting x==1.0\nERROR: Could not find a version that satisfies the requirement x==1.0 (from versions: none)\n"
                           "ERROR: No matching distribution found for x==1.0\n") == cn.PipOutcome("other")


@pytest.mark.parametrize("line", ["OSError: [Errno 28] No space left on device", "ERROR: Disk quota exceeded", "OSError: [Errno 30] Read-only file system: 'x'",
                                  "PermissionError: [Errno 13] Permission denied: 'x'", "ERROR: 404 Client Error: Not Found for url: https://x/y.whl",
                                  "ERROR: 403 Client Error: Forbidden for url: https://x/y.whl", "ERROR: 401 Client Error: Unauthorized for url: https://x",
                                  "ProxyError: 407 Proxy Authentication Required", "ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: x",
                                  "Could not fetch URL https://x: There was a problem confirming the ssl certificate: x", "ERROR: In --require-hashes mode, all requirements must have their versions pinned",
                                  "ERROR: x.whl is not a supported wheel on this platform."])
def test_failures_that_waiting_cannot_fix_are_not_drops_even_after_a_retry_line(line):
    text = "WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'X'\n" + line + "\n"
    assert cn.classify_pip(text) == cn.PipOutcome("other")


@pytest.mark.parametrize("line", ["WARNING: Retrying (Retry(total=4)) after connection broken by 'NewConnectionError'", "OSError: Failed to establish a new connection",
                                  "HTTPSConnectionPool(host='x', port=443): Max retries exceeded with url: /y", "ProtocolError: ('Connection broken: x', x)",
                                  "ConnectionResetError: [Errno 104] Connection reset by peer", "ConnectionError: ('Connection aborted.', x)",
                                  "http.client.RemoteDisconnected: Remote end closed connection without response", "ReadTimeoutError: x: Read timed out.",
                                  "socket.timeout: The read operation timed out", "urllib3.exceptions.ProtocolError: x", "requests.exceptions.ChunkedEncodingError: x",
                                  "IncompleteRead(5 bytes read, 9 more expected)", "WARNING: Connection interrupted while downloading.", "error: incomplete-download",
                                  "note: This is an issue with network connectivity, not pip.", "Temporary failure in name resolution", "Name or service not known",
                                  "OSError: [Errno 101] Network is unreachable", "OSError: [Errno 113] No route to host",
                                  "WARNING: Retrying (Retry(total=4)) after something else", "an HTTP library said: Connection broken: x"])
def test_every_known_sign_of_a_dropped_connection_is_one(line):
    assert cn.classify_pip("Collecting x\n" + line + "\nERROR: Exception:\n").kind == "lost"


def test_markers_are_found_whatever_the_capitals():
    assert cn.classify_pip("READ TIMED OUT").kind == "lost"
    assert cn.classify_pip("THESE PACKAGES DO NOT MATCH THE HASHES").kind == "mismatch"


def test_only_the_end_of_the_output_counts_so_an_old_retry_line_does_not_hide_a_real_failure():
    old = "WARNING: Retrying (Retry(total=4)) after connection broken by 'x'\n"
    quiet = "".join("Collecting package-%d\n" % i for i in range(cn.WINDOW_LINES))        # a retry that happened, then plenty of ordinary progress
    assert cn.classify_pip(old + quiet + "ERROR: some other thing\n").kind == "other"
    assert cn.classify_pip(old + quiet[: -len("Collecting package-0\n")] + "ERROR: some other thing\n").kind == "other"    # window-1 lines of progress...
    nearer = old + "".join("Collecting package-%d\n" % i for i in range(cn.WINDOW_LINES - 2)) + "ERROR: some other thing\n"
    assert cn.classify_pip(nearer).kind == "lost"                                         # ...but the retry line is still inside the window here


def test_the_window_edge_is_exact_and_eighty_lines_deep_which_a_whole_traceback_fits_in():
    marker = "Read timed out.\n"
    assert cn.WINDOW_LINES == 80
    inside = marker + "x\n" * 79                      # the marker is the 80th line from the end
    outside = marker + "x\n" * 80                     # and now the 81st
    assert cn.classify_pip(inside).kind == "lost" and cn.classify_pip(outside).kind == "other"
    traceback_and_before = "WARNING: Retrying (Retry(total=0)) after x\n" + "  File \"x.py\", line 1, in f\n" * 70 + "ValueError: something unrelated\n"
    assert cn.classify_pip(traceback_and_before).kind == "lost"          # a long traceback still has the retry lines in reach


def test_a_mismatch_beats_a_retry_line_in_the_same_output():
    text = "WARNING: Retrying (Retry(total=4)) after connection broken by 'x'\nERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE.\n" \
           "    Expected sha256 " + "a" * 64 + "\n         Got        " + "b" * 64 + "\n"
    assert cn.classify_pip(text) == cn.PipOutcome("mismatch", ("b" * 64,))


def test_a_mismatch_signature_is_every_wrong_file_sorted_and_lower_case():
    text = "THESE PACKAGES DO NOT MATCH THE HASHES\n  Got        " + "D" * 64 + "\n  Got        " + "c" * 64 + "\n"
    assert cn.classify_pip(text).signature == ("c" * 64, "d" * 64)


def test_a_mismatch_with_no_readable_hash_still_has_a_signature_so_it_cannot_loop_for_half_an_hour():
    assert cn.classify_pip("THESE PACKAGES DO NOT MATCH THE HASHES\n").signature == ("unreadable",)
    assert cn.classify_pip("THESE PACKAGES DO NOT MATCH THE HASHES\n  Got        short\n").signature == ("unreadable",)


def test_only_a_whole_sixty_four_digit_hash_counts():
    assert cn.classify_pip("THESE PACKAGES DO NOT MATCH THE HASHES\n  Got        " + "e" * 63 + "\n").signature == ("unreadable",)
    assert cn.classify_pip("THESE PACKAGES DO NOT MATCH THE HASHES\n  Got        " + "e" * 65 + "\n").signature == ("unreadable",)


def test_nothing_at_all_is_not_a_drop():
    assert cn.classify_pip("") == cn.PipOutcome("other")


# ---------------------------------------------------------------- a failed download of a registry file

@pytest.mark.parametrize("code, detail, lost", [
    ("size", "got 5 of 9 bytes", True), ("http", "URLError", True), ("http", "TimeoutError", True), ("http", "IncompleteRead", True),
    ("http", "429", True), ("http", "500", True), ("http", "503", True), ("http", "599", True),
    ("http", "404", False), ("http", "403", False), ("http", "401", False), ("http", "416", False), ("http", "499", False), ("http", "600", False),
    ("checksum", "", False), ("disk", "No space left", False), ("room", "9 bytes needed", False), ("consent", "x", False), ("cancelled", "", False),
    ("not_pinned", "", False), ("unsafe_name", "", False),
])
def test_which_failed_downloads_are_the_connection(code, detail, lost):
    assert cn.fetch_lost(code, detail) is lost


# ---------------------------------------------------------------- how long to wait

def test_the_waits_grow_and_the_last_one_repeats():
    patience = cn.Patience()
    assert [patience.pause(n) for n in range(8)] == [5, 10, 20, 30, 60, 60, 60, 60]


def test_the_defaults_are_thirty_minutes_and_a_minute_of_progress():
    assert (cn.DEFAULT_PATIENCE.total_s, cn.DEFAULT_PATIENCE.progress_s) == (1800, 60)


class Clock:
    """A clock that only moves when something sleeps or an attempt takes time."""

    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def take(self, seconds):
        self.now += seconds


def run(script, patience=cn.DEFAULT_PATIENCE, clock=None):
    """`script` is a list of: an Exception to raise, a number of seconds the attempt takes before failing as ConnectionLost, or the string "ok"."""
    clock = clock or Clock()
    waits, backs = [], []
    steps = list(script)

    def attempt():
        step = steps.pop(0)
        if isinstance(step, Exception):
            raise step
        if step == "ok":
            return "done"
        clock.take(step)
        raise cn.ConnectionLost("lost")

    try:
        value = cn.keep_trying(attempt, on_wait=waits.append, on_back=lambda: backs.append(clock.now), sleep=clock.sleep, clock=clock, patience=patience)
    except Exception as error:
        return error, waits, backs, clock, steps
    return value, waits, backs, clock, steps


def test_a_first_try_that_works_says_nothing_and_waits_for_nothing():
    value, waits, backs, clock, _ = run(["ok"])
    assert (value, waits, backs, clock.slept) == ("done", [], [], [])


def test_a_drop_that_comes_back_waits_five_seconds_and_says_so_once():
    value, waits, backs, clock, _ = run([0, "ok"])
    assert value == "done" and clock.slept == [5] and len(backs) == 1
    assert waits == [cn.Wait(5, 0, 1800, True)]


def test_the_pauses_follow_the_schedule_and_only_the_first_is_the_first():
    value, waits, backs, clock, _ = run([0, 0, 0, 0, 0, 0, 0, "ok"])
    assert clock.slept == [5, 10, 20, 30, 60, 60, 60]
    assert [w.first for w in waits] == [True] + [False] * 6
    assert [w.waited_s for w in waits] == [0, 5, 15, 35, 65, 125, 185]
    assert all(w.budget_s == 1800 for w in waits) and len(backs) == 1


def test_it_gives_up_when_the_connection_has_been_away_for_the_whole_patience():
    patience = cn.Patience(total_s=100, pauses_s=(30,), progress_s=60)
    error, waits, backs, clock, left = run([0, 0, 0, 0, 0, "ok"], patience)
    assert isinstance(error, cn.ConnectionGaveUp) and error.waited_s == 120 and error.detail == "lost"
    assert clock.slept == [30, 30, 30, 30] and left == ["ok"] and backs == []        # five tries, none after the patience ran out


def test_one_second_short_of_the_patience_still_tries_and_exactly_the_patience_gives_up():
    patience = cn.Patience(total_s=60, pauses_s=(30,), progress_s=1000)
    error, _, _, clock, _ = run([0, 0, 0, "ok"], patience)             # fails at 0, 30, 60 seconds into the spell
    assert isinstance(error, cn.ConnectionGaveUp) and error.waited_s == 60 and clock.slept == [30, 30]
    longer = cn.Patience(total_s=61, pauses_s=(30,), progress_s=1000)
    value, _, _, clock, _ = run([0, 0, 0, "ok"], longer)
    assert value == "done" and clock.slept == [30, 30, 30]


def test_an_attempt_that_ran_for_a_minute_before_failing_starts_the_waiting_afresh():
    patience = cn.Patience(total_s=100, pauses_s=(30,), progress_s=60)
    error, waits, backs, clock, _ = run([0, 0, 60, 0, 0, 0, "ok"], patience)
    # the third attempt ran 60 s (it got somewhere), so the spell restarts: it can wait 30 s three more times
    assert not isinstance(error, Exception) and error == "done"
    assert [w.first for w in waits] == [True, False, True, False, False, False] and len(backs) == 2
    assert [w.waited_s for w in waits] == [0, 30, 0, 30, 60, 90]


def test_an_attempt_one_second_short_of_a_minute_does_not_count_as_progress():
    patience = cn.Patience(total_s=1000, pauses_s=(30,), progress_s=60)
    _, waits, backs, _, _ = run([0, 0, 59, 0, "ok"], patience)
    assert [w.first for w in waits] == [True, False, False, False] and len(backs) == 1


def test_the_first_failure_of_all_is_never_treated_as_progress_however_long_it_took():
    _, waits, backs, _, _ = run([500, "ok"])
    assert waits == [cn.Wait(5, 0, 1800, True)] and len(backs) == 1


def test_something_that_is_not_the_connection_goes_straight_through_without_waiting():
    boom = RuntimeError("boom")
    error, waits, backs, clock, left = run([boom, "ok"])
    assert error is boom and waits == [] and clock.slept == [] and left == ["ok"]


def test_something_that_is_not_the_connection_after_a_drop_also_goes_straight_through():
    boom = RuntimeError("boom")
    error, waits, backs, clock, _ = run([0, boom])
    assert error is boom and len(waits) == 1 and backs == []


def test_ctrl_c_during_a_wait_goes_straight_through():
    clock = Clock()

    def stop(seconds):
        raise KeyboardInterrupt

    steps = iter([0])

    def attempt():
        next(steps)
        raise cn.ConnectionLost("x")

    with pytest.raises(KeyboardInterrupt):
        cn.keep_trying(attempt, on_wait=lambda w: None, on_back=lambda: None, sleep=stop, clock=clock)


def test_the_same_wrong_file_twice_in_a_row_is_not_the_connection():
    sig = ("a" * 64,)
    error, waits, _, clock, left = run([cn.ConnectionLost("x", sig), cn.ConnectionLost("x", sig), "ok"])
    assert isinstance(error, cn.NotTheConnection) and error.detail == "x" and clock.slept == [5] and left == ["ok"]


def test_a_different_wrong_file_each_time_is_a_cut_download_and_goes_on():
    value, waits, _, clock, _ = run([cn.ConnectionLost("x", ("a" * 64,)), cn.ConnectionLost("x", ("b" * 64,)), cn.ConnectionLost("x", ("a" * 64,)), "ok"])
    assert value == "done" and clock.slept == [5, 10, 20]


def test_a_drop_between_two_identical_wrong_files_breaks_the_run_of_them():
    sig = ("a" * 64,)
    value, _, _, clock, _ = run([cn.ConnectionLost("x", sig), cn.ConnectionLost("x", None), cn.ConnectionLost("x", sig), "ok"])
    assert value == "done" and clock.slept == [5, 10, 20]


def test_a_fresh_spell_forgets_the_last_wrong_file():
    patience = cn.Patience(total_s=1000, pauses_s=(5,), progress_s=60)
    sig = ("a" * 64,)

    class Slow(Clock):
        pass

    clock = Slow()
    steps = [cn.ConnectionLost("x", sig), "slow-lost-with-sig", "ok"]

    def attempt():
        step = steps.pop(0)
        if step == "ok":
            return "done"
        if step == "slow-lost-with-sig":
            clock.take(61)                      # it ran a minute: the connection was back, so this is a new spell
            raise cn.ConnectionLost("x", sig)
        raise step

    assert cn.keep_trying(attempt, on_wait=lambda w: None, on_back=lambda: None, sleep=clock.sleep, clock=clock, patience=patience) == "done"


def test_a_drop_without_a_signature_never_counts_as_the_same_file():
    value, _, _, clock, _ = run([0, 0, 0, "ok"])
    assert value == "done" and clock.slept == [5, 10, 20]
