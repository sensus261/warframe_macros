"""Checks configuration export / import, and that settings and library files from older or
newer versions still load.

Run from the buff_watch folder:  python -m pytest tests   (or: python tests/test_backup.py)
"""

import json
import os
import sys
import tempfile
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cv2  # noqa: E402

from bw import backup, config, library, skills  # noqa: E402


def _use_data_dir(d):
    """Point the app's data paths at `d`."""
    config.DATA_DIR = d
    config.ICON_DIR = os.path.join(d, "icons")
    config.SETTINGS_FILE = os.path.join(d, "settings.json")
    config.LIBRARY_FILE = os.path.join(d, "library.json")


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))


def _make_config(d):
    _write(os.path.join(d, "settings.json"), {"fps": 12, "overlay": {"zoom": 4.0}})
    _write(os.path.join(d, "library.json"), [{"id": "abc", "name": "Roar"}])
    os.makedirs(os.path.join(d, "icons"))
    cv2.imwrite(os.path.join(d, "icons", "abc.png"), np.full((8, 8, 3), 200, np.uint8))
    os.makedirs(os.path.join(d, "skill_icons"))
    cv2.imwrite(os.path.join(d, "skill_icons", "default_1.png"), np.zeros((8, 8), np.uint8))
    _write(os.path.join(d, "settings.json.tmp"), "half written")
    _write(os.path.join(d, backup.BACKUP_DIR, "old.zip"), "not exported")


def test_round_trip():
    src, dst = tempfile.mkdtemp(), tempfile.mkdtemp()
    _make_config(src)
    out = os.path.join(tempfile.mkdtemp(), "export.zip")
    assert backup.export_config(out, src) == 4
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
    assert names == {backup.MANIFEST, "settings.json", "library.json", "icons/abc.png",
                     "skill_icons/default_1.png"}
    info = backup.check_archive(out)
    assert info["files"] == 4 and info["icons"] == 1

    # The destination's own configuration is replaced, and backed up first.
    _write(os.path.join(dst, "settings.json"), {"fps": 3})
    _write(os.path.join(dst, "icons", "zzz.png"), "old icon")
    saved = backup.import_config(out, dst)
    assert saved and os.path.isfile(saved)
    with zipfile.ZipFile(saved) as z:
        assert {"settings.json", "icons/zzz.png"} <= set(z.namelist())
    assert not os.path.exists(os.path.join(dst, "icons", "zzz.png"))
    assert os.path.isfile(os.path.join(dst, "skill_icons", "default_1.png"))

    _use_data_dir(dst)
    s = config.load_settings()
    assert s["fps"] == 12 and s["overlay"]["zoom"] == 4.0
    assert s["overlay"]["anchor"] == "top-left"  # missing fields get their defaults
    lib = library.Library()
    lib.load()
    assert [e.name for e in lib.entries] == ["Roar"]


def test_rejects_bad_files():
    d = tempfile.mkdtemp()
    for name, files in (("empty.zip", {"readme.txt": "hi"}),
                        ("evil.zip", {"settings.json": "{}", "../evil.txt": "x"}),
                        ("broken.zip", {"settings.json": "{not json"})):
        p = os.path.join(d, name)
        with zipfile.ZipFile(p, "w") as z:
            for n, data in files.items():
                z.writestr(n, data)
        try:
            backup.check_archive(p)
        except backup.BadExport:
            pass
        else:
            raise AssertionError(name + " was accepted")
    notzip = os.path.join(d, "x.zip")
    _write(notzip, "plain text")
    try:
        backup.check_archive(notzip)
    except backup.BadExport:
        pass
    else:
        raise AssertionError("a text file was accepted")


def test_other_versions_load():
    d = tempfile.mkdtemp()
    _use_data_dir(d)
    # A newer version's fields are kept in settings and skipped in the library; a section
    # that isn't a section any more falls back to its defaults.
    _write(config.SETTINGS_FILE, {
        "future_option": 1, "overlay": "oops", "autokey": {"enabled": False, "new": 2},
        "skills": {"profiles": [{"id": "volt", "slots": [None, {"auto": True}]}, "junk",
                                {"name": "no id"}]},
    })
    s = config.load_settings()
    assert s["future_option"] == 1
    assert s["overlay"] == config.DEFAULTS["overlay"]
    assert s["autokey"]["enabled"] is False and s["autokey"]["new"] == 2
    profs = skills.profiles(s)
    assert [p["id"] for p in profs] == ["volt"] and profs[0]["name"] == "volt"
    assert skills.slot_settings(s, 0)["key"] == "1"
    assert skills.slot_settings(s, 1)["auto"] is True

    _write(config.LIBRARY_FILE, [{"id": "a", "name": "A", "shiny_new_field": True},
                                 {"id": "b"}, {"name": "no id"}, "junk"])
    os.makedirs(config.ICON_DIR)
    for i in "ab":
        cv2.imwrite(os.path.join(config.ICON_DIR, i + ".png"), np.zeros((4, 4, 3), np.uint8))
    lib = library.Library()
    lib.load()
    assert [(e.id, e.name) for e in lib.entries] == [("a", "A"), ("b", "(unnamed)")]
    assert lib.entries[1].key_interval == 1500  # missing fields get their defaults

    _write(config.SETTINGS_FILE, "[1, 2]")
    assert config.load_settings()["fps"] == config.DEFAULTS["fps"]


if __name__ == "__main__":
    test_round_trip()
    test_rejects_bad_files()
    test_other_versions_load()
    print("ok")
