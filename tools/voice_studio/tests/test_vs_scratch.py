# SPDX-License-Identifier: GPL-3.0-or-later
"""Where scratch may live (plan task VS-1.11, decision D24): every refusal and warning, the marker, and the speed arithmetic.

The mount tables and lsblk output are written from the documented formats (proc(5), lsblk(8)); replace them with captures from the
developer's machines when the spikes run. No real drive is touched except a temporary folder.
"""
import json
import time
from dataclasses import replace

import pytest

from vs_fakes import FakeSystem
from voice_studio.core import scratch as sc
from voice_studio.core.scratch import FsGroup, MarkerState, Verdict
from voice_studio.core.system import CommandResult, RealSystem

MOUNTS = r"""/dev/nvme0n1p2 / ext4 rw,relatime 0 0
/dev/nvme0n1p1 /boot/efi vfat rw,relatime,fmask=0077 0 0
/dev/sda1 /data ext4 rw,relatime 0 0
/dev/sdb1 /media/user/USB\040STICK exfat rw,nosuid,nodev,relatime,uid=1000 0 0
tmpfs /run tmpfs rw,nosuid,nodev 0 0
nas:/export /mnt/nas nfs4 rw,relatime 0 0
/dev/sdc1 /media/user/OLD vfat rw 0 0
/dev/sdd1 /media/user/READONLY ext4 ro,relatime 0 0
/dev/sde1 /media/user/NTFSDISK fuseblk rw,nosuid,nodev 0 0
tmpfs /ramdisk tmpfs rw 0 0
/dev/sdf1 /media/user/EXTUSB ext4 rw,nosuid,nodev 0 0
/dev/sdg1 /weird xyzfs rw 0 0
"""
WSL_MOUNTS = r"""/dev/sdc / ext4 rw,relatime 0 0
C:\134 /mnt/c 9p rw,noatime,dirsync,aname=drvfs;path=C:\;uid=1000;gid=1000 0 0
D:\134 /mnt/d 9p rw,noatime,dirsync,aname=drvfs;path=D:\;uid=1000;gid=1000 0 0
"""
LSBLK = json.dumps({"blockdevices": [
    {"name": "sda", "mountpoints": [None], "fstype": None, "rm": False, "tran": "sata", "type": "disk",
     "children": [{"name": "sda1", "mountpoints": ["/data"], "fstype": "ext4", "rm": False, "tran": None, "type": "part"}]},
    {"name": "sdb", "mountpoints": [None], "fstype": None, "rm": True, "tran": "usb", "type": "disk",
     "children": [{"name": "sdb1", "mountpoints": ["/media/user/USB STICK"], "fstype": "exfat", "rm": False, "tran": None, "type": "part"}]},
    {"name": "sdf", "mountpoints": [None], "rm": "0", "tran": "usb", "type": "disk",
     "children": [{"name": "sdf1", "mountpoints": ["/media/user/EXTUSB"], "rm": "0", "type": "part"}]}]})

ROOT = "/home/user/voice/projects/anna-1"


def facts(place="/data", **over):
    base = dict(given=place, real=place, project_id="anna-1", project_root=ROOT, home="/home/user", wsl=False, exists=True, is_dir=True, writable=True,
                parent_is_dir=True, parent_writable=True, device=2, project_device=1, mounts_text=MOUNTS, lsblk_json=None,
                other_project_roots=("/home/user/voice/projects/ben-2",))
    base.update(over)
    return sc.PlaceFacts(**base)


def assess(place="/data", **over):
    return sc.assess_scratch(facts(place, **over))


# ---------------------------------------------------------------- mounts

def test_the_mount_table_is_read_with_escaped_spaces_and_odd_options():
    mounts = sc.parse_mounts(MOUNTS)
    usb = next(m for m in mounts if m.fstype == "exfat")
    assert usb.point == "/media/user/USB STICK" and usb.device == "/dev/sdb1" and "nosuid" in usb.options
    wsl = sc.parse_mounts(WSL_MOUNTS)[1]
    assert wsl.point == "/mnt/c" and wsl.fstype == "9p" and "aname=drvfs;path=C:\\;uid=1000;gid=1000" in wsl.options
    assert sc.parse_mounts(None) == [] and sc.parse_mounts("short line\n\n") == []


