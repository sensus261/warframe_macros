"""Small Win32 helpers (no-ops on other platforms).

Only plain window-management calls are used on BuffWatch's own windows and to
read the position of the game window. Nothing touches the game process.
"""

import ctypes
import sys

IS_WIN = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11

if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    _ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def enable_dpi_awareness():
    """Work in physical pixels so capture and window coordinates agree."""
    if not IS_WIN:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def toplevel_hwnd(tk_window):
    if not IS_WIN:
        return None
    tk_window.update_idletasks()
    return user32.GetParent(tk_window.winfo_id()) or tk_window.winfo_id()


def set_overlay_style(tk_window, click_through):
    """Tool window (no taskbar button), never takes focus from the game, and
    optionally lets mouse clicks pass through to whatever is underneath."""
    hwnd = toplevel_hwnd(tk_window)
    if not hwnd:
        return
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if click_through:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def set_hidden_from_capture(tk_window, hidden):
    """Keep our own overlay out of screen captures (Windows 10 2004+), so BuffWatch
    never reads its own magnified icons back. Returns False if unsupported."""
    hwnd = toplevel_hwnd(tk_window)
    if not hwnd:
        return False
    try:
        return bool(user32.SetWindowDisplayAffinity(
            hwnd, WDA_EXCLUDEFROMCAPTURE if hidden else WDA_NONE))
    except Exception:
        return False


def list_windows():
    """[(hwnd, title)] of visible top-level windows with a title."""
    if not IS_WIN:
        return []
    out = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                out.append((hwnd, buf.value))
        return True

    user32.EnumWindows(_ENUM_PROC(cb), 0)
    return out


def find_window_client_rect(title):
    """Screen rect (left, top, width, height) of the client area of the first visible
    window whose title contains `title` (case-insensitive), or None."""
    if not IS_WIN or not title:
        return None
    t = title.lower()
    for hwnd, name in list_windows():
        if t in name.lower() and "buffwatch" not in name.lower():
            if user32.IsIconic(hwnd):
                return None
            rc = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rc))
            pt = wintypes.POINT(0, 0)
            user32.ClientToScreen(hwnd, ctypes.byref(pt))
            w, h = rc.right - rc.left, rc.bottom - rc.top
            if w > 0 and h > 0:
                return (pt.x, pt.y, w, h)
    return None
