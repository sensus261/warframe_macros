"""Ability (skill) watching: the four ability slots in the bottom-right HUD.

While an ability is active, Warframe draws a dark box over its icon with the seconds
left on it ("41", "9.4"). BuffWatch reads that number with small digit templates and
keeps a running countdown per slot, so auto-press can recast an ability a few seconds
before it runs out, or right when it does.

Everything here works on plain numpy images, so it can be tested on screenshots.
"""

import os
import re
import sys
import threading

import cv2
import numpy as np

from . import config

N_SLOTS = 4
CELL_W, CELL_H = 9, 14  # digit template size; digits are about 12 px tall at this scale
REF_DIGIT_H = 12  # digit height in the templates
REF_CAPTURE_H = 1800  # the templates come from 3200x1800 screenshots at 100% HUD scale

PEAK_MIN = 0.55  # weakest template match that counts as a glyph candidate
PRESENT_MIN, PRESENT_MEAN = 0.6, 0.76  # a timer is showing
CONFIDENT_MIN = 0.75  # every glyph at least this good -> trust the value
LOCK_TOL = 1.3  # seconds a reading may differ from the countdown and still agree
READY_SIM = 0.6  # ready-icon similarity that proves the HUD is on screen
COAST_MIN, COAST_S = 1.5, 3.0  # see SkillWatcher.process
ADVANCE, DOT_EXTRA = 10, 5  # template-scale x distance between digits, extra across "."

_FORMAT = re.compile(r"^(\d\.\d|\d{2,3})$")

DIGITS_FILE = os.path.join(config.DATA_DIR, "skill_digits.npz")
ICON_DIR = os.path.join(config.DATA_DIR, "skill_icons")  # ready look of each slot, per profile
OLD_REF_FILE = os.path.join(config.DATA_DIR, "skill_slot_%d.png")  # before profiles


def _bundled_digits_path():
    base = getattr(sys, "_MEIPASS", None) or config.app_dir()
    return os.path.join(base, "catalog", "skill_digits.png")


def _norm(cell):
    cell = cell.astype(np.float32)
    return (cell - cell.mean()) / (cell.std() + 1e-6)


def slot_columns(roi):
    """The skills area split into its four slots, left to right."""
    w = roi.shape[1] / N_SLOTS
    return [roi[:, int(round(i * w)):int(round((i + 1) * w))] for i in range(N_SLOTS)]


# ---------------------------------------------------------------- profiles
def profiles(settings):
    """The skill profiles (one per Warframe, say), creating "Default" from older settings."""
    sk = settings["skills"]
    profs = sk.get("profiles")
    # Drop anything that isn't a usable profile (e.g. from a hand-edited or newer export).
    ok = [p for p in profs if isinstance(p, dict) and p.get("id")] \
        if isinstance(profs, list) else []
    if not isinstance(profs, list) or len(ok) != len(profs):
        profs = sk["profiles"] = ok
    if not profs:
        profs.append({"id": "default", "name": "Default", "slots": sk.pop("slots", None) or []})
    for p in profs:
        p.setdefault("name", p["id"])
        if not isinstance(p.get("slots"), list):
            p["slots"] = []
        for k, v in config.SKILL_PROFILE_DEFAULTS.items():
            p.setdefault(k, v)
    if sk.get("profile") not in {p["id"] for p in profs}:
        sk["profile"] = profs[0]["id"]
    return profs


def active_profile(settings):
    pid = settings["skills"].get("profile")
    profs = profiles(settings)
    return next((p for p in profs if p["id"] == pid), profs[0])


def new_profile(settings, name, copy_from=None):
    """Add a profile (a copy of `copy_from`'s slots, if given) and return it."""
    profs = profiles(settings)
    base = "".join(c for c in name.lower() if c.isalnum())[:24] or "profile"
    pid, n = base, 2
    while any(p["id"] == pid for p in profs):
        pid, n = "%s%d" % (base, n), n + 1
    p = {"id": pid, "name": name, "slots": [], "min_energy": 0}
    if copy_from:
        p["slots"] = [dict(x) for x in copy_from["slots"]]
        p["min_energy"] = copy_from.get("min_energy", 0)
    profs.append(p)
    return p


