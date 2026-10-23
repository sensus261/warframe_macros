"""Colours, fonts and icons. Call init() once the Tk root exists."""

import tkinter.font as tkfont

BG = "#0e1015"
SIDEBAR = "#13161d"
CARD = "#191d26"
CARD_HOVER = "#1f2430"
INPUT = "#11141a"
BORDER = "#262b37"
TEXT = "#e9ebf1"
MUTED = "#8b92a6"
FAINT = "#5d6477"
ACCENT = "#5b7cfa"
ACCENT_HOVER = "#7190ff"
ACCENT_DIM = "#1d2547"

GREEN, GREEN_BG = "#34d399", "#0f2e24"
AMBER, AMBER_BG = "#fbbf24", "#33280c"
RED, RED_BG = "#f87171", "#3a1717"
BLUE, BLUE_BG = "#7ea2ff", "#1a2342"
GREY, GREY_BG = "#9aa1b2", "#22262f"

TONES = {
    "green": (GREEN, GREEN_BG),
    "amber": (AMBER, AMBER_BG),
    "red": (RED, RED_BG),
    "blue": (BLUE, BLUE_BG),
    "grey": (GREY, GREY_BG),
}

# Filled in by init().
FAMILY = "TkDefaultFont"
MONO = "TkFixedFont"


def init(root):
    global FAMILY, MONO
    families = set(tkfont.families(root))
    for f in ("Segoe UI Variable Text", "Segoe UI", "Inter", "DejaVu Sans"):
        if f in families:
            FAMILY = f
            break
    for f in ("Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono"):
        if f in families:
            MONO = f
            break


def font(size=13, weight="normal"):
    return (FAMILY, size, weight)


def mono(size=12, weight="normal"):
    return (MONO, size, weight)

