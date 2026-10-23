"""Macro configs (macros/configs/*.json) and the AutoHotkey scripts generated from them."""

import json
import os
import shutil
import subprocess
import sys

from . import paths

IS_WIN = sys.platform == "win32"
NO_WINDOW = 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW

# Status of a config's generated script.
MISSING = "missing"  # never generated
STALE = "stale"  # the JSON changed after the script was generated
READY = "ready"
BROKEN = "broken"  # the JSON can't be read

TEMPLATE = {
    "$schema": "../ahkgen.schema.json",
    "settings": {
        "tick_ms": 10,
        "sounds": {"on": [1000, 100], "off": [500, 100]},
    },
    "macros": [
        {
            "name": "My macro",
            "hotkey": "F1",
            "steps": [
                {"tap": "1"}, {"wait": 500, "jitter": 100},
            ],
        }
    ],
}


class Config:
    """One macro config file and what is known about it."""

    def __init__(self, path, generated_dir=None):
        self.path = path
        self.key = os.path.splitext(os.path.basename(path))[0]
        self.script = os.path.join(generated_dir or paths.GENERATED_DIR, self.key + ".ahk")
        self.macros = []  # [(hotkey, name, description)]
        self.panic_hotkey = None
        self.error = None
        self._load()

    @property
    def title(self):
        """"vauban_auto" -> "Vauban auto"."""
        t = self.key.replace("_", " ").replace("-", " ").strip()
        return t[:1].upper() + t[1:] if t else self.key

    def _load(self):
        try:
            with open(self.path, encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            self.error = str(e)
            return
        if not isinstance(data, dict):
            self.error = "The file is not a JSON object."
            return
        settings = data.get("settings") or {}
        if isinstance(settings, dict):
            self.panic_hotkey = settings.get("panic_hotkey")
        for i, m in enumerate(data.get("macros") or []):
            if not isinstance(m, dict):
                continue
            hk = str(m.get("hotkey", "?"))
            self.macros.append((hk, str(m.get("name") or hk or "macro%d" % (i + 1)),
                                str(m.get("description") or "")))

    def status(self):
        if self.error:
            return BROKEN
        if not os.path.isfile(self.script):
            return MISSING
        try:
            if os.path.getmtime(self.path) > os.path.getmtime(self.script):
                return STALE
        except OSError:
            return MISSING
        return READY


def list_configs(configs_dir=None, generated_dir=None):
    configs_dir = configs_dir or paths.CONFIGS_DIR
    try:
        names = sorted(n for n in os.listdir(configs_dir) if n.lower().endswith(".json"))
    except OSError:
        return []
    return [Config(os.path.join(configs_dir, n), generated_dir) for n in names]


def powershell():
    """The PowerShell to run the generator with, or None."""
    if IS_WIN:
        return shutil.which("powershell") or shutil.which("pwsh") or "powershell.exe"
    return shutil.which("pwsh")


def generate(config, generator=None):
    """Run macros/ahkgen.ps1 on `config`. Returns (ok, output text). Blocks; call it from a
    worker thread."""
    ps = powershell()
    if not ps:
        return False, "PowerShell was not found."
    os.makedirs(os.path.dirname(config.script), exist_ok=True)
    cmd = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", generator or paths.GENERATOR,
           config.path, "-Output", config.script]
    try:
        p = subprocess.run(cmd, cwd=os.path.dirname(config.path), capture_output=True,
                           text=True, timeout=120, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    out = "\n".join(s.strip() for s in (p.stdout, p.stderr) if s and s.strip())
    return p.returncode == 0, out


def safe_name(name):
    """A file name for a new config, from what the user typed."""
    keep = "".join(c if c.isalnum() or c in "-_ " else " " for c in name.strip())
    return "_".join(keep.lower().split())


def create_config(name, configs_dir=None):
    """Write a starter config and return its path. Raises FileExistsError / ValueError."""
    key = safe_name(name)
    if not key:
        raise ValueError("Type a name with at least one letter or number.")
    path = os.path.join(configs_dir or paths.CONFIGS_DIR, key + ".json")
    if os.path.exists(path):
        raise FileExistsError("A config called %s already exists." % (key + ".json"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x", encoding="utf-8") as f:
        f.write(json.dumps(TEMPLATE, indent=2) + "\n")
    return path
