"""Always-on-top overlay that shows the pinned buffs magnified."""

import sys
import tkinter as tk

import cv2

from . import winutil
from .ui_common import context_crop, to_photo

KEY = "#ff00fe"  # this colour is made fully transparent
ANCHORS = ("top-left", "top-right", "bottom-left", "bottom-right")


def _font(ov):
    return (ov["font_family"], int(ov["font_size"]), "bold" if ov["font_bold"] else "normal")


class _Cell:
    def __init__(self, parent, entry_id, ov):
        self.entry_id = entry_id
        bg = ov["cell_color"]
        pad = int(ov["cell_padding"])
        self.beside = ov["name_position"] == "right"
        self.frame = tk.Frame(parent, bg=bg, highlightthickness=int(ov["border_width"]),
                              highlightbackground=bg)
        self.img = tk.Label(self.frame, bg=bg, bd=0)
        self.text = tk.Label(self.frame, bg=bg, fg=ov["text_color"], font=_font(ov),
                             justify="left" if self.beside else "center")
        if self.beside:
            self.img.pack(side="left", padx=(pad, 0), pady=pad)
            self._text_pack = dict(side="left", fill="y", padx=pad)
        else:
            self.img.pack(side="top", padx=pad, pady=(pad, 0))
            self._text_pack = dict(side="top", fill="x", pady=(0, pad))
        self.show_text()
        self.photo = None
        self.was_present = None
        self.flash_until = 0

    def show_text(self):
        if not self.text.winfo_manager():
            self.text.pack(**self._text_pack)

    def hide_text(self):
        if self.text.winfo_manager():
            self.text.pack_forget()


