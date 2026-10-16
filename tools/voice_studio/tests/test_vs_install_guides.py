# SPDX-License-Identifier: GPL-3.0-or-later
"""The two installation guides (`docs/ACK_Voice_Studio_Installation_Guide.MD` for Windows, `docs/ACK_Voice_Studio_Installation_Guide_Ubuntu.MD` for Ubuntu).

Each guide has to be readable on its own and must not say anything the code does not do. So every command in a code block is checked against the files and options that exist (the one-line
PowerShell command is the one install.ps1 holds, the Ubuntu one-liner is built from get.sh's own address and default release, every `python3 -m voice_studio...` command names a module and options
that are real, every PowerShell block parses, every shell block is valid shell), every sentence it quotes as what the tool prints is a sentence the tool prints (the catalog, the Windows helper's own
words, or the lines of get.sh), every button it names is a button, and every number it gives is the number the code uses. The prose has no jargon that the tool's own sentences avoid, and nothing in it
points the reader to another file as something to read first.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import test_vs_device_test_doc as device_doc
import test_vs_text as wording
from voice_studio.core import diskbudget, envspec, preflight, registry as reg, setupplan as sp, startvoice
from voice_studio.core import projects_flow as pf, voices_flow as vf, recordings_flow as rf, uninstall_flow as uf, update_flow as upf, reportcmd_flow as rcf, windowcli
from voice_studio.core.setup_flow import parse_options

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / "tools" / "voice_studio"
WIN, UBU = ROOT / "docs" / "ACK_Voice_Studio_Installation_Guide.MD", ROOT / "docs" / "ACK_Voice_Studio_Installation_Guide_Ubuntu.MD"
GUIDES = {"windows": WIN, "ubuntu": UBU}
SCRIPT_PS1 = (PKG / "install.ps1").read_text()
GET_SH = (PKG / "get.sh").read_text()
GIB = 2 ** 30
FENCE = re.compile(r"^[ \t]*```([a-z]*)\n(.*?)^[ \t]*```[ \t]*$", re.S | re.M)
PWSH = os.environ.get("ACK_VS_PWSH") or shutil.which("pwsh")

# words in backticks that are Windows' own names, not something this tool prints
NOT_THE_TOOLS = {"Terminal (Admin)", "Windows PowerShell (Admin)"}


def text_of(path):
    return path.read_text(encoding="utf-8")


def blocks(path, language):
    return ["\n".join(line.strip() for line in body.splitlines()) + "\n" for lang, body in FENCE.findall(text_of(path)) if lang == language]


def prose(path):
    """The guide without its code blocks."""
    return FENCE.sub("", text_of(path))


def spans(path):
    return re.findall(r"`([^`\n]+)`", prose(path))


def helper_texts():
    """The sentences install.ps1 prints (its text table)."""
    table = SCRIPT_PS1.split("function Get-AckVsText", 1)[1].split("function Format-AckVsText", 1)[0]
    return {key: value.replace("''", "'") for key, value in re.findall(r"^\s+([a-z0-9_]+)\s*=\s*'((?:[^']|'')*)'\s*$", table, re.M)}


def script_texts(name):
    return [m.replace("\\\"", "\"") for m in re.findall(r'(?:say|ask|ask_person) "([^"]*)"', (PKG / name).read_text())]


_real_catalog = device_doc.text_catalog_strings


def _extended():
    """Everything the tool says: the catalog, the Windows helper's own sentences, and the lines of the two shell scripts."""
    return _real_catalog() + list(helper_texts().values()) + script_texts("get.sh") + script_texts("setup.sh")


@pytest.fixture(autouse=True)
def the_corpus_includes_the_windows_helper_and_the_shell_scripts(monkeypatch):
    monkeypatch.setattr(device_doc, "text_catalog_strings", _extended)


# ================================================================ the files

@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_the_guide_exists_under_its_name_with_a_title_and_a_licence_free_body(path):
    assert path.is_file() and path.name.endswith(".MD")
    first = text_of(path).splitlines()[0]
    assert first.startswith("# ACK Voice Studio: Installation Guide for ")


