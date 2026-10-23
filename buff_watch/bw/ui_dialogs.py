"""Region picker and "teach a buff" box picker."""

import tkinter as tk
from tkinter import messagebox, ttk

import cv2

from .ui_common import to_photo


class _DragRect:
    """Rubber-band rectangle on a canvas. Coordinates in canvas pixels."""

    def __init__(self, canvas, color="#00ff66"):
        self.canvas = canvas
        self.color = color
        self.rect = None
        self.start = None
        self.box = None  # (x0, y0, x1, y1)
        canvas.bind("<ButtonPress-1>", self._down)
        canvas.bind("<B1-Motion>", self._move)

    def set(self, x0, y0, x1, y1):
        self.box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        if self.rect is None:
            self.rect = self.canvas.create_rectangle(*self.box, outline=self.color, width=2)
        else:
            self.canvas.coords(self.rect, *self.box)

    def _down(self, ev):
        self.start = (ev.x, ev.y)
        self.set(ev.x, ev.y, ev.x, ev.y)

    def _move(self, ev):
        if self.start:
            self.set(self.start[0], self.start[1], ev.x, ev.y)


class RegionPicker(tk.Toplevel):
    """Shows a full screenshot; the user drags a box around the buff area."""

    def __init__(self, master, full_bgr, roi, on_done):
        super().__init__(master)
        self.title("BuffWatch - select the buff area")
        self.on_done = on_done
        H, W = full_bgr.shape[:2]
        sw, sh = self.winfo_screenwidth() * 0.9, self.winfo_screenheight() * 0.8
        self.scale = min(1.0, sw / W, sh / H)
        self.img_w, self.img_h = int(W * self.scale), int(H * self.scale)
        self.photo = to_photo(cv2.resize(full_bgr, (self.img_w, self.img_h),
                                          interpolation=cv2.INTER_AREA))
        ttk.Label(self, text="Drag a box around the area where buff icons appear "
                             "(include room to the left - the list grows leftwards). "
                             "Enter = save, Esc = cancel.").pack(anchor="w", padx=6, pady=4)
        c = tk.Canvas(self, width=self.img_w, height=self.img_h, highlightthickness=0,
                      cursor="crosshair")
        c.pack()
        c.create_image(0, 0, image=self.photo, anchor="nw")
        self.drag = _DragRect(c)
        x0, y0, x1, y1 = roi
        self.drag.set(x0 * self.img_w, y0 * self.img_h, x1 * self.img_w, y1 * self.img_h)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=4)
        ttk.Button(bar, text="Save", command=self._ok).pack(side="right", padx=6)
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.focus_force()

    def _ok(self):
        x0, y0, x1, y1 = self.drag.box
        if x1 - x0 < 10 or y1 - y0 < 10:
            messagebox.showwarning("BuffWatch", "Drag a bigger box.", parent=self)
            return
        self.on_done([round(x0 / self.img_w, 4), round(y0 / self.img_h, 4),
                      round(x1 / self.img_w, 4), round(y1 / self.img_h, 4)])
        self.destroy()


class BoxPicker(tk.Toplevel):
    """Zoomed view of the buff area: drag a tight box around ONE icon (without the
    number under it) and give it a name."""

    def __init__(self, master, roi_bgr, on_done, box=None, name=""):
        super().__init__(master)
        self.title("BuffWatch - teach an icon")
        self.on_done = on_done
        self.roi = roi_bgr
        H, W = roi_bgr.shape[:2]
        self.zoom = max(1.0, min(6.0, 1200 / W, 560 / H))
        self.photo = to_photo(roi_bgr, self.zoom, cv2.INTER_LINEAR)
        ttk.Label(self, text="Drag a tight box around ONE icon - just the symbol, not the "
                             "number under it.").pack(anchor="w", padx=6, pady=4)
        c = tk.Canvas(self, width=int(W * self.zoom), height=int(H * self.zoom), highlightthickness=0,
                      cursor="crosshair", bg="black")
        c.pack(padx=6)
        c.create_image(0, 0, image=self.photo, anchor="nw")
        self.drag = _DragRect(c, "#ffdd00")
        if box:
            x, y, w, h = box
            z = self.zoom
            self.drag.set(x * z, y * z, (x + w) * z, (y + h) * z)

        form = ttk.Frame(self)
        form.pack(fill="x", padx=6, pady=6)
        ttk.Label(form, text="Name:").pack(side="left")
        self.name = tk.StringVar(value=name)
        ent = ttk.Entry(form, textvariable=self.name, width=32)
        ent.pack(side="left", padx=4)
        self.pin = tk.BooleanVar(value=True)
        ttk.Checkbutton(form, text="Show in overlay", variable=self.pin).pack(side="left", padx=8)
        ttk.Button(form, text="Save buff", command=lambda: self._ok("buff")).pack(side="right")
        ttk.Button(form, text="Not a buff (ignore)",
                   command=lambda: self._ok("ignore")).pack(side="right", padx=4)
        ttk.Button(form, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        self.bind("<Return>", lambda e: self._ok("buff"))
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        ent.focus_force()

    def _ok(self, kind):
        if not self.drag.box:
            messagebox.showwarning("BuffWatch", "Drag a box around the icon first.", parent=self)
            return
        z = self.zoom
        x0, y0, x1, y1 = (int(round(v / z)) for v in self.drag.box)
        H, W = self.roi.shape[:2]
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if x1 - x0 < 6 or y1 - y0 < 6:
            messagebox.showwarning("BuffWatch", "That box is too small.", parent=self)
            return
        name = self.name.get().strip()
        if kind == "buff" and not name:
            messagebox.showwarning("BuffWatch", "Give the buff a name.", parent=self)
            return
        self.on_done(self.roi[y0:y1, x0:x1].copy(), name or "(ignored)", kind,
                     self.pin.get() and kind == "buff")
        self.destroy()
