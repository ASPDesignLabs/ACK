# SPDX-License-Identifier: GPL-3.0-or-later
"""The page for an IT department (docs/VOICE_STUDIO_IT_GUIDE.md) says what the tool downloads, installs, needs and opens. Those are facts that live in code and data, so this
test reads them from there and fails if the page and the code part ways: a changed pin, a new host, a different package, another disk figure, a moved folder.

A page like this that is wrong costs a person the one approval they were asking for, so it is held to the code the same way the privacy page is."""
import re
from pathlib import Path

import pytest

from voice_studio.core import connection, fetch, jobs, preflight, registry as reg, setupplan as sp
from voice_studio.core.envspec import load_environments
from voice_studio.core.paths import DataHome

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[1]
GUIDE = (REPO / "docs" / "VOICE_STUDIO_IT_GUIDE.md").read_text(encoding="utf-8")
GIB = 2**30


def section(number):
    """The text of one numbered section ("## 5. ...") up to the next."""
    match = re.search(r"^## %d\. .*?(?=^## \d+\. |\Z)" % number, GUIDE, flags=re.M | re.S)
    assert match, "section %d is missing" % number
    return match.group(0)


# ---------------------------------------------------------------- the downloads

def test_every_pinned_download_is_listed_with_its_exact_address_size_and_checksum():
    items = [i for i in reg.load_registry().items]
    assert items and all(i.pinned for i in items)
    for item in items:
        row = "| `%s` | %d | `%s` |" % (item.url, item.size_bytes, item.sha256)
        assert row in GUIDE, item.id


def test_the_page_lists_no_address_that_is_not_in_the_registry():
    pinned = {i.url for i in reg.load_registry().items}
    in_table = set(re.findall(r"^\| `(https://huggingface\.co/[^`]+)` \|", GUIDE, flags=re.M))
    assert in_table == pinned


def test_the_folder_to_hand_files_to_is_the_one_the_setup_run_looks_in_and_the_names_are_the_pinned_ones():
    model = [i for i in reg.load_registry().items if i.kind == "model"]
    folder = {i.folder for i in model}
    assert len(folder) == 1
    (name,) = folder
    expected = DataHome("~").downloads + "/models/" + name + "/"
    assert expected.replace("~/", "~/") in GUIDE.replace("`", "") and "~/ack-voice-studio/tool/downloads/models/speech-small-en/" == expected
    assert all(i.filename in GUIDE for i in model)


def test_the_folder_a_starting_voice_is_placed_in_by_hand_is_the_one_the_voices_command_looks_in_and_it_names_the_command_and_the_acknowledgment():
    from voice_studio.core import voices_flow
    expected = DataHome("~").voices + "/<voice>/"
    offline = section(6).replace("`", "")
    assert expected == "~/ack-voice-studio/tool/downloads/voices/<voice>/" and expected in offline
    assert "python3 -m voice_studio.voices get <voice>" in offline and "acknowledge" in offline and "get" in voices_flow.OPTIONS and (PKG / "voices.py").is_file()


def test_a_file_already_in_place_is_checked_by_size_and_checksum_and_skipped_which_is_what_the_offline_route_relies_on(tmp_path):
    item = next(i for i in reg.load_registry().items if i.filename == "config.json")
    folder = tmp_path / "models" / item.folder
    folder.mkdir(parents=True)
    (folder / item.filename).write_bytes(b"not the right content")
    assert not fetch.is_fetched(item, folder)
    assert "checks size and SHA-256" in GUIDE.replace("\n   ", " ") or "checks size and SHA-256" in GUIDE.replace("\n", " ")


# ---------------------------------------------------------------- the hosts

def test_the_hosts_the_code_knows_are_all_in_the_network_table_and_no_other_internet_host_is():
    table = section(5)
    for host in list(sp.PACKAGE_HOSTS) + list(reg.ALLOWED_HOSTS):
        assert "`%s`" % host in table or host in table, host
    mentioned = {m for m in re.findall(r"`([a-z0-9*.-]+\.[a-z]{2,})`", table) if not m.endswith((".conf", ".json", ".txt"))}      # file names are not hosts
    assert mentioned <= {"pypi.org", "files.pythonhosted.org", "huggingface.co", "*.hf.co", "us.aws.cdn.hf.co", "archive.ubuntu.com", "security.ubuntu.com", "github.com", "raw.githubusercontent.com"}, mentioned


def test_only_port_443_is_asked_for_and_nothing_is_said_to_be_inbound_by_voice_studio():
    assert "port 443" in section(5) and "No inbound ports" in section(2)
    assert "opens no listening port" in section(7) or "open no listening port" in section(7)