def test_a_path_belongs_to_the_deepest_mount_above_it():
    mounts = sc.parse_mounts(MOUNTS + "/dev/sda2 /data/big ext4 rw 0 0\n")
    assert sc.mount_for("/data/big/x/y", mounts).point == "/data/big"
    assert sc.mount_for("/data/other", mounts).point == "/data"
    assert sc.mount_for("/home/user", mounts).point == "/"
    assert sc.mount_for("/data", mounts).point == "/data"
    assert sc.mount_for("/media/user/USB STICK/x", mounts).fstype == "exfat"


def test_a_mount_point_is_not_a_prefix_of_a_longer_name():
    mounts = sc.parse_mounts("/dev/a / ext4 rw 0 0\n/dev/b /mnt/c 9p rw 0 0\n")
    assert sc.mount_for("/mnt/cx/file", mounts).point == "/"
    assert sc.mount_for("/mnt/c/file", mounts).point == "/mnt/c"


def test_when_two_mounts_share_a_point_the_later_one_is_what_you_see():
    mounts = sc.parse_mounts("/dev/a /x ext4 rw 0 0\n/dev/b /x xfs rw 0 0\n")
    assert sc.mount_for("/x/y", mounts).fstype == "xfs"


@pytest.mark.parametrize("fstype, wsl, group", [
    ("ext4", False, FsGroup.GOOD), ("EXT4", False, FsGroup.GOOD), ("xfs", False, FsGroup.GOOD), ("btrfs", False, FsGroup.GOOD), ("f2fs", False, FsGroup.GOOD),
    ("ntfs3", False, FsGroup.PERMISSIVE), ("fuseblk", False, FsGroup.PERMISSIVE), ("exfat", False, FsGroup.PERMISSIVE),
    ("vfat", False, FsGroup.FAT), ("msdos", False, FsGroup.FAT),
    ("nfs4", False, FsGroup.NETWORK), ("cifs", False, FsGroup.NETWORK), ("fuse.sshfs", False, FsGroup.NETWORK),
    ("tmpfs", False, FsGroup.MEMORY), ("ramfs", False, FsGroup.MEMORY),
    ("9p", True, FsGroup.WINDOWS), ("drvfs", True, FsGroup.WINDOWS), ("9p", False, FsGroup.NETWORK),
    ("overlay", False, FsGroup.UNKNOWN), ("fuse.mystery", False, FsGroup.UNKNOWN), ("", False, FsGroup.UNKNOWN),
])
def test_each_filesystem_falls_in_one_group(fstype, wsl, group):
    assert sc.fs_group(fstype, wsl=wsl) is group


def test_removable_drives_are_found_from_lsblk_including_a_partition_of_a_usb_disk():
    table = sc.parse_lsblk_removable(LSBLK)
    assert table["/data"] is False and table["/media/user/USB STICK"] is True       # the stick's partition inherits from its disk
    assert table["/media/user/EXTUSB"] is True                                       # "tran": "usb" even though rm is "0"
    older = json.dumps({"blockdevices": [{"name": "sdb", "mountpoint": "/mnt/x", "rm": "1", "children": []}]})
    assert sc.parse_lsblk_removable(older) == {"/mnt/x": True}


@pytest.mark.parametrize("text", [None, "", "not json", "{}", json.dumps({"blockdevices": "x"}), json.dumps([1])])
def test_unreadable_lsblk_output_is_unknown_not_a_guess(text):
    assert sc.parse_lsblk_removable(text) in (None, {})


# ---------------------------------------------------------------- the place

def test_a_clean_ext4_drive_is_accepted_and_the_folder_is_named_for_the_project():
    a = assess("/data")
    assert a.verdict is Verdict.ACCEPT and a.refusals == () and a.warnings == ()
    assert a.scratch_dir == "/data/ack-voice-scratch/anna-1" and a.fstype == "ext4" and a.fs_group is FsGroup.GOOD and a.mount_point == "/data"


