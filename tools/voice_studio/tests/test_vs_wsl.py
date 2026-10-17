# SPDX-License-Identifier: GPL-3.0-or-later
"""Help for the Windows side of Ubuntu under WSL (plan task VS-3.6, decision D17, choices P26): reading and changing `.wslconfig` without disturbing anything else in it, finding the
person's Windows home folder with and without a Windows program to ask, what is true now, and the firewall command. The Windows drive is a real folder in a temporary place."""
import os
import random
from datetime import datetime, timedelta, timezone

import pytest

from vs_fakes import PROC_NATIVE, PROC_WSL1, PROC_WSL2
from vs_wsl_helpers import VER_10, VER_11, WslSystem
from voice_studio.core import preflight, wsl
from voice_studio.core.system import CommandResult

NOW = datetime(2026, 10, 17, 9, 30, 15)
MIRRORED = "[wsl2]\nnetworkingMode=mirrored\n"


def slurp(path, mode="rb"):
    with open(path, mode) as source:
        return source.read()


def code_of(fn, *a, **kw):
    with pytest.raises(wsl.WslError) as caught:
        fn(*a, **kw)
    return caught.value.code


# ---------------------------------------------------------------- reading the text

def test_a_value_is_found_inside_its_section_whatever_the_case_and_the_spacing():
    text = "[WSL2]\nNetworkingMode = mirrored  \n[general]\ninstanceIdleTimeout=-1\n"
    assert wsl.find(text, "wsl2", "networkingMode") == ["mirrored"]
    assert wsl.find(text, "general", "INSTANCEIDLETIMEOUT") == ["-1"]
    assert wsl.find(text, "wsl2", "instanceIdleTimeout") == [], "a key in another section is not this section's"


def test_a_comment_gives_nothing_and_a_missing_key_gives_nothing():
    text = "[wsl2]\n# networkingMode=nat\n; networkingMode=none\n   # networkingMode=nat\nmemory=8GB\n"
    assert wsl.find(text, "wsl2", "networkingMode") == []
    assert wsl.find("", "wsl2", "networkingMode") == [] and wsl.find("networkingMode=mirrored\n", "wsl2", "networkingMode") == [], "outside every section is nothing"


def test_every_value_is_returned_in_file_order_and_a_byte_order_mark_and_crlf_do_not_matter():
    text = "\ufeff[wsl2]\r\nnetworkingMode=nat\r\nnetworkingMode=mirrored\r\n"
    assert wsl.find(text, "wsl2", "networkingMode") == ["nat", "mirrored"]


# ---------------------------------------------------------------- changing the text

def test_a_value_that_is_there_is_changed_in_place_and_the_key_the_spacing_and_the_rest_are_kept():
    text = "# my settings\n[wsl2]\nmemory=8GB\n  NetworkingMode = nat \nprocessors=4\n\n[general]\nx=1\n"
    assert wsl.with_setting(text, "wsl2", "networkingMode", "mirrored") == "# my settings\n[wsl2]\nmemory=8GB\n  NetworkingMode = mirrored\nprocessors=4\n\n[general]\nx=1\n"


def test_a_key_is_added_to_a_section_that_is_there_after_its_last_setting_and_before_the_next_section():
    text = "[wsl2]\nmemory=8GB\n# about the next\n\n[general]\nx=1\n"
    assert wsl.with_setting(text, "wsl2", "networkingMode", "mirrored") == "[wsl2]\nmemory=8GB\nnetworkingMode=mirrored\n# about the next\n\n[general]\nx=1\n"
    assert wsl.with_setting("[wsl2]\n", "wsl2", "networkingMode", "mirrored") == "[wsl2]\nnetworkingMode=mirrored\n"
    assert wsl.with_setting("[wsl2]", "wsl2", "networkingMode", "mirrored") == "[wsl2]\nnetworkingMode=mirrored", "a file with no final line end keeps having none"