# ---------------------------------------------------------------- the machine

def test_the_ubuntu_packages_are_exactly_the_ones_the_set_up_asks_for_in_the_order_it_asks():
    packages = [r.package for r in preflight.REQUIREMENTS]
    command = "sudo apt-get install -y " + " ".join(packages)
    assert command in section(4)
    for package in packages:
        assert "`%s`" % package in section(4), package


def test_the_python_range_and_the_graphics_card_and_memory_figures_are_the_codes():
    python_min = ".".join(str(n) for n in preflight.MIN_PYTHON)
    top = max(spec.python_max for spec in load_environments() if spec.python_max)
    assert python_min + " to " + ".".join(str(n) for n in top) in section(2) or ("**3.10, 3.11 or 3.12**" in section(3) and top == (3, 12) and python_min == "3.10")
    assert str(preflight.GPU_MIN_MIB) .replace("900", ",900") in section(3) or "7,900 MiB" in section(3)
    assert preflight.GPU_MIN_MIB == 7900 and preflight.RAM_WARN_MIB == 7000 and "7,000 MiB" in section(3)


def test_the_disk_figures_are_the_ones_the_tool_computes_today():
    plan = sp.plan_setup(reg.load_registry(), load_environments(), free={"home": 500 * GIB})
    full = round(plan.verdict.need["home"] / GIB)
    minimum = round(plan.verdict.need_minimum["home"] / GIB)
    for number in (full, minimum):
        assert re.search(r"\b%d GiB\b" % number, section(3)) and re.search(r"\b%d GiB\b" % number, section(2)), number
    assert (full, minimum) == (63, 25)


def test_the_package_counts_and_the_nvidia_count_are_the_locks():
    lock_dir = PKG / "data" / "locks"
    training = (lock_dir / "training.lock.txt").read_text()
    studio = (lock_dir / "studio.lock.txt").read_text()
    count = lambda text: len(re.findall(r"^[A-Za-z0-9_.-]+==", text, flags=re.M))
    nvidia = len(re.findall(r"^nvidia-[a-z0-9-]+==", training, flags=re.M))
    assert (count(training), count(studio), nvidia) == (91, 46, 15)
    text = section(5) + section(8) + section(10)
    assert "91 packages" in text and "46 packages" in text and "**91**" in text and "**46**" in text and "**15**" in text and "15 packages" in text
    assert not re.search(r"^nvidia-", studio, flags=re.M), "the page says the studio list has none"


def test_the_flags_the_page_says_the_install_uses_are_the_ones_the_builder_uses():
    source = (PKG / "core" / "envbuild.py").read_text()
    for flag in ("--require-hashes", "--only-binary=:all:", "--no-deps"):
        assert flag in source and flag in section(8) + section(6)


# ---------------------------------------------------------------- what runs and listens

def test_the_offline_settings_the_page_names_are_the_ones_jobs_start_with():
    for name, value in jobs.OFFLINE_ENV.items():
        assert "`%s=%s`" % (name, value) in section(5), name                       # the value too: DO_NOT_TRACK=0 would be a different promise
    assert set(jobs.OFFLINE_ENV) == {"HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK", "TRANSFORMERS_OFFLINE"}


def test_the_optional_recording_server_is_described_as_the_code_has_it():
    freeform = (PKG.parent / "freeform_studio")
    main = (freeform / "__main__.py").read_text()
    assert 'default="127.0.0.1"' in main and "default=8001" in main
    assert "--host 0.0.0.0" in (freeform / "start.sh").read_text()
    text = section(7)
    assert "127.0.0.1" in text and "8001" in text and "0.0.0.0" in text


def test_the_waits_the_page_gives_are_the_connection_modules():
    assert connection.PAUSES_S == (5, 10, 20, 30, 60) and connection.PATIENCE_S == 30 * 60
    assert "(5, 10, 20, 30, then 60 seconds, for up to 30 minutes)" in GUIDE


def test_the_folder_names_the_page_gives_are_the_data_homes():
    home = DataHome("~")
    root = home.root
    assert root == "~/ack-voice-studio" and home.consent_file == root + "/state/consent.json"
    for needle in ("~/ack-voice-studio/", "~/ack-voice-studio/state/consent.json"):
        assert needle in GUIDE
    for folder in ("projects/", "tool/", "state/", "backups/"):
        assert folder in section(7)


# ---------------------------------------------------------------- what it must not say