def test_a_place_that_does_not_exist_yet_is_fine_if_it_can_be_made():
    assert assess("/data/new", exists=False, is_dir=False, writable=False).verdict is Verdict.ACCEPT
    assert assess("/data/new", exists=False, is_dir=False, writable=False, parent_writable=False).refusals == ("cannot_create",)
    assert assess("/data/new", exists=False, is_dir=False, writable=False, parent_is_dir=False).refusals == ("cannot_create",)


@pytest.mark.parametrize("over, code", [
    (dict(exists=True, is_dir=False), "not_a_folder"),
    (dict(writable=False), "not_writable"),
])
def test_a_place_that_is_not_a_folder_or_cannot_be_written_is_refused(over, code):
    assert code in assess("/data", **over).refusals


@pytest.mark.parametrize("given, real, code", [
    ("relative/place", "/home/user/relative/place", "not_absolute"),
    ("", "", "not_absolute"),
    ("/", "/", "root_folder"),
    ("/etc", "/etc", "system_folder"), ("/usr/local", "/usr/local", "system_folder"), ("/proc/1", "/proc/1", "system_folder"), ("/var/lib/x", "/var/lib/x", "system_folder"),
    ("/data/../etc", "/etc", "system_folder"),                           # what it points at decides, not what was typed
    ("/home/user/link", "/etc/ssl", "system_folder"),                    # a symbolic link into a system folder
])
def test_a_path_that_is_not_a_sensible_place_is_refused(given, real, code):
    assert code in assess(given, real=real).refusals


def test_a_removable_drive_mounted_under_run_is_not_mistaken_for_a_system_folder():
    mounts = MOUNTS + "/dev/sdh1 /run/media/user/BIG ext4 rw 0 0\n"
    assert assess("/run/media/user/BIG", mounts_text=mounts).verdict is Verdict.ACCEPT


def test_a_control_character_in_the_name_is_refused():
    assert "not_absolute" in assess("/data/a\nb", real="/data/a\nb").refusals


@pytest.mark.parametrize("place, code", [
    ("/media/user/OLD", "fs_fat"), ("/boot/efi", "fs_fat"),
    ("/mnt/nas", "fs_network"), ("/ramdisk", "fs_memory"), ("/media/user/READONLY", "read_only"),
])
def test_a_filesystem_that_cannot_keep_the_files_safely_is_refused(place, code):
    assert code in assess(place, real=place).refusals


def test_a_ram_disk_and_a_network_drive_are_not_merely_warned_about():
    assert assess("/ramdisk").verdict is Verdict.REFUSE and assess("/mnt/nas").verdict is Verdict.REFUSE


@pytest.mark.parametrize("place, codes", [
    ("/media/user/NTFSDISK", {"fs_permissive", "perms_loose"}),
    ("/media/user/USB STICK", {"fs_permissive", "perms_loose"}),
    ("/weird", {"fs_unknown"}),
])
def test_a_permissive_or_unknown_filesystem_is_accepted_with_warnings(place, codes):
    a = assess(place)
    assert a.verdict is Verdict.WARN and set(a.warnings) == codes and a.refusals == ()


def test_a_windows_drive_seen_from_wsl_is_accepted_with_warnings_about_speed_and_permissions():
    a = assess("/mnt/d/voice", mounts_text=WSL_MOUNTS, wsl=True)
    assert a.verdict is Verdict.WARN and set(a.warnings) == {"windows_drive", "perms_loose"} and a.fs_group is FsGroup.WINDOWS and a.mount_point == "/mnt/d"
    assert a.scratch_dir == "/mnt/d/voice/ack-voice-scratch/anna-1"


def test_a_mount_table_that_cannot_be_read_gives_an_unknown_filesystem_warning_not_a_pass():
    a = assess("/data", mounts_text=None)
    assert a.verdict is Verdict.WARN and a.warnings == ("fs_unknown",)