def test_a_section_is_added_at_the_end_when_the_file_has_none_and_a_blank_line_keeps_it_apart():
    assert wsl.with_setting("[general]\nx=1\n", "wsl2", "networkingMode", "mirrored") == "[general]\nx=1\n\n[wsl2]\nnetworkingMode=mirrored\n"
    assert wsl.with_setting("[general]\nx=1\n\n", "wsl2", "networkingMode", "mirrored") == "[general]\nx=1\n\n[wsl2]\nnetworkingMode=mirrored\n"
    assert wsl.with_setting("[general]\nx=1", "wsl2", "networkingMode", "mirrored") == "[general]\nx=1\n\n[wsl2]\nnetworkingMode=mirrored\n"
    assert wsl.with_setting("", "wsl2", "networkingMode", "mirrored") == "[wsl2]\nnetworkingMode=mirrored\n"
    assert wsl.with_setting("# only a note\n", "wsl2", "networkingMode", "mirrored") == "# only a note\n\n[wsl2]\nnetworkingMode=mirrored\n"


def test_windows_line_ends_and_a_byte_order_mark_are_kept():
    text = "\ufeff[wsl2]\r\nmemory=8GB\r\n\r\n[general]\r\nx=1\r\n"
    assert wsl.with_setting(text, "wsl2", "networkingMode", "mirrored") == "\ufeff[wsl2]\r\nmemory=8GB\r\nnetworkingMode=mirrored\r\n\r\n[general]\r\nx=1\r\n"
    assert wsl.with_setting(text, "general", "instanceIdleTimeout", "-1") == "\ufeff[wsl2]\r\nmemory=8GB\r\n\r\n[general]\r\nx=1\r\ninstanceIdleTimeout=-1\r\n"
    assert wsl.with_setting("[a]\r\nx=1\r\n", "wsl2", "k", "v") == "[a]\r\nx=1\r\n\r\n[wsl2]\r\nk=v\r\n"


def test_the_same_text_comes_back_when_the_value_is_already_right_whatever_its_case():
    text = "[wsl2]\nnetworkingMode=Mirrored\n"
    assert wsl.with_setting(text, "wsl2", "networkingMode", "mirrored") is text
    assert wsl.with_setting("[general]\ninstanceIdleTimeout = -1\n", "general", "instanceIdleTimeout", "-1") == "[general]\ninstanceIdleTimeout = -1\n"


def test_a_setting_in_another_section_does_not_count():
    text = "[general]\nnetworkingMode=nat\n"
    assert wsl.with_setting(text, "wsl2", "networkingMode", "mirrored") == "[general]\nnetworkingMode=nat\n\n[wsl2]\nnetworkingMode=mirrored\n"


def test_a_setting_given_twice_or_a_section_given_twice_is_refused_and_so_is_text_that_is_not_text():
    assert code_of(wsl.with_setting, "[wsl2]\nnetworkingMode=nat\nnetworkingMode=none\n", "wsl2", "networkingMode", "mirrored") == "duplicate"
    assert code_of(wsl.with_setting, "[wsl2]\nmemory=1\n[wsl2]\nprocessors=2\n", "wsl2", "networkingMode", "mirrored") == "duplicate"
    assert code_of(wsl.with_setting, "[\x00w\x00s\x00l\x002\x00]\x00", "wsl2", "networkingMode", "mirrored") == "bad_text"
    assert wsl.with_setting("[wsl2]\nmemory=1\n[general]\nx=1\n", "wsl2", "networkingMode", "mirrored")


def test_a_comment_that_looks_like_a_section_or_a_setting_is_never_taken_for_one():
    text = "# [wsl2]\n; networkingMode=nat\n"
    assert wsl.with_setting(text, "wsl2", "networkingMode", "mirrored") == "# [wsl2]\n; networkingMode=nat\n\n[wsl2]\nnetworkingMode=mirrored\n"


