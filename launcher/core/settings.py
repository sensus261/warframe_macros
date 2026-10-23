"""The launcher's own settings (launcher/settings.json, not in git)."""

import copy
import json
import os

from . import paths

DEFAULTS = {
    "ahk_exe": "",  # empty = detect AutoHotkey.exe automatically
    "editor": "",  # empty = the program Windows opens .json files with (Notepad if none)
    "buffwatch_mode": "auto",  # auto | source | exe
    "page": "macros",
    "log_open": True,
    "geometry": "",
}


def load(path=None):
    path = path or paths.SETTINGS_FILE
    out = copy.deepcopy(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            out.update(data)
    except (OSError, ValueError):
        pass
    return out


def save(settings, path=None):
    path = path or paths.SETTINGS_FILE
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass
