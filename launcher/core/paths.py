"""Where everything lives in the repository."""

import os

LAUNCHER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(LAUNCHER_DIR)

MACROS_DIR = os.path.join(ROOT, "macros")
CONFIGS_DIR = os.path.join(MACROS_DIR, "configs")
GENERATED_DIR = os.path.join(MACROS_DIR, "generated")
GENERATOR = os.path.join(MACROS_DIR, "ahkgen.ps1")

BUFFWATCH_DIR = os.path.join(ROOT, "buff_watch")
BUFFWATCH_SCRIPT = os.path.join(BUFFWATCH_DIR, "buffwatch.pyw")
BUFFWATCH_RUN_BAT = os.path.join(BUFFWATCH_DIR, "run.bat")
BUFFWATCH_VENV_PYTHONW = os.path.join(BUFFWATCH_DIR, ".venv", "Scripts", "pythonw.exe")
BUFFWATCH_VENV_READY = os.path.join(BUFFWATCH_DIR, ".venv", "installed.txt")
BUFFWATCH_EXE = os.path.join(BUFFWATCH_DIR, "dist", "BuffWatch", "BuffWatch.exe")

SETTINGS_FILE = os.path.join(LAUNCHER_DIR, "settings.json")


def same_path(a, b):
    """True when two paths name the same file (Windows paths are case-insensitive)."""
    if not a or not b:
        return False
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