def test_a_folder_under_the_media_directory_on_the_main_disk_means_the_drive_is_not_plugged_in():
    a = assess("/media/user/MISSINGDRIVE")
    assert a.verdict is Verdict.REFUSE and "not_mounted" in a.refusals
    assert "not_mounted" in assess("/mnt/backupdisk").refusals
    assert "not_mounted" not in assess("/media/user/EXTUSB").refusals                      # the same place with the drive mounted
    assert "not_mounted" not in assess("/mnt/d/voice", mounts_text=WSL_MOUNTS, wsl=True).refusals
    assert "not_mounted" not in assess("/home/user/big").refusals                           # an ordinary folder on the main disk is simply on the main disk


def test_a_cloud_synced_place_is_refused_not_just_warned_about():
    a = assess("/data", sync_reason="it is inside a folder that looks like OneDrive ('onedrive')")
    assert a.verdict is Verdict.REFUSE and "synced_folder" in a.refusals


def test_the_removable_warning_comes_from_lsblk_and_an_unreadable_lsblk_adds_nothing():
    assert "removable" in assess("/media/user/USB STICK", lsblk_json=LSBLK).warnings
    assert assess("/media/user/USB STICK", lsblk_json=LSBLK).removable is True
    assert assess("/data", lsblk_json=LSBLK).removable is False and "removable" not in assess("/data", lsblk_json=LSBLK).warnings
    assert assess("/media/user/USB STICK", lsblk_json="garbage").removable is None


def test_choosing_the_same_drive_as_the_project_is_said_not_refused():
    a = assess("/data", device=1, project_device=1)
    assert a.verdict is Verdict.WARN and a.warnings == ("same_device_as_project",)
    assert assess("/data", device=2, project_device=1).warnings == ()
    assert assess("/data", device=None, project_device=1).warnings == ()


def test_a_place_inside_this_project_or_another_is_refused():
    assert "inside_project" in assess(ROOT + "/more").refusals
    assert "inside_project" in assess(ROOT).refusals
    assert "inside_other_project" in assess("/home/user/voice/projects/ben-2/scratch").refusals
    assert "inside_other_project" in assess("/home/user/voice/projects/ben-2").refusals
    assert assess("/home/user/voice/projects/ben-22").verdict is not Verdict.REFUSE or "inside_other_project" not in assess("/home/user/voice/projects/ben-22").refusals
    assert "inside_project" not in assess("/home/user/voice/projects/anna-10").refusals


def test_several_problems_are_all_reported_and_refusing_beats_warning():
    a = assess("/media/user/OLD", real="/media/user/OLD", sync_reason="x", writable=False)
    assert a.verdict is Verdict.REFUSE and {"fs_fat", "synced_folder", "not_writable"} <= set(a.refusals)
    assert len(a.refusals) == len(set(a.refusals))


# ---------------------------------------------------------------- the marker and earlier scratch

def test_the_marker_names_the_project_and_is_checked_before_every_job():
    text = sc.marker_text("anna-1")
    assert sc.check_marker(text, "anna-1") is MarkerState.OK and sc.may_start_job(MarkerState.OK)
    assert sc.check_marker(text, "ben-2") is MarkerState.OTHER_PROJECT
    assert sc.check_marker(None, "anna-1") is MarkerState.MISSING
    for bad in ("", "not json", "[]", "{}", json.dumps({"schema": 9, "project": "anna-1"}), json.dumps({"schema": 1, "project": 5}), json.dumps({"schema": 1})):
        assert sc.check_marker(bad, "anna-1") is MarkerState.DAMAGED, bad
    assert not any(sc.may_start_job(s) for s in (MarkerState.MISSING, MarkerState.OTHER_PROJECT, MarkerState.DAMAGED))


def test_an_earlier_scratch_of_this_project_is_picked_up_again():
    a = assess("/data", scratch_exists=True, marker=sc.marker_text("anna-1"), scratch_nonempty=True)
    assert a.verdict is Verdict.ACCEPT and a.reusing


