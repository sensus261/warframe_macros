"""The Skills tab: where the ability slots are, what each one is doing, and its
auto-press settings."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import cv2

from .skills import (N_SLOTS, SlotState, active_profile, new_profile, profiles,
                     slot_settings)
from . import ui_theme as th
from .ui_common import to_photo
from .ui_dialogs import KeyEntry, RegionPicker

COLUMNS = ("Slot", "Live", "Name", "Status", "Auto-press", "Key", "Press early (s)",
           "Retry every (ms)", "Give up after", "Hold key (ms)", "In overlay")


class SkillsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padding=14)
        self.app = app
        self.rows = []
        self._photos = [None] * N_SLOTS
        sk = app.settings["skills"]

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="we")
        self.enabled = tk.BooleanVar(value=sk["enabled"])
        ttk.Checkbutton(top, text="Watch abilities", variable=self.enabled,
                        command=self._enabled_changed).pack(side="left")
        ttk.Button(top, text="Select ability area...", style="Accent.TButton",
                   command=self.pick_region).pack(side="left", padx=(12, 4))
        ttk.Button(top, text="Capture ready icons",
                   command=self.capture_icons).pack(side="left", padx=4)
        self.info = ttk.Label(top, style="Muted.TLabel")
        self.info.pack(side="left", padx=12)

        prof = ttk.Frame(self)
        prof.grid(row=1, column=0, sticky="we", pady=(8, 0))
        ttk.Label(prof, text="Profile:").pack(side="left")
        self.profile_var = tk.StringVar()
        self.profile_box = ttk.Combobox(prof, textvariable=self.profile_var, width=20,
                                        state="readonly")
        self.profile_box.pack(side="left", padx=4)
        self.profile_box.bind("<<ComboboxSelected>>", lambda e: self._profile_picked())
        for text, cmd in (("New...", self._profile_new), ("Copy...", self._profile_copy),
                          ("Rename...", self._profile_rename), ("Delete", self._profile_delete)):
            ttk.Button(prof, text=text, command=cmd).pack(side="left", padx=2)
        self.auto_profile = tk.BooleanVar(value=bool(sk.get("auto_profile", True)))
        ttk.Checkbutton(prof, text="Switch by itself when another profile's ready icons are "
                                   "on screen", variable=self.auto_profile,
                        command=self._auto_profile_changed).pack(side="left", padx=10)

        en = ttk.Frame(self)
        en.grid(row=2, column=0, sticky="we", pady=(8, 0))
        self.energy = ttk.Label(en, text="Energy: -", width=16)
        self.energy.pack(side="left")
        ttk.Label(en, text="Don't auto-press below").pack(side="left", padx=(8, 4))
        self.min_energy = tk.IntVar(value=0)
        sb = ttk.Spinbox(en, from_=0, to=100, increment=5, textvariable=self.min_energy,
                         width=5, command=self._min_energy_changed)
        sb.pack(side="left")
        sb.bind("<Return>", lambda e: self._min_energy_changed())
        sb.bind("<FocusOut>", lambda e: self._min_energy_changed())
        ttk.Label(en, text="% energy (0 = no limit, per profile)").pack(side="left", padx=4)
        ttk.Button(en, text="Select energy bar...",
                   command=self.pick_energy_bar).pack(side="left", padx=12)

        ttk.Label(self, wraplength=900, justify="left", style="Muted.TLabel", text=(
            "BuffWatch reads the seconds Warframe shows over an ability while it is active. "
            "Auto-press taps the slot's key when that timer ends, or the set number of "
            "seconds before, and keeps tapping every few seconds until a new timer shows "
            "up. It only presses after it has seen the ability's timer once, never while "
            "the HUD is hidden, and shares the on/off switch, hotkey and focus check of the "
            "Auto-press tab. 'Hold key' is for abilities you hold to cast.")).grid(
            row=3, column=0, sticky="w", pady=(6, 8))

        g = ttk.Frame(self)
        g.grid(row=4, column=0, sticky="w")
        for c, text in enumerate(COLUMNS):
            ttk.Label(g, text=text.upper(), style="Section.TLabel").grid(
                row=0, column=c, sticky="w", padx=4)
        for i in range(N_SLOTS):
            self.rows.append(self._row(g, i))

        bottom = ttk.Frame(self)
        bottom.grid(row=5, column=0, sticky="we", pady=(10, 0))
        self.digits = ttk.Label(bottom, style="Muted.TLabel")
        self.digits.pack(side="left")
        ttk.Button(bottom, text="Re-detect HUD scale",
                   command=self._reset_scale).pack(side="right")
        self.load_profile()
        self._update_info()

    # ------------------------------------------------------------ profiles
    def load_profile(self):
        """Show the active profile's settings (after a switch)."""
        profs = profiles(self.app.settings)
        cur = active_profile(self.app.settings)
        self.profile_box["values"] = [p["name"] for p in profs]
        self.profile_var.set(cur["name"])
        self.min_energy.set(cur["min_energy"])
        for i, w in enumerate(self.rows):
            cfg = slot_settings(self.app.settings, i)
            w["name"].set(cfg["name"])
            w["auto"].set(cfg["auto"])
            w["key"].var.set(cfg["key"] or "")
            w["key"]._last = cfg["key"] or ""
            for k in ("early", "interval", "max", "hold", "show"):
                w[k].set(cfg[k])

    def _switch_to(self, profile):
        self.app.settings["skills"]["profile"] = profile["id"]
        self.app.save_settings()
        self.load_profile()
        self.app.skill_overlay.refresh_layout()

    def _profile_picked(self):
        name = self.profile_var.get()
        p = next((p for p in profiles(self.app.settings) if p["name"] == name), None)
        if p:
            self._switch_to(p)

    def _ask_name(self, title, initial=""):
        name = simpledialog.askstring("BuffWatch", title, initialvalue=initial, parent=self)
        name = (name or "").strip()
        if name and any(p["name"] == name for p in profiles(self.app.settings)):
            messagebox.showwarning("BuffWatch", "There is already a profile called '%s'."
                                   % name, parent=self)
            return None
        return name or None

    def _profile_new(self):
        name = self._ask_name("Name of the new profile (e.g. the Warframe):")
        if name:
            self._switch_to(new_profile(self.app.settings, name))
            self.app.flash_status("New profile: click Capture ready icons with its abilities "
                                  "ready")

    def _profile_copy(self):
        cur = active_profile(self.app.settings)
        name = self._ask_name("Name of the copy of '%s':" % cur["name"], cur["name"] + " 2")
        if name:
            self._switch_to(new_profile(self.app.settings, name, copy_from=cur))

    def _profile_rename(self):
        cur = active_profile(self.app.settings)
        name = self._ask_name("New name for '%s':" % cur["name"], cur["name"])
        if name:
            cur["name"] = name
            self.app.save_settings()
            self.load_profile()

    def _profile_delete(self):
        profs = profiles(self.app.settings)
        cur = active_profile(self.app.settings)
        if len(profs) < 2:
            messagebox.showinfo("BuffWatch", "This is the only profile.", parent=self)
            return
        if not messagebox.askyesno("BuffWatch", "Delete the profile '%s'?" % cur["name"],
                                   parent=self):
            return
        profs.remove(cur)
        self.app.worker.forget_skill_profile(cur["id"])
        self._switch_to(profs[0])

    def _auto_profile_changed(self):
        self.app.settings["skills"]["auto_profile"] = bool(self.auto_profile.get())
        self.app.save_settings()

    def _min_energy_changed(self):
        try:
            v = max(0, min(100, int(self.min_energy.get())))
        except (tk.TclError, ValueError):
            return
        active_profile(self.app.settings)["min_energy"] = v
        self.app.save_settings()

    def pick_energy_bar(self):
        self.app.hide_overlays_and(self._pick_energy_grab)

    def _pick_energy_grab(self, full):
        x0, y0, x1, y1 = self.app.settings["skills"]["energy_bar"]

        def done(roi):
            self.app.settings["skills"]["energy_bar"] = roi
            self.app.save_settings()

        RegionPicker(self.app.root, full, [x0, y0, x1, y1], done,
                     title="select the energy bar", prompt=(
                         "Drag from the LEFT end of the energy bar (under the abilities) to "
                         "its RIGHT end. The bar slopes down, so the box's corners are its "
                         "ends. Enter = save, Esc = cancel."))

    # ------------------------------------------------------------ widgets
    def _row(self, g, i):
        cfg = slot_settings(self.app.settings, i)
        r = i + 1
        w = {}
        ttk.Label(g, text=str(i + 1)).grid(row=r, column=0, padx=4)
        w["live"] = tk.Label(g, bg=th.INPUT, width=6, height=3)
        w["live"].grid(row=r, column=1, padx=4, pady=2)
        w["name"] = tk.StringVar(value=cfg["name"])
        e = ttk.Entry(g, textvariable=w["name"], width=16)
        e.grid(row=r, column=2, padx=4)
        e.bind("<Return>", lambda ev: self._changed(i))
        e.bind("<FocusOut>", lambda ev: self._changed(i))
        w["status"] = ttk.Label(g, width=24)
        w["status"].grid(row=r, column=3, padx=4, sticky="w")
        w["auto"] = tk.BooleanVar(value=cfg["auto"])
        ttk.Checkbutton(g, variable=w["auto"], command=lambda: self._changed(i)).grid(
            row=r, column=4)
        w["key"] = KeyEntry(g, cfg["key"] or "", on_change=lambda v: self._changed(i))
        w["key"].grid(row=r, column=5, padx=4)
        for c, (k, lo, hi, step, kind) in enumerate(
                (("early", 0, 60, 0.5, float), ("interval", 300, 30000, 100, int),
                 ("max", 1, 50, 1, int), ("hold", 10, 5000, 10, int)), start=6):
            v = (tk.DoubleVar if kind is float else tk.IntVar)(value=cfg[k])
            w[k] = v
            sb = ttk.Spinbox(g, from_=lo, to=hi, increment=step, textvariable=v, width=7,
                             command=lambda: self._changed(i))
            sb.grid(row=r, column=c, padx=4)
            sb.bind("<Return>", lambda ev: self._changed(i))
            sb.bind("<FocusOut>", lambda ev: self._changed(i))
        w["show"] = tk.BooleanVar(value=cfg["show"])
        ttk.Checkbutton(g, variable=w["show"], command=lambda: self._changed(i)).grid(
            row=r, column=10)
        return w

    # ------------------------------------------------------------ apply
    def _changed(self, i):
        cfg = slot_settings(self.app.settings, i)
        w = self.rows[i]
        cfg["name"] = w["name"].get().strip() or "Ability %d" % (i + 1)
        key = w["key"].get()
        cfg["key"] = key if key and w["key"].valid() else None
        cfg["auto"] = bool(w["auto"].get()) and bool(cfg["key"])
        if bool(w["auto"].get()) and not cfg["key"]:
            w["auto"].set(False)
        for k, kind, lo, hi in (("early", float, 0, 60), ("interval", int, 300, 30000),
                                ("max", int, 1, 50), ("hold", int, 10, 5000)):
            try:
                cfg[k] = kind(max(lo, min(hi, w[k].get())))
            except (tk.TclError, ValueError):
                pass
        show_changed = cfg["show"] != bool(w["show"].get())
        cfg["show"] = bool(w["show"].get())
        self.app.save_settings()
        if show_changed:
            self.app.skill_overlay.refresh_layout()

    def _enabled_changed(self):
        self.app.settings["skills"]["enabled"] = bool(self.enabled.get())
        self.app.save_settings()
        self.app.skill_overlay.apply_settings()

    def _reset_scale(self):
        self.app.settings["skills"]["digit_scale"] = None
        self.app.save_settings()
        self._update_info()

    def _update_info(self):
        sk = self.app.settings["skills"]
        scale = sk.get("digit_scale")
        self.info.configure(text="HUD scale found" if scale else
                            "cast an ability to let BuffWatch find the timer size")
        known = self.app.worker.skills.reader.known_digits()
        missing = [d for d in "0123456789" if d not in known]
        self.digits.configure(text="Timer digits known: %s%s" % (
            " ".join(known), "  (still learning %s from running timers)" % " ".join(missing)
            if missing else ""))

    def pick_region(self):
        self.app.hide_overlays_and(self._pick_region_grab)

    def _pick_region_grab(self, full):
        def done(roi):
            self.app.settings["skills"]["roi"] = roi
            self.app.settings["skills"]["digit_scale"] = None
            self.app.save_settings()

        RegionPicker(self.app.root, full, self.app.settings["skills"]["roi"], done,
                     title="select the ability area", prompt=(
                         "Drag a box around the four ability icons in the bottom right, "
                         "tight left and right (it is split into four equal slots) and tall "
                         "enough for the timer numbers. Enter = save, Esc = cancel."))

    def capture_icons(self):
        if not messagebox.askokcancel("BuffWatch", (
                "With every ability ready (no timers showing) and the HUD on screen, "
                "click OK. BuffWatch saves how each slot looks while ready, for the "
                "current profile. That tells it when the HUD is hidden, so auto-press "
                "never fires in a menu, and lets it switch to this profile by itself "
                "when you play this Warframe.\n\n"
                "It also does this by itself the first time a slot is ready while another "
                "slot shows a timer."), parent=self):
            return
        self.app.worker.capture_skill_icons()
        self.app.flash_status("Saved how the ability slots look while ready")

    # ------------------------------------------------------------ live
    def refresh(self, result, status):
        self._update_info()
        e = result.energy if result is not None else None
        self.energy.configure(text="Energy: %s" % ("-" if e is None else "%d%%" % round(e * 100)))
        states = result.skills if result is not None else []
        roi = result.skill_roi if result is not None else None
        for i, w in enumerate(self.rows):
            st = states[i] if i < len(states) else None
            if st is None:
                w["status"].configure(text="off" if not self.app.settings["skills"]["enabled"]
                                      else "no picture yet")
                continue
            text = st.label()
            if st.state == SlotState.ACTIVE and st.text and st.remaining is None:
                text += " (reading %s)" % st.text
            auto = status.get(i)
            if auto:
                text += " - " + auto
            w["status"].configure(text=text)
            if roi is not None and st.box:
                x, y, bw, bh = st.box
                img = roi[y:y + bh, x:x + bw]
                s = min(2.0, 60 / max(1, img.shape[0]))
                self._photos[i] = to_photo(img, s, cv2.INTER_LINEAR)
                w["live"].configure(image=self._photos[i], width=0, height=0)