def test_the_two_guides_are_named_for_the_two_systems():
    assert text_of(WIN).splitlines()[0] == "# ACK Voice Studio: Installation Guide for Windows"
    assert text_of(UBU).splitlines()[0] == "# ACK Voice Studio: Installation Guide for Ubuntu"
    assert WIN.name == "ACK_Voice_Studio_Installation_Guide.MD" and UBU.name == "ACK_Voice_Studio_Installation_Guide_Ubuntu.MD"


def test_each_guide_points_at_the_other_by_its_exact_file_name_and_says_which_to_use():
    assert "`%s`" % UBU.name in text_of(WIN) and "`%s`" % WIN.name in text_of(UBU)
    assert "If you use Ubuntu directly" in text_of(WIN) and "If you are on Windows" in text_of(UBU)


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_a_guide_stands_on_its_own_no_link_to_another_file_and_no_task_codes_or_pull_requests(path):
    body = text_of(path)
    assert not re.findall(r"\]\((?!https?://|#)[^)]*\)", body), "a markdown link to a file"
    assert "docs/" not in body and "../" not in body
    assert not re.search(r"\b(VS-\d|F\d\d\b|D\d\d\b|P\d\d\b|PR #|pull request)", body)
    assert "setup_plan" not in body.lower() and "device_test" not in body.lower() and "it_guide" not in body.lower()


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_the_prose_avoids_the_jargon_the_tools_own_sentences_avoid(path):
    jargon = [w for w in wording.JARGON if w != "python"]                      # the guide has to name the Python that comes with Ubuntu
    plain = re.sub(r"`[^`\n]+`", "", prose(path))
    found = [w for w in jargon if re.search(r"\b%s\b" % re.escape(w), plain, re.I)]
    assert not found, found


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_no_sentence_in_the_prose_is_a_wall_of_words(path):
    long = []
    for paragraph in re.split(r"\n\s*\n", prose(path)):
        if paragraph.lstrip().startswith("|") or paragraph.lstrip().startswith("#") or paragraph.strip() == "---":
            continue
        flat = re.sub(r"`[^`\n]+`", "X", re.sub(r"\*\*", "", paragraph))
        for sentence in re.split(r"(?<=[.!?:])\s+", flat):
            if len(sentence.split()) > 45:
                long.append(sentence[:90])
    assert not long, long


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_the_sections_are_numbered_in_order_without_a_gap(path):
    numbers = [int(n) for n in re.findall(r"^## (\d+)\. ", text_of(path), re.M)]
    assert numbers == list(range(1, len(numbers) + 1)) and len(numbers) >= 8


# ================================================================ the commands

def one_liner():
    return re.search(r"OneLiner\s*=\s*'([^']+)'", SCRIPT_PS1).group(1)


def get_sh_address():
    default = re.search(r'DEFAULT_TAG="([^"]+)"', GET_SH).group(1)
    return "https://raw.githubusercontent.com/ASPDesignLabs/ACK/%s/tools/voice_studio/get.sh" % default


def test_the_windows_guides_one_command_is_the_one_the_script_holds_and_it_comes_first():
    shells = blocks(WIN, "powershell")
    assert shells[0].strip() == one_liner()
    assert one_liner() in text_of(WIN)


def test_the_ubuntu_guides_one_command_is_built_from_get_shs_own_address_and_default_release():
    first = blocks(UBU, "bash")[0].strip()
    assert first == "curl -fsSL %s | bash" % get_sh_address()
    assert blocks(UBU, "bash")[1].strip() == "wget -qO- %s | bash" % get_sh_address()


def test_every_address_in_a_guide_is_a_raw_file_or_the_repository_the_script_names():
    for path in GUIDES.values():
        for address in set(re.findall(r"https?://[^\s`'\"|)]+", text_of(path))):
            assert address.startswith("https://raw.githubusercontent.com/ASPDesignLabs/ACK/"), (path.name, address)
            assert address.endswith(("install.ps1", "get.sh")), (path.name, address)
    assert re.search(r'REPO_URL="https://github.com/ASPDesignLabs/ACK.git"', GET_SH)


