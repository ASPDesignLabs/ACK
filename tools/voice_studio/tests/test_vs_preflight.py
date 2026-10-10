# SPDX-License-Identifier: GPL-3.0-or-later
"""Preflight (plan task VS-1.2): the parsers, the thresholds at their exact edges, and the whole report for typical computers."""
import pytest

from vs_fakes import (ALL_PACKAGES, DEBIAN_12, LINUX_MINT, MEM_16G, MEM_4G, MEM_8G, PROC_NATIVE, PROC_WSL1, PROC_WSL2, SMI_3090, SMI_4060,
                      SMI_6G, SMI_DRIVER_DOWN, SMI_TWO, UBUNTU_2004, UBUNTU_2204, UBUNTU_2404, FakeSystem, wsl2)
from voice_studio.core import preflight as pf
from voice_studio.core.preflight import GpuState, Platform, Status
from voice_studio.core.system import CommandResult, RealSystem


# ---------------------------------------------------------------- os-release

def test_os_release_of_the_two_supported_releases():
    for text, version in ((UBUNTU_2404, "24.04"), (UBUNTU_2204, "22.04")):
        info = pf.parse_os_release(text)
        assert (info.id, info.version_id) == ("ubuntu", version) and pf.is_supported_os(info)
    assert "24.04" in pf.parse_os_release(UBUNTU_2404).name


@pytest.mark.parametrize("text", [UBUNTU_2004, LINUX_MINT, DEBIAN_12])
def test_other_releases_and_other_distributions_are_not_the_supported_pair(text):
    assert not pf.is_supported_os(pf.parse_os_release(text))


def test_os_release_reading_is_forgiving():
    info = pf.parse_os_release("# comment\n\nID='ubuntu'\nVERSION_ID=\"22.04\"\nnot a pair\nPRETTY_NAME=Plain\n")
    assert (info.id, info.version_id, info.name) == ("ubuntu", "22.04", "Plain")
    assert pf.parse_os_release(None) == pf.OsInfo() and pf.parse_os_release("") == pf.OsInfo()
    assert pf.parse_os_release(LINUX_MINT).id_like == ("ubuntu", "debian")
    assert not pf.is_supported_os(pf.parse_os_release("ID=ubuntu\n"))        # no version at all


def test_an_ubuntu_point_release_number_is_not_mistaken_for_the_supported_version():
    assert not pf.is_supported_os(pf.OsInfo(id="ubuntu", version_id="24.10"))
    assert not pf.is_supported_os(pf.OsInfo(id="ubuntu", version_id="22.04.5"))      # VERSION_ID has no patch number; if it did, do not guess


# ---------------------------------------------------------------- native or WSL

@pytest.mark.parametrize("proc, env, expected", [
    (PROC_NATIVE, {}, Platform.NATIVE),
    (PROC_WSL2, {}, Platform.WSL2),
    (PROC_WSL1, {}, Platform.WSL1),
    (PROC_WSL1, {"WSL_DISTRO_NAME": "Ubuntu"}, Platform.WSL1),          # the kernel string wins over the variable
    (None, {"WSL_DISTRO_NAME": "Ubuntu-24.04"}, Platform.WSL2),
    (None, {"WSL_INTEROP": "/run/WSL/1_interop"}, Platform.WSL2),
    (None, {}, Platform.NATIVE),
    ("", {}, Platform.NATIVE),
])
def test_wsl_is_told_from_native_and_wsl_2_from_wsl_1(proc, env, expected):
    assert pf.detect_platform(proc, env) is expected


# ---------------------------------------------------------------- the GPU

def test_one_gpu_is_read_with_its_memory_and_driver():
    report = pf.parse_nvidia_smi(0, SMI_4060)
    assert report.state is GpuState.OK
    assert report.best == pf.Gpu("NVIDIA GeForce RTX 4060", 8188, "560.35.03")


def test_the_largest_gpu_decides_when_there_are_two():
    report = pf.parse_nvidia_smi(0, SMI_TWO)
    assert report.best.name == "NVIDIA GeForce RTX 4060" and report.state is GpuState.OK and len(report.gpus) == 2