def test_changing_a_file_changes_one_line_and_leaves_every_other_line_where_it_was():
    rng = random.Random(20261017)
    words = ["memory=8GB", "processors=4", "# a note", "; another", "", "[wsl2]", "[general]", "[experimental]", "swap=0", "localhostForwarding=true", "  indented=1", "autoMemoryReclaim=gradual"]
    for _ in range(300):
        lines = [rng.choice(words) for _ in range(rng.randint(0, 12))]
        text = "\n".join(lines) + rng.choice(["", "\n"])
        try:
            new = wsl.with_setting(text, "wsl2", "networkingMode", "mirrored")
        except wsl.WslError as error:
            assert error.code == "duplicate" and lines.count("[wsl2]") > 1
            continue
        assert wsl.find(new, "wsl2", "networkingMode") == ["mirrored"], text
        old_lines = text.split("\n")
        if old_lines and old_lines[-1] == "":
            old_lines.pop()
        new_lines = new.split("\n")
        if new_lines and new_lines[-1] == "":
            new_lines.pop()
        remaining = list(new_lines)
        for line in old_lines:
            assert line in remaining, (text, new)
            remaining = remaining[remaining.index(line) + 1:]


def test_the_changes_are_listed_as_removed_and_added_lines_with_a_line_either_side():
    old = "[wsl2]\nmemory=8GB\n\n[general]\nx=1\n"
    new = wsl.with_setting(old, "wsl2", "networkingMode", "mirrored")
    assert wsl.changes(old, new) == [" memory=8GB", "+networkingMode=mirrored", " "]
    assert wsl.changes("[wsl2]\nnetworkingMode=nat\n", "[wsl2]\nnetworkingMode=mirrored\n") == [" [wsl2]", "-networkingMode=nat", "+networkingMode=mirrored"]
    assert wsl.changes("a\r\nb\r\n", "a\nb\n") == [] and wsl.changes("", "") == [] and wsl.changes("a", "a\nb") == [" a", "+b"]


# ---------------------------------------------------------------- the Windows drive

def test_windows_drives_are_under_mnt_unless_the_system_says_otherwise(tmp_path):
    assert wsl.automount_root(WslSystem(tmp_path, wsl_conf=None)) == "/mnt"
    assert wsl.automount_root(WslSystem(tmp_path, wsl_conf="[boot]\nsystemd=true\n")) == "/mnt"
    assert wsl.automount_root(WslSystem(tmp_path, wsl_conf="[automount]\nroot = /windir/\n")) == "/windir"
    assert wsl.automount_root(WslSystem(tmp_path, wsl_conf='# note\n[Automount]\nRoot="/w"\n')) == "/w"
    assert wsl.automount_root(WslSystem(tmp_path, wsl_conf="[boot]\nroot=/elsewhere\n")) == "/mnt", "only the automount section counts"
    for odd in ("relative", "/", "/a/../b", ""):
        assert wsl.automount_root(WslSystem(tmp_path, wsl_conf="[automount]\nroot=%s\n" % odd)) == "/mnt", odd


def test_a_name_the_person_gives_wins_and_must_be_a_folder_there(tmp_path):
    system = WslSystem(tmp_path, users=("Anna", "Ben"))
    got = wsl.windows_home(system, asked=True, named="Ben")
    assert got == wsl.WindowsHome(system.c_users + "/Ben", wsl.HOW_NAMED) and system.ran == [], "no Windows program is asked when a name was given"
    for bad in ("Nobody", "", ".", "..", "../Anna", "Anna/..", "An\\na", "x" * 65, "a:b"):
        assert code_of(wsl.windows_home, system, asked=True, named=bad) == "no_such_user", bad


def test_windows_is_asked_for_the_profile_folder_first_and_its_answer_is_turned_into_a_path_here(tmp_path):
    system = WslSystem(tmp_path, users=("Anna", "Ben"))
    got = wsl.windows_home(system, asked=True)
    assert got == wsl.WindowsHome(system.c_users + "/Anna", wsl.HOW_ASKED)
    assert system.ran == [(("/mnt/c/Windows/System32/cmd.exe", "/c", "echo %USERPROFILE%"), wsl.INTEROP_TIMEOUT_S)]


