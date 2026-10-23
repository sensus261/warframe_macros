"""The dark look of BuffWatch's windows (the same palette as the launcher).

apply(root) restyles every ttk widget through the "clam" theme and sets option-database
defaults for the few classic Tk widgets (canvas, listbox, text, menus, simple dialogs).
The overlays draw their own colours and are not affected.
"""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

BG = "#0e1015"
HEADER = "#13161d"
CARD = "#191d26"
CARD_HOVER = "#1f2430"
INPUT = "#11141a"
BORDER = "#262b37"
BORDER_HOVER = "#363d4d"
TEXT = "#e9ebf1"
MUTED = "#8b92a6"
FAINT = "#5d6477"
ACCENT = "#5b7cfa"
ACCENT_HOVER = "#7190ff"
ACCENT_DIM = "#1d2547"
GREEN = "#34d399"
AMBER = "#fbbf24"
RED = "#f87171"
RED_BG = "#3a1717"
RED_HOVER = "#4a1d1d"

FAMILY = "Segoe UI"


def font(size=10, weight="normal"):
    return (FAMILY, size, weight)


def _pick_family(root):
    global FAMILY
    families = set(tkfont.families(root))
    for f in ("Segoe UI Variable Text", "Segoe UI", "Inter", "DejaVu Sans"):
        if f in families:
            FAMILY = f
            return


_images = []  # PhotoImages must stay referenced


