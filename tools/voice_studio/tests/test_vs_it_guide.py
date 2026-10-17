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


def test_only_port_443_is_asked_for_and_the_one_listener_is_said_to_be_the_send_command():
    assert "port 443" in section(5) and "No inbound ports, except one optional command" in section(2)
    assert "open no listening port" in section(7) and "listens only during `voicefile send`" in section(7)
    assert "core/lansend.py" in section(5) and "core/lansend.py" in section(7)


def test_what_the_guide_says_about_the_listener_is_what_the_code_does():
    from voice_studio.core import lansend, phonecert
    text = section(7)
    assert "at most ten minutes" in text and lansend.MINUTES == 10
    assert "port %d" % lansend.DEFAULT_PORT in text
    assert "twelve requests" in text and lansend.MAX_STRANGERS == 12
    assert "(seven days)" in text and phonecert.LEAF_DAYS == 7
    assert "valid for two years" in text and phonecert.AUTHORITY_DAYS == 730
    assert "22 characters" in text and len(lansend.new_token()) == 22
    assert [low for low, _mask in phonecert.PRIVATE_RANGES] == ["10.0.0.0", "172.16.0.0", "192.168.0.0"]
    assert "`10.`, `172.16.` to `172.31.` or `192.168.`" in text
    assert "~/ack-voice-studio/state/phone-certificate/" in text and phonecert.folder(DataHome("~/ack-voice-studio")).endswith("/state/phone-certificate")
    assert "`openssl`" in text
    assert "I16" in text


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


# ---------------------------------------------------------------- backing up a project (plan task VS-6.1)

def test_the_page_describes_the_backup_the_way_the_code_does():
    from voice_studio.core import projectbackup as pb
    text = section(7)
    home = DataHome("~")
    assert "python3 -m voice_studio.backup now" in text and "python3 -m voice_studio.backup restore" in text
    assert home.backups == "~/ack-voice-studio/backups" and "`" + home.backups + "`" in text
    assert "`state/%s`" % pb.STATE_FILE in text and home.state == "~/ack-voice-studio/state"
    for claim in ("one plain, uncompressed `.tar` file", "a small `.tar.json` note", "`.partial` name", "**read back in full**", "SHA-256", "**never replaces, prunes or removes a backup**",
                  "only adds what is missing and never overwrites a file", "refuses while a task of that project is running", "never inside a backup", "has not been backed up yet", "has changed since the last backup"):
        assert claim in text, claim
    for left_out in ("working files and training sets", "the test sounds", "older saved points", "the trainer's logs", "earlier backups"):
        assert left_out in text, left_out
    assert pb.PARTS == ("record", "recordings", "packages", "rounds", "saved_points", "exports") and pb.MANIFEST == "MANIFEST.json"


def test_the_backup_code_uses_no_network_as_the_page_says():
    names = ("core/projectbackup.py", "core/backup_flow.py", "core/backupnudge.py", "backup.py")
    for name in names:
        source = (PKG / name).read_text(encoding="utf-8")
        imports = " ".join(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_.]+)", source, flags=re.M))
        for banned in ("socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib", "webbrowser", "subprocess"):
            assert not re.search(r"(^| )%s(\.|$| )" % banned, imports), (name, banned)
    assert "(a test reads the source for it)" in section(7)


def test_the_page_says_a_backup_is_personal_data_not_encrypted_and_not_sent_anywhere_and_what_was_not_tested():
    nine, eleven, twelve = section(9), section(11), section(12)
    for claim in ("**not encrypted**", "refuses a folder inside a project", "looks synchronised", "never sends a backup anywhere"):
        assert claim in nine, claim
    assert "Backing up a project (`python3 -m voice_studio.backup`)" in eleven and "checklist section I9" in eleven and "a folder that a cloud service really synchronises" in eleven
    assert "so a backup kept there is deleted with it" in twelve and "`--to`" in twelve


# ---------------------------------------------------------------- checking the tool and refreshing it (plan task VS-6.6)

def test_the_page_describes_refresh_the_way_the_code_does():
    from voice_studio.core import envgen, refresh_flow
    text = section(7)
    for command in refresh_flow.COMMANDS:
        if command != "help":
            assert "python3 -m voice_studio.refresh %s" % command in text or "`%s`" % command in text or "%s --remove" % command in text, command
    assert "`state/%s`" % envgen.FILE in text
    for claim in ("writing nothing, not even to its log", "byte for byte", "reaches no network", "never deletes, a note that cannot be read", "a **second whole copy**", "a generation number",
                  "the old copy stays in use until then", "`--yes` does not answer it", "never one that is being built", "never while a task is running", "only the list that was shown",
                  "None of it touches a project, a recording, a round, a finished voice or a backup."):
        assert claim in text, claim
    assert "Checking and refreshing the tool (`python3 -m voice_studio.refresh`)" in section(11) and "checklist section I10" in section(11)


