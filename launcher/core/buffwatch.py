"""Starting BuffWatch, from its source folder (run.bat's way) or from a built BuffWatch.exe.

BuffWatch keeps its configuration in a "data" folder next to whatever runs it, so the
two ways have separate data folders: buff_watch/data and buff_watch/dist/BuffWatch/data.
"""

import os
import subprocess
import sys

from . import paths

IS_WIN = sys.platform == "win32"
CREATE_NEW_CONSOLE = 0x00000010 if IS_WIN else 0

SOURCE = "source"
EXE = "exe"


def source_ready():
    return os.path.isfile(paths.BUFFWATCH_VENV_PYTHONW) and os.path.isfile(paths.BUFFWATCH_VENV_READY)


def exe_exists():
    return os.path.isfile(paths.BUFFWATCH_EXE)


def resolve_mode(setting):
    """"source" or "exe" for the "auto" / "source" / "exe" setting."""
    if setting in (SOURCE, EXE):
        return setting
    if source_ready():
        return SOURCE
    return EXE if exe_exists() else SOURCE


def data_dir(mode):
    if mode == EXE:
        return os.path.join(os.path.dirname(paths.BUFFWATCH_EXE), "data")
    return os.path.join(paths.BUFFWATCH_DIR, "data")


def needs_setup(mode):
    """True when starting will first install BuffWatch's Python packages (in a console)."""
    return mode == SOURCE and IS_WIN and not source_ready()


def start(mode):
    """Start BuffWatch. Returns the process id when it is BuffWatch itself, or None when
    run.bat is setting up first (BuffWatch then shows up on its own)."""
    if mode == EXE:
        if not exe_exists():
            raise OSError("BuffWatch.exe is not built yet (run buff_watch\\build_exe.bat).")
        return subprocess.Popen([paths.BUFFWATCH_EXE],
                                cwd=os.path.dirname(paths.BUFFWATCH_EXE)).pid
    if not IS_WIN:
        return subprocess.Popen([sys.executable, paths.BUFFWATCH_SCRIPT],
                                cwd=paths.BUFFWATCH_DIR).pid
    if source_ready():
        return subprocess.Popen([paths.BUFFWATCH_VENV_PYTHONW, paths.BUFFWATCH_SCRIPT],
                                cwd=paths.BUFFWATCH_DIR).pid
    subprocess.Popen(["cmd", "/c", paths.BUFFWATCH_RUN_BAT], cwd=paths.BUFFWATCH_DIR,
                     creationflags=CREATE_NEW_CONSOLE)
    return None