def test_the_release_a_guide_fetches_is_the_one_both_scripts_default_to_and_says_so():
    default = re.search(r"DefaultRef\s*=\s*'([^']+)'", SCRIPT_PS1).group(1)
    assert default == re.search(r'DEFAULT_TAG="([^"]+)"', GET_SH).group(1)
    assert "The default is `%s`." % default in text_of(WIN) and "The default is `%s`." % default in text_of(UBU)


def commands_of(path):
    found = []
    for lang in ("bash", "powershell"):
        for body in blocks(path, lang):
            for line in body.splitlines():
                if line.strip():
                    found.append((lang, line.strip()))
    return found


def modules_run(path):
    """(module, words after it) for every `python3 -m voice_studio...` command in a block."""
    found = []
    for lang, line in commands_of(path):
        match = re.search(r"-m (voice_studio[A-Za-z_.]*)(.*)$", line)
        if match:
            found.append((match.group(1), match.group(2).split("|")[0].split()))
    return found


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_every_voice_studio_command_names_a_real_module_and_options_it_takes(path):
    window_options = set(windowcli.OPTIONS)
    setup_options = {"--check", "--dry-run", "--yes", "-y", "--no-window"}
    seen = set()
    for module, words in modules_run(path):
        seen.add(module)
        assert (PKG.parent / (module.replace(".", "/") + ".py")).is_file() or (PKG.parent / module.replace(".", "/") / "__main__.py").is_file(), module
        options = [w for w in words if w.startswith("-")]
        if module == "voice_studio":
            assert parse_options(words)[0] is not None, words
        elif module == "voice_studio.window":
            assert set(options) <= window_options, options
        elif module == "voice_studio.projects":
            assert words[0] in pf.OPTIONS, words
        elif module == "voice_studio.uninstall":
            assert words[0] in uf.OPTIONS and set(options) <= set(uf.OPTIONS[words[0]]), words
        elif module == "voice_studio.report":
            assert words[0] in rcf.OPTIONS and set(options) <= set(rcf.OPTIONS[words[0]]), words
        elif module == "voice_studio.update":
            assert words[0] in upf.OPTIONS and set(options) <= set(upf.OPTIONS[words[0]]), words
        elif module == "voice_studio.voices":
            assert words[0] in vf.OPTIONS and set(options) <= (set(vf.OPTIONS[words[0]]) | {"--project"}), words
            if words[0] == "get":
                assert startvoice.find_voice(reg.load_registry(), words[1]) == "voice-mike", words
        else:
            pytest.fail("a command for a module this test does not know: " + module)
    assert {"voice_studio.window", "voice_studio.projects", "voice_studio.voices", "voice_studio.uninstall", "voice_studio.update", "voice_studio.report"} <= seen


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_the_path_the_commands_use_is_where_get_sh_puts_the_files(path):
    assert 'DEST="${ACK_VOICE_DIR:-$HOME/ack-tools}"' in GET_SH
    for _lang, line in commands_of(path):
        if "PYTHONPATH=" in line:
            assert "PYTHONPATH=~/ack-tools/tools" in line, line
    assert (PKG / "setup.sh").is_file() and "./tools/voice_studio/setup.sh" in text_of(UBU)
    assert "exec \"$DEST/tools/voice_studio/setup.sh\"" in GET_SH


def test_the_options_the_ubuntu_guide_lists_for_get_sh_are_the_ones_it_reads_and_the_settings_are_the_ones_it_uses():
    for flag in ("--yes", "--dry-run", "--check"):
        assert flag in GET_SH
    for setting in ("ACK_VOICE_TAG", "ACK_VOICE_DIR"):
        assert "${%s:-" % setting in GET_SH and "`%s`" % setting in text_of(UBU)


def test_the_windows_options_and_settings_are_the_ones_the_script_reads():
    reference = text_of(WIN).split("## 11. Reference", 1)[1]
    for option in re.findall(r"^\| `(-[A-Za-z]+)(?: name)?` \|", reference, re.M):
        assert re.search(r"'\^%s\$'" % option, SCRIPT_PS1), option
    for setting in re.findall(r"`(ACK_VOICE_[A-Z]+)`", reference):
        assert "'%s'" % setting in SCRIPT_PS1, setting
    for code in ("`0` done", "`1` something stopped it", "`2` nothing was done", "`3` a step is left for you"):
        assert code in reference
    assert "# Exit codes: 0 done" in SCRIPT_PS1 and "3 a step is left for you" in SCRIPT_PS1


