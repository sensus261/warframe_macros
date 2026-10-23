"""Finding, watching and stopping the running AutoHotkey scripts and BuffWatch."""

import ctypes
import os
import re
import sys
import time

import psutil

from . import paths

IS_WIN = sys.platform == "win32"
WM_CLOSE = 0x0010

# BuffWatch's main window; its overlays and dialogs must not get the close message.
BUFFWATCH_MAIN_TITLE = re.compile(r"^BuffWatch( - \d+ new icons?)?$")


class Proc:
    """A running process the launcher cares about."""

    def __init__(self, pid, name, started, script=None):
        self.pid = pid
        self.name = name
        self.started = started
        self.script = script  # AutoHotkey: full path of the .ahk file

    @property
    def script_name(self):
        return os.path.basename(self.script) if self.script else self.name

    def uptime(self, now=None):
        return max(0.0, (now or time.time()) - self.started)

    def __repr__(self):
        return "Proc(%d, %s, %s)" % (self.pid, self.name, self.script)


def is_ahk_exe(name):
    n = (name or "").lower()
    return n.startswith("autohotkey") and not n.startswith("autohotkeyux")


def ahk_script_of(cmdline):
    """The .ahk file in an AutoHotkey command line (after the exe and its /switches)."""
    for arg in (cmdline or [])[1:]:
        if arg.lower().endswith(".ahk"):
            return arg
    return None


def is_buffwatch(name, cmdline):
    if (name or "").lower() == "buffwatch.exe":
        return True
    return any(a.replace("\\", "/").rsplit("/", 1)[-1].lower() == "buffwatch.pyw"
               for a in (cmdline or [])[1:])


def snapshot():
    """({pid: Proc} of AutoHotkey scripts, [Proc] of BuffWatch instances)."""
    scripts, buffwatch = {}, []
    for p in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            name = p.info["name"] or ""
            if is_ahk_exe(name):
                cmd = p.cmdline()
                script = ahk_script_of(cmd)
                if script:
                    if not os.path.isabs(script):
                        try:
                            script = os.path.join(p.cwd(), script)
                        except (psutil.Error, OSError):
                            pass
                    scripts[p.pid] = Proc(p.pid, name, p.info["create_time"] or time.time(),
                                          os.path.normpath(script))
            elif name.lower() in ("buffwatch.exe", "python.exe", "pythonw.exe") or \
                    name.lower().startswith("python"):
                cmd = p.cmdline()
                if is_buffwatch(name, cmd):
                    buffwatch.append(Proc(p.pid, name, p.info["create_time"] or time.time()))
        except (psutil.Error, OSError):
            continue
    return scripts, buffwatch


def _post_close(pid, title_filter=None):
    """Ask the windows of `pid` to close, like clicking their X. Returns how many were
    asked. AutoHotkey scripts exit when their (hidden) main window gets this."""
    if not IS_WIN:
        return 0
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                    wintypes.LPARAM]
    found = []

    def cb(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if title_filter is None or title_filter(buf.value):
                found.append(hwnd)
        return True

    user32.EnumWindows(proc_type(cb), 0)
    for hwnd in found:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    return len(found)


def stop(pid, buffwatch=False, timeout=5.0, force=True):
    """Close a process politely (so BuffWatch saves its settings), and kill it if it is
    still there after `timeout` s and `force` is set. Returns True once it is gone.
    Blocks; call it from a worker thread."""
    try:
        p = psutil.Process(pid)
    except psutil.Error:
        return True
    title_filter = (lambda t: bool(BUFFWATCH_MAIN_TITLE.match(t))) if buffwatch else None
    asked = _post_close(pid, title_filter)
    if not asked:
        try:
            p.terminate()
        except psutil.Error:
            return True
    try:
        p.wait(timeout)
        return True
    except psutil.TimeoutExpired:
        pass
    except psutil.Error:
        return True
    if not force:
        return False
    try:
        p.kill()
        p.wait(3)
    except psutil.TimeoutExpired:
        return False
    except psutil.Error:
        pass
    return True


def format_uptime(seconds):
    s = int(seconds)
    if s < 60:
        return "%ds" % s
    m, s = divmod(s, 60)
    if m < 60:
        return "%dm %02ds" % (m, s)
    h, m = divmod(m, 60)
    return "%dh %02dm" % (h, m)


def scripts_for(config_script, scripts):
    """The running processes of one generated script."""
    return [p for p in scripts.values() if paths.same_path(p.script, config_script)]
