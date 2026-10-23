"""Always-on-top overlay that shows the pinned buffs magnified."""

import sys
import tkinter as tk

import cv2

from . import winutil
from .ui_common import context_crop, to_photo

KEY = "#ff00fe"  # this colour is made fully transparent
BG = "#101014"


class _Cell:
    def __init__(self, parent, entry_id):
        self.entry_id = entry_id
        self.frame = tk.Frame(parent, bg=BG, highlightthickness=2, highlightbackground=BG)
        self.img = tk.Label(self.frame, bg=BG, bd=0)
        self.img.pack(padx=2, pady=(2, 0))
        self.text = tk.Label(self.frame, bg=BG, fg="#e8e8e8", font=("Segoe UI", 10, "bold"))
        self.text.pack(fill="x", pady=(0, 2))
        self.photo = None
        self.was_present = None
        self.flash_until = 0


class Overlay(tk.Toplevel):
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
        self.handle = tk.Label(self, text="BuffWatch overlay - drag me", bg="#2b5d9b",
                               fg="white", font=("Segoe UI", 8), padx=4)
        self.cells = {}
        self.order = []
        self._drag = None
        self._styled = None
        for w in (self, self.body, self.handle):
            self._bind_drag(w)
        ov = app.settings["overlay"]
        self.geometry("+%d+%d" % (ov["x"], ov["y"]))

    # ------------------------------------------------------------ window state
    def apply_settings(self):
        ov = self.app.settings["overlay"]
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
        ov = self.app.settings["overlay"]
        ov["x"], ov["y"] = self.winfo_x(), self.winfo_y()
        self.app.save_settings()

    # ------------------------------------------------------------ content
    def _layout(self, pinned):
        ids = [e.id for e in pinned]
        if ids == self.order:
            return
        for cid in list(self.cells):
            if cid not in ids:
                self.cells.pop(cid).frame.destroy()
        for e in pinned:
            if e.id not in self.cells:
                c = _Cell(self.body, e.id)
                for w in (c.frame, c.img, c.text):
                    self._bind_drag(w)
                self.cells[e.id] = c
        self.order = ids
        self._regrid()

    def _regrid(self):
        horiz = self.app.settings["overlay"]["orientation"] == "horizontal"
        for i, cid in enumerate(self.order):
            c = self.cells[cid]
            c.frame.grid_forget()
            c.frame.grid(row=0 if horiz else i, column=i if horiz else 0, padx=2, pady=2,
                         sticky="nsew")

    def refresh_layout(self):
        self.order = []
        self._layout([e for e in self.app.library.snapshot()[0] if e.pinned and e.kind == "buff"])

    def show(self, result, unknown_count, now, autokey_status=None, autokey_on=True):
        ov = self.app.settings["overlay"]
        if not ov["visible"]:
            return
        entries = [e for e in self.app.library.snapshot()[0] if e.pinned and e.kind == "buff"]
        self._layout(entries)
        zoom = float(ov["zoom"])
        for e in entries:
            c = self.cells[e.id]
            th, tw = e.image.shape[:2]
            cw, ch = int(tw * 1.8), int(th * 2.1)
            det = result.present.get(e.id) if result is not None else None
            present = det is not None and result.roi is not None
            if present:
                img = context_crop(result.roi, det.box, cw, ch)
            elif ov["show_missing"]:
                img = context_crop(e.image, (0, 0, tw, th), cw, ch) // 3
            else:
                img = None
            if c.was_present is not None and present != c.was_present:
                c.flash_until = now + 0.6
            c.was_present = present
            if img is None:
                if c.frame.winfo_ismapped():
                    c.frame.grid_remove()
                continue
            if not c.frame.winfo_ismapped():
                c.frame.grid()
            c.photo = to_photo(img, zoom, cv2.INTER_LINEAR)
            c.img.configure(image=c.photo)
            auto = (autokey_status or {}).get(e.id)
            if ov["show_names"] or not present or auto:
                label = e.name if present else e.name + "  (off)"
                if auto and not present:
                    label += "\n" + auto
                if c.text.cget("text") != label:
                    c.text.configure(text=label)
                if not c.text.winfo_ismapped():
                    c.text.pack(fill="x", pady=(0, 2))
            elif c.text.winfo_ismapped():
                c.text.pack_forget()
            missing_alert = not present and e.alert_missing
            c.text.configure(fg="#ff5050" if missing_alert else ("#e8e8e8" if present else "#8a8a8a"))
            border = "#ffd400" if now < c.flash_until else ("#d02020" if missing_alert else BG)
            c.frame.configure(highlightbackground=border)

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