def test_an_answer_that_does_not_lead_to_a_folder_is_not_trusted_and_the_user_folders_are_looked_at_instead(tmp_path):
    for answer in ("%USERPROFILE%\r\n", "C:\\Users\\Nobody\r\n", "C:\\Users\\..\\..\r\n", "\\\\server\\share\\Anna\r\n", "", "C:\\Users\\Anna\\..\\Ben\r\n", "C:Users\\Anna\r\n"):
        system = WslSystem(tmp_path, users=("Anna",), profile=CommandResult(0, answer))
        got = wsl.windows_home(system, asked=True)
        assert got == wsl.WindowsHome(system.c_users + "/Anna", wsl.HOW_ONLY), answer


def test_without_a_windows_program_the_only_user_folder_is_used(tmp_path):
    system = WslSystem(tmp_path, cmd=None)
    assert wsl.windows_home(system, asked=False) == wsl.WindowsHome(system.c_users + "/Anna", wsl.HOW_ONLY) and system.ran == []
    system = WslSystem(tmp_path, users=("Anna",))
    assert wsl.windows_home(system, asked=False).how == wsl.HOW_ONLY, "a Windows program that is there is not asked when the caller says it does not work"
    assert system.ran == []


def test_the_folders_windows_keeps_for_itself_and_loose_files_are_not_users(tmp_path):
    system = WslSystem(tmp_path, users=("Anna", "Public", "Default", "Default User", "All Users", "defaultuser0", "WsiAccount"))
    open(system.c_users + "/desktop.ini", "w").close()
    open(system.c_users + "/notes.txt", "w").close()
    assert wsl.windows_home(system, asked=False).path.endswith("/Anna")


def test_more_than_one_user_folder_is_told_with_the_names_and_none_is_told(tmp_path):
    system = WslSystem(tmp_path, cmd=None, users=("Ben", "Anna", "Public"))
    with pytest.raises(wsl.WslError) as caught:
        wsl.windows_home(system, asked=False)
    assert caught.value.code == "several_users" and caught.value.detail == "Anna, Ben"
    empty = WslSystem(tmp_path / "other", cmd=None, users=())
    assert code_of(wsl.windows_home, empty, asked=False) == "no_windows_home"
    gone = WslSystem(tmp_path / "third", cmd=None, users=())
    os.rmdir(gone.c_users)
    assert code_of(wsl.windows_home, gone, asked=False) == "no_windows_home"


def test_a_drive_other_than_c_is_followed_when_windows_says_the_profile_is_there(tmp_path):
    system = WslSystem(tmp_path, users=("Anna",), profile=CommandResult(0, "D:\\Users\\Anna\r\n"))
    os.makedirs(system.root + "/d/Users/Anna")
    assert wsl.windows_home(system, asked=True) == wsl.WindowsHome(system.root + "/d/Users/Anna", wsl.HOW_ASKED)


# ---------------------------------------------------------------- what works now

def test_a_windows_program_that_answers_gives_the_build_number_it_asked_for_with_a_time_limit(tmp_path):
    system = WslSystem(tmp_path)
    assert wsl.interop(system) == (wsl.INTEROP_WORKS, 22631)
    assert system.ran == [(("/mnt/c/Windows/System32/cmd.exe", "/c", "ver"), wsl.INTEROP_TIMEOUT_S)] and wsl.INTEROP_TIMEOUT_S == 10.0
    assert wsl.interop(WslSystem(tmp_path, cmd=CommandResult(0, VER_10))) == (wsl.INTEROP_WORKS, 19045)
    assert wsl.interop(WslSystem(tmp_path, cmd=CommandResult(0, "something else\r\n"))) == (wsl.INTEROP_WORKS, None)


def test_a_windows_program_that_does_not_start_or_fails_is_failed_and_one_that_is_not_there_is_missing(tmp_path):
    assert wsl.interop(WslSystem(tmp_path, cmd=None)) == (wsl.INTEROP_MISSING, None)
    assert wsl.interop(WslSystem(tmp_path, cmd=CommandResult(1, VER_11))) == (wsl.INTEROP_FAILED, None), "a failure code is a failure whatever it printed"
    system = WslSystem(tmp_path)
    system.run = lambda argv, timeout=15.0, cwd=None, env=None: None                       # "cannot execute binary file: Exec format error" (F4)
    assert wsl.interop(system) == (wsl.INTEROP_FAILED, None)