def _check_images(root):
    """Rounded check box images (off, on, disabled) sized for the screen's DPI."""
    scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
    px = int(round(16 * scale))
    big = px * 4

    def draw(fill, border, tick):
        im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        w = max(4, big // 14)
        d.rounded_rectangle((w // 2, w // 2, big - w // 2 - 1, big - w // 2 - 1),
                            radius=big // 5, fill=fill, outline=border, width=w)
        if tick:
            d.line([(big * 0.27, big * 0.52), (big * 0.44, big * 0.69), (big * 0.75, big * 0.33)],
                   fill="#ffffff", width=int(big * 0.11), joint="curve")
        return ImageTk.PhotoImage(im.resize((px, px), Image.LANCZOS), master=root)

    imgs = (draw(INPUT, BORDER_HOVER, False), draw(ACCENT, ACCENT, True),
            draw(BG, BORDER, False), draw(ACCENT_DIM, ACCENT_DIM, True),
            draw(CARD_HOVER, MUTED, False))
    _images.extend(imgs)
    return imgs, px + int(round(7 * scale))


def apply(root):
    _pick_family(root)
    root.configure(background=BG)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family=FAMILY, size=10)
        except tk.TclError:
            pass

    # Classic Tk widgets (dialogs, canvases, combobox drop-downs) read these defaults.
    for pattern, value in (
            ("*Toplevel.background", BG), ("*Canvas.background", BG),
            ("*Listbox.background", INPUT), ("*Listbox.foreground", TEXT),
            ("*Listbox.selectBackground", ACCENT), ("*Listbox.selectForeground", "#ffffff"),
            ("*Listbox.highlightThickness", 0), ("*Listbox.borderWidth", 0),
            ("*Text.background", INPUT), ("*Text.foreground", TEXT),
            ("*Text.insertBackground", TEXT), ("*Text.selectBackground", ACCENT),
            ("*Text.highlightThickness", 1), ("*Text.highlightBackground", BORDER),
            ("*Text.highlightColor", ACCENT), ("*Text.relief", "flat"),
            ("*Menu.background", CARD), ("*Menu.foreground", TEXT),
            ("*Menu.activeBackground", ACCENT), ("*Menu.activeForeground", "#ffffff"),
            ("*Menu.relief", "flat"), ("*Menu.borderWidth", 1),
            ("*Label.background", BG), ("*Label.foreground", TEXT),
            ("*Entry.background", INPUT), ("*Entry.foreground", TEXT),
            ("*Entry.insertBackground", TEXT), ("*Button.background", CARD_HOVER),
            ("*Button.foreground", TEXT), ("*Frame.background", BG),
            ("*TCombobox*Listbox.background", CARD), ("*TCombobox*Listbox.foreground", TEXT),
            ("*TCombobox*Listbox.selectBackground", ACCENT),
            ("*TCombobox*Listbox.selectForeground", "#ffffff")):
        root.option_add(pattern, value)

    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, fieldbackground=INPUT, bordercolor=BORDER,
                lightcolor=BORDER, darkcolor=BORDER, troughcolor=INPUT, focuscolor=ACCENT,
                selectbackground=ACCENT, selectforeground="#ffffff", insertcolor=TEXT,
                font=font(10))
    s.map(".", foreground=[("disabled", FAINT)])

    # Surfaces
    s.configure("TFrame", background=BG)
    s.configure("Header.TFrame", background=HEADER)
    s.configure("Card.TFrame", background=CARD)
    s.configure("TLabel", background=BG, foreground=TEXT)
    s.configure("Muted.TLabel", foreground=MUTED)
    s.configure("Faint.TLabel", foreground=FAINT)
    s.configure("Warn.TLabel", foreground=AMBER)
    s.configure("Title.TLabel", font=font(13, "bold"))
    s.configure("Section.TLabel", foreground=FAINT, font=font(8, "bold"))
    s.configure("Header.TLabel", background=HEADER)
    s.configure("HeaderTitle.TLabel", background=HEADER, font=font(15, "bold"))
    s.configure("HeaderMuted.TLabel", background=HEADER, foreground=MUTED)
    s.configure("Card.TLabel", background=CARD)
    s.configure("CardMuted.TLabel", background=CARD, foreground=MUTED)
    s.configure("Preview.TLabel", background=INPUT, bordercolor=BORDER)
    s.configure("TLabelframe", background=BG, bordercolor=BORDER, lightcolor=BORDER,
                darkcolor=BORDER, relief="solid", borderwidth=1)
    s.configure("TLabelframe.Label", background=BG, foreground=MUTED, font=font(9, "bold"))
    s.configure("TSeparator", background=BORDER)

    # Buttons: default (secondary), Accent (primary), Danger, Ghost.
    s.configure("TButton", background=CARD_HOVER, foreground=TEXT, bordercolor=BORDER,
                lightcolor=CARD_HOVER, darkcolor=CARD_HOVER, padding=(10, 5), relief="flat",
                focusthickness=0, focuscolor=CARD_HOVER, width=-4, anchor="center")
    s.map("TButton",
          background=[("disabled", CARD), ("pressed", BORDER), ("active", "#2a3040")],
          lightcolor=[("active", "#2a3040")], darkcolor=[("active", "#2a3040")],
          bordercolor=[("active", BORDER_HOVER)], foreground=[("disabled", FAINT)])
    s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", bordercolor=ACCENT,
                lightcolor=ACCENT, darkcolor=ACCENT, focuscolor=ACCENT, font=font(10, "bold"))
    s.map("Accent.TButton",
          background=[("disabled", ACCENT_DIM), ("pressed", ACCENT), ("active", ACCENT_HOVER)],
          lightcolor=[("active", ACCENT_HOVER)], darkcolor=[("active", ACCENT_HOVER)],
          bordercolor=[("active", ACCENT_HOVER)])
    s.configure("Danger.TButton", background=RED_BG, foreground=RED, bordercolor="#5a2424",
                lightcolor=RED_BG, darkcolor=RED_BG, focuscolor=RED_BG)
    s.map("Danger.TButton", background=[("active", RED_HOVER)],
          lightcolor=[("active", RED_HOVER)], darkcolor=[("active", RED_HOVER)])
    s.configure("Ghost.TButton", background=BG, foreground=MUTED, bordercolor=BG,
                lightcolor=BG, darkcolor=BG, focuscolor=BG)
    s.map("Ghost.TButton", background=[("active", CARD_HOVER)], foreground=[("active", TEXT)],
          lightcolor=[("active", CARD_HOVER)], darkcolor=[("active", CARD_HOVER)],
          bordercolor=[("active", CARD_HOVER)])
    s.configure("Suggestion.TButton", padding=(6, 4), anchor="w")
    s.configure("TMenubutton", background=CARD_HOVER, foreground=TEXT, bordercolor=BORDER,
                lightcolor=CARD_HOVER, darkcolor=CARD_HOVER, arrowcolor=MUTED, padding=(10, 5),
                relief="flat", width=-4)
    s.map("TMenubutton", background=[("active", "#2a3040")], arrowcolor=[("active", TEXT)])

    # Inputs
    for w in ("TEntry", "TCombobox", "TSpinbox"):
        s.configure(w, fieldbackground=INPUT, foreground=TEXT, bordercolor=BORDER,
                    lightcolor=INPUT, darkcolor=INPUT, arrowcolor=MUTED, background=CARD_HOVER,
                    insertcolor=TEXT, padding=4)
        s.map(w, bordercolor=[("focus", ACCENT), ("hover", BORDER_HOVER)],
              lightcolor=[("focus", INPUT)], fieldbackground=[("readonly", INPUT),
                                                              ("disabled", BG)],
              foreground=[("disabled", FAINT)], arrowcolor=[("disabled", FAINT)],
              background=[("active", "#2a3040")])
    (off, on, off_dis, on_dis, off_hover), box_w = _check_images(root)
    if "Bw.Checkbutton.indicator" not in s.element_names():
        s.element_create("Bw.Checkbutton.indicator", "image", off,
                         ("disabled", "selected", on_dis), ("disabled", off_dis),
                         ("selected", on), ("active", off_hover), border=0, width=box_w,
                         sticky="w")
    s.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
        ("Bw.Checkbutton.indicator", {"side": "left", "sticky": ""}),
        ("Checkbutton.label", {"side": "left", "sticky": "w"})]})])
    s.configure("TCheckbutton", background=BG, foreground=TEXT, focuscolor=BG, padding=(0, 2))
    s.map("TCheckbutton", background=[("active", BG)], foreground=[("disabled", FAINT)])
    s.configure("Header.TCheckbutton", background=HEADER, focuscolor=HEADER)
    s.map("Header.TCheckbutton", background=[("active", HEADER)])
    s.configure("TRadiobutton", background=BG, foreground=TEXT, indicatorbackground=INPUT,
                focuscolor=BG)
    s.map("TRadiobutton", background=[("active", BG)],
          indicatorbackground=[("selected", ACCENT)])
    s.configure("Horizontal.TScale", background=MUTED, troughcolor=INPUT, bordercolor=BORDER,
                lightcolor=MUTED, darkcolor=MUTED)
    s.map("Horizontal.TScale", background=[("active", TEXT)])

    # Scrollbars
    for orient in ("Vertical", "Horizontal"):
        s.configure("%s.TScrollbar" % orient, background=BORDER, troughcolor=BG,
                    bordercolor=BG, lightcolor=BORDER, darkcolor=BORDER, arrowcolor=MUTED,
                    gripcount=0, arrowsize=12)
        s.map("%s.TScrollbar" % orient, background=[("active", FAINT)])

    # Tabs: flat, the selected one lit up.
    s.configure("TNotebook", background=BG, bordercolor=BORDER, lightcolor=BG, darkcolor=BG,
                tabmargins=(0, 4, 0, 0))
    s.configure("TNotebook.Tab", background=BG, foreground=MUTED, bordercolor=BG,
                lightcolor=BG, darkcolor=BG, padding=(14, 7), font=font(10))
    s.map("TNotebook.Tab",
          background=[("selected", HEADER), ("active", HEADER)],
          foreground=[("selected", TEXT), ("active", TEXT)],
          lightcolor=[("selected", ACCENT)], bordercolor=[("selected", BORDER)],
          padding=[("selected", (14, 7))], expand=[("selected", (0, 0, 0, 0))])

    # Lists
    s.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT,
                bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, rowheight=36)
    s.map("Treeview", background=[("selected", ACCENT_DIM)],
          foreground=[("selected", TEXT)])
    s.configure("Treeview.Heading", background=HEADER, foreground=MUTED, bordercolor=BORDER,
                lightcolor=HEADER, darkcolor=HEADER, relief="flat", font=font(9, "bold"),
                padding=(6, 5))
    s.map("Treeview.Heading", background=[("active", CARD_HOVER)])
    return s