def test_the_wsl_commands_the_windows_guide_gives_name_the_ubuntu_the_script_installs():
    install = re.search(r"InstallDistro\s*=\s*'([^']+)'", SCRIPT_PS1).group(1)
    body = text_of(WIN)
    assert install == "Ubuntu-24.04" and "wsl --unregister %s" % install in body and "Install WSL and Ubuntu 24.04 now?" in body
    for command in ("wsl --set-version", "wsl.exe --shutdown", "wsl --update"):
        assert command in body, command


@pytest.mark.skipif(not PWSH, reason="no PowerShell here")
def test_every_powershell_block_parses_without_an_error(tmp_path):
    for number, body in enumerate(blocks(WIN, "powershell") + blocks(UBU, "powershell")):
        script = tmp_path / ("block%d.ps1" % number)
        script.write_text(body)
        done = subprocess.run([PWSH, "-NoProfile", "-Command", "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('%s',[ref]$null,[ref]$e); @($e).Count" % script],
                              capture_output=True, text=True, timeout=60)
        assert done.stdout.strip() == "0", (body, done.stdout)


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_every_shell_block_is_valid_shell(path, tmp_path):
    for number, body in enumerate(blocks(path, "bash")):
        script = tmp_path / ("block%d.sh" % number)
        script.write_text(body)
        assert subprocess.run(["bash", "-n", str(script)], capture_output=True).returncode == 0, body


def test_the_wsl_settings_file_lines_are_the_ones_that_were_tested():
    text_blocks = blocks(WIN, "text")
    assert text_blocks and text_blocks[0].strip().splitlines() == ["[general]", "instanceIdleTimeout=-1"]


def test_the_backup_comes_before_the_edit_of_the_settings_file():
    shell = blocks(WIN, "powershell")
    joined = "\n".join(b for b in shell if "wslconfig" in b)
    assert joined.index("Copy-Item") < joined.index("notepad") and ".wslconfig.bak" in joined


def test_removing_says_back_up_first_and_names_a_place_that_is_not_synced_and_never_a_documents_folder():
    for path in GUIDES.values():
        removing = prose(path).split("**Removing.**", 1)[1]
        assert "make a copy of your projects first" in removing and "USB drive" in removing and "synced" in removing
        assert removing.count("Documents") <= 1 and ("Documents" not in removing or "Do not copy it into OneDrive, Dropbox or Documents, which may be synced." in removing)
        assert "This deletes your projects and recordings." in removing


# ================================================================ what the guides quote

def candidates(path):
    for span in spans(path):
        if span in NOT_THE_TOOLS:
            continue
        if re.match(r"^[A-Z][A-Za-z']+( |$)", span) and (" " in span) and not span.startswith(("PYTHONPATH", "ACK_VOICE")):
            yield span


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_every_sentence_or_button_name_a_guide_quotes_is_one_the_tool_says(path):
    corpus = _extended()
    missing = []
    for span in candidates(path):
        cut = span.endswith("…")
        if any(span in template for template in corpus) or device_doc.says(span, truncated=cut):
            continue
        missing.append(span)
    assert not missing, "the guide quotes what the tool does not say:\n" + "\n".join(missing)


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_a_guide_quotes_plenty_of_what_the_tool_prints_so_the_check_above_means_something(path):
    assert len(list(candidates(path))) >= 18


def test_the_windows_guide_quotes_the_windows_helpers_own_sentences_and_the_ubuntu_guide_get_shs():
    helper = list(helper_texts().values())
    assert sum(1 for span in candidates(WIN) if any(span in t for t in helper)) >= 8
    assert any(span in t for span in candidates(UBU) for t in script_texts("get.sh"))


