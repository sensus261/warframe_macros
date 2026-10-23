"""Second always-on-top overlay: the four ability slots magnified, with the time left
on each and what auto-press is doing. Same look and layout options as the buff overlay,
kept separately in settings["skills_overlay"]."""

import tkinter as tk

import cv2

from .skills import SlotState, active_profile, slot_settings
from .ui_common import to_photo
from .ui_overlay import Overlay, _font


class _Slot:
    """Stands in for a library entry in Overlay._sync_cells."""

    def __init__(self, i):
        self.id = "slot%d" % i


class SkillOverlay(Overlay):
    SETTINGS_KEY = "skills_overlay"
    PLACEHOLDER_TEXT = "Skills overlay (empty)"

    def __init__(self, app):
        super().__init__(app)
        self.energy_label = tk.Label(self, padx=6, pady=1)
        self._bind_drag(self.energy_label)

    def apply_settings(self):
        if not self.app.settings["skills"]["enabled"]:
            self.withdraw()
            return
        super().apply_settings()

    def _shown_slots(self):
        s = self.app.settings
        return [i for i in range(4) if slot_settings(s, i)["show"]]

    def refresh_layout(self):
        for c in self.cells.values():
            c.frame.destroy()
        self.cells = {}
        self.order = []
        self.visible = []
        self._style_window()
        self._sync_cells([_Slot(i) for i in self._shown_slots()])
        self.place()

    def show(self, result, now, status=None, autokey_on=True):
        ov = self.cfg
        if not ov["visible"] or not self.app.settings["skills"]["enabled"]:
            return
        shown = self._shown_slots()
        self._sync_cells([_Slot(i) for i in shown])
        zoom = float(ov["zoom"])
        dim = max(0.0, min(1.0, float(ov["dim_missing"])))
        states = result.skills if result is not None else []
        roi = result.skill_roi if result is not None else None
        visible = []
        for i in shown:
            c = self.cells["slot%d" % i]
            cfg = slot_settings(self.app.settings, i)
            st = states[i] if i < len(states) else None
            state = st.state if st else SlotState.UNKNOWN
            ready = state != SlotState.ACTIVE
            if not ready or ov["show_missing"]:
                visible.append(c.entry_id)
            if roi is not None and st is not None and st.box:
                x, y, w, h = st.box
                img = roi[y:y + h, x:x + w]
                if ready and dim < 1.0:
                    img = cv2.convertScaleAbs(img, alpha=dim)
                c.photo = to_photo(img, zoom, cv2.INTER_LINEAR)
                c.img.configure(image=c.photo)
            if c.was_present is not None and (not ready) != c.was_present:
                c.flash_until = now + float(ov["flash_seconds"])
            c.was_present = not ready
            auto = (status or {}).get(i, "")
            lines = [cfg["name"]] if ov["show_names"] else []
            lines.append(st.label() if st else "unknown")
            if auto:
                lines.append(auto)
            self.set_label(c, "\n".join(lines))
            alert = auto.startswith("gave up")
            c.text.configure(fg=ov["alert_color"] if alert else (
                ov["off_text_color"] if ready else ov["text_color"]))
            border = ov["flash_color"] if now < c.flash_until else (
                ov["alert_color"] if alert else ov["cell_color"])
            c.frame.configure(highlightbackground=border)
        if visible != self.visible:
            self._regrid(visible)

        self._show_energy(result, now)
        any_auto = any(slot_settings(self.app.settings, i)["auto"] for i in range(4))
        self.show_extras(any_auto and not autokey_on, not visible)
        self.place()

    def _show_energy(self, result, now):
        """Energy line under the slots; alert colours (blinking) below the profile's
        auto-press limit."""
        ov = self.cfg
        energy = result.energy if result is not None else None
        if not ov.get("show_energy", True) or energy is None:
            if self.energy_label.winfo_ismapped():
                self.energy_label.pack_forget()
            return
        low = active_profile(self.app.settings)["min_energy"]
        pct = round(energy * 100)
        text = "Energy %d%%" % pct
        if low and pct < low:
            text += " - below %d%%, auto-press paused" % low
            blink = int(now * 2) % 2 == 0
            fg, bg = (ov["background_color"], ov["alert_color"]) if blink else (
                ov["alert_color"], ov["cell_color"])
        else:
            fg, bg = ov["text_color"], ov["cell_color"]
        self.energy_label.configure(text=text, fg=fg, bg=bg, font=_font(ov))
        if not self.energy_label.winfo_ismapped():
            self.energy_label.pack(side="bottom", fill="x", after=self.body)
