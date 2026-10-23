"""Opt-in auto-press: when a buff that was up drops off, tap its key every
`interval` ms until the buff is seen again, at most `max_presses` times."""

import time

from .library import KIND_BUFF


class _State:
    __slots__ = ("armed", "presses", "next_at")

    def __init__(self):
        self.armed = False  # seen active since the last press run, so its expiry counts
        self.presses = 0
        self.next_at = 0.0


class AutoKey:
    def __init__(self, settings, sender, foreground=None):
        self.settings = settings
        self.sender = sender
        self.foreground = foreground  # () -> title of the focused window
        self.state = {}  # entry_id -> _State

    @property
    def enabled(self):
        return bool(self.settings["autokey"]["enabled"])

    def toggle(self):
        self.settings["autokey"]["enabled"] = not self.enabled
        if not self.enabled:
            for st in self.state.values():
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