@pytest.mark.parametrize("mib, state", [(pf.GPU_MIN_MIB - 1, GpuState.SMALL), (pf.GPU_MIN_MIB, GpuState.OK), (pf.GPU_MIN_MIB + 1, GpuState.OK),
                                        (6144, GpuState.SMALL), (8188, GpuState.OK), (8192, GpuState.OK), (24576, GpuState.OK), (0, GpuState.SMALL)])
def test_gpu_memory_is_judged_at_its_exact_edge(mib, state):
    assert pf.parse_nvidia_smi(0, "Some GPU, %d, 535.1\n" % mib).state is state


def test_the_provisional_gpu_limit_still_lets_every_real_8_gb_card_through():
    assert pf.GPU_MIN_MIB < 8188 and pf.GPU_MIN_MIB > 6144


def test_a_failing_nvidia_smi_is_an_error_state_not_a_crash():
    report = pf.parse_nvidia_smi(9, SMI_DRIVER_DOWN)
    assert report.state is GpuState.ERROR and report.error.startswith("NVIDIA-SMI has failed") and not report.gpus
    assert pf.parse_nvidia_smi(18, "", "Failed to initialize NVML: Driver/library version mismatch\n").error.startswith("Failed to initialize NVML")
    assert len(pf.parse_nvidia_smi(9, "x" * 500).error) == 200


@pytest.mark.parametrize("text", ["", "\n\n", "garbage with no commas\n", " , 1, 2\n"])
def test_output_with_no_readable_gpu_is_none(text):
    assert pf.parse_nvidia_smi(0, text).state is GpuState.NONE


def test_an_unreadable_memory_figure_is_unknown_not_zero():
    report = pf.parse_nvidia_smi(0, "NVIDIA Thing, [N/A], 535.1\n")
    assert report.state is GpuState.UNKNOWN and report.gpus[0].memory_mib is None


def test_a_gpu_name_with_a_comma_keeps_its_name():
    assert pf.parse_nvidia_smi(0, "NVIDIA RTX, Special Edition, 12282, 535.1\n").best.name == "NVIDIA RTX, Special Edition"


# ---------------------------------------------------------------- memory and packages

@pytest.mark.parametrize("text, mib", [(MEM_16G, 15741), ("MemTotal: 1024 kB\n", 1), ("MemTotal: 1023 kB\n", 0), ("nothing\n", None), (None, None)])
def test_meminfo(text, mib):
    assert pf.parse_meminfo_mib(text) == mib


def test_dpkg_status_lines():
    out = "git installed\ncmake not-installed\nffmpeg config-files\n\nodd line here too\n"
    assert pf.parse_dpkg_status(out) == {"git"}


def test_the_package_list_is_what_the_plan_says_and_each_has_a_reason():
    assert [r.package for r in pf.REQUIREMENTS] == ALL_PACKAGES
    assert all(r.why_key.startswith("apt.why.") for r in pf.REQUIREMENTS) and len({r.why_key for r in pf.REQUIREMENTS}) == len(pf.REQUIREMENTS)


def test_nothing_is_missing_on_a_complete_system():
    assert pf.missing_requirements(FakeSystem()) == ()


def test_a_package_dpkg_does_not_know_is_missing_unless_the_thing_is_there_another_way():
    system = FakeSystem(installed=[], tools={}, failing_probes=("import",))      # no tools, no Python modules, nothing installed
    assert [r.package for r in pf.missing_requirements(system)] == ALL_PACKAGES
    only_by_tool = FakeSystem(installed=[], failing_probes=("ensurepip", "import gi"))     # tools on the PATH satisfy their packages
    assert {r.package for r in pf.missing_requirements(only_by_tool)} == {"python3-venv", "python3-dev", "python3-gi", "gir1.2-gtk-4.0"}


def test_gtk_and_the_python_binding_are_probed_separately():
    no_typelib = FakeSystem(installed=["python3-gi", "python3-dev"], failing_probes=("require_version",))
    assert [r.package for r in pf.missing_requirements(no_typelib)] == ["gir1.2-gtk-4.0"]