@pytest.mark.parametrize("over, code", [
    (dict(scratch_exists=True, marker=sc.marker_text("ben-2"), scratch_nonempty=True), "marker_other_project"),
    (dict(scratch_exists=True, marker="garbage", scratch_nonempty=True), "marker_damaged"),
    (dict(scratch_exists=True, marker=None, scratch_nonempty=True), "not_empty_unmarked"),
])
def test_a_folder_that_is_not_certainly_this_projects_scratch_is_never_written_into(over, code):
    a = assess("/data", **over)
    assert a.verdict is Verdict.REFUSE and code in a.refusals and not a.reusing


def test_an_empty_unmarked_folder_with_the_right_name_may_be_used():
    assert assess("/data", scratch_exists=True, marker=None, scratch_nonempty=False).verdict is Verdict.ACCEPT


def test_the_scratch_folder_name_is_safe_for_any_project_id_or_refuses():
    assert sc.scratch_dir_for("/data", "anna-1") == "/data/ack-voice-scratch/anna-1"
    for bad in ("", "../x", "a/b", "A", "-x", "x" * 65):
        with pytest.raises(ValueError):
            sc.scratch_dir_for("/data", bad)
    bad = assess("/data", project_id="../bad")
    assert bad.scratch_dir == "" and bad.verdict is Verdict.REFUSE and "bad_project_id" in bad.refusals


# ---------------------------------------------------------------- reading the computer

def system(**kw):
    dirs = {"/", "/data", "/home/user", "/media/user/USB STICK"} | set(kw.pop("dirs", ()))
    devices = {"/data": 2, "/": 1, "/media/user/USB STICK": 3, **kw.pop("devices", {})}
    s = FakeSystem(dirs=dirs, devices=devices, **kw)
    s.files["/proc/mounts"] = MOUNTS
    return s


def gather(s, given, **kw):
    kw.setdefault("project_id", "anna-1")
    kw.setdefault("project_root", ROOT)
    return sc.gather_place_facts(s, given, **kw)


def test_a_place_that_does_not_exist_yet_is_measured_on_its_nearest_existing_folder():
    f = gather(system(), "/data/new/deeper")
    assert (f.real, f.exists, f.is_dir, f.parent_is_dir) == ("/data/new/deeper", False, False, False) and f.device == 2
    f = gather(system(), "/data/new")
    assert f.exists is False and f.parent_is_dir is True and f.parent_writable is True and f.device == 2


def test_the_home_shortcut_is_expanded_and_a_link_is_followed():
    s = system(symlinks={"/home/user/link": "/etc"})
    assert gather(s, "~/big").real == "/home/user/big" and gather(s, "~").real == "/home/user"
    assert gather(s, "/home/user/link").real == "/etc" and sc.assess_scratch(gather(s, "/home/user/link")).verdict is Verdict.REFUSE


def test_a_file_where_a_folder_was_chosen_is_seen_as_a_file():
    s = system(present=["/data/afile"])
    f = gather(s, "/data/afile")
    assert f.exists and not f.is_dir and "not_a_folder" in sc.assess_scratch(f).refusals


def test_an_unplugged_drive_is_a_folder_on_the_main_disk_and_is_refused():
    s = system(dirs=["/", "/media/user/GONE"], devices={"/": 1, "/media/user/GONE": 1})
    s.files["/proc/mounts"] = MOUNTS
    assert "not_mounted" in sc.assess_scratch(gather(s, "/media/user/GONE")).refusals


def test_an_earlier_scratch_is_found_by_its_marker_and_listing():
    s = system(dirs=["/", "/data", "/data/ack-voice-scratch/anna-1"], listings={"/data/ack-voice-scratch/anna-1": [".ack-voice-scratch", "dataset"]})
    s.files["/data/ack-voice-scratch/anna-1/.ack-voice-scratch"] = sc.marker_text("anna-1")
    f = gather(s, "/data")
    assert f.scratch_exists and f.scratch_nonempty and sc.assess_scratch(f).reusing


def test_lsblk_is_asked_and_its_output_is_used_and_nothing_else_is_run():
    s = system(lsblk=CommandResult(0, LSBLK))
    f = gather(s, "/media/user/USB STICK")
    assert f.lsblk_json == LSBLK and "removable" in sc.assess_scratch(f).warnings
    assert [a[0] for a in s.ran] == ["lsblk"]
    assert gather(system(lsblk=CommandResult(1, "")), "/data").lsblk_json is None and gather(system(), "/data").lsblk_json is None