@pytest.mark.parametrize("phrase", ["free for personal use", "you are allowed to use", "is permitted to use", "use is permitted", "legal to use", "licensed for personal"])
def test_the_page_never_says_or_implies_that_use_is_permitted(phrase):
    assert phrase not in GUIDE.lower().replace("nothing in this project says or implies that use is permitted", "")


def test_the_page_says_it_is_not_legal_advice_and_that_the_project_hosts_none_of_the_voices_and_that_amys_licence_is_not_established():
    text = section(10)
    assert "not legal advice" in section(10) + GUIDE[:0]
    assert "hosts, mirrors and sublicenses none of it" in text and "not established" in text and "Nothing in this project says or implies that use is permitted" in text


def test_the_licence_pages_the_tool_will_show_are_listed_exactly_and_the_page_says_they_are_shown_and_never_opened():
    pages = {address for item in reg.load_registry().items for _, address in item.pages}
    assert len(pages) == 3
    listed = set(re.findall(r"`(https://[^`]+)`", section(10)))
    assert pages <= listed, sorted(pages - listed)
    assert "never opens" in section(5) and "never opens" in section(10)
    assert not any(address in section(5) for address in pages), "the network table must not suggest these hosts are contacted"


def test_the_page_does_not_claim_the_licence_screen_exists_before_it_does():
    text = section(10)
    assert "designed to show" in text and "not built yet" in text and "the tool says so" not in text


def test_the_status_box_and_section_eleven_say_what_was_not_tested():
    assert "native Ubuntu" in GUIDE and "not** yet been run" in GUIDE.replace("*not*", "not") or "has **not** yet been run" in GUIDE
    for not_tested in ("Native Ubuntu", "A proxy, TLS inspection", "A training round with the network cut off", "Port-scanning"):
        assert not_tested in section(11), not_tested


def test_the_sections_are_numbered_without_a_gap():
    numbers = [int(n) for n in re.findall(r"^## (\d+)\. ", GUIDE, flags=re.M)]
    assert numbers == list(range(1, 14))


# ---------------------------------------------------------------- hearing a voice (plan task VS-5.4)

def test_the_page_names_every_audio_player_the_tool_may_start_and_the_one_windows_command():
    from voice_studio.core import listen, playback
    text = section(7)
    for name in set(playback.NATIVE_ORDER) | set(playback.WSL_ORDER):
        assert ("`%s`" % name in text) or name == "windows", name
    assert "powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand" in text and "System.Media.SoundPlayer" in text and "PlaySync()" in text and "wslpath -w" in text
    assert listen.RUNNER_MODULE in text and "python3 -m voice_studio.voicefile listen" in text and "scratch/listening" not in text and "sherpa-onnx 1.13.8" in text
    assert "the project's own `listening` folder" in text and "removed only by the tool's *Free up space* page or command" in text
    assert "opens no network connection" in text and "prints no sentence" in text


def test_the_page_describes_the_two_additions_to_listening_the_way_the_code_does():
    from voice_studio import hear_runner
    from voice_studio.core import listen
    from voice_studio.core.text import size_text
    text = section(7)
    assert listen.HEAR_MODULE in text and "python3 -m voice_studio.voicefile listen --round chosen" in text
    for name in hear_runner.OFFLINE:
        assert "`%s=1`" % name in text, name
    assert size_text(listen.ROUND_NEED_BYTES) in text, "the disk a round-mode listen may need, as the tool prints it"
    assert "makes no zip file" in text and "it is told no sentence" in text and "Neither addition opens a network connection" in text


def test_the_player_order_the_page_gives_is_the_order_in_the_code():
    from voice_studio.core import playback
    text = section(7)
    native = ", ".join("`%s`" % n for n in playback.NATIVE_ORDER)
    assert native in text
    wsl = ", ".join("`%s`" % n if n != "windows" else "Windows' own player" for n in playback.WSL_ORDER[:-1]) + ", then `%s`" % playback.WSL_ORDER[-1]
    assert wsl in text


def test_the_engine_version_the_page_gives_is_the_one_in_the_lock_and_the_one_the_phone_is_pinned_to():
    lock = (PKG / "data" / "locks" / "studio.lock.txt").read_text(encoding="utf-8")
    phone = (REPO / "app" / "libs" / "README.md").read_text(encoding="utf-8")
    assert "sherpa-onnx==1.13.8" in lock and "sherpa-onnx-core==1.13.8" in lock and "sherpa-onnx-1.13.8.aar" in phone and "sherpa-onnx 1.13.8" in section(7)