@pytest.mark.parametrize("said,expected", [("nat\n", "nat"), ("Mirrored\n", "mirrored"), (" virtioproxy \n", "virtioproxy"), ("", None), ("nat is the mode\n", None), ("n" * 21, None), ("12\n", None)])
def test_the_running_networking_mode_is_what_wslinfo_says_when_it_says_a_plain_word(tmp_path, said, expected):
    system = WslSystem(tmp_path, wslinfo=CommandResult(0, said))
    assert wsl.runtime_networking_mode(system) == expected
    assert system.ran == [(("/usr/bin/wslinfo", "--networking-mode"), wsl.INTEROP_TIMEOUT_S)]


def test_without_wslinfo_or_when_it_fails_the_running_mode_is_not_known(tmp_path):
    assert wsl.runtime_networking_mode(WslSystem(tmp_path)) is None
    assert wsl.runtime_networking_mode(WslSystem(tmp_path, wslinfo=CommandResult(2, "nat\n"))) is None
    system = WslSystem(tmp_path, wslinfo=CommandResult(0, "nat"))
    system.run = lambda argv, timeout=15.0, cwd=None, env=None: None
    assert wsl.runtime_networking_mode(system) is None


# ---------------------------------------------------------------- all of it

def test_a_computer_that_is_not_ubuntu_in_windows_is_told_so_before_anything_is_asked(tmp_path):
    system = WslSystem(tmp_path, kernel=PROC_NATIVE)
    facts = wsl.look(system)
    assert facts.platform is preflight.Platform.NATIVE and facts.home is None and facts.config_text is None and system.ran == []


def test_the_facts_come_from_the_file_the_running_ubuntu_and_the_programs_that_answer(tmp_path):
    system = WslSystem(tmp_path, wslinfo=CommandResult(0, "nat\n"))
    system.write_config("[wsl2]\nnetworkingMode=Mirrored\n\n[general]\ninstanceIdleTimeout=-1\n")
    facts = wsl.look(system)
    assert (facts.platform, facts.distro, facts.interop, facts.build) == (preflight.Platform.WSL2, "Ubuntu-24.04", wsl.INTEROP_WORKS, 22631)
    assert facts.runtime_mode == "nat" and facts.file_mode == "mirrored" and facts.file_idle == "-1" and not facts.config_bad
    assert facts.home == wsl.WindowsHome(system.c_users + "/Anna", wsl.HOW_ASKED) and facts.config_path == system.config_path() and facts.config_text.startswith("[wsl2]")


def test_the_last_value_in_the_file_is_the_one_that_counts_and_a_file_that_is_not_there_gives_nothing(tmp_path):
    system = WslSystem(tmp_path)
    facts = wsl.look(system)
    assert facts.config_text is None and facts.file_mode is None and facts.file_idle is None and facts.config_path == system.config_path() and not facts.config_bad
    system.write_config("[wsl2]\nnetworkingMode=nat\nnetworkingMode=mirrored\n")
    assert wsl.look(system).file_mode == "mirrored"


def test_a_file_that_is_not_plain_utf8_text_is_marked_and_never_read_as_text(tmp_path):
    system = WslSystem(tmp_path)
    for raw in ("[wsl2]\nnetworkingMode=mirrored\n".encode("utf-16"), b"[wsl2]\n# caf\xe9\n", b"\x00\x00"):
        system.write_config("", binary=raw)
        facts = wsl.look(system)
        assert facts.config_bad and facts.config_text is None and facts.file_mode is None, raw


