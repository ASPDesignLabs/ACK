# SPDX-License-Identifier: GPL-3.0-or-later
"""The ACK app keeps a person's data on the phone: no network permission, no cloud backup, no network code.

These are checks on files in the repository (no Android SDK needed), so they run anywhere the whole repo is checked out and
skip themselves when this folder has been copied out on its own.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "app" / "src" / "main"
MANIFEST = APP / "AndroidManifest.xml"
CLOUD_RULES = APP / "res" / "xml" / "data_extraction_rules.xml"
FULL_RULES = APP / "res" / "xml" / "backup_rules.xml"

pytestmark = pytest.mark.skipif(not MANIFEST.exists(), reason="the Android app is not next to this folder")

ANDROID = "{http://schemas.android.com/apk/res/android}"
NETWORK_PERMISSIONS = {"INTERNET", "ACCESS_NETWORK_STATE", "CHANGE_NETWORK_STATE", "ACCESS_WIFI_STATE", "CHANGE_WIFI_STATE"}
ALL_DOMAINS = {"root", "file", "database", "sharedpref", "external", "device_root", "device_file", "device_database", "device_sharedpref"}


def domains(parent, tag):
    return {e.get("domain"): e.get("path") for e in parent.findall(tag)}


def test_the_app_asks_for_no_network_permission():
    root = ET.parse(MANIFEST).getroot()
    asked = {e.get(ANDROID + "name").rsplit(".", 1)[-1] for e in root.findall("uses-permission")}
    assert not (asked & NETWORK_PERMISSIONS), f"network permissions: {sorted(asked & NETWORK_PERMISSIONS)}"
    app = root.find("application")
    assert app.get(ANDROID + "usesCleartextTraffic") is None and app.get(ANDROID + "networkSecurityConfig") is None


def test_no_cloud_backup_of_anything_the_app_stores():
    cloud = ET.parse(CLOUD_RULES).getroot().find("cloud-backup")
    assert cloud is not None and cloud.findall("include") == [], "cloud backup must not include anything"
    excluded = domains(cloud, "exclude")
    assert set(excluded) == ALL_DOMAINS and set(excluded.values()) == {"."}, f"missing: {sorted(ALL_DOMAINS - set(excluded))}"


def test_the_older_android_rules_say_the_same_thing():
    full = ET.parse(FULL_RULES).getroot()
    assert full.tag == "full-backup-content" and full.findall("include") == []
    assert set(domains(full, "exclude")) >= {"root", "file", "database", "sharedpref", "external"}


def test_a_direct_phone_to_phone_transfer_still_keeps_everything():
    """A replaced phone must not lose a person's way of communicating; this path does not go through the cloud."""
    transfer = ET.parse(CLOUD_RULES).getroot().find("device-transfer")
    assert transfer is not None and transfer.findall("exclude") == []
    assert set(domains(transfer, "include")) == ALL_DOMAINS


def test_the_manifest_uses_those_two_files():
    app = ET.parse(MANIFEST).getroot().find("application")
    assert app.get(ANDROID + "dataExtractionRules") == "@xml/data_extraction_rules"
    assert app.get(ANDROID + "fullBackupContent") == "@xml/backup_rules"


def test_the_apps_own_code_opens_no_connection():
    forbidden = re.compile(r"java\.net\.|HttpURLConnection|HttpsURLConnection|OkHttp|\bWebView\b|\.loadUrl\(|\bSocket\(|InetAddress|"
                           r"DownloadManager|ConnectivityManager|android\.net\.(?!Uri\b)")
    found = []
    for p in (APP / "java").rglob("*.kt"):
        for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if forbidden.search(line):
                found.append(f"{p.relative_to(APP)}:{n}: {line.strip()[:80]}")
    assert not found, "network code in the app:\n" + "\n".join(found)


def test_recording_training_data_can_only_be_saved_where_the_person_chooses():
    """RECORD TRAINING DATA saves a package through the system file picker (CreateDocument) and nowhere else: no share sheet, no
    intent that hands the audio to another app, no file provider that would let another app read it, no way to start a transfer."""
    forbidden = re.compile(r"ACTION_SEND|ACTION_SEND_MULTIPLE|createChooser|ShareCompat|FileProvider|ACTION_VIEW|startActivity\(|"
                           r"ACTION_INSTALL|BroadcastReceiver|sendBroadcast|ContentResolver\.insert|MediaStore|ClipboardManager|setPrimaryClip")
    found = []
    for folder in ("voicecapture", "capture"):
        for p in (APP / "java" / "com" / "example" / "besu" / folder).rglob("*.kt"):
            for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                code = line.split("//", 1)[0]
                if forbidden.search(code):
                    found.append(f"{p.relative_to(APP)}:{n}: {line.strip()[:80]}")
    assert not found, "a way for training recordings to leave the phone other than the file picker:\n" + "\n".join(found)
    home = (APP / "java" / "com" / "example" / "besu" / "voicecapture" / "TrainingCaptureHome.kt").read_text(encoding="utf-8")
    assert "ActivityResultContracts.CreateDocument" in home, "saving no longer goes through the file picker"


def test_the_portable_capture_code_has_no_android_classes():
    """capture/ is compiled and tested without an Android SDK (tools/kotlin_check); one android.* import there breaks that."""
    found = []
    for p in (APP / "java" / "com" / "example" / "besu" / "capture").rglob("*.kt"):
        for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if re.match(r"\s*import\s+(android|androidx)\.", line):
                found.append(f"{p.name}:{n}: {line.strip()}")
    assert not found, "Android imports in the portable package:\n" + "\n".join(found)