def slot_settings(settings, i, profile=None):
    """Settings of slot `i` in the active profile, with defaults filled in."""
    slots = (profile or active_profile(settings)).setdefault("slots", [])
    while len(slots) < N_SLOTS:
        slots.append({})
    if not isinstance(slots[i], dict):
        slots[i] = {}
    s = slots[i]
    s.setdefault("name", "Ability %d" % (i + 1))
    s.setdefault("key", str(i + 1))  # the game's default ability keys
    for k, v in config.SKILL_SLOT_DEFAULTS.items():
        s.setdefault(k, v)
    return s


def icon_path(profile_id, i):
    return os.path.join(ICON_DIR, "%s_%d.png" % (profile_id, i + 1))


# ---------------------------------------------------------------- energy bar
ENERGY_PAD = 0.008  # capture this much (fraction of height) above and below the bar


def energy_rect(settings):
    """Capture area (fractions x0, y0, x1, y1) around the energy bar."""
    x0, y0, x1, y1 = settings["skills"]["energy_bar"]
    return [min(x0, x1), max(0.0, min(y0, y1) - ENERGY_PAD),
            max(x0, x1), min(1.0, max(y0, y1) + ENERGY_PAD)]


def read_energy(img, bar, rect):
    """How full the energy bar is (0..1) in `img`, the capture of `rect`; None if no
    bar is there. The filled part of the bar is white, the empty part cyan."""
    h, w = img.shape[:2]
    if w < 8 or h < 4:
        return None
    rx0, ry0, rx1, ry1 = rect
    bx0, by0, bx1, by1 = bar
    if bx1 < bx0:
        bx0, by0, bx1, by1 = bx1, by1, bx0, by0
    sy = h / max(1e-6, ry1 - ry0)
    ya, yb = (by0 - ry0) * sy, (by1 - ry0) * sy
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    half = max(2, int(round(h * 0.17)))
    white, lit = [], 0
    for x in range(w):
        yc = int(round(ya + (yb - ya) * x / max(1, w - 1)))
        band = hsv[max(0, yc - half):yc + half + 1, x]
        if band.size == 0:
            white.append(False)
            continue
        v, s_ = band[:, 2].astype(int), band[:, 1].astype(int)
        white.append(bool(((v >= 170) & (s_ < 60)).any()))
        lit += bool((v >= 110).any())
    if lit < 0.6 * w:
        return None  # nothing bar-like along the line: HUD hidden or area wrong
    # The fill runs from the left end; stop at the first real gap so bright scenery
    # behind the empty part isn't counted.
    end, gap = 0, 0
    for x, wh in enumerate(white):
        if wh:
            end, gap = x + 1, 0
        else:
            gap += 1
            if gap > max(3, w // 30) and end:
                break
    return end / w


# ---------------------------------------------------------------- digit reading
class Glyph:
    __slots__ = ("digit", "score", "x", "y", "cell")

    def __init__(self, digit, score, x, y, cell):
        self.digit, self.score, self.x, self.y, self.cell = digit, score, x, y, cell


class Reading:
    """What one slot's number looks like this scan."""

    def __init__(self, glyphs=(), scale=None):
        self.glyphs = list(glyphs)
        self.line = self.glyphs  # every glyph on the number's line, for learning
        self.image = None  # the slot at template scale (grey)
        self.scale = scale
        scores = [g.score for g in self.glyphs]
        self.text = self._text()
        self.present = (len(scores) >= 2 and min(scores) >= PRESENT_MIN
                        and sum(scores) / len(scores) >= PRESENT_MEAN
                        and bool(_FORMAT.match(self.text)))
        self.confident = (self.present and min(scores) >= CONFIDENT_MIN
                          and bool(_FORMAT.match(self.text)))
        self.value = float(self.text) if self.confident else None

    def _text(self):
        out, prev = "", None
        for g in self.glyphs:
            if prev is not None and g.x - prev.x >= 13:  # a wider gap holds the decimal point
                out += "."
            out += g.digit
            prev = g
        return out

    @property
    def mean_score(self):
        return sum(g.score for g in self.glyphs) / len(self.glyphs) if self.glyphs else 0.0


class DigitReader:
    """Template matching of the HUD's digits. Starts from the digits bundled with the
    program and adds samples it learns on this screen (see `learn`)."""

    def __init__(self):
        self.bundled = {}  # digit -> normalised cell
        self.learned = {}  # digit -> (sum of normalised cells, count)
        self._lock = threading.Lock()
        self._dirty = 0
        self._load()

    def _load(self):
        strip = cv2.imread(_bundled_digits_path(), cv2.IMREAD_GRAYSCALE)
        if strip is not None:
            for d in range(10):
                c = strip[:, d * CELL_W:(d + 1) * CELL_W]
                if c.size and c.std() > 5:
                    self.bundled[str(d)] = _norm(c)
        try:
            data = np.load(DIGITS_FILE)
            for d in range(10):
                k = str(d)
                if "sum" + k in data:
                    self.learned[k] = (data["sum" + k].astype(np.float32), int(data["n" + k]))
        except (OSError, ValueError, KeyError):
            pass

    def templates(self):
        """[(digit, cell)]: the bundled cell and the learned average, where known."""
        out = list(self.bundled.items())
        with self._lock:
            for d, (s, n) in self.learned.items():
                if n >= 2:
                    out.append((d, _norm(s / n)))
        return out

    def known_digits(self):
        with self._lock:
            return sorted(set(self.bundled) | {d for d, (_, n) in self.learned.items() if n >= 2})

    def learn(self, digit, cell):
        with self._lock:
            s, n = self.learned.get(digit, (np.zeros((CELL_H, CELL_W), np.float32), 0))
            if n >= 40:  # enough; keep the average from drifting
                return
            self.learned[digit] = (s + _norm(cell), n + 1)
            self._dirty += 1

    def save(self, force=False):
        with self._lock:
            if not self._dirty or (not force and self._dirty < 10):
                return
            arrays = {}
            for d, (s, n) in self.learned.items():
                arrays["sum" + d], arrays["n" + d] = s, np.array(n)
            self._dirty = 0
        try:
            os.makedirs(config.DATA_DIR, exist_ok=True)
            tmp = DIGITS_FILE + ".tmp.npz"
            np.savez(tmp, **arrays)
            os.replace(tmp, DIGITS_FILE)
        except OSError:
            pass

    def read(self, col_bgr, scale, templates=None):
        """Read the number in one slot. `scale` resizes the slot so its digits are
        REF_DIGIT_H pixels tall."""
        g = cv2.cvtColor(col_bgr, cv2.COLOR_BGR2GRAY) if col_bgr.ndim == 3 else col_bgr
        if abs(scale - 1.0) > 0.02:
            g = cv2.resize(g, None, fx=scale, fy=scale,
                           interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        g = g.astype(np.float32)
        if g.shape[0] < CELL_H or g.shape[1] < CELL_W:
            return Reading(scale=scale)
        templates = templates or self.templates()
        best, label = None, None
        for i, (d, t) in enumerate(templates):
            r = np.nan_to_num(cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED),
                              nan=0.0, posinf=0.0, neginf=0.0)
            if best is None:
                best, label = r, np.zeros(r.shape, np.int16)
            else:
                better = r > best
                best = np.where(better, r, best)
                label[better] = i
        peaks = []
        b = best.copy()
        for _ in range(5):
            _, mx, _, (x, y) = cv2.minMaxLoc(b)
            if mx < PEAK_MIN:
                break
            peaks.append(Glyph(templates[label[y, x]][0], float(mx), x, y,
                               g[y:y + CELL_H, x:x + CELL_W].copy()))
            b[max(0, y - 7):y + 8, max(0, x - 6):x + 7] = -1
        if not peaks:
            return Reading(scale=scale)
        top = peaks[0]
        line = sorted((p for p in peaks if abs(p.y - top.y) <= 3), key=lambda p: p.x)
        # Icon artwork next to the number can add a stray glyph, so take the run of
        # neighbouring glyphs through the strongest one that reads best as a timer.
        best = Reading([top], scale)
        k = line.index(top)
        for a in range(k + 1):
            for b in range(k + 1, len(line) + 1):
                run = line[a:b]
                if len(run) < 2 or len(run) > 3 or not _spaced(run):
                    continue
                r = Reading(run, scale)
                if (r.confident, r.present, r.mean_score) > (
                        best.confident, best.present, best.mean_score):
                    best = r
        best.line, best.image = line, g
        return best


def _spaced(run):
    """Glyphs sit one digit apart, or a bit more across the decimal point."""
    gaps = [b.x - a.x for a, b in zip(run, run[1:])]
    return all(7 <= g <= 20 for g in gaps) and sum(g >= 13 for g in gaps) <= 1


# ---------------------------------------------------------------- per-slot countdown
class SlotState:
    """What the UI and auto-press need to know about one slot."""

    READY, ACTIVE, HIDDEN, UNKNOWN = "ready", "active", "hidden", "unknown"

    def __init__(self, index):
        self.index = index
        self.state = SlotState.UNKNOWN
        self.remaining = None  # seconds left, while the countdown is locked
        self.text = ""  # the number as read this scan
        self.score = 0.0
        self.box = None  # (x, y, w, h) of the slot inside the skills area
        self.ready_sim = None  # similarity to the captured ready icon (None = no icon yet)
        self.changed_at = 0.0  # when `state` last changed

    def label(self):
        if self.state == SlotState.ACTIVE:
            if self.remaining is None:
                return "active"
            r = max(0.0, self.remaining)
            return "%.1fs" % r if r < 10 else "%ds" % int(r + 0.5)
        return self.state


class _Tracker:
    """Turns noisy per-scan readings into a smooth countdown."""

    def __init__(self):
        self.last_seen = None  # time the number was last on screen
        self.base = None  # (value, time) the countdown runs from
        self.last_text = None
        self.pending = None  # (value, time) of a confident reading not yet confirmed
        self.disagree = 0

    def predict(self, now):
        if self.base is None:
            return None
        v, t = self.base
        return v - (now - t)

    def update(self, reading, now):
        if reading.present:
            self.last_seen = now
        if not reading.confident:
            return
        v = reading.value
        # Above 10 the HUD shows whole seconds; the true value is somewhere in
        # [v, v + 1), so count from the middle when the shown number changes.
        whole = "." not in reading.text
        pred = self.predict(now)
        if pred is None:
            if self.pending is not None:
                pv, pt = self.pending
                if abs(v - (pv - (now - pt))) <= LOCK_TOL:
                    self.base = (v + (0.5 if whole else 0.0), now)
                    self.last_text = reading.text
                    self.pending = None
                    return
            self.pending = (v, now)
            return
        if abs(v - pred) <= LOCK_TOL or (whole and v <= pred <= v + 1 + LOCK_TOL):
            self.disagree = 0
            if reading.text != self.last_text:
                self.base = (v + (0.5 if whole else 0.0), now)
                self.last_text = reading.text
            return
        # Two confident readings in a row that agree with each other but not with the
        # countdown: the ability was recast or its duration changed.
        self.disagree += 1
        if self.disagree >= 2 and self.pending is not None and abs(
                v - (self.pending[0] - (now - self.pending[1]))) <= LOCK_TOL:
            self.base = (v + (0.5 if whole else 0.0), now)
            self.last_text = reading.text
            self.disagree = 0
            self.pending = None
        else:
            self.pending = (v, now)

    def reset(self):
        self.base = None
        self.pending = None
        self.last_text = None
        self.disagree = 0


class SkillWatcher:
    """Reads the four ability slots each scan. Used from the worker thread."""

    def __init__(self, settings, reader=None):
        self.settings = settings
        self.reader = reader or DigitReader()
        self.trackers = [_Tracker() for _ in range(N_SLOTS)]
        self.states = [SlotState(i) for i in range(N_SLOTS)]
        self._refs = {}  # profile id -> [grey image of each slot while ready]
        self._capture_refs = False
        self._match_at = float("-inf")
        self._switch = None  # (profile id, since) another profile whose icons are on screen
        self.energy = None  # 0..1 from the energy bar, None = not found
        self._energy = []  # last few readings, for a median

    # ------------------------------------------------------------ ready icons
    @property
    def refs(self):
        return self._profile_refs(active_profile(self.settings)["id"])

    def _profile_refs(self, pid):
        if pid not in self._refs:
            refs = []
            for i in range(N_SLOTS):
                path = icon_path(pid, i)
                if pid == "default" and not os.path.exists(path) and os.path.exists(
                        OLD_REF_FILE % (i + 1)):
                    path = OLD_REF_FILE % (i + 1)
                refs.append(cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                            if os.path.exists(path) else None)
            self._refs[pid] = refs
        return self._refs[pid]

    def request_capture(self):
        """Save the next scan's slots as their ready look (call with every ability ready)."""
        self._capture_refs = True

    def _set_ref(self, i, gray):
        pid = active_profile(self.settings)["id"]
        self._profile_refs(pid)[i] = gray.copy()
        try:
            os.makedirs(ICON_DIR, exist_ok=True)
            cv2.imwrite(icon_path(pid, i), gray)
        except OSError:
            pass

    def forget_profile(self, pid):
        self._refs.pop(pid, None)
        for i in range(N_SLOTS):
            try:
                os.remove(icon_path(pid, i))
            except OSError:
                pass

    def _auto_switch(self, grays, readings, sims, now):
        """Switch to the profile whose ready icons are on screen (a different Warframe),
        when the current profile's icons clearly aren't."""
        sk = self.settings["skills"]
        if not sk.get("auto_profile") or now - self._match_at < 0.5:
            return
        self._match_at = now
        idle = [i for i in range(N_SLOTS) if not readings[i].present]
        if len(idle) < 3:
            return
        cur = active_profile(self.settings)["id"]

        def matches(refs, lo):
            vals = [self._similarity(refs[i], grays[i]) for i in idle]
            return sum(v is not None and v >= lo for v in vals)

        # A profile without captured icons yet (just made) is never switched away from.
        if (sum(r is not None for r in self.refs) < 3
                or matches(self.refs, 0.75) >= len(idle) - 1):
            self._switch = None
            return
        best = None
        for p in profiles(self.settings):
            if p["id"] != cur and matches(self._profile_refs(p["id"]), 0.8) >= len(idle):
                best = p["id"]
                break
        if best is None:
            self._switch = None
        elif self._switch is None or self._switch[0] != best:
            self._switch = (best, now)
        elif now - self._switch[1] >= 1.5:  # held steady: not a passing flicker
            sk["profile"] = best
            self._switch = None

    @staticmethod
    def _similarity(ref, gray):
        if ref is None:
            return None
        h, w = gray.shape[:2]
        if abs(ref.shape[0] - h) > 3 or abs(ref.shape[1] - w) > 3:
            ref = cv2.resize(ref, (w, h), interpolation=cv2.INTER_AREA)
        mx, my = max(1, w // 10), max(1, h // 6)  # allow a few pixels of shift
        t = ref[my:h - my, mx:w - mx].astype(np.float32)
        if t.size == 0 or t.std() < 2:
            return None
        r = cv2.matchTemplate(gray.astype(np.float32), t, cv2.TM_CCOEFF_NORMED)
        return float(np.nan_to_num(r).max())

    # ------------------------------------------------------------ per scan
    def _scales(self, capture_h):
        sk = self.settings["skills"]
        base = REF_CAPTURE_H / max(1, capture_h)
        if sk.get("digit_scale"):
            s = float(sk["digit_scale"])
            return [s, s * 0.95, s * 1.05]
        return [base * f for f in (1.0, 0.9, 1.1, 0.8, 1.25, 0.7, 1.4)]

    def _read(self, col, capture_h, templates):
        best = None
        for s in self._scales(capture_h):
            r = self.reader.read(col, s, templates)
            if best is None or (r.present, r.confident, r.mean_score) > (
                    best.present, best.confident, best.mean_score):
                best = r
            if r.confident and r.mean_score >= 0.85:
                break
        sk = self.settings["skills"]
        if (best is not None and not sk.get("digit_scale") and best.confident
                and best.mean_score >= 0.85):
            sk["digit_scale"] = round(best.scale, 3)  # found the HUD scale; stop searching
        return best

    def update_energy(self, img, rect):
        e = read_energy(img, self.settings["skills"]["energy_bar"], rect)
        if e is None:
            self._energy = []
            self.energy = None
        else:
            self._energy = (self._energy + [e])[-3:]
            self.energy = float(np.median(self._energy))
        return self.energy

    def process(self, roi, capture_h, now, miss_s=0.25):
        """Update and return the four SlotStates for this scan of the skills area."""
        cols = slot_columns(roi)
        templates = self.reader.templates()
        grays = [cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) for c in cols]
        readings = [self._read(c, capture_h, templates) for c in cols]
        if self._capture_refs:
            self._capture_refs = False
            for i, g in enumerate(grays):
                if not readings[i].present:
                    self._set_ref(i, g)
        sims = [self._similarity(self.refs[i], g) for i, g in enumerate(grays)]
        self._auto_switch(grays, readings, sims, now)
        any_timer = any(r.present for r in readings)
        hud = any_timer or any(s is not None and s >= READY_SIM for s in sims)
        x = 0
        for i, (col, rd, tr, st) in enumerate(zip(cols, readings, self.trackers, self.states)):
            st.box = (x, 0, col.shape[1], col.shape[0])
            x += col.shape[1]
            st.ready_sim = sims[i]
            st.text, st.score = rd.text, rd.mean_score
            tr.update(rd, now)
            showing = tr.last_seen is not None and now - tr.last_seen <= miss_s
            # A number the reader can't make out (a digit it hasn't learned yet) must not
            # look like the ability ending: while the countdown says there is time left,
            # keep the slot active for a few seconds without a reading.
            pred = tr.predict(now)
            coasting = (not showing and hud and pred is not None and pred > COAST_MIN
                        and now - tr.last_seen <= COAST_S)
            if showing or coasting:
                new = SlotState.ACTIVE
                self._learn(rd, tr, now)
            elif hud:
                new = SlotState.READY
                tr.reset()
                if self.refs[i] is None and any_timer:
                    self._set_ref(i, grays[i])  # the HUD is up and this slot is idle
            else:
                new = SlotState.HIDDEN if any(r is not None for r in self.refs) else (
                    SlotState.UNKNOWN)
            if new != st.state:
                st.state, st.changed_at = new, now
            st.remaining = tr.predict(now) if new == SlotState.ACTIVE else None
        self.reader.save()
        return [self._copy(s) for s in self.states]

    def _learn(self, rd, tr, now):
        """Teach the reader digits it doesn't know yet (or reads poorly) from the
        countdown: once it is locked, the number on screen is known."""
        pred = tr.predict(now)
        if pred is None or pred < 0.6:
            return
        # Only when the shown text can't flip within the countdown's error.
        texts = {_shown(pred + d) for d in (-0.45, 0.0, 0.45)}
        if len(texts) != 1:
            return
        text = texts.pop()
        # Anchor on a digit the reader is sure of, then step to where the others must be.
        offsets, x = [], 0
        for i, ch in enumerate(text):
            if ch == ".":
                x += DOT_EXTRA
                continue
            offsets.append((ch, x))
            x += ADVANCE
        for anchor in sorted(rd.line, key=lambda g: -g.score):
            if anchor.score < CONFIDENT_MIN:
                break
            idx = [k for k, (ch, _) in enumerate(offsets) if ch == anchor.digit]
            if len(idx) != 1:
                continue
            ax = anchor.x - offsets[idx[0]][1]
            for k, (ch, off) in enumerate(offsets):
                if k == idx[0]:
                    continue
                cell = _glyph_near(rd.image, ax + off, anchor.y)
                if cell is not None:
                    self.reader.learn(ch, cell)
            return

    @staticmethod
    def _copy(s):
        c = SlotState(s.index)
        c.__dict__.update(s.__dict__)
        return c


def _glyph_near(img, x, y, r=2):
    """The CELL-sized patch around (x, y) with the most contrast (where a glyph is)."""
    if img is None:
        return None
    best, out = 0.0, None
    for dy in (-1, 0, 1):
        for dx in range(-r, r + 1):
            x0, y0 = x + dx, y + dy
            if x0 < 0 or y0 < 0 or x0 + CELL_W > img.shape[1] or y0 + CELL_H > img.shape[0]:
                continue
            c = img[y0:y0 + CELL_H, x0:x0 + CELL_W]
            # Favour a patch whose bright pixels are centred, so the glyph isn't clipped.
            m = c > c.mean() + c.std()
            if not m.any():
                continue
            cx = np.nonzero(m)[1].mean()
            score = float(c.std()) - 4.0 * abs(cx - (CELL_W - 1) / 2)
            if score > best:
                best, out = score, c.copy()
    return out


def _shown(v):
    """How the HUD would print `v` seconds (whole seconds from 10 up)."""
    if v < 10:
        return "%.1f" % (int(v * 10) / 10.0)
    return "%d" % int(v)