def test_the_check_and_the_list_of_old_copies_reach_no_network_and_only_a_repair_fetches():
    import ast
    def uses(path, module):
        return sorted({node.attr for node in ast.walk(ast.parse((PKG / path).read_text())) if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == module})
    assert uses("core/refresh.py", "fetch") == ["is_fetched"], "the library only reads the disk against what was agreed"
    assert uses("core/refresh_flow.py", "fetch") == ["FetchError", "fetch_patiently"]
    flow = ast.parse((PKG / "core/refresh_flow.py").read_text())
    callers = {fn.name for fn in ast.walk(flow) if isinstance(fn, ast.FunctionDef) and any(isinstance(n, ast.Attribute) and n.attr == "fetch_patiently" for n in ast.walk(fn))}
    assert callers == {"_fetch_again"}
    for name in ("core/refresh.py", "core/refresh_flow.py", "core/envgen.py", "refresh.py"):
        imports = " ".join(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_.]+)", (PKG / name).read_text(), flags=re.M))
        for banned in ("socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib", "webbrowser", "subprocess"):
            assert not re.search(r"(^| )%s(\.|$| )" % banned, imports), (name, banned)



# ---------------------------------------------------------------- removing the programs and downloads (plan task VS-6.3)

def test_the_page_describes_uninstall_the_way_the_code_does():
    from voice_studio.core import uninstall, uninstall_flow
    text = section(7)
    for command in uninstall_flow.COMMANDS:
        if command != "help":
            assert "python3 -m voice_studio.uninstall %s" % command in text, command
    for claim in ("changes nothing", "asks once", "removes only what was shown", "a folder that carries this tool's own record and is not being built", "`tool/environments`", "`tool/downloads`",
                  "never removes a project, a recording, a round, a finished voice, a backup (`backups/`), the starting voices (`tool/downloads/voices`", "`state/`", "refuses while any task is running",
                  "removes a link as a link and never follows it", "removes nothing if what is there is no longer what it showed", "`--remove-launcher`", "It contacts no network."):
        assert claim in text, claim
    assert uninstall.KEPT_VOICES == "voices" and uninstall.KEPT == ("backups", "voices", "state")
    assert "Removing the programs and downloads (`python3 -m voice_studio.uninstall`)" in section(11) and "checklist section I11" in section(11)
    twelve = section(12)
    assert "`python3 -m voice_studio.uninstall remove` takes the programs the tool built and the files it downloaded off the disk and nothing else" in twelve and "copy them out first" in twelve


def test_uninstall_reaches_no_network_starts_no_program_and_removes_only_through_the_one_remover():
    import ast
    for name in ("core/uninstall.py", "core/uninstall_flow.py", "uninstall.py"):
        imports = " ".join(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_.]+)", (PKG / name).read_text(), flags=re.M))
        for banned in ("socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib", "webbrowser", "subprocess", "shutil"):
            assert not re.search(r"(^| )%s(\.|$| )" % banned, imports), (name, banned)
    for name in ("core/uninstall.py", "core/uninstall_flow.py"):
        calls = {node.func.attr for node in ast.walk(ast.parse((PKG / name).read_text())) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        assert not calls & {"rmtree", "unlink", "removedirs", "rename", "replace", "write_text", "write_bytes", "open", "system", "popen", "run", "Popen"}, (name, calls)
        assert ("remove" in calls) == (name == "core/uninstall_flow.py"), "only the front calls the library's remove"
    flow = (PKG / "core/uninstall_flow.py").read_text()
    assert "un.remove(" in flow and flow.count("un.remove(") == 1, "the flow removes through the library's remove, called from one place"


# ---------------------------------------------------------------- moving a project's scratch (plan task VS-6.5)

def test_the_page_describes_moving_scratch_the_way_the_code_does():
    from voice_studio.core import scratchmove, scratchmove_flow
    text = section(7)
    for command in scratchmove_flow.COMMANDS:
        if command != "help":
            assert "python3 -m voice_studio.scratch %s" % command in text, command
    for claim in ("changes nothing", "asks once", "only then", "`project.json.previous`", "the same command carries on", "`--yes` does not answer", "removes only a folder this tool made",
                  "refuses while any task for the project is running", "checked again just before the switch", "readable by the person only", "never follows a link", "contacts no network",
                  "a folder that looks cloud-synchronised", "cannot yet be rebuilt"):
        assert claim in text, claim
    assert scratchmove.PARTIAL == ".partial"
    assert "Moving a project's scratch (`python3 -m voice_studio.scratch`)" in section(11) and "checklist section I12" in section(11)


def test_moving_scratch_reaches_no_network_starts_no_program_and_switches_only_after_the_copy_is_checked():
    import ast
    for name in ("core/scratchmove.py", "core/scratchmove_flow.py", "scratch.py"):
        imports = " ".join(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_.]+)", (PKG / name).read_text(), flags=re.M))
        for banned in ("socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib", "webbrowser", "subprocess", "shutil"):
            assert not re.search(r"(^| )%s(\.|$| )" % banned, imports), (name, banned)
    flow = ast.parse((PKG / "core/scratchmove_flow.py").read_text())
    move = next(n for n in ast.walk(flow) if isinstance(n, ast.FunctionDef) and n.name == "_move")
    order = [n.func.attr for n in ast.walk(move) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "sm"
             and n.func.attr in ("prepare_target", "copy_tree", "check_copy", "switch")]
    assert order == ["prepare_target", "copy_tree", "check_copy", "switch"], "the project is switched only after the copy is made and checked"
    source = (PKG / "core/scratchmove.py").read_text()
    assert source.count("save_project(") == 1 and "def switch(" in source[:source.index("save_project(")], "the project's record is written in one place, the switch"


