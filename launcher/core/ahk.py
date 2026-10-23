"""Finding AutoHotkey v1 and starting scripts with it."""

import glob
import os
import subprocess
import sys

IS_WIN = sys.platform == "win32"

# Executable names, best first. The generated scripts are AutoHotkey v1.
V1_NAMES = ("AutoHotkeyU64.exe", "AutoHotkey.exe", "AutoHotkeyU32.exe", "AutoHotkeyA32.exe")


def _install_dirs():
    dirs = []
    if IS_WIN:
        try:
            import winreg
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for view in (0, winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                    try:
                        with winreg.OpenKey(hive, r"SOFTWARE\AutoHotkey", 0,
                                            winreg.KEY_READ | view) as k:
                            dirs.append(winreg.QueryValueEx(k, "InstallDir")[0])
                    except OSError:
                        pass
        except ImportError:
            pass
    for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        if os.environ.get(var):
            dirs.append(os.path.join(os.environ[var], "AutoHotkey"))
    if os.environ.get("LOCALAPPDATA"):
        dirs.append(os.path.join(os.environ["LOCALAPPDATA"], "Programs", "AutoHotkey"))
    seen, out = set(), []
    for d in dirs:
        key = os.path.normcase(os.path.abspath(d))
        if d and key not in seen:
            seen.add(key)
            out.append(d)
    return out


def find_v1(dirs=None):
    """Path of an AutoHotkey v1 executable, or "" when none is installed."""
    for d in (dirs if dirs is not None else _install_dirs()):
        for name in V1_NAMES:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                return p
        # The v2 installer keeps v1 in a versioned subfolder, e.g. v1.1.37.02\.
        subs = sorted(glob.glob(os.path.join(d, "v1*")), reverse=True)
        for sub in subs:
            for name in V1_NAMES:
                p = os.path.join(sub, name)
                if os.path.isfile(p):
                    return p
    return ""


def resolve(setting):
    """The AutoHotkey to use: the one in the settings when it exists, else detected."""
    if setting and os.path.isfile(setting):
        return setting
    return find_v1()


def run_script(script, ahk_exe):
    """Start `script`. Uses `ahk_exe` when given, else whatever Windows opens .ahk files
    with. Returns the new process id, or None when it is not known."""
    cwd = os.path.dirname(script)
    if ahk_exe:
        p = subprocess.Popen([ahk_exe, script], cwd=cwd)
        return p.pid
    if IS_WIN:
        os.startfile(script)
        return None
    raise OSError("AutoHotkey was not found. Set its path in Settings.")