def test_a_synced_folder_is_noticed_by_the_shared_detector():
    s = FakeSystem(dirs=["/", "/mnt/c/Users/me/OneDrive"], symlinks={})
    s.files["/proc/mounts"] = WSL_MOUNTS
    f = gather(s, "/mnt/c/Users/me/OneDrive/voice", wsl=True)
    assert f.sync_reason and "synced_folder" in sc.assess_scratch(f).refusals


def test_the_real_computer_can_be_read_for_a_new_folder_in_a_temporary_place(tmp_path):
    f = gather(RealSystem(), str(tmp_path / "new"), project_root=str(tmp_path / "project"))
    assert f.exists is False and f.parent_is_dir and f.parent_writable and f.device is not None and f.mounts_text
    assert sc.assess_scratch(f).refusals == () or "not_mounted" not in sc.assess_scratch(f).refusals


# ---------------------------------------------------------------- speed

class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeDisk:
    def __init__(self, clock, write_bps, read_bps, per_small_op_s):
        self.clock, self.write_bps, self.read_bps, self.per_small = clock, write_bps, read_bps, per_small_op_s
        self.files = {}

    def write(self, name, nbytes):
        self.files[name] = nbytes
        self.clock.t += nbytes / self.write_bps + (self.per_small if name.startswith("speed-small") else 0)

    def read(self, name):
        self.clock.t += self.files[name] / self.read_bps + (self.per_small if name.startswith("speed-small") else 0)
        return self.files[name]

    def remove(self, name):
        del self.files[name]


def speed(write_bps, read_bps, per_small):
    clock = Clock()
    disk = FakeDisk(clock, write_bps, read_bps, per_small)
    result = sc.measure_speed(disk, clock, big_bytes=30_000_000, small_files=100, small_bytes=1000)
    assert disk.files == {}, "everything written is removed"
    return result


def test_speeds_are_worked_out_from_the_time_each_part_took():
    r = speed(30e6, 60e6, 0.005)
    assert r.write_mbps == pytest.approx(30.0) and r.read_mbps == pytest.approx(60.0)
    assert r.small_files_per_s == pytest.approx(100 / (100 * (1000 / 30e6) + 100 * (1000 / 60e6) + 200 * 0.005), rel=1e-3)


def test_a_drive_exactly_at_the_slow_limits_is_not_called_slow_and_just_under_is():
    assert sc.judge_speed(sc.Speed(30.0, 30.0, 200.0)) == ()
    assert sc.judge_speed(sc.Speed(29.99, 30.0, 200.0)) == ("slow_write",)
    assert sc.judge_speed(sc.Speed(30.0, 29.99, 200.0)) == ("slow_read",)
    assert sc.judge_speed(sc.Speed(30.0, 30.0, 199.99)) == ("slow_small_files",)
    assert sc.judge_speed(sc.Speed(1.0, 1.0, 1.0)) == ("slow_write", "slow_read", "slow_small_files")


def test_a_drive_that_answers_instantly_does_not_divide_by_zero():
    clock = Clock()
    disk = FakeDisk(clock, 10**30, 10**30, 0)
    r = sc.measure_speed(disk, clock, big_bytes=1000, small_files=2, small_bytes=10)
    assert r.write_mbps > 0 and r.small_files_per_s > 0


def test_a_slow_windows_drive_style_disk_is_slow_at_small_files_though_fast_at_big_ones():
    r = speed(200e6, 400e6, 0.01)
    assert sc.judge_speed(r) == ("slow_small_files",)


def test_the_real_disk_writes_reads_and_removes_in_a_folder(tmp_path):
    r = sc.measure_speed(sc.RealDisk(str(tmp_path)), time.perf_counter, big_bytes=1 << 20, small_files=5, small_bytes=1024)
    assert r.write_mbps > 0 and r.read_mbps > 0 and r.small_files_per_s > 0 and list(tmp_path.iterdir()) == []