def test_missing_requirements_survives_dpkg_not_running_at_all():
    class NoDpkg(FakeSystem):
        def run(self, argv, timeout=15.0):
            return None if argv[0] == "dpkg-query" else super().run(argv, timeout)
    assert {r.package for r in pf.missing_requirements(NoDpkg(tools={}))} >= {"git", "cmake"}


# ---------------------------------------------------------------- the whole report

def ids(checks):
    return [c.id for c in checks]


def test_a_healthy_native_ubuntu_24_04_passes_everything():
    report = pf.run_preflight(FakeSystem())
    assert report.can_continue and not report.warnings and not report.blockers
    assert report.platform is Platform.NATIVE and report.gpu.state is GpuState.OK and report.missing == ()
    assert report.check("os").key == "preflight.os.supported" and report.check("gpu").args["memory_mib"] == 8188
    assert report.disks == {"/home/user": (500 * 2**30, 300 * 2**30)}


def test_check_ids_are_unique_and_every_key_is_namespaced():
    report = pf.run_preflight(wsl2(installed=[], tools={"apt-get": "/usr/bin/apt-get"}, euid=1000))
    assert len(set(ids(report.checks))) == len(report.checks)
    assert all(c.key.startswith("preflight.") for c in report.checks)


def test_wsl2_on_ubuntu_22_04_without_a_gpu_can_still_go_on():
    report = pf.run_preflight(wsl2(os_release=UBUNTU_2204, python=(3, 10, 12), smi=None))
    assert report.can_continue and report.platform is Platform.WSL2 and report.gpu.state is GpuState.NONE
    assert report.check("gpu").status is Status.WARN and report.check("gpu").key == "preflight.gpu.none"
    assert "/mnt/c" in report.disks                      # the Windows system drive is measured on WSL 2


def test_no_nvidia_smi_program_at_all_is_no_gpu_and_the_wsl_location_is_tried():
    tools = {k: v for k, v in FakeSystem().tools.items() if k != "nvidia-smi"}
    assert pf.run_preflight(FakeSystem(tools=tools)).gpu.state is GpuState.NONE
    found = pf.run_preflight(wsl2(tools=tools, present={"/mnt/wslg", "/mnt/c", pf.WSL_NVIDIA_SMI}))
    assert found.gpu.state is GpuState.OK


def test_a_gpu_that_cannot_be_asked_is_none_and_one_that_errors_is_a_warning():
    assert pf.run_preflight(FakeSystem(smi=None)).gpu.state is GpuState.NONE
    erroring = pf.run_preflight(FakeSystem(smi=CommandResult(9, SMI_DRIVER_DOWN)))
    assert erroring.gpu.state is GpuState.ERROR and erroring.check("gpu").status is Status.WARN and erroring.can_continue


def test_a_small_gpu_warns_and_does_not_block():
    report = pf.run_preflight(FakeSystem(smi=CommandResult(0, SMI_6G)))
    assert report.check("gpu").key == "preflight.gpu.small" and report.can_continue


@pytest.mark.parametrize("kwargs, blocked", [
    (dict(euid=0), "root"),
    (dict(proc_version=PROC_WSL1), "platform"),
    (dict(python=(3, 9, 18)), "python"),
    (dict(tools={}), "apt"),
    (dict(environ={}), "display"),
])
def test_each_blocker_blocks_and_nothing_else_does(kwargs, blocked):
    report = pf.run_preflight(FakeSystem(**kwargs))
    assert not report.can_continue and blocked in ids(report.blockers)


def test_python_3_10_is_enough_and_3_9_is_not():
    assert pf.run_preflight(FakeSystem(python=(3, 10, 0))).check("python").status is Status.OK
    assert pf.run_preflight(FakeSystem(python=(3, 9, 99))).check("python").status is Status.BLOCK