# ---------------------------------------------------------------- updating the tool (plan task VS-6.2)

def test_the_page_describes_updating_the_way_the_code_does():
    from voice_studio.core import update, update_flow
    text = section(7)
    for command in update_flow.COMMANDS:
        if command != "help":
            assert "python3 -m voice_studio.update %s" % command in text, command
    source = reg.load_release_source()
    for claim in ("A release is a git tag", "asks once", "git ls-remote --tags " + source.url, "git clone --depth 1 --branch %sRELEASE %s" % (source.tag_prefix, source.url), "GIT_TERMINAL_PROMPT=0",
                  "nothing is saved and nothing is ever checked in the background", "(at most 64)", "no program started for that", "A folder that already exists is never used and never removed",
                  "**cannot replace the folder it is running from**", "two `mv` commands", "touches no project, recording, round, finished voice or backup", "No tag beginning with `%s` exists yet" % source.tag_prefix, "A release is a git tag whose name begins with `%s`" % source.tag_prefix,
                  "the phone app's tags (`v1.0-beta.1` and the rest)"):
        assert claim in text, claim
    assert source.tag_prefix == "voice-studio-" and "**No release has been tagged yet**" not in text
    assert update.RELEASE_NAME.match("x" * 64) and not update.RELEASE_NAME.match("x" * 65)
    assert 'GIT_TERMINAL_PROMPT="0"' in (PKG / "core/fetch.py").read_text()
    assert "Updating the tool (`python3 -m voice_studio.update`)" in section(11) and "checklist section I13" in section(11)
    five = section(5)
    assert "python3 -m voice_studio.update" in five and "no automatic update check" in five and "no update check," not in five


