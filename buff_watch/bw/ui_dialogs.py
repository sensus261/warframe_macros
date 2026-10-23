"""Region picker and "teach a buff" box picker."""

import tkinter as tk
from tkinter import messagebox, ttk

import cv2

from . import keys
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

    BUFF_PROMPT = ("Drag a box around the area where buff icons appear "
                   "(include room to the left - the list grows leftwards). "
                   "Enter = save, Esc = cancel.")

    def __init__(self, master, full_bgr, roi, on_done, title="select the buff area",
                 prompt=BUFF_PROMPT):
        super().__init__(master)
        self.title("BuffWatch - " + title)
        self.on_done = on_done
        H, W = full_bgr.shape[:2]
        sw, sh = self.winfo_screenwidth() * 0.9, self.winfo_screenheight() * 0.8
        self.scale = min(1.0, sw / W, sh / H)
        self.img_w, self.img_h = int(W * self.scale), int(H * self.scale)
        self.photo = to_photo(cv2.resize(full_bgr, (self.img_w, self.img_h),
                                          interpolation=cv2.INTER_AREA))
        ttk.Label(self, text=prompt).pack(anchor="w", padx=6, pady=4)
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


class CatalogPicker(tk.Toplevel):
    """Search the buff catalog by name and add one to the library, before ever
    seeing it in game."""

    def __init__(self, master, catalog, on_done):
        super().__init__(master)
        self.title("BuffWatch - add from catalog")
        self.on_done = on_done
        self.all = catalog.all_names()
        self.shown = self.all
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *a: self._filter())
        ent = ttk.Entry(top, textvariable=self.query, width=40)
        ent.pack(side="left", padx=4)

        mid = ttk.Frame(self, padding=(6, 0))
        mid.pack(fill="both", expand=True)
        self.lb = tk.Listbox(mid, width=48, height=18, activestyle="none", exportselection=False)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.lb.bind("<<ListboxSelect>>", lambda e: self._show())
        self.lb.bind("<Double-1>", lambda e: self._ok(True))
        side = ttk.Frame(mid, padding=(10, 0))
        side.pack(side="left", fill="y")
        self.preview = tk.Label(side, bg="black")
        self.preview.pack(anchor="n")
        self.info = ttk.Label(side, wraplength=220, justify="left")
        self.info.pack(anchor="n", pady=6)

        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        ttk.Button(bar, text="Add + show in overlay", command=lambda: self._ok(True)).pack(side="right")
        ttk.Button(bar, text="Add", command=lambda: self._ok(False)).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        self.bind("<Return>", lambda e: self._ok(True))
        self.bind("<Escape>", lambda e: self.destroy())
        self._filter()
        ent.focus_force()

    def _filter(self):
        q = self.query.get().strip().lower()
        self.shown = [x for x in self.all if q in x[0].lower()] if q else self.all
        self.lb.delete(0, "end")
        for name, _ in self.shown:
            self.lb.insert("end", name)
        if self.shown:
            self.lb.selection_set(0)
        self._show()

    def _current(self):
        sel = self.lb.curselection()
        return self.shown[sel[0]] if sel else None

    def _show(self):
        cur = self._current()
        if cur is None:
            self.preview.configure(image="")
            self.info.configure(text="")
            return
        name, icon = cur
        self._photo = to_photo(icon.thumb(96))
        self.preview.configure(image=self._photo)
        n = len(icon.names)
        self.info.configure(text=(
            "This icon is shared by %d buffs. BuffWatch can only tell that one of them is "
            "active, not which." % n) if n > 1 else "")

    def _ok(self, pin):
        cur = self._current()
        if cur is None:
            return
        self.on_done(cur[0], cur[1], pin)
        self.destroy()


class KeyEntry(ttk.Frame):
    """A key field: type a key name ('4', 'shift+e', 'f5', 'mouse4') or click Record
    and press the key."""

    def __init__(self, master, value="", on_change=None):
        super().__init__(master)
        self.on_change = on_change
        self.var = tk.StringVar(value=value or "")
        self.entry = ttk.Entry(self, textvariable=self.var, width=14)
        self.entry.pack(side="left")
        self.entry.bind("<Return>", lambda e: self._commit())
        self.entry.bind("<FocusOut>", lambda e: self._commit())
        self.btn = ttk.Button(self, text="Record", command=self._record)
        self.btn.pack(side="left", padx=4)
        self._last = self.var.get()

    def get(self):
        return self.var.get().strip().lower()

    def valid(self):
        try:
            keys.parse(self.get())
            return True
        except ValueError:
            return False

    def _commit(self):
        v = self.get()
        if v != self._last and (not v or self.valid()):
            self._last = v
            if self.on_change:
                self.on_change(v)

    def _record(self):
        self.btn.configure(text="press a key...")
        top = self.winfo_toplevel()
        top.focus_force()

        def got(ev):
            name = keys.from_tk_event(ev)
            if name is None or name in keys.MODIFIERS:
                return "break"  # wait for the real key (modifiers are combined in)
            top.unbind("<KeyPress>")
            self.btn.configure(text="Record")
            if name != "escape":
                self.var.set(name)
                self._commit()
            return "break"

        top.bind("<KeyPress>", got)


class AutoKeyDialog(tk.Toplevel):
    """Per-buff auto-press settings."""

    def __init__(self, master, entry, on_done):
        super().__init__(master)
        self.title("BuffWatch - auto-press for %s" % entry.name)
        self.on_done = on_done
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        ttk.Label(f, wraplength=420, justify="left", text=(
            "When '%s' runs out, BuffWatch taps this key until it sees the buff again. "
            "Use the key the ability or item is bound to in game." % entry.name)).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(f, text="Key:").grid(row=1, column=0, sticky="w")
        self.key = KeyEntry(f, entry.key or "")
        self.key.grid(row=1, column=1, sticky="w")
        ttk.Label(f, foreground="#666", text="e.g. 4, shift+e, f5, mouse4").grid(
            row=2, column=1, sticky="w")
        ttk.Label(f, text="Press every (ms):").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.interval = tk.IntVar(value=entry.key_interval)
        ttk.Spinbox(f, from_=300, to=30000, increment=100, textvariable=self.interval,
                    width=8).grid(row=3, column=1, sticky="w", pady=(8, 0))
        ttk.Label(f, foreground="#666", wraplength=300, justify="left",
                  text="Longer than the cast animation, or a second press may cancel it."
                  ).grid(row=4, column=1, sticky="w")
        ttk.Label(f, text="Give up after (presses):").grid(row=5, column=0, sticky="w", pady=(8, 0))
        self.max = tk.IntVar(value=entry.key_max)
        ttk.Spinbox(f, from_=1, to=50, textvariable=self.max, width=8).grid(
            row=5, column=1, sticky="w", pady=(8, 0))
        bar = ttk.Frame(f)
        bar.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._ok).pack(side="right")
        ttk.Button(bar, text="Turn off", command=self._off).pack(side="right", padx=4)
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()

    def _ok(self):
        k = self.key.get()
        if not k:
            return self._off()
        if not self.key.valid():
            messagebox.showwarning("BuffWatch", "Unknown key '%s'." % k, parent=self)
            return
        try:
            interval = max(300, int(self.interval.get()))
            n = max(1, int(self.max.get()))
        except (tk.TclError, ValueError):
            messagebox.showwarning("BuffWatch", "Enter whole numbers.", parent=self)
            return
        self.on_done(k, interval, n)
        self.destroy()

    def _off(self):
        self.on_done(None, int(self.interval.get() or 1500), int(self.max.get() or 5))
        self.destroy()
