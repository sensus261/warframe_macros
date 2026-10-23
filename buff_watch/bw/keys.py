"""Key names, simulated key presses (SendInput) and the global on/off hotkey.

Only used by the opt-in auto-press feature. Keys are sent as hardware scan codes,
like AutoHotkey does, so games that read raw keyboard input see them.
"""

import ctypes
import queue
import threading
import time

from .winutil import IS_WIN

_VK = {"space": 0x20, "tab": 0x09, "enter": 0x0D, "escape": 0x1B, "backspace": 0x08,
       "shift": 0x10, "ctrl": 0x11, "alt": 0x12, "capslock": 0x14,
       "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24,
       "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
       "insert": 0x2D, "delete": 0x2E, "`": 0xC0, "-": 0xBD, "=": 0xBB,
       "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
       "\\": 0xDC}
_VK.update({chr(c): c for c in range(ord("0"), ord("9") + 1)})
_VK.update({chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)})
_VK.update({"f%d" % i: 0x6F + i for i in range(1, 25)})
_VK.update({"numpad%d" % i: 0x60 + i for i in range(10)})
_EXTENDED = {"pageup", "pagedown", "end", "home", "left", "up", "right", "down",
             "insert", "delete"}
_MOUSE = {"mouse3": (0x0020, 0x0040, 0), "mouse4": (0x0080, 0x0100, 1),
          "mouse5": (0x0080, 0x0100, 2)}  # (down flag, up flag, xbutton)
MODIFIERS = ("ctrl", "shift", "alt")

_TK_NAMES = {"Return": "enter", "Escape": "escape", "BackSpace": "backspace", "Tab": "tab",
             "space": "space", "Prior": "pageup", "Next": "pagedown", "End": "end",
             "Home": "home", "Left": "left", "Up": "up", "Right": "right", "Down": "down",
             "Insert": "insert", "Delete": "delete", "Caps_Lock": "capslock",
             "grave": "`", "minus": "-", "equal": "=", "bracketleft": "[",
             "bracketright": "]", "semicolon": ";", "apostrophe": "'", "comma": ",",
             "period": ".", "slash": "/", "backslash": "\\",
             "Shift_L": "shift", "Shift_R": "shift", "Control_L": "ctrl",
             "Control_R": "ctrl", "Alt_L": "alt", "Alt_R": "alt"}


def parse(spec):
    """'shift+4' -> (['shift'], '4'). Raises ValueError for unknown keys."""
    parts = [p.strip().lower() for p in (spec or "").split("+") if p.strip()]
    if not parts:
        raise ValueError("no key")
    *mods, key = parts
    for m in mods:
        if m not in MODIFIERS:
            raise ValueError("unknown modifier '%s'" % m)
    if key not in _VK and key not in _MOUSE:
        raise ValueError("unknown key '%s'" % key)
    return mods, key


def from_tk_event(ev):
    """Key name for a Tk <KeyPress> event, with held modifiers, or None."""
    sym = ev.keysym
    name = _TK_NAMES.get(sym)
    if name is None:
        low = sym.lower()
        if low in _VK:
            name = low
        elif sym.startswith("KP_") and sym[3:].isdigit():
            name = "numpad" + sym[3:]
        else:
            return None
    if name in MODIFIERS:
        return name
    mods = [m for m, bit in (("ctrl", 0x4), ("shift", 0x1)) if ev.state & bit]
    if ev.state & 0x20000 or ev.state & 0x8:  # Alt on Windows / X11
        mods.append("alt")
    return "+".join(mods + [name])


# ---------------------------------------------------------------- Windows input
if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    ULONG_PTR = ctypes.c_size_t

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class _UNION(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _UNION)]

    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM,
                                          wintypes.LPARAM]

    def _key_event(name, up):
        vk = _VK[name]
        flags = 0x0008  # KEYEVENTF_SCANCODE
        if up:
            flags |= 0x0002
        if name in _EXTENDED:
            flags |= 0x0001
        inp = _INPUT(type=1)
        inp.u.ki = _KEYBDINPUT(0, user32.MapVirtualKeyW(vk, 0), flags, 0, 0)
        return inp

    def _mouse_event(name, up):
        down_flag, up_flag, xb = _MOUSE[name]
        inp = _INPUT(type=0)
        inp.u.mi = _MOUSEINPUT(0, 0, xb, up_flag if up else down_flag, 0, 0)
        return inp

    def _send(events):
        arr = (_INPUT * len(events))(*events)
        user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))


def tap(spec, hold=0.05):
    """Press and release `spec` (e.g. '4', 'shift+f', 'mouse4')."""
    mods, key = parse(spec)
    if not IS_WIN:
        return
    ev = _mouse_event if key in _MOUSE else _key_event
    _send([_key_event(m, False) for m in mods] + [ev(key, False)])
    time.sleep(hold)
    _send([ev(key, True)] + [_key_event(m, True) for m in reversed(mods)])


def foreground_title():
    if not IS_WIN:
        return ""
    hwnd = user32.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


class Sender(threading.Thread):
    """Sends taps off the UI thread so a key hold never freezes the window."""

    def __init__(self, tap_fn=tap):
        super().__init__(daemon=True)
        self.jobs = queue.Queue()
        self.tap_fn = tap_fn

    def press(self, spec):
        self.jobs.put(spec)

    def run(self):
        while True:
            spec = self.jobs.get()
            if spec is None:
                return
            try:
                self.tap_fn(spec)
            except Exception:
                pass

    def stop(self):
        self.jobs.put(None)


class HotkeyListener(threading.Thread):
    """Registers one global hotkey (RegisterHotKey - no keyboard hook) and puts
    'toggle' in `events` whenever it is pressed."""

    WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

    def __init__(self, spec, events):
        super().__init__(daemon=True)
        self.spec = spec
        self.events = events
        self.error = None
        self._tid = None
        self._ready = threading.Event()

    def start_and_wait(self):
        self.start()
        self._ready.wait(2)
        return self.error

    def run(self):
        if not IS_WIN:
            self._ready.set()
            return
        try:
            mods, key = parse(self.spec)
            if key in _MOUSE:
                raise ValueError("mouse buttons can't be global hotkeys")
        except ValueError as ex:
            self.error = str(ex)
            self._ready.set()
            return
        flags = 0x4000  # MOD_NOREPEAT
        for m in mods:
            flags |= {"alt": 0x1, "ctrl": 0x2, "shift": 0x4}[m]
        self._tid = ctypes.windll.kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, flags, _VK[key]):
            self.error = "'%s' is already used by another program" % self.spec
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == self.WM_HOTKEY:
                self.events.put("toggle")
        user32.UnregisterHotKey(None, 1)

    def stop(self):
        if IS_WIN and self._tid:
            user32.PostThreadMessageW(self._tid, self.WM_QUIT, 0, 0)
