"""Main window: source/region setup, live preview, buff library and unknown-icon queue."""

import queue
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import cv2

from . import config, keys, winutil
from .autokey import AutoKey
from .capture import CaptureError, ImageSource, ScreenSource, list_monitors
from .catalog import Catalog
from .library import KIND_BUFF, KIND_IGNORE, Library
from .ui_common import context_crop, thumb, to_photo
from .ui_dialogs import AutoKeyDialog, BoxPicker, CatalogPicker, KeyEntry, RegionPicker
from .ui_overlay import Overlay
from .ui_overlay_settings import OverlaySettingsTab
from .worker import Worker

PREVIEW_W = 760


class App:
    def __init__(self, image_path=None):
        winutil.enable_dpi_awareness()
        self.image_path = image_path
        self.settings = config.load_settings()
        self.library = Library()
        self.library.load()
        self.catalog = Catalog().load()
        self.worker = Worker(self.settings, self.library, self.catalog, image_path)
        self.sender = keys.Sender()
        self.autokey = AutoKey(self.settings, self.sender, keys.foreground_title)
        self.autokey_status = {}
        self.hotkey_events = queue.Queue()
        self.hotkey = None
        self.result = None
        self.unknowns = []
        self.unknown_idx = 0
        self._thumbs = {}
        self._last_tree = 0
        self._last_preview = 0

        self.root = tk.Tk()
        self.root.title("BuffWatch")
        self.root.minsize(780, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        style = ttk.Style(self.root)
        style.configure("Treeview", rowheight=36)
        self._build()
        self.overlay = Overlay(self)
        self.overlay.apply_settings()

    # ================================================================ layout
    def _build(self):
        r = self.root
        top = ttk.Frame(r, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Capture:").pack(side="left")
        self.source_var = tk.StringVar()
        self.source_box = ttk.Combobox(top, textvariable=self.source_var, width=34,
                                       state="readonly")
        self.source_box.pack(side="left", padx=4)
        self.source_box.bind("<<ComboboxSelected>>", self._source_changed)
        self.source_box.bind("<Button-1>", lambda e: self._fill_sources())
        ttk.Button(top, text="Select buff area...", command=self.pick_region).pack(side="left", padx=4)
        ttk.Button(top, text="Teach icon...", command=self.teach).pack(side="left", padx=4)
        self.pause_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Pause", variable=self.pause_var,
                        command=self._pause_changed).pack(side="left", padx=8)
        self.status = ttk.Label(top, text="starting...", foreground="#666")
        self.status.pack(side="right")
        self._fill_sources()

        self.preview = ttk.Label(r, anchor="center", background="black")
        self.preview.pack(fill="x", padx=6)

        self.nb = ttk.Notebook(r)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._build_library_tab()
        self._build_unknown_tab()
        self._build_overlay_tab()
        self._build_settings_tab()
        self._build_autokey_tab()

    def _fill_sources(self):
        opts = []
        try:
            for i, m in list_monitors():
                opts.append("Monitor %d (%dx%d)" % (i, m["width"], m["height"]))
        except Exception:
            pass
        opts.append("Window: " + self.settings["source"].get("window_title", "Warframe"))
        self.source_box["values"] = opts
        src = self.settings["source"]
        if self.image_path:
            self.source_var.set("Test image: " + self.image_path)
            self.source_box.configure(state="disabled")
        elif src["kind"] == "window":
            self.source_var.set(opts[-1])
        else:
            cur = [o for o in opts if o.startswith("Monitor %d " % src["monitor"])]
            self.source_var.set(cur[0] if cur else opts[0])

    def _source_changed(self, _ev=None):
        v = self.source_var.get()
        src = dict(self.settings["source"])
        if v.startswith("Window"):
            title = simpledialog.askstring(
                "BuffWatch", "Capture the window whose title contains:",
                initialvalue=src.get("window_title", "Warframe"), parent=self.root)
            if not title:
                self._fill_sources()
                return
            src.update(kind="window", window_title=title)
        else:
            src.update(kind="monitor", monitor=int(v.split()[1]))
        self.settings["source"] = src
        self.save_settings()
        self._fill_sources()

    def _pause_changed(self):
        if self.pause_var.get():
            self.worker.running.clear()
        else:
            self.worker.running.set()

    # ------------------------------------------------------------ library tab
    def _build_library_tab(self):
        f = ttk.Frame(self.nb, padding=4)
        self.nb.add(f, text="Buffs")
        cols = ("pin", "name", "status", "auto", "score", "thr", "opts")
        self.tree = ttk.Treeview(f, columns=cols, height=8, selectmode="extended")
        self.tree.heading("#0", text="Icon")
        self.tree.column("#0", width=60, stretch=False)
        for c, t, w in (("pin", "Overlay", 64), ("name", "Name", 220), ("status", "Status", 70),
                        ("auto", "Auto-press", 190), ("score", "Match", 56),
                        ("thr", "Threshold", 70), ("opts", "Options", 150)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, stretch=c == "name",
                             anchor="w" if c in ("name", "opts", "auto") else "center")
        self.tree.tag_configure("on", foreground="#0a7a20")
        self.tree.tag_configure("ignored", foreground="#999")
        sb = ttk.Scrollbar(f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda e: self.toggle_pin())
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

        bar = ttk.Frame(f)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        for text, cmd in (("Add from catalog...", self.add_from_catalog),
                          ("Show / hide in overlay", self.toggle_pin),
                          ("Auto-press key...", self.set_autokey),
                          ("Rename", self.rename), ("Threshold...", self.set_threshold)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        bar2 = ttk.Frame(f)
        bar2.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        for text, cmd in (("Warn when missing", self.toggle_alert),
                          ("Coloured icon", self.toggle_mode),
                          ("Up", lambda: self.move(-1)), ("Down", lambda: self.move(1)),
                          ("Delete", self.delete)):
            ttk.Button(bar2, text=text, command=cmd).pack(side="left", padx=2)
        self.show_ignored = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar2, text="Show ignored", variable=self.show_ignored,
                        command=self.refresh_tree).pack(side="right")
        ttk.Label(f, foreground="#666", text=(
            "Double-click a row to show/hide it in the overlay. Select several rows with "
            "Ctrl/Shift. 'Coloured icon' matches in grayscale instead of white-only "
            "(use it for icons that are not white).")).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.refresh_tree()

    def _selected(self):
        return [self.library.get(i) for i in self.tree.selection() if self.library.get(i)]

    def refresh_tree(self):
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for e in self.library.snapshot()[0]:
            if e.kind == KIND_IGNORE and not self.show_ignored.get():
                continue
            if e.id not in self._thumbs:
                self._thumbs[e.id] = to_photo(thumb(e.image, 32))
            self.tree.insert("", "end", iid=e.id, image=self._thumbs[e.id],
                             values=self._row_values(e),
                             tags=("ignored",) if e.kind == KIND_IGNORE else ())
        keep = [i for i in sel if self.tree.exists(i)]
        if keep:
            self.tree.selection_set(keep)
        self._last_tree = 0

    def _row_values(self, e, present=False, score=None):
        opts = []
        if e.kind == KIND_IGNORE:
            opts.append("ignored")
        if e.alert_missing:
            opts.append("warn when missing")
        if e.mode == "gray":
            opts.append("coloured")
        auto = ""
        if e.key:
            auto = "%s every %.1fs" % (e.key, e.key_interval / 1000.0)
            live = self.autokey_status.get(e.id)
            if live:
                auto += " - " + live
        return ("yes" if e.pinned else "",
                e.name,
                "ACTIVE" if present else "-",
                auto,
                "%.2f" % score if score else "",
                "%.2f" % e.threshold if e.threshold else "default",
                ", ".join(opts))

    def _update_tree_status(self):
        res = self.result
        for e in self.library.snapshot()[0]:
            if not self.tree.exists(e.id):
                continue
            present = res is not None and e.id in res.present
            score = res.scores.get(e.id) if res is not None else None
            self.tree.item(e.id, values=self._row_values(e, present, score),
                           tags=("on",) if present else (
                               ("ignored",) if e.kind == KIND_IGNORE else ()))

    def add_from_catalog(self):
        if not len(self.catalog):
            messagebox.showinfo("BuffWatch", "The catalog folder is missing.", parent=self.root)
            return
        cap_h = self.result.capture_h if self.result is not None else 1080
        size = self.catalog.icon_size(self.settings, cap_h)

        def done(name, icon, pin):
            self.library.add(name, icon.render(size), KIND_BUFF, pinned=pin,
                             catalog=icon.file, learned=False)
            self.refresh_tree()

        CatalogPicker(self.root, self.catalog, done)

    def toggle_pin(self):
        for e in self._selected():
            if e.kind == KIND_BUFF:
                self.library.update(e.id, pinned=not e.pinned)
        self.refresh_tree()

    def set_autokey(self):
        sel = [e for e in self._selected() if e.kind == KIND_BUFF]
        if len(sel) != 1:
            messagebox.showinfo("BuffWatch", "Select one buff first.", parent=self.root)
            return
        e = sel[0]

        def done(key, interval, max_presses):
            self.library.update(e.id, key=key, key_interval=interval, key_max=max_presses)
            self.refresh_tree()

        AutoKeyDialog(self.root, e, done)

    def toggle_alert(self):
        for e in self._selected():
            self.library.update(e.id, alert_missing=not e.alert_missing)
        self.refresh_tree()

    def toggle_mode(self):
        for e in self._selected():
            self.library.update(e.id, mode="white" if e.mode == "gray" else "gray")
        self.refresh_tree()

    def rename(self):
        sel = self._selected()
        if len(sel) != 1:
            return
        name = simpledialog.askstring("BuffWatch", "Name:", initialvalue=sel[0].name,
                                      parent=self.root)
        if name and name.strip():
            self.library.update(sel[0].id, name=name.strip())
            self.refresh_tree()

    def set_threshold(self):
        sel = self._selected()
        if not sel:
            return
        v = simpledialog.askfloat(
            "BuffWatch", "Match threshold 0.30 - 0.99 (lower = finds it more easily but "
                         "may confuse it with similar icons). 0 = use the default.",
            initialvalue=sel[0].threshold or self.settings["match_threshold"],
            minvalue=0.0, maxvalue=0.99, parent=self.root)
        if v is None:
            return
        for e in sel:
            self.library.update(e.id, threshold=round(v, 2) if v >= 0.3 else None)
        self.refresh_tree()

    def move(self, delta):
        sel = self._selected()
        for e in (sel if delta < 0 else reversed(sel)):
            self.library.move(e.id, delta)
        self.refresh_tree()

    def delete(self):
        sel = self._selected()
        if sel and messagebox.askyesno("BuffWatch", "Delete %d icon(s)?" % len(sel),
                                       parent=self.root):
            for e in sel:
                self.library.remove(e.id)
                self._thumbs.pop(e.id, None)
            self.refresh_tree()

    # ------------------------------------------------------------ unknown tab
    def _build_unknown_tab(self):
        f = ttk.Frame(self.nb, padding=8)
        self.unknown_tab = f
        self.nb.add(f, text="New icons")
        self.unk_title = ttk.Label(f, text="No new icons.", font=("Segoe UI", 11, "bold"))
        self.unk_title.grid(row=0, column=0, columnspan=3, sticky="w")
        self.unk_img = ttk.Label(f)
        self.unk_img.grid(row=1, column=0, rowspan=5, padx=(0, 12), pady=6, sticky="n")
        self.unk_ctx = ttk.Label(f)
        self.unk_ctx.grid(row=6, column=0, columnspan=3, sticky="w")
        self.unk_sugg_label = ttk.Label(f, text="")
        self.unk_sugg_label.grid(row=1, column=1, columnspan=2, sticky="w")
        self.unk_sugg = ttk.Frame(f)
        self.unk_sugg.grid(row=2, column=1, columnspan=2, sticky="w", pady=(2, 6))
        ttk.Label(f, text="What is it?").grid(row=3, column=1, sticky="w")
        self.unk_name = tk.StringVar()
        self.unk_entry = ttk.Combobox(f, textvariable=self.unk_name, width=40)
        self.unk_entry.grid(row=3, column=2, sticky="w")
        self.unk_entry.bind("<Return>", lambda e: self.unknown_save(True))
        self.unk_choice = None  # catalog Icon picked from the suggestions
        b = ttk.Frame(f)
        b.grid(row=4, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Button(b, text="Save + show in overlay",
                   command=lambda: self.unknown_save(True)).pack(side="left", padx=2)
        ttk.Button(b, text="Save", command=lambda: self.unknown_save(False)).pack(side="left", padx=2)
        ttk.Button(b, text="Fix the box...", command=self.unknown_adjust).pack(side="left", padx=2)
        ttk.Button(b, text="Not a buff (ignore forever)",
                   command=self.unknown_ignore).pack(side="left", padx=2)
        ttk.Button(b, text="Skip for now", command=self.unknown_skip).pack(side="left", padx=2)
        b2 = ttk.Frame(f)
        b2.grid(row=5, column=1, columnspan=2, sticky="nw")
        ttk.Button(b2, text="< Prev", command=lambda: self.unknown_step(-1)).pack(side="left", padx=2)
        ttk.Button(b2, text="Next >", command=lambda: self.unknown_step(1)).pack(side="left", padx=2)
        ttk.Label(b2, foreground="#666", wraplength=440, justify="left", text=(
            "Pick the matching icon from the catalog suggestions, or type a name. If the "
            "box cuts the icon or grabs the number under it, use 'Fix the box...'. If "
            "nothing gets detected, use 'Teach icon...' at the top.")).pack(side="left", padx=12)

    def _current_unknown(self):
        if not self.unknowns:
            return None
        self.unknown_idx %= len(self.unknowns)
        return self.unknowns[self.unknown_idx]

    def show_unknown(self):
        n = len(self.unknowns)
        self.nb.tab(self.unknown_tab, text="New icons (%d)" % n if n else "New icons")
        self.root.title("BuffWatch - %d new icon%s" % (n, "" if n == 1 else "s") if n else "BuffWatch")
        for w in self.unk_sugg.winfo_children():
            w.destroy()
        self._sugg_photos = []
        self.unk_choice = None
        self.unk_entry["values"] = ()
        self.unk_name.set("")
        u = self._current_unknown()
        if u is None:
            self.unk_title.configure(text="No new icons.")
            self.unk_img.configure(image="")
            self.unk_ctx.configure(image="")
            self.unk_sugg_label.configure(text="")
            return
        self.unk_title.configure(text="New icon %d of %d" % (self.unknown_idx + 1, n))
        x, y, w, h = u.box
        self._unk_photo = to_photo(thumb(context_crop(u.frame, u.box), 150))
        self.unk_img.configure(image=self._unk_photo)
        ctx = u.frame.copy()
        cv2.rectangle(ctx, (x - 1, y - 1), (x + w, y + h), (0, 220, 255), 1)
        s = min(2.0, PREVIEW_W / ctx.shape[1])
        self._unk_ctx_photo = to_photo(ctx, s, cv2.INTER_LINEAR)
        self.unk_ctx.configure(image=self._unk_ctx_photo)

        sugg = [m for m in u.suggestions if m.score >= 0.5][:4]
        if not len(self.catalog):
            self.unk_sugg_label.configure(text="")
        elif not sugg:
            self.unk_sugg_label.configure(
                text="Not in the catalog - probably a newer buff. Type a name.")
        else:
            self.unk_sugg_label.configure(text="Looks like (best match first):")
            for m in sugg:
                photo = to_photo(m.icon.thumb(40))
                self._sugg_photos.append(photo)
                ttk.Button(self.unk_sugg, image=photo, compound="left",
                           text="%s\n%d%% match" % (m.icon.label[:40], round(m.score * 100)),
                           command=lambda ic=m.icon: self._pick_suggestion(ic)).pack(
                    side="left", padx=2)
            # Prefer a buff the user already added from the catalog but hasn't seen yet.
            waiting = [m for m in sugg if any(not e.learned for e in
                                             self.library.find_catalog(m.icon.file))]
            if waiting:
                self._pick_suggestion(waiting[0].icon)
            elif sugg[0].score >= 0.6:
                self._pick_suggestion(sugg[0].icon)

    def _pick_suggestion(self, icon):
        self.unk_choice = icon
        self.unk_entry["values"] = icon.names
        added = [e.name for e in self.library.find_catalog(icon.file) if not e.learned]
        self.unk_name.set(added[0] if added else icon.names[0])
        if len(icon.names) > 1:
            self.unk_sugg_label.configure(
                text="%d buffs share this icon - pick yours from the name list:" % len(icon.names))
        self.unk_entry.focus_set()

    def unknown_step(self, d):
        self.unknown_idx += d
        self.show_unknown()

    def _drop_unknown(self, u):
        self.worker.resolve_unknown(u.uid)
        self.unknowns = [x for x in self.unknowns if x.uid != u.uid]
        self.show_unknown()

    def unknown_save(self, pin):
        u = self._current_unknown()
        name = self.unk_name.get().strip()
        if u is None:
            return
        if not name:
            self.unk_entry.focus_set()
            return
        icon = self.unk_choice
        waiting = [e for e in self.library.find_catalog(icon.file)
                   if not e.learned and e.name == name] if icon else []
        if waiting:  # added from the catalog earlier: now we know how it really looks
            self.library.set_image(waiting[0].id, u.crop)
            if pin:
                self.library.update(waiting[0].id, pinned=True)
        else:
            self.library.add(name, u.crop, KIND_BUFF, pinned=pin,
                             catalog=icon.file if icon and name in icon.names else None)
        self._drop_unknown(u)
        self.refresh_tree()

    def unknown_ignore(self):
        u = self._current_unknown()
        if u is not None:
            self.library.add("(ignored)", u.crop, KIND_IGNORE)
            self._drop_unknown(u)
            self.refresh_tree()

    def unknown_skip(self):
        u = self._current_unknown()
        if u is not None:
            self._drop_unknown(u)

    def unknown_adjust(self):
        u = self._current_unknown()
        if u is None:
            return

        def done(crop, name, kind, pin):
            self.library.add(name, crop, kind, pinned=pin)
            self._drop_unknown(u)
            self.refresh_tree()

        BoxPicker(self.root, u.frame, done, box=u.box, name=self.unk_name.get().strip())

    # ------------------------------------------------------------ overlay tab
    def _build_overlay_tab(self):
        self.overlay_tab = OverlaySettingsTab(self.nb, self)
        self.nb.add(self.overlay_tab, text="Overlay")

    def overlay_moved(self):
        self.overlay_tab.sync_position()

    # ------------------------------------------------------------ settings tab
    def _build_settings_tab(self):
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="Detection")
        s = self.settings
        self.set_vars = {}
        rows = (("match_threshold", "Default match threshold", 0.3, 0.99, 0.01),
                ("fps", "Scans per second", 1, 30, 1),
                ("miss_frames", "Frames a buff may be unseen before it counts as off", 0, 30, 1),
                ("stable_frames", "Frames an unknown icon must stay put before asking", 2, 100, 1))
        for i, (key, text, lo, hi, step) in enumerate(rows):
            ttk.Label(f, text=text).grid(row=i, column=0, sticky="w", pady=2)
            v = tk.DoubleVar(value=s[key])
            self.set_vars[key] = v
            ttk.Spinbox(f, from_=lo, to=hi, increment=step, textvariable=v, width=7,
                        command=self._settings_changed).grid(row=i, column=1, sticky="w", padx=6)
        self.disc_var = tk.BooleanVar(value=s["discovery"])
        ttk.Checkbutton(f, text="Detect new icons and ask me to name them", variable=self.disc_var,
                        command=self._settings_changed).grid(row=len(rows), column=0, sticky="w", pady=4)
        self.prev_var = tk.BooleanVar(value=s["preview"])
        ttk.Checkbutton(f, text="Live preview in this window", variable=self.prev_var,
                        command=self._settings_changed).grid(row=len(rows) + 1, column=0, sticky="w")
        self.auto_var = tk.BooleanVar(value=s["catalog_auto_name"])
        ttk.Checkbutton(f, text="Name new icons by myself when the catalog match is certain",
                        variable=self.auto_var, command=self._settings_changed).grid(
            row=len(rows) + 2, column=0, sticky="w", pady=(4, 0))
        self.only_var = tk.BooleanVar(value=s["catalog_only"])
        ttk.Checkbutton(f, text="Only ask about icons that are in the catalog "
                                "(hides newer buffs the catalog doesn't have)",
                        variable=self.only_var, command=self._settings_changed).grid(
            row=len(rows) + 3, column=0, sticky="w")
        ttk.Label(f, foreground="#666", text="Catalog: %d icons, %d buff names." % (
            len(self.catalog), len(self.catalog.all_names()))).grid(
            row=len(rows) + 4, column=0, sticky="w", pady=4)
        ttk.Button(f, text="Apply", command=self._settings_changed).grid(
            row=len(rows) + 5, column=0, sticky="w", pady=8)

    # ------------------------------------------------------------ auto-press tab
    def _build_autokey_tab(self):
        f = ttk.Frame(self.nb, padding=8)
        self.nb.add(f, text="Auto-press")
        ak = self.settings["autokey"]
        ttk.Label(f, wraplength=700, justify="left", text=(
            "Give a buff a key (Buffs tab > Auto-press key...) and BuffWatch taps that key "
            "when the buff runs out, every few seconds, until the buff shows up again. It "
            "gives up after the set number of presses (out of energy, menu open...) and "
            "tries again only after it has seen the buff once more.")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(f, wraplength=700, justify="left", foreground="#9a4b00", text=(
            "This sends simulated key presses to the game, like AutoHotkey does. That is "
            "automation, so Digital Extremes' rules on macros apply. Use it at your own "
            "risk. Nothing is pressed unless you assign a key to a buff.")).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(6, 10))
        self.ak_enabled = tk.BooleanVar(value=ak["enabled"])
        ttk.Checkbutton(f, text="Auto-press on", variable=self.ak_enabled,
                        command=self._autokey_changed).grid(row=2, column=0, sticky="w")
        self.ak_focus = tk.BooleanVar(value=ak["only_when_focused"])
        ttk.Checkbutton(f, text="Only press while the game window is focused (title contains "
                                "the window title from the Capture box, default 'Warframe')",
                        variable=self.ak_focus, command=self._autokey_changed).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=2)
        ttk.Label(f, text="On/off hotkey (works in game):").grid(row=4, column=0, sticky="w", pady=6)
        self.ak_hotkey = KeyEntry(f, ak["toggle_hotkey"], on_change=self._hotkey_changed)
        self.ak_hotkey.grid(row=4, column=1, sticky="w")
        self.ak_hotkey_msg = ttk.Label(f, foreground="#666")
        self.ak_hotkey_msg.grid(row=4, column=2, sticky="w", padx=8)

    def _autokey_changed(self):
        ak = self.settings["autokey"]
        ak["enabled"] = bool(self.ak_enabled.get())
        ak["only_when_focused"] = bool(self.ak_focus.get())
        self.save_settings()

    def _hotkey_changed(self, spec):
        self.settings["autokey"]["toggle_hotkey"] = spec
        self.save_settings()
        self._start_hotkey()

    def _start_hotkey(self):
        if self.hotkey is not None:
            self.hotkey.stop()
            self.hotkey = None
        spec = self.settings["autokey"].get("toggle_hotkey")
        if not spec:
            self.ak_hotkey_msg.configure(text="no hotkey")
            return
        self.hotkey = keys.HotkeyListener(spec, self.hotkey_events)
        err = self.hotkey.start_and_wait()
        self.ak_hotkey_msg.configure(text=err or "press %s in game to switch auto-press on/off"
                                     % spec.upper(), foreground="#b00020" if err else "#666")

    def _settings_changed(self):
        s = self.settings
        for k, v in self.set_vars.items():
            try:
                val = float(v.get())
            except (tk.TclError, ValueError):
                continue
            s[k] = round(val, 2) if k == "match_threshold" else int(val)
        s["discovery"] = bool(self.disc_var.get())
        s["preview"] = bool(self.prev_var.get())
        s["catalog_auto_name"] = bool(self.auto_var.get())
        s["catalog_only"] = bool(self.only_var.get())
        self.library.touch()
        self.save_settings()

    # ================================================================ actions
    def save_settings(self):
        config.save_settings(self.settings)

    def _grab_full(self):
        if self.image_path:
            return ImageSource(self.image_path).grab_full()
        src = ScreenSource(self.settings["source"])
        try:
            return src.grab_full()
        finally:
            src.close()

    def pick_region(self):
        # Hide our windows for a moment so they are not in the screenshot.
        self.root.withdraw()
        self.overlay.withdraw()
        self.root.after(350, self._pick_region_grab)

    def _pick_region_grab(self):
        try:
            full = self._grab_full()
        except (CaptureError, Exception) as ex:
            self.root.deiconify()
            self.overlay.apply_settings()
            messagebox.showerror("BuffWatch", "Capture failed: %s" % ex, parent=self.root)
            return
        self.root.deiconify()
        self.overlay.apply_settings()

        def done(roi):
            self.settings["roi"] = roi
            self.save_settings()

        RegionPicker(self.root, full, self.settings["roi"], done)

    def teach(self):
        if self.result is None or self.result.roi is None:
            messagebox.showinfo("BuffWatch", "Nothing captured yet.", parent=self.root)
            return

        def done(crop, name, kind, pin):
            self.library.add(name, crop, kind, pinned=pin)
            self.refresh_tree()

        BoxPicker(self.root, self.result.roi.copy(), done)

    # ================================================================ loop
    def _poll(self):
        res = None
        new, recognised, learned = [], [], []
        try:
            while True:
                res = self.worker.results.get_nowait()
                new += res.new_unknowns
                recognised += res.recognised
                learned += res.learned
        except queue.Empty:
            pass
        now = time.monotonic()
        try:
            while True:
                self.hotkey_events.get_nowait()
                self.autokey.toggle()
                self.ak_enabled.set(self.autokey.enabled)
                self.save_settings()
                self.flash_status("Auto-press " + ("ON" if self.autokey.enabled else "OFF"))
        except queue.Empty:
            pass
        if recognised or learned:
            self._apply_catalog_events(recognised, learned)
        if res is not None:
            if res.error:
                self.status.configure(text=res.error, foreground="#b00020")
            else:
                self.result = res
                self.autokey_status = self.autokey.update(
                    self.library.snapshot()[0], set(res.present), now)
                flash = getattr(self, "_flash", None)
                if flash and now < flash[1]:
                    self.status.configure(text=flash[0], foreground="#0a7a20")
                else:
                    self.status.configure(
                        text="%.1f scans/s - %d active" % (res.fps, len(res.present)),
                        foreground="#666")
                if new:
                    known = {u.uid for u in self.unknowns}
                    self.unknowns += [u for u in new if u.uid not in known]
                    self.show_unknown()
                if self.settings["preview"] and now - self._last_preview > 0.12:
                    self._last_preview = now
                    self._draw_preview(res)
                if now - self._last_tree > 0.3:
                    self._last_tree = now
                    self._update_tree_status()
        self.overlay.show(self.result, len(self.unknowns), now, self.autokey_status,
                          self.autokey.enabled)
        self.root.after(40, self._poll)

    def _apply_catalog_events(self, recognised, learned):
        names = []
        for u in recognised:
            m = u.suggestions[0]
            if not self.library.find_catalog(m.icon.file):
                self.library.add(m.icon.names[0], u.crop, KIND_BUFF, catalog=m.icon.file)
                names.append(m.icon.names[0])
            self.worker.resolve_unknown(u.uid)
        for entry_id, crop in learned:
            self.library.set_image(entry_id, crop)
        if names:
            self.flash_status("Recognised: " + ", ".join(names))
        self.save_settings()  # the detector may have learned the icon size
        self.refresh_tree()

    def flash_status(self, text):
        self._flash = (text, time.monotonic() + 6)

    def _draw_preview(self, res):
        if self.root.state() == "iconic":
            return
        img = res.roi.copy()
        for d in res.detections:
            col = (80, 220, 80) if d.kind == KIND_BUFF else (120, 120, 120)
            x, y, w, h = d.box
            cv2.rectangle(img, (x, y), (x + w - 1, y + h - 1), col, 1)
        for u in self.unknowns:
            if u.frame.shape == img.shape:
                x, y, w, h = u.box
                cv2.rectangle(img, (x, y), (x + w - 1, y + h - 1), (0, 220, 255), 1)
        s = min(3.0, PREVIEW_W / img.shape[1], 240 / img.shape[0])
        self._preview_photo = to_photo(img, s, cv2.INTER_LINEAR)
        self.preview.configure(image=self._preview_photo)

    def run(self):
        self.worker.start()
        self.sender.start()
        self._start_hotkey()
        self.root.after(100, self._poll)
        self.root.mainloop()

    def quit(self):
        self.worker.stop()
        self.sender.stop()
        if self.hotkey is not None:
            self.hotkey.stop()
        self.save_settings()
        self.root.destroy()