def test_the_file_is_read_with_its_line_ends_and_its_mark_as_they_are(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("", binary=b"\xef\xbb\xbf[wsl2]\r\nmemory=1GB\r\n")
    assert wsl.look(system).config_text == "\ufeff[wsl2]\r\nmemory=1GB\r\n"


def test_a_name_that_is_not_a_folder_or_several_users_leave_the_home_out_with_the_reason(tmp_path):
    facts = wsl.look(WslSystem(tmp_path, users=("Anna",)), named="Nobody")
    assert facts.home is None and facts.home_error.code == "no_such_user" and facts.config_path is None
    facts = wsl.look(WslSystem(tmp_path / "x", cmd=None, users=("Anna", "Ben")))
    assert facts.home is None and facts.home_error.code == "several_users" and facts.interop == wsl.INTEROP_MISSING
    assert wsl.look(WslSystem(tmp_path / "y", users=("Anna", "Ben"), kernel=PROC_WSL1)).platform is preflight.Platform.WSL1


# ---------------------------------------------------------------- the firewall command and the version

def test_the_firewall_command_names_the_port_the_rule_and_wsls_virtual_machine_and_the_undo_removes_that_rule():
    add, undo = wsl.firewall_commands(8443)
    assert add == ("New-NetFirewallHyperVRule -Name 'ACK-Voice-Studio-send' -DisplayName 'ACK Voice Studio: send the voice file' -Direction Inbound "
                   "-VMCreatorId '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -Protocol TCP -LocalPorts 8443")
    assert undo == "Remove-NetFirewallHyperVRule -Name 'ACK-Voice-Studio-send'"
    assert wsl.firewall_commands(1024)[0].endswith("-LocalPorts 1024") and wsl.firewall_commands(65535)[0].endswith("-LocalPorts 65535")


@pytest.mark.parametrize("port", [1023, 65536, 0, -1, None, "8443", 8443.0, True, False])
def test_a_port_that_is_not_a_whole_number_in_the_allowed_range_is_refused(port):
    with pytest.raises(ValueError):
        wsl.firewall_commands(port)


def test_mirrored_networking_needs_the_windows_11_build_that_has_it_and_an_unknown_build_is_unknown():
    assert wsl.mirrored_possible(22620) is False and wsl.mirrored_possible(22621) is True and wsl.mirrored_possible(26100) is True and wsl.mirrored_possible(19045) is False
    assert wsl.mirrored_possible(None) is None and wsl.MIRRORED_MIN_BUILD == 22621


# ---------------------------------------------------------------- the plan and the write

def facts_for(system, **kw):
    return wsl.look(system, **kw)


def test_a_file_that_already_says_so_has_nothing_to_change(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nnetworkingMode=mirrored\n")
    assert wsl.plan_edit(facts_for(system), wsl.SECTION_NETWORK, wsl.KEY_NETWORK, wsl.MIRRORED) is None


def test_the_plan_for_a_file_that_is_there_has_the_new_text_the_listing_and_is_not_a_creation(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nmemory=8GB\n")
    plan = wsl.plan_edit(facts_for(system), wsl.SECTION_NETWORK, wsl.KEY_NETWORK, wsl.MIRRORED)
    assert plan.path == system.config_path() and plan.old == "[wsl2]\nmemory=8GB\n" and plan.new == "[wsl2]\nmemory=8GB\nnetworkingMode=mirrored\n" and not plan.creates
    assert plan.listing == (" memory=8GB", "+networkingMode=mirrored") and (plan.section, plan.key, plan.value) == ("wsl2", "networkingMode", "mirrored")


def test_the_plan_for_no_file_makes_one(tmp_path):
    plan = wsl.plan_edit(facts_for(WslSystem(tmp_path)), wsl.SECTION_IDLE, wsl.KEY_IDLE, wsl.NEVER)
    assert plan.creates and plan.old is None and plan.new == "[general]\ninstanceIdleTimeout=-1\n" and plan.listing == ("+[general]", "+instanceIdleTimeout=-1")


def test_a_plan_is_refused_when_the_home_is_not_known_or_the_file_cannot_be_edited_safely(tmp_path):
    assert code_of(wsl.plan_edit, facts_for(WslSystem(tmp_path, users=("Anna",)), named="Nobody"), "wsl2", "k", "v") == "no_such_user"
    assert code_of(wsl.plan_edit, facts_for(WslSystem(tmp_path / "a", cmd=None, users=("A", "B"))), "wsl2", "k", "v") == "several_users"
    system = WslSystem(tmp_path / "b")
    system.write_config("", binary=b"\xff\xfe")
    assert code_of(wsl.plan_edit, facts_for(system), "wsl2", "k", "v") == "bad_text"
    system.write_config("[wsl2]\nk=1\nk=2\n")
    assert code_of(wsl.plan_edit, facts_for(system), "wsl2", "k", "v") == "duplicate"
    facts = wsl.Facts(preflight.Platform.WSL2, "", wsl.INTEROP_MISSING, None, None, None, None, None, None, None, None)
    assert code_of(wsl.plan_edit, facts, "wsl2", "k", "v") == "no_windows_home", "no reason given is still a reason"


def test_a_copy_of_the_old_file_is_made_first_under_a_name_that_does_not_exist_and_the_new_text_is_exact(tmp_path):
    system = WslSystem(tmp_path)
    original = b"\xef\xbb\xbf[wsl2]\r\nmemory=8GB\r\n"
    system.write_config("", binary=original)
    plan = wsl.plan_edit(facts_for(system), wsl.SECTION_NETWORK, wsl.KEY_NETWORK, wsl.MIRRORED)
    kept = wsl.apply_edit(plan, NOW)
    assert kept == system.config_path() + ".bak" and slurp(kept) == original
    assert slurp(system.config_path()) == b"\xef\xbb\xbf[wsl2]\r\nmemory=8GB\r\nnetworkingMode=mirrored\r\n"
    assert sorted(os.listdir(os.path.dirname(kept))) == [".wslconfig", ".wslconfig.bak"], "no temporary file is left"


def test_an_earlier_copy_is_never_replaced_a_later_one_gets_the_time_and_then_a_number(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nmemory=1GB\n")
    names = []
    for value in ("a", "b", "c", "d"):
        plan = wsl.plan_edit(facts_for(system), "wsl2", "extra", value)
        names.append(wsl.apply_edit(plan, NOW))
    base = system.config_path()
    assert names == [base + ".bak", base + ".bak-20261017-093015", base + ".bak-20261017-093015-2", base + ".bak-20261017-093015-3"]
    assert [slurp(n, "r") for n in names] == ["[wsl2]\nmemory=1GB\n", "[wsl2]\nmemory=1GB\nextra=a\n", "[wsl2]\nmemory=1GB\nextra=b\n", "[wsl2]\nmemory=1GB\nextra=c\n"]
    assert slurp(base, "r") == "[wsl2]\nmemory=1GB\nextra=d\n"


def test_a_name_with_the_time_in_it_is_in_utc_for_a_clock_with_a_zone(tmp_path):
    base = str(tmp_path / ".wslconfig")
    open(base + ".bak", "w").close()
    zone = timezone(timedelta(hours=5))
    assert wsl.backup_name(base, datetime(2026, 10, 17, 9, 30, 15, tzinfo=zone)) == base + ".bak-20261017-043015"
    assert wsl.backup_name(base, datetime(2026, 10, 17, 9, 30, 15)) == base + ".bak-20261017-093015"


def test_with_no_file_there_is_nothing_to_copy_and_the_file_is_made(tmp_path):
    system = WslSystem(tmp_path)
    plan = wsl.plan_edit(facts_for(system), wsl.SECTION_IDLE, wsl.KEY_IDLE, wsl.NEVER)
    assert wsl.apply_edit(plan, NOW) is None
    assert system.read_config() == "[general]\ninstanceIdleTimeout=-1\n" and os.listdir(os.path.dirname(system.config_path())) == [".wslconfig"]


def test_a_file_that_appeared_while_waiting_is_not_written_over(tmp_path):
    system = WslSystem(tmp_path)
    plan = wsl.plan_edit(facts_for(system), wsl.SECTION_IDLE, wsl.KEY_IDLE, wsl.NEVER)
    system.write_config("[wsl2]\nmemory=1GB\n")
    assert code_of(wsl.apply_edit, plan, NOW) == "not_written"
    assert system.read_config() == "[wsl2]\nmemory=1GB\n" and os.listdir(os.path.dirname(system.config_path())) == [".wslconfig"]


def test_a_write_that_cannot_happen_says_so_with_the_systems_words_and_leaves_the_old_file_and_no_temporary_file(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nmemory=1GB\n")
    plan = wsl.plan_edit(facts_for(system), wsl.SECTION_IDLE, wsl.KEY_IDLE, wsl.NEVER)
    missing = wsl.EditPlan(str(tmp_path / "no-such-folder" / ".wslconfig"), "general", "instanceIdleTimeout", "-1", None, "[general]\ninstanceIdleTimeout=-1\n", (), True)
    with pytest.raises(wsl.WslError) as caught:
        wsl.apply_edit(missing, NOW)
    assert caught.value.code == "not_written" and caught.value.detail
    assert not os.path.exists(str(tmp_path / "no-such-folder")), "nothing was made"
    gone = wsl.EditPlan(str(tmp_path / "gone" / ".wslconfig"), "general", "k", "v", "old text", "new text", (), False)
    assert code_of(wsl.apply_edit, gone, NOW) == "not_written"
    assert system.read_config() == "[wsl2]\nmemory=1GB\n"


def test_the_kinds_of_error_this_module_raises_are_the_ones_it_lists():
    assert wsl.ERROR_CODES == ("no_windows_home", "several_users", "no_such_user", "bad_text", "duplicate", "not_written")


# ---------------------------------------------------------------- the notice before a long job

from vs_fakes import FakeSystem, wsl2


def fake_windows(config=None, *, users=("Anna",), kernel=PROC_WSL2, extra_dirs=()):
    """A computer for `idle_state`: no real files, only what a made-up system hands out."""
    root = "/mnt/c/Users"
    files = {"/etc/wsl.conf": None}
    present = {"/mnt/c"}
    if config is not None:
        files["%s/Anna/.wslconfig" % root] = config
        present.add("%s/Anna/.wslconfig" % root)
    return FakeSystem(proc_version=kernel, environ={"WSL_DISTRO_NAME": "Ubuntu-24.04"} if kernel != PROC_NATIVE else {}, present=present, dirs=["%s/%s" % (root, u) for u in users] + list(extra_dirs),
                      listings={root: list(users)}), files


def idle(config=None, **kw):
    system, files = fake_windows(config, **kw)
    system.files.update(files)
    return wsl.idle_state(system)


def test_ubuntu_that_is_not_in_windows_has_no_idle_state():
    assert idle(kernel=PROC_NATIVE) is None and idle(MIRRORED, kernel=PROC_NATIVE) is None


def test_a_file_with_the_setting_keeps_ubuntu_running_and_one_without_it_does_not():
    assert idle("[general]\ninstanceIdleTimeout=-1\n") == wsl.IDLE_NEVER
    assert idle("[general]\nInstanceIdleTimeout = -1 \n") == wsl.IDLE_NEVER
    assert idle("[general]\ninstanceIdleTimeout=15000\n") == wsl.IDLE_STOPS
    assert idle("[wsl2]\ninstanceIdleTimeout=-1\n") == wsl.IDLE_STOPS, "in the wrong section it is not the setting"
    assert idle("[general]\n# instanceIdleTimeout=-1\n") == wsl.IDLE_STOPS
    assert idle(MIRRORED) == wsl.IDLE_STOPS and idle() == wsl.IDLE_STOPS, "no file at all is the usual behaviour"
    assert idle("[general]\ninstanceIdleTimeout=0\ninstanceIdleTimeout=-1\n") == wsl.IDLE_NEVER, "the last value counts"


def test_a_home_that_cannot_be_told_or_a_file_that_cannot_be_read_is_unknown():
    assert idle(None, users=("Anna", "Ben")) == wsl.IDLE_UNKNOWN and idle(None, users=()) == wsl.IDLE_UNKNOWN
    system, files = fake_windows("x")
    system.files["/mnt/c/Users/Anna/.wslconfig"] = None
    assert wsl.idle_state(system) == wsl.IDLE_UNKNOWN
    assert idle("[general]\x00\n") == wsl.IDLE_UNKNOWN


def test_it_starts_no_program_to_find_out():
    system, files = fake_windows("[general]\ninstanceIdleTimeout=-1\n")
    system.files.update(files)
    assert wsl.idle_state(system) == wsl.IDLE_NEVER and system.ran == []
