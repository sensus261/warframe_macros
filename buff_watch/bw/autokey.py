"""Opt-in auto-press: when a buff that was up drops off, tap its key every
`interval` ms until the buff is seen again, at most `max_presses` times.

Abilities work the same way, keyed on their timer: press when it ends (or a set number
of seconds before), and keep pressing until a fresh timer shows up."""

import time

from .library import KIND_BUFF


class _State:
    __slots__ = ("armed", "presses", "next_at", "last_left")

    def __init__(self):
        self.armed = False  # seen active since the last press run, so its expiry counts
        self.presses = 0
        self.next_at = 0.0
        self.last_left = None  # ability: seconds left at the last scan


class AutoKey:
    def __init__(self, settings, sender, foreground=None):
        self.settings = settings
        self.sender = sender
        self.foreground = foreground  # () -> title of the focused window
        self.state = {}  # entry_id -> _State
        self.skill_state = {}  # slot index -> _State

    @property
    def enabled(self):
        return bool(self.settings["autokey"]["enabled"])

    def toggle(self):
        self.settings["autokey"]["enabled"] = not self.enabled
        if not self.enabled:
            for st in list(self.state.values()) + list(self.skill_state.values()):
                st.presses, st.next_at = 0, 0.0

    def _game_focused(self):
        if not self.settings["autokey"]["only_when_focused"] or self.foreground is None:
            return True
        title = self.settings["source"].get("window_title") or "Warframe"
        return title.lower() in self.foreground().lower()

    def update(self, entries, present_ids, now=None):
        """Call once per scan result. Returns {entry_id: status text} for entries
        that have a key, for the UI."""
        now = time.monotonic() if now is None else now
        status = {}
        focused = None
        for e in entries:
            if e.kind != KIND_BUFF or not e.key:
                self.state.pop(e.id, None)
                continue
            st = self.state.setdefault(e.id, _State())
            if e.id in present_ids:
                st.armed, st.presses, st.next_at = True, 0, 0.0
                status[e.id] = ""
                continue
            if not st.armed:
                status[e.id] = "waiting to see it once"
                continue
            if st.presses >= e.key_max:
                status[e.id] = "gave up after %d presses" % st.presses
                continue
            if not self.enabled:
                status[e.id] = "auto-press off"
                continue
            if focused is None:
                focused = self._game_focused()
            if not focused:
                status[e.id] = "game not focused"
                continue
            if now >= st.next_at:
                self.sender.press(e.key)
                st.presses += 1
                st.next_at = now + max(100, e.key_interval) / 1000.0
            status[e.id] = "pressing %s (%d/%d)" % (e.key, st.presses, e.key_max)
        return status

    def update_skills(self, slots, states, now=None, energy=None, min_energy=0):
        """`slots`: per-slot settings; `states`: skills.SlotState list from the scan;
        `energy`: 0..1 from the energy bar (None = unknown). Below `min_energy` percent
        nothing is pressed. Returns {slot index: status text} for slots with auto-press on."""
        from .skills import SlotState

        now = time.monotonic() if now is None else now
        status = {}
        focused = None
        for i, (cfg, ss) in enumerate(zip(slots, states)):
            if not cfg.get("auto") or not cfg.get("key"):
                self.skill_state.pop(i, None)
                continue
            st = self.skill_state.setdefault(i, _State())
            early = max(0.0, float(cfg.get("early") or 0))
            left = ss.remaining if ss.state == SlotState.ACTIVE else None
            if ss.state == SlotState.ACTIVE:
                # A new timer, or one that jumped up (recast): the last press worked.
                if not st.armed or st.last_left is None or (
                        left is not None and left > st.last_left + 1.0):
                    st.presses, st.next_at = 0, 0.0
                st.armed = True
                st.last_left = left
                due = early > 0 and left is not None and left <= early
            elif ss.state == SlotState.READY:
                st.last_left = None
                due = st.armed
            else:  # HUD hidden (menu, cutscene...) or unknown: never press
                status[i] = ("HUD not visible" if ss.state == SlotState.HIDDEN
                             else "can't tell if the HUD is up: Capture ready icons")
                continue
            if not due:
                if not st.armed:
                    status[i] = "waiting for a timer"
                elif st.presses:
                    status[i] = "pressed %s" % cfg["key"]
                else:
                    status[i] = ""
                continue
            if st.presses >= int(cfg.get("max") or 5):
                status[i] = "gave up after %d presses" % st.presses
                continue
            if not self.enabled:
                status[i] = "auto-press off"
                continue
            if min_energy and energy is not None and energy * 100 < min_energy:
                status[i] = "low energy (%d%%), not pressing" % round(energy * 100)
                continue
            if focused is None:
                focused = self._game_focused()
            if not focused:
                status[i] = "game not focused"
                continue
            if now >= st.next_at:
                self.sender.press(cfg["key"], max(10, int(cfg.get("hold") or 50)) / 1000.0)
                st.presses += 1
                st.next_at = now + max(300, int(cfg.get("interval") or 1500)) / 1000.0
            status[i] = "pressing %s (%d/%d)" % (cfg["key"], st.presses, int(cfg.get("max") or 5))
        return status