def test_the_pages_and_buttons_of_the_window_are_named_as_the_window_names_them():
    strings = _real_catalog()
    for page in ("Projects", "Recordings", "Training rounds", "Voice file", "Free up space", "Display"):
        assert page in strings, page
    for guide in GUIDES.values():
        assert "pages for Projects, Recordings, Training rounds, Voice file, Free up space and Display" in text_of(guide)
    for button in ("New project…", "Bring in recordings…", "Get the listening model…", "Let the computer listen…", "Make a training set…", "See what a training set would hold",
                   "Start a round…", "Make the voice file…", "Show the folder", "Starting voice", "Choose later"):
        assert button in strings, button
        for guide in GUIDES.values():
            assert "`%s`" % button in text_of(guide), (button, guide.name)


def test_the_order_of_the_steps_in_the_window_is_the_order_the_buttons_can_be_used_in():
    for guide in GUIDES.values():
        body = text_of(guide)
        order = ["`New project…`", "`Bring in recordings…`", "`Get the listening model…`", "`Let the computer listen…`", "`Make a training set…`", "voice_studio.voices get", "`Start a round…`", "`Make the voice file…`"]
        positions = [body.index(item) for item in order]
        assert positions == sorted(positions)


# ================================================================ the numbers

def test_the_room_the_guides_ask_for_is_what_the_tool_computes_and_what_the_helper_checks():
    plan = sp.plan_setup(reg.load_registry(), envspec.load_environments(), free={"home": 500 * GIB})
    full = round(plan.verdict.need["home"] / GIB)
    minimum = round(plan.verdict.need_minimum["home"] / GIB)
    assert (full, minimum) == (63, 25)
    assert int(re.search(r"MinFreeGiB\s*=\s*(\d+)", SCRIPT_PS1).group(1)) == minimum
    for guide in GUIDES.values():
        body = text_of(guide)
        assert "At least %d GB free" % minimum in body and "About %d GB is comfortable" % full in body


def test_the_graphics_card_and_memory_the_guides_ask_for_are_the_tools_limits():
    assert preflight.GPU_MIN_MIB == 7900 and preflight.RAM_WARN_MIB == 7000
    for guide in GUIDES.values():
        body = text_of(guide)
        assert "8 GB or more of its own memory" in body and "About 8 GB of memory (RAM) or more" in body


def test_the_python_range_is_the_one_the_programs_are_built_for():
    top = max(spec.python_max for spec in envspec.load_environments() if spec.python_max)
    assert top == (3, 12) and preflight.MIN_PYTHON == (3, 10)
    assert "version 3.10, 3.11 or 3.12" in text_of(UBU)


def test_the_sizes_the_guides_quote_are_the_sizes_of_the_pinned_files_and_programs():
    items = reg.load_registry().items
    model = sum(i.size_bytes for i in items if i.kind == "model")
    assert abs(model - 485_000_000) < 3_000_000 and "485 MB" in text_of(WIN) and "485 MB" in text_of(UBU)
    voice = max(i.size_bytes for i in items if i.kind == "voice")
    assert abs(voice - 846_000_000) < 2_000_000 and "846 MB" in text_of(WIN) and "846 MB" in text_of(UBU)
    training = next(s for s in envspec.load_environments() if s.id == "training")
    assert training.approx_size_bytes == 10 * GIB and "about 10 GB free is needed while they are built" in text_of(WIN) and "about 10 GB free is needed while they are built" in text_of(UBU)


def test_the_download_total_is_the_sum_of_the_documented_downloads():
    # Ubuntu packages 233 MB + Python packages 3.3 GB + the listening model 483 MB + one starting voice 846 MB = about 4.9 GB
    assert round((233 + 3300 + 485 + 846) / 1000) == 5
    for guide in GUIDES.values():
        assert "about 5 GB in all" in text_of(guide)


def test_the_windows_build_floor_in_the_guide_is_the_first_windows_that_shows_linux_windows():
    assert int(re.search(r"MinBuild\s*=\s*(\d+)", SCRIPT_PS1).group(1)) == 19044
    assert "Windows 10 version 21H2 or newer" in text_of(WIN) and "21H2 or newer" in helper_texts()["windows_old"]