class Overlay(tk.Toplevel):
    SETTINGS_KEY = "overlay"
    HANDLE_TEXT = "BuffWatch overlay - drag me"

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=KEY)
        if sys.platform == "win32":
            self.attributes("-transparentcolor", KEY)
        self.body = tk.Frame(self, bg=KEY)
        self.body.pack()
        self.badge = tk.Label(self, bg="#7a1f1f", fg="white", font=("Segoe UI", 9, "bold"),
                              padx=6, pady=2)
        self.ak_label = tk.Label(self, text="AUTO-PRESS OFF", bg="#444", fg="#ffcc00",
                                 font=("Segoe UI", 8, "bold"), padx=4)
        self.handle = tk.Label(self, text=self.HANDLE_TEXT, bg="#2b5d9b",
                               fg="white", font=("Segoe UI", 8), padx=4)
        self.cells = {}
        self.order = []
        self.visible = []
        self._drag = None
        self._styled = None
        self._geom = None
        for w in (self, self.body, self.handle):
            self._bind_drag(w)
        self._style_window()
        self.place()

    @property
    def cfg(self):
        return self.app.settings[self.SETTINGS_KEY]

    # ------------------------------------------------------------ window state
    def apply_settings(self):
        ov = self.cfg
        if not ov["visible"]:
            self.withdraw()
            return
        self.deiconify()
        self.attributes("-topmost", True)
        style = (ov["click_through"], ov["hide_from_capture"])
        if style != self._styled:
            self._styled = style
            winutil.set_overlay_style(self, ov["click_through"])
            winutil.set_hidden_from_capture(self, ov["hide_from_capture"])
        self.attributes("-alpha", max(0.2, min(1.0, float(ov["opacity"]))))

    def _style_window(self):
        ov = self.cfg
        bg = ov["background_color"] if ov["solid_background"] else KEY
        self.configure(bg=bg)
        self.body.configure(bg=bg)

    def _anchor(self):
        a = self.cfg["anchor"]
        return a if a in ANCHORS else "top-left"

    def place(self):
        """Position the window so its anchor corner sits at the saved x, y."""
        if self._drag:
            return
        ov = self.cfg
        self.update_idletasks()
        a = self._anchor()
        x, y = int(ov["x"]), int(ov["y"])
        if a.endswith("right"):
            x -= self.winfo_reqwidth()
        if a.startswith("bottom"):
            y -= self.winfo_reqheight()
        if (x, y) != self._geom:
            self._geom = (x, y)
            self.geometry("+%d+%d" % (x, y))

    def remember_position(self):
        """Store the current spot of the anchor corner as x, y (after a drag, or after
        the anchor corner changes, so the window stays where it is)."""
        ov = self.cfg
        self.update_idletasks()
        a = self._anchor()
        x, y = self.winfo_x(), self.winfo_y()
        if a.endswith("right"):
            x += self.winfo_width()
        if a.startswith("bottom"):
            y += self.winfo_height()
        ov["x"], ov["y"] = x, y
        self._geom = (self.winfo_x(), self.winfo_y())

    def snap_to(self, corner, margin=20):
        """Anchor to `corner` of the monitor the overlay is on."""
        ov = self.cfg
        cx = self.winfo_x() + self.winfo_width() // 2
        cy = self.winfo_y() + self.winfo_height() // 2
        mon = None
        try:
            from .capture import list_monitors
            for _, m in list_monitors():
                if (m["left"] <= cx < m["left"] + m["width"]
                        and m["top"] <= cy < m["top"] + m["height"]):
                    mon = m
                    break
            mon = mon or list_monitors()[0][1]
        except Exception:
            pass
        if mon is None:
            mon = {"left": 0, "top": 0, "width": self.winfo_screenwidth(),
                   "height": self.winfo_screenheight()}
        ov["anchor"] = corner
        ov["x"] = (mon["left"] + mon["width"] - margin if corner.endswith("right")
                   else mon["left"] + margin)
        ov["y"] = (mon["top"] + mon["height"] - margin if corner.startswith("bottom")
                   else mon["top"] + margin)
        self.place()

    def _bind_drag(self, w):
        w.bind("<ButtonPress-1>", self._drag_start)
        w.bind("<B1-Motion>", self._drag_move)
        w.bind("<ButtonRelease-1>", self._drag_end)

    def _drag_start(self, ev):
        self._drag = (ev.x_root - self.winfo_x(), ev.y_root - self.winfo_y())

    def _drag_move(self, ev):
        if self._drag:
            self.geometry("+%d+%d" % (ev.x_root - self._drag[0], ev.y_root - self._drag[1]))

    def _drag_end(self, ev):
        self._drag = None
        self.remember_position()
        self.app.save_settings()
        self.app.overlay_moved(self)

    # ------------------------------------------------------------ content
    def _sync_cells(self, pinned):
        ids = [e.id for e in pinned]
        if ids == self.order:
            return
        ov = self.cfg
        for cid in list(self.cells):
            if cid not in ids:
                self.cells.pop(cid).frame.destroy()
        for e in pinned:
            if e.id not in self.cells:
                c = _Cell(self.body, e.id, ov)
                for w in (c.frame, c.img, c.text):
                    self._bind_drag(w)
                self.cells[e.id] = c
        self.order = ids
        self.visible = None  # force a regrid

    def _regrid(self, visible):
        ov = self.cfg
        mode = ov["orientation"]
        if mode == "horizontal":
            cols = max(1, len(visible))
        elif mode == "grid":
            cols = max(1, int(ov["columns"]))
        else:
            cols = 1
        gap = int(ov["cell_gap"])
        for c in self.cells.values():
            c.frame.grid_forget()
        for i, cid in enumerate(visible):
            r, col = divmod(i, cols)
            self.cells[cid].frame.grid(row=r, column=col, sticky="nsew",
                                       padx=(gap if col else 0, 0), pady=(gap if r else 0, 0))
        self.visible = visible

    def refresh_layout(self):
        """Rebuild every cell, for when a look or layout setting changed."""
        for c in self.cells.values():
            c.frame.destroy()
        self.cells = {}
        self.order = []
        self.visible = []
        self._style_window()
        self._sync_cells([e for e in self.app.library.snapshot()[0]
                          if e.pinned and e.kind == "buff"])
        self.place()

    def show(self, result, unknown_count, now, autokey_status=None, autokey_on=True):
        ov = self.cfg
        if not ov["visible"]:
            return
        entries = [e for e in self.app.library.snapshot()[0] if e.pinned and e.kind == "buff"]
        self._sync_cells(entries)
        zoom = float(ov["zoom"])
        dim = max(0.0, min(1.0, float(ov["dim_missing"])))
        visible = []
        for e in entries:
            c = self.cells[e.id]
            th, tw = e.image.shape[:2]
            cw, ch = int(tw * 1.8), int(th * 2.1)
            det = result.present.get(e.id) if result is not None else None
            present = det is not None and result.roi is not None
            if present:
                img = context_crop(result.roi, det.box, cw, ch)
            elif ov["show_missing"]:
                img = cv2.convertScaleAbs(context_crop(e.image, (0, 0, tw, th), cw, ch),
                                          alpha=dim)
            else:
                img = None
            if c.was_present is not None and present != c.was_present:
                c.flash_until = now + float(ov["flash_seconds"])
            c.was_present = present
            if img is None:
                continue
            visible.append(e.id)
            c.photo = to_photo(img, zoom, cv2.INTER_LINEAR)
            c.img.configure(image=c.photo)
            auto = (autokey_status or {}).get(e.id)
            if ov["show_names"] or not present or auto:
                label = e.name if present else e.name + "  (off)"
                if auto and not present:
                    label += "\n" + auto
                if c.text.cget("text") != label:
                    c.text.configure(text=label)
                c.show_text()
            else:
                c.hide_text()
            missing_alert = not present and e.alert_missing
            c.text.configure(fg=ov["alert_color"] if missing_alert else (
                ov["text_color"] if present else ov["off_text_color"]))
            border = ov["flash_color"] if now < c.flash_until else (
                ov["alert_color"] if missing_alert else ov["cell_color"])
            c.frame.configure(highlightbackground=border)
        if visible != self.visible:
            self._regrid(visible)

        any_key = any(e.key for e in self.app.library.snapshot()[0])
        if any_key and not autokey_on:
            if not self.ak_label.winfo_ismapped():
                self.ak_label.pack(side="bottom", fill="x")
        elif self.ak_label.winfo_ismapped():
            self.ak_label.pack_forget()
        if unknown_count:
            self.badge.configure(text="%d new icon%s - name %s in BuffWatch" % (
                unknown_count, "" if unknown_count == 1 else "s",
                "it" if unknown_count == 1 else "them"))
            if not self.badge.winfo_ismapped():
                self.badge.pack(side="bottom", fill="x")
        elif self.badge.winfo_ismapped():
            self.badge.pack_forget()
        # The drag handle shows while unlocked, or as a hint while there is nothing else.
        want_handle = not ov["click_through"] or (not entries and not unknown_count)
        if want_handle and not self.handle.winfo_ismapped():
            self.handle.pack(side="top", fill="x", before=self.body)
        elif not want_handle and self.handle.winfo_ismapped():
            self.handle.pack_forget()
        self.place()