def test_updating_reaches_the_network_only_through_the_download_module_and_replaces_nothing():
    import ast
    for name in ("core/update.py", "core/update_flow.py", "update.py"):
        imports = " ".join(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_.]+)", (PKG / name).read_text(), flags=re.M))
        for banned in ("socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib", "webbrowser", "subprocess", "shutil"):
            assert not re.search(r"(^| )%s(\.|$| )" % banned, imports), (name, banned)
    for name in ("core/update.py", "core/update_flow.py"):
        calls = {node.func.attr for node in ast.walk(ast.parse((PKG / name).read_text())) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        assert not calls & {"rmtree", "unlink", "removedirs", "rename", "replace", "write_text", "write_bytes", "system", "popen", "run", "Popen"}, (name, calls)
    library = (PKG / "core/update.py").read_text()
    assert library.count("networked(") == 2 and library.count("remove_tree(dest, [])") == 1, "two requests (the list and the fetch), and one remover that is only given the folder the fetch made"
    assert "mv " in (PKG / "core/update_flow.py").read_text() and "os.rename" not in (PKG / "core/update_flow.py").read_text(), "the switch is printed for the person to type, never done"


# ---------------------------------------------------------------- the problem report (plan task VS-6.4)

def test_the_page_describes_the_problem_report_the_way_the_code_does():
    from voice_studio.core import report, reportcmd, reportcmd_flow
    text = section(7)
    for command in reportcmd_flow.COMMANDS:
        if command != "help":
            assert "python3 -m voice_studio.report %s" % command in text, command
    for claim in ("prints all of it", "asks once", "writes exactly that text to the one file named", "the last 60 lines of that task's log, each cut to 300 characters", "**no place for a recording, a transcript or a phrase**",
                  "**contacts no network and starts no program**", "makes no folder", "never replaces a file unless `--replace` is given", "readable by its owner only", "reads it back and removes it if it differs",
                  "removes a half-written file of its own on a failure or Ctrl+C", "warns, and does not refuse, when the folder looks cloud-synchronised", "ends with two lines pointing at it",
                  "a command that was declined or could not ask gets none", "when there was exactly one", "a name of one letter is not hidden", "which is why the log is opt-in"):
        assert claim in text, claim
    assert report.MAX_LOG_LINES == 60 and report.MAX_LINE_CHARS == 300 and report.MIN_NAME == 2 and report.SHORT_NAME == 4
    assert "The problem report (`python3 -m voice_studio.report`)" in section(11) and "checklist section I14" in section(11)
    assert "A problem report is a copy of facts about the computer" in section(9) and "never sent by the tool" in section(9)


def test_the_problem_report_reaches_no_network_starts_no_program_and_writes_only_the_one_file_it_was_told():
    import ast
    for name in ("core/reportcmd.py", "core/reportcmd_flow.py", "report.py", "core/report.py"):
        imports = " ".join(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_.]+)", (PKG / name).read_text(), flags=re.M))
        for banned in ("socket", "urllib", "http", "requests", "ssl", "ftplib", "smtplib", "webbrowser", "subprocess", "shutil"):
            assert not re.search(r"(^| )%s(\.|$| )" % banned, imports), (name, banned)
    for name in ("core/reportcmd_flow.py", "report.py"):
        calls = {node.func.attr for node in ast.walk(ast.parse((PKG / name).read_text())) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        assert not calls & {"rmtree", "unlink", "removedirs", "rename", "replace", "write_text", "write_bytes", "system", "popen", "run", "Popen", "makedirs", "mkdir"}, (name, calls)
    library = (PKG / "core/reportcmd.py").read_text()
    assert library.count("os.unlink(") == 1 and "makedirs" not in library and "mkdir" not in library and library.count("write_report(") == 1, "one file is written, and only a half-written file of its own is removed"


# ---------------------------------------------------------------- the window

def test_the_window_paragraph_names_every_page_the_window_has_in_the_order_of_its_list_and_says_which_can_reach_the_internet():
    from voice_studio.core import text as catalog_text, windowmodel
    cat = catalog_text.load_catalog("en")
    paragraph = " ".join(next(line for line in GUIDE.splitlines() if line.startswith("* **The window (")).split())
    numbers = {9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen"}
    assert "opens one window with %s pages:" % numbers[len(windowmodel.PAGES)] in paragraph
    places = [paragraph.index(cat.t("window.nav." + page)) for page in windowmodel.PAGES]
    assert places == sorted(places) and len(set(places)) == len(places), "every page is named once, in the order of the window's list"
    assert "Updates (a look at which releases exist, and fetching one) and on Check the tool (the buttons that mend or build fresh, which can download again)" in paragraph
    assert "Hear the voice, Backup and Problem report contact nothing" in paragraph
    status = " ".join(GUIDE.split("## 1.", 1)[0].split())
    assert "a window with pages for projects, recordings, training rounds, hearing a voice, the voice file, backup, freeing up space, checking the tool, updates and problem reports" in status


def test_what_the_guide_says_about_the_windows_file_is_what_the_code_does():
    from voice_studio.core import wsl, wsl_flow
    text, top = section(7), section(2)
    assert "**The tool never restarts WSL and never runs a firewall command.**" in text and "One file on the Windows side, only on a typed yes" in top
    assert "`networkingMode=mirrored` under `[wsl2]`" in text and (wsl.KEY_NETWORK, wsl.MIRRORED, wsl.SECTION_NETWORK) == ("networkingMode", "mirrored", "wsl2")
    assert "`instanceIdleTimeout=-1` under `[general]`" in text and (wsl.KEY_IDLE, wsl.NEVER, wsl.SECTION_IDLE) == ("instanceIdleTimeout", "-1", "general")
    assert "ten-second limit" in text and wsl.INTEROP_TIMEOUT_S == 10.0 and "`cmd.exe /c ver`" in text and "`cmd.exe /c echo %USERPROFILE%`" in text
    assert "`.wslconfig.bak`" in text and wsl.CONFIG_NAME == ".wslconfig" and "`wslinfo --networking-mode`" in text and "`--windows-user`" in text
    assert "`New-NetFirewallHyperVRule`" in text and wsl.firewall_commands(8443)[0].startswith("New-NetFirewallHyperVRule ") and "8443 unless told otherwise" in text and wsl_flow.DEFAULT_PORT == 8443
    assert "the command was not tried by the tool's author" in text and "section I17" in text