def test_no_desktop_says_how_wsl_differs_from_native():
    native = pf.run_preflight(FakeSystem(environ={})).check("display")
    wsl = pf.run_preflight(wsl2(environ={"WSL_DISTRO_NAME": "Ubuntu"}, present={"/mnt/c"})).check("display")
    assert native.key == "preflight.display.none" and wsl.key == "preflight.display.none_wsl" and wsl.args["wslg_folder"] == 0
    assert pf.run_preflight(wsl2(environ={"WSL_DISTRO_NAME": "Ubuntu"})).check("display").args["wslg_folder"] == 1


def test_either_display_variable_will_do():
    assert pf.run_preflight(FakeSystem(environ={"WAYLAND_DISPLAY": "wayland-0"})).check("display").status is Status.OK
    assert pf.run_preflight(FakeSystem(environ={"DISPLAY": ""})).check("display").status is Status.BLOCK


def test_other_ubuntu_releases_are_untested_not_refused():
    for text in (UBUNTU_2004, LINUX_MINT, DEBIAN_12):
        check = pf.run_preflight(FakeSystem(os_release=text)).check("os")
        assert check.status is Status.WARN and check.key == "preflight.os.untested"
    assert pf.run_preflight(FakeSystem(os_release=None)).check("os").key == "preflight.os.unknown"


def test_missing_packages_are_information_and_need_sudo_unless_root():
    report = pf.run_preflight(FakeSystem(installed=["git"], tools={"apt-get": "/usr/bin/apt-get"}, failing_probes=("import",)))
    assert report.check("packages").status is Status.INFO and report.check("packages").args["count"] == len(ALL_PACKAGES) - 1
    assert "sudo" in ids(report.blockers) and not report.can_continue
    assert pf.run_preflight(FakeSystem(installed=[], tools={"apt-get": "/usr/bin/apt-get"}, failing_probes=("import",), euid=0)).check("root").status is Status.BLOCK


@pytest.mark.parametrize("memory, status", [(MEM_16G, Status.OK), (MEM_8G, Status.OK), (MEM_4G, Status.WARN), (None, Status.INFO)])
def test_memory(memory, status):
    assert pf.run_preflight(FakeSystem(meminfo=memory)).check("ram").status is status


def test_memory_at_its_exact_provisional_edge():
    below = "MemTotal: %d kB\n" % ((pf.RAM_WARN_MIB - 1) * 1024)
    at = "MemTotal: %d kB\n" % (pf.RAM_WARN_MIB * 1024)
    assert pf.run_preflight(FakeSystem(meminfo=below)).check("ram").status is Status.WARN
    assert pf.run_preflight(FakeSystem(meminfo=at)).check("ram").status is Status.OK


def test_a_home_folder_on_the_windows_drive_warns():
    assert pf.run_preflight(wsl2(home="/mnt/c/Users/me")).check("home").status is Status.WARN
    assert "home" not in ids(pf.run_preflight(FakeSystem()).checks)
    assert "home" not in ids(pf.run_preflight(FakeSystem(home="/mntx/me")).checks)


def test_extra_folders_are_measured_and_unreadable_ones_are_left_out():
    system = FakeSystem(disks={"/home/user": (10, 5), "/media/usb": (100, 90)})
    report = pf.run_preflight(system, measure=["/media/usb", "/media/gone"])
    assert report.disks == {"/home/user": (10, 5), "/media/usb": (100, 90)}


def test_preflight_runs_only_local_read_only_commands():
    system = wsl2(installed=[], tools={"apt-get": "/usr/bin/apt-get", "nvidia-smi": "/usr/bin/nvidia-smi"})
    pf.run_preflight(system)
    assert system.ran and {a[0].rsplit("/", 1)[-1] for a in system.ran} <= {"dpkg-query", "nvidia-smi", "python3"}
    assert all(a[1] == "-c" and a[2].startswith("import ") for a in system.ran if a[0] == "/usr/bin/python3"), "Python is only asked to import a module"


def test_the_real_system_can_be_read_without_error_on_whatever_runs_the_tests():
    report = pf.run_preflight(RealSystem())
    assert report.checks and all(isinstance(c.status, Status) for c in report.checks)
    assert report.platform in (Platform.NATIVE, Platform.WSL1, Platform.WSL2)
