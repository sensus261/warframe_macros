"""The Buffs overlay tab of the main window: every look, layout and position setting of
the overlay, applied live and saved to settings.json. The Skills overlay tab is the
same tab pointed at the skills overlay."""

import tkinter as tk
from tkinter import colorchooser, font as tkfont, messagebox, ttk

from . import config
from .ui_overlay import ANCHORS

LAYOUTS = ("vertical", "horizontal", "grid")
NAME_POSITIONS = {"below": "below the icon", "right": "beside the icon"}
# Settings the tab leaves alone on "Reset overlay to defaults".
KEEP_ON_RESET = ("visible", "click_through", "hide_from_capture", "x", "y", "anchor")
# Changing one of these rebuilds the overlay's cells.
REBUILD = ("orientation", "columns", "cell_gap", "cell_padding", "border_width",
           "name_position", "font_family", "font_size", "font_bold", "cell_color",
           "solid_background", "background_color", "text_color")


# Labels that change on the Skills overlay tab.
SKILL_TEXT = {
    "Show pinned buffs while they are off (dimmed)": "Show abilities while they are ready",
    "Show buff names": "Show ability names",
    "Gap between buffs (px)": "Gap between abilities (px)",
    "Padding inside each buff (px)": "Padding inside each ability (px)",
    "Name colour (buff on)": "Text colour (ability active)",
    "Name colour (buff off)": "Text colour (ability ready)",
    "Alert colour (off buff set to alert)": "Alert colour (auto-press gave up)",
    "Brightness of off buffs": "Brightness of ready abilities",
    "Fill the gaps between buffs": "Fill the gaps between abilities",
    "Flash colour (buff turns on / off)": "Flash colour (timer starts / ends)",
    "Buff background": "Ability background",
}


class _Scrolled(ttk.Frame):
    """A frame whose content scrolls vertically when the window is too short for it."""

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas, padding=8)
        win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(win, width=e.width))
        self.inner.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>", self._wheel))
        self.inner.bind("<Leave>", lambda e: self.unbind_all("<MouseWheel>"))

    def _wheel(self, ev):
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-ev.delta / 120) or (-1 if ev.delta > 0 else 1), "units")