# ================================================================ honesty

def test_the_windows_guide_says_what_has_and_has_not_been_run_on_a_real_windows():
    body = text_of(WIN).split("## 12. What has been tested", 1)[1]
    assert "**Not yet run on a real, clean Windows:**" in body and "**With stand-ins, not on Windows:**" in body and "**On a real computer**" in body


def test_the_ubuntu_guide_says_a_plain_ubuntu_desktop_has_not_been_tried():
    assert "A normal Ubuntu desktop on its own hardware has not been tried yet." in text_of(UBU)


def test_neither_guide_says_or_implies_that_using_a_voice_is_allowed():
    for guide in GUIDES.values():
        body = text_of(guide).lower()
        assert "the tool says nothing about whether your use of a voice is allowed" in body
        for phrase in ("free for personal use", "you are allowed to use", "is permitted to use", "legal to use", "licensed for personal"):
            assert phrase not in body


def test_neither_guide_claims_an_effect_or_calls_the_tool_clinical():
    for guide in GUIDES.values():
        body = text_of(guide).lower()
        for word in ("clinical", "therapy", "therapeutic", "medical", "cure", "improves", "proven"):
            assert not re.search(r"\b%s\b" % word, body), word


def test_neither_guide_tells_the_reader_to_turn_off_a_security_feature_or_to_use_an_administrator_for_everything():
    for guide in GUIDES.values():
        body = text_of(guide).lower()
        for phrase in ("disable your antivirus", "turn off the firewall", "set-executionpolicy", "unrestricted", "chmod 777", "run everything as root", "sudo su"):
            assert phrase not in body
    assert "never changes powershell's script rules" in text_of(WIN).lower()


# ================================================================ the checklist section for the installation

def checklist_section():
    body = (ROOT / "docs" / "VOICE_STUDIO_DEVICE_TEST.md").read_text(encoding="utf-8")
    return body.split("## I7. Installing from scratch", 1)[1].split("## J. Making the voice file", 1)[0]


def test_the_checklist_section_for_the_installation_quotes_only_what_the_tool_says():
    corpus = _extended()
    quoted = [s for s in re.findall(r"`([^`\n]+)`", checklist_section()) if re.match(r"^[A-Z][A-Za-z']+ ", s) and s not in NOT_THE_TOOLS]
    missing = [s for s in quoted if not (any(s in t for t in corpus) or device_doc.says(s.rstrip("…").rstrip(), truncated=s.endswith("…")))]
    assert len(quoted) >= 15 and not missing, missing


def test_the_checklist_section_names_both_guides_and_the_commands_the_guides_give():
    body = checklist_section()
    assert WIN.name in body and UBU.name in body and one_liner() in body
    assert "irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/install.ps1 | iex" in body
    for option in ("ACK_VOICE_CHECK", "ACK_VOICE_DRYRUN", "-Distro", "-Ref", "ACK_VOICE_TAG"):
        assert option in body


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_the_guides_say_updating_asks_first_never_touches_the_running_copy_and_is_not_automatic(path):
    body = " ".join(text_of(path).split())
    for claim in ("Each says first what it will ask github.com and shows the exact commands, then asks before it contacts anything.", "`get` never touches this copy",
                  "you type them", "If ACK Voice Studio has not named a release yet, `check` says so.", "The phone app's own version names are not releases of this tool and are not listed.", "no automatic update checks", "when you run the update command in section"):
        assert claim in body, claim
    assert "no update checks" not in body


@pytest.mark.parametrize("path", GUIDES.values(), ids=GUIDES.keys())
def test_the_guides_say_the_problem_report_is_shown_first_saved_where_you_say_and_never_sent(path):
    body = " ".join(text_of(path).split())
    for claim in ("A command that fails after it began ends with two lines about a problem report.", "with your names and folders blanked and no recordings, no text you made and no phrases",
                  "You see all of it first, and it is saved only where you say", "`show` prints the report and changes nothing.", "never replaces a file unless you add `--replace`",
                  "the tool never sends it anywhere", "give the file to the helper yourself"):
        assert claim in body, claim
