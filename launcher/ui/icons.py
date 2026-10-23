"""Small icons drawn from the Windows icon font (Segoe Fluent Icons / Segoe MDL2 Assets),
with plain Unicode symbols as the fallback on systems without it."""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

import customtkinter as ctk

# name: (Segoe icon font glyph, Unicode fallback)
GLYPHS = {
    "macros": ("\uE765", "\u2328"),
    "running": ("\uE9D9", "\u25C9"),
    "buffwatch": ("\uE7B3", "\u25CE"),
    "settings": ("\uE713", "\u2699"),
    "play": ("\uE768", "\u25B6"),
    "stop": ("\uE71A", "\u25A0"),
    "restart": ("\uE72C", "\u21BB"),
    "build": ("\uE90F", "\u2692"),
    "edit": ("\uE70F", "\u270E"),
    "folder": ("\uE8B7", "\u2750"),
    "add": ("\uE710", "+"),
    "clear": ("\uE74D", "\u2715"),
    "expand": ("\uE70E", "\u25B4"),
    "collapse": ("\uE70D", "\u25BE"),
    "warning": ("\uE7BA", "\u26A0"),
    "doc": ("\uE8A5", "\u2630"),
}

_WIN_FONTS = ("SegoeIcons.ttf", "segmdl2.ttf")
_FALLBACK_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
)
_SCALE = 3  # draw big, let CTkImage scale down: crisp at any DPI

_font_path = None
_use_segoe = False
_cache = {}


def _find_font():
    global _font_path, _use_segoe
    if _font_path is not None:
        return
    _font_path = ""
    if sys.platform == "win32":
        fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for name in _WIN_FONTS:
            p = os.path.join(fonts, name)
            if os.path.isfile(p):
                _font_path, _use_segoe = p, True
                return
        p = os.path.join(fonts, "seguisym.ttf")
        if os.path.isfile(p):
            _font_path = p
            return
    for p in _FALLBACK_FONTS:
        if os.path.isfile(p):
            _font_path = p
            return


def _draw(char, px, color):
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    try:
        f = ImageFont.truetype(_font_path, int(px * 0.86))
    except OSError:
        return img
    d = ImageDraw.Draw(img)
    l, t, r, b = d.textbbox((0, 0), char, font=f)
    d.text(((px - (r - l)) / 2 - l, (px - (b - t)) / 2 - t), char, font=f, fill=color)
    return img


def get(name, size=16, color="#e9ebf1"):
    """A CTkImage of the icon, or None when no icon font is available."""
    key = (name, size, color)
    if key in _cache:
        return _cache[key]
    _find_font()
    if not _font_path:
        _cache[key] = None
        return None
    glyph = GLYPHS[name][0 if _use_segoe else 1]
    img = _draw(glyph, size * _SCALE, color)
    out = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    _cache[key] = out
    return out