class OverlaySettingsTab(_Scrolled):
    def __init__(self, parent, app, key="overlay"):
        super().__init__(parent)
        self.app = app
        self.key = key  # settings section: "overlay" or "skills_overlay"
        self._words = SKILL_TEXT if key == "skills_overlay" else {}
        self.vars = {}  # settings key -> (tk variable, kind)
        self._color_buttons = {}
        self._percent_labels = []
        f = self.inner
        f.columnconfigure(0, weight=1, uniform="col")
        f.columnconfigure(1, weight=1, uniform="col")

        g = self._section(f, "General", 0, 0)
        for key, text in (("visible", "Show overlay"),
                          ("click_through", "Lock overlay (clicks go through to the game)"),
                          ("show_missing", "Show pinned buffs while they are off (dimmed)"),
                          ("show_names", "Show buff names"),
                          ("hide_from_capture", "Hide overlay from screen capture / recordings\n"
                                                "(stops BuffWatch reading its own overlay)")):
            self._check(g, key, text)
        if self.key == "skills_overlay":
            self._check(g, "show_energy", "Show energy (blinks below the auto-press limit)")

        g = self._section(f, "Size and layout", 0, 1)
        self._spin(g, "zoom", "Zoom", 1.0, 8.0, 0.25, float)
        self._combo(g, "orientation", "Layout", LAYOUTS)
        self.columns_spin = self._spin(g, "columns", "Columns (grid layout)", 1, 20, 1, int)
        self._spin(g, "cell_gap", "Gap between buffs (px)", 0, 60, 1, int)
        self._spin(g, "cell_padding", "Padding inside each buff (px)", 0, 30, 1, int)
        self._spin(g, "border_width", "Alert / flash border (px, 0 = none)", 0, 10, 1, int)

        g = self._section(f, "Text", 1, 0)
        families = sorted({n for n in tkfont.families(self) if not n.startswith("@")})
        self._combo(g, "font_family", "Font", families, readonly=False)
        self._spin(g, "font_size", "Size", 6, 40, 1, int)
        self._check(g, "font_bold", "Bold")
        self._combo(g, "name_position", "Name position", tuple(NAME_POSITIONS.values()),
                    labels=NAME_POSITIONS)
        self._color(g, "text_color", "Name colour (buff on)")
        self._color(g, "off_text_color", "Name colour (buff off)")
        self._color(g, "alert_color", "Alert colour (off buff set to alert)")

        g = self._section(f, "Look", 1, 1)
        self._percent(g, "opacity", "Opacity", 20)
        self._percent(g, "dim_missing", "Brightness of off buffs", 0)
        self._color(g, "cell_color", "Buff background")
        self._check(g, "solid_background", "Fill the gaps between buffs")
        self._color(g, "background_color", "Gap colour")
        self._color(g, "flash_color", "Flash colour (buff turns on / off)")
        self._spin(g, "flash_seconds", "Flash length (s, 0 = none)", 0.0, 5.0, 0.1, float)

        g = self._section(f, "Position", 2, 0, columnspan=2)
        self._combo(g, "anchor", "Corner that stays put", ANCHORS)
        self._spin(g, "x", "X of that corner", -20000, 20000, 1, int)
        self._spin(g, "y", "Y of that corner", -20000, 20000, 1, int)
        snap = ttk.Frame(g)
        snap.grid(row=self._next_row(g), column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(snap, text="Snap to screen corner:").pack(side="left")
        for corner in ANCHORS:
            ttk.Button(snap, text=corner.replace("-", " "),
                       command=lambda c=corner: self._snap(c)).pack(side="left", padx=2)

        bottom = ttk.Frame(f)
        bottom.grid(row=3, column=0, columnspan=2, sticky="we", pady=(8, 0))
        ttk.Button(bottom, text="Reset overlay to defaults",
                   command=self._reset).pack(side="left")
        ttk.Label(f, foreground="#666", wraplength=700, justify="left", text=(
            "Drag the overlay by its blue bar to move it, then tick 'Lock overlay'. The corner "
            "that stays put keeps its place while buffs come and go, so pick bottom-right for "
            "an overlay in the bottom-right of the screen. The game must run in Borderless "
            "Fullscreen or Windowed mode for the overlay to show on top of it.")).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=8)
        self._update_states()

    # ------------------------------------------------------------ widgets
    def _section(self, parent, title, row, col, columnspan=1):
        g = ttk.LabelFrame(parent, text=title, padding=8)
        g.grid(row=row, column=col, columnspan=columnspan, sticky="nsew", padx=4, pady=4)
        g.columnconfigure(1, weight=1)
        g._rows = 0
        return g

    @staticmethod
    def _next_row(g):
        g._rows += 1
        return g._rows - 1

    def _ov(self):
        return self.app.settings[self.key]

    @property
    def overlay(self):
        return self.app.skill_overlay if self.key == "skills_overlay" else self.app.overlay

    def _t(self, text):
        return self._words.get(text, text)

    def _check(self, g, key, text):
        v = tk.BooleanVar(value=bool(self._ov()[key]))
        self.vars[key] = (v, bool)
        ttk.Checkbutton(g, text=self._t(text), variable=v, command=self._changed).grid(
            row=self._next_row(g), column=0, columnspan=2, sticky="w", pady=1)

    def _label(self, g, text):
        r = self._next_row(g)
        ttk.Label(g, text=self._t(text)).grid(row=r, column=0, sticky="w", pady=2, padx=(0, 6))
        return r

    def _spin(self, g, key, text, lo, hi, step, kind):
        r = self._label(g, text)
        v = (tk.DoubleVar if kind is float else tk.IntVar)(value=self._ov()[key])
        sb = ttk.Spinbox(g, from_=lo, to=hi, increment=step, textvariable=v, width=8,
                         command=self._changed)
        sb.grid(row=r, column=1, sticky="w")
        sb.bind("<Return>", lambda e: self._changed())
        sb.bind("<FocusOut>", lambda e: self._changed())
        self.vars[key] = (v, kind, lo, hi)
        return sb

    def _combo(self, g, key, text, values, readonly=True, labels=None):
        """`labels` maps stored values to the text shown in the list."""
        r = self._label(g, text)
        shown = labels.get(self._ov()[key], self._ov()[key]) if labels else self._ov()[key]
        v = tk.StringVar(value=shown)
        self.vars[key] = (v, labels or str)
        cb = ttk.Combobox(g, textvariable=v, values=values, width=22,
                          state="readonly" if readonly else "normal")
        cb.grid(row=r, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._changed())
        if not readonly:
            cb.bind("<Return>", lambda e: self._changed())
            cb.bind("<FocusOut>", lambda e: self._changed())

    def _percent(self, g, key, text, lo):
        r = self._label(g, text)
        v = tk.DoubleVar(value=round(float(self._ov()[key]) * 100))
        self.vars[key] = (v, "percent")
        box = ttk.Frame(g)
        box.grid(row=r, column=1, sticky="we")
        shown = ttk.Label(box, width=5)
        sc = ttk.Scale(box, from_=lo, to=100, variable=v, length=140)
        sc.pack(side="left")
        shown.pack(side="left", padx=4)

        def moved(_=None):
            shown.configure(text="%d%%" % round(v.get()))
        sc.configure(command=moved)
        sc.bind("<ButtonRelease-1>", lambda e: self._changed())
        moved()
        self._percent_labels.append(moved)

    def _color(self, g, key, text):
        r = self._label(g, text)
        v = tk.StringVar(value=self._ov()[key])
        self.vars[key] = (v, "color")
        b = tk.Button(g, width=6, relief="groove", bg=v.get(), activebackground=v.get(),
                      command=lambda: self._pick_color(key))
        b.grid(row=r, column=1, sticky="w")
        self._color_buttons[key] = b

    def _pick_color(self, key):
        v = self.vars[key][0]
        _, hexcol = colorchooser.askcolor(color=v.get(), parent=self, title="Choose colour")
        if hexcol:
            v.set(hexcol)
            self._changed()

    # ------------------------------------------------------------ apply
    def _read(self):
        """Settings values from the widgets; a field with a bad entry is left out."""
        out = {}
        for key, spec in self.vars.items():
            v, kind = spec[0], spec[1]
            try:
                val = v.get()
            except (tk.TclError, ValueError):
                continue
            if kind is bool:
                out[key] = bool(val)
            elif kind in (int, float):
                lo, hi = spec[2], spec[3]
                out[key] = kind(max(lo, min(hi, val)))
                if kind is float:
                    out[key] = round(out[key], 2)
            elif kind == "percent":
                out[key] = round(float(val) / 100, 2)
            elif isinstance(kind, dict):  # combobox with display labels
                rev = {t: k for k, t in kind.items()}
                out[key] = rev.get(val, val)
            elif str(val).strip():
                out[key] = str(val).strip()
        return out

    def _changed(self):
        ov = self._ov()
        new = self._read()
        overlay = self.overlay
        if new.get("anchor", ov["anchor"]) != ov["anchor"]:
            # Keep the window where it is: re-measure x, y from the new corner.
            ov["anchor"] = new["anchor"]
            overlay.remember_position()
            new["x"], new["y"] = ov["x"], ov["y"]
            self.sync_position()
        rebuild = any(new.get(k, ov[k]) != ov[k] for k in REBUILD)
        ov.update(new)
        self.app.save_settings()
        overlay.apply_settings()
        if rebuild:
            overlay.refresh_layout()
        overlay.place()
        self._update_states()

    def _update_states(self):
        self.columns_spin.configure(
            state="normal" if self._ov()["orientation"] == "grid" else "disabled")
        for key, b in self._color_buttons.items():
            col = self.vars[key][0].get()
            try:
                b.configure(bg=col, activebackground=col)
            except tk.TclError:
                pass

    def _snap(self, corner):
        self.overlay.snap_to(corner)
        self.app.save_settings()
        self.sync_position()

    def sync_position(self):
        """Show the overlay's current anchor and position (after a drag or snap)."""
        ov = self._ov()
        self.vars["anchor"][0].set(ov["anchor"])
        self.vars["x"][0].set(ov["x"])
        self.vars["y"][0].set(ov["y"])

    def _reset(self):
        if not messagebox.askyesno("BuffWatch", "Reset every overlay look and layout setting "
                                   "to its default? Position and lock stay as they are.",
                                   parent=self):
            return
        ov = self._ov()
        for key, val in config.DEFAULTS[self.key].items():
            if key not in KEEP_ON_RESET:
                ov[key] = val
        for key, spec in self.vars.items():
            v, kind = spec[0], spec[1]
            val = ov[key]
            if kind == "percent":
                val = round(float(val) * 100)
            elif isinstance(kind, dict):
                val = kind.get(val, val)
            v.set(val)
        for moved in self._percent_labels:
            moved()
        self.app.save_settings()
        self.overlay.apply_settings()
        self.overlay.refresh_layout()
        self._update_states()
