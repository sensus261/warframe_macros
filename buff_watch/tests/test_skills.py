"""Checks ability-timer reading on HUD crops from real 3200x1800 screenshots.

Run from the buff_watch folder:  python -m pytest tests   (or: python tests/test_skills.py)
"""

import os
import sys

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from bw import config, skills  # noqa: E402

# Each crop is 260x100 px; the four ability slots sit at x 32..228, y 20..82.
SLOTS = (32, 20, 228, 82)
EXPECTED = {
    # file: number shown in slots 1-4 ("" = ready, no timer)
    "off": ["", "", "", ""],
    "zero": ["", "", "", ""],  # no energy, icons greyed out
    "on": ["", "41", "21", "11"],
    "casting4": ["", "59", "20", ""],  # 4 held down, its timer not started yet
    "active2": ["", "52", "10", "6.7"],
    "zero_active": ["", "48", "9.4", "8.9"],
}


def _settings():
    return config._merge(config.DEFAULTS, {})


def _roi(name):
    im = cv2.imread(os.path.join(HERE, "skills", name + ".png"))
    x0, y0, x1, y1 = SLOTS
    return im[y0:y1, x0:x1]


def _bundled_only():
    r = skills.DigitReader.__new__(skills.DigitReader)
    r.bundled, r.learned = {}, {}
    r._lock = skills.threading.Lock()
    r._dirty = 0
    strip = cv2.imread(skills._bundled_digits_path(), cv2.IMREAD_GRAYSCALE)
    for d in range(10):
        c = strip[:, d * skills.CELL_W:(d + 1) * skills.CELL_W]
        if c.std() > 5:
            r.bundled[str(d)] = skills._norm(c)
    r.save = lambda force=False: None
    return r


def test_reads_timers():
    reader = _bundled_only()
    for name, want in EXPECTED.items():
        cols = skills.slot_columns(_roi(name))
        for i, (col, w) in enumerate(zip(cols, want)):
            rd = reader.read(col, 1.0)
            if w:
                assert rd.present and rd.confident and rd.text == w, (name, i + 1, rd.text)
            else:
                assert not rd.present, (name, i + 1, rd.text)


def test_watcher_states_and_scale():
    s = _settings()
    w = skills.SkillWatcher(s, _bundled_only())
    w.refs = [None] * 4
    w._set_ref = lambda i, g: w.refs.__setitem__(i, g.copy())
    st = w.process(_roi("active2"), 1800, 0.0)
    assert [x.state for x in st] == ["ready", "active", "active", "active"]
    assert abs(s["skills"]["digit_scale"] - 1.0) < 0.01
    # Slot 1 had no timer while others did, so its ready look was captured.
    assert w.refs[0] is not None
    st = w.process(_roi("off"), 1800, 1.0)
    assert all(x.state == "ready" for x in st)


def test_countdown_locks_and_runs():
    tr = skills._Tracker()

    class R:
        def __init__(self, text):
            self.present = self.confident = True
            self.text, self.value = text, float(text)

    tr.update(R("41"), 0.0)
    assert tr.predict(0.0) is None  # one reading isn't enough
    tr.update(R("41"), 0.2)
    assert abs(tr.predict(0.2) - 41.5) < 0.01
    tr.update(R("40"), 1.0)  # shown number changed: re-anchor
    assert abs(tr.predict(2.0) - 39.5) < 0.01
    tr.update(R("12"), 2.1)  # a single wild misread is ignored
    assert abs(tr.predict(2.5) - 39.0) < 0.01
    tr.update(R("60"), 3.0)  # recast: two agreeing readings re-lock
    tr.update(R("60"), 3.2)
    assert abs(tr.predict(3.2) - 60.5) < 0.01


def test_learns_missing_digit():
    """A digit missing from the bundled set is learned from a running countdown."""
    reader = _bundled_only()
    del reader.bundled["4"]
    col = skills.slot_columns(_roi("on"))[1]  # shows 41
    assert reader.read(col, 1.0).text != "41"
    w = skills.SkillWatcher(_settings(), reader)
    tr = w.trackers[1]
    for t in (0.0, 0.02):
        tr.base, tr.last_seen = (41.5, 0.0), 0.0
        w._learn(reader.read(col, 1.0), tr, t)
    assert reader.learned["4"][1] == 2
    assert reader.read(col, 1.0).text == "41"


if __name__ == "__main__":
    for fn in (test_reads_timers, test_watcher_states_and_scale, test_countdown_locks_and_runs,
               test_learns_missing_digit):
        fn()
        print("ok", fn.__name__)
