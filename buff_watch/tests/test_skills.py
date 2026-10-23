"""Checks ability-timer reading on HUD crops from real 3200x1800 screenshots.

Run from the buff_watch folder:  python -m pytest tests   (or: python tests/test_skills.py)
"""

import os
import sys
import tempfile

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from bw import config, skills  # noqa: E402

# Keep the tests' captured slot icons out of the real data folder.
_TMP = tempfile.mkdtemp()
skills.ICON_DIR = _TMP
skills.OLD_REF_FILE = os.path.join(_TMP, "old_%d.png")

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
    s["skills"]["profiles"] = [{"id": "states", "name": "States"}]
    w = skills.SkillWatcher(s, _bundled_only())
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


def test_energy_bar():
    """Fill of the energy bar; the screenshots show 755 (full), 452, 741, 685, 0, 11."""
    want = {"off": 1.0, "on": 0.599, "casting4": 0.981, "active2": 0.907, "zero": 0.0,
            "zero_active": 0.015}
    bar = [33 / 260, 67 / 100, 217 / 260, 85 / 100]  # bar ends inside the 260x100 crops
    rect = [bar[0], bar[1] - 0.1, bar[2], bar[3] + 0.1]
    for name, e in want.items():
        im = cv2.imread(os.path.join(HERE, "skills", name + ".png"))
        x0, y0 = int(round(rect[0] * 260)), int(round(rect[1] * 100))
        x1, y1 = int(round(rect[2] * 260)), int(round(rect[3] * 100))
        got = skills.read_energy(im[y0:y1, x0:x1], bar, rect)
        assert got is not None and abs(got - e) <= 0.03, (name, got, e)
    assert skills.read_energy(np.zeros((30, 180, 3), np.uint8), bar, rect) is None


def test_profiles():
    s = _settings()
    s["skills"]["slots"] = [{"name": "Sonar", "key": "2"}]  # settings from before profiles
    profs = skills.profiles(s)
    assert [p["id"] for p in profs] == ["default"] and "slots" not in s["skills"]
    assert skills.slot_settings(s, 0)["name"] == "Sonar"
    b = skills.new_profile(s, "Banshee", copy_from=profs[0])
    b2 = skills.new_profile(s, "Banshee!")
    assert b["id"] == "banshee" and b2["id"] == "banshee2"
    s["skills"]["profile"] = b2["id"]
    assert skills.slot_settings(s, 0)["name"] == "Ability 1"
    s["skills"]["profile"] = b["id"]
    assert skills.slot_settings(s, 0)["name"] == "Sonar"


def test_profile_switches_by_icons():
    s = _settings()
    banshee = skills.new_profile(s, "Banshee")
    other = skills.new_profile(s, "Other")
    w = skills.SkillWatcher(s, _bundled_only())
    cols = [cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) for c in skills.slot_columns(_roi("off"))]
    rng = np.random.default_rng(1)
    w._refs[banshee["id"]] = cols
    w._refs[other["id"]] = [rng.integers(0, 255, c.shape, dtype=np.uint8) for c in cols]
    s["skills"]["profile"] = other["id"]
    for t in (0.0, 1.0, 2.0):
        w.process(_roi("off"), 1800, t)
    assert s["skills"]["profile"] == banshee["id"]
    for t in (3.0, 4.0, 5.0):  # and it stays on the profile that matches
        w.process(_roi("zero"), 1800, t)
    assert s["skills"]["profile"] == banshee["id"]


if __name__ == "__main__":
    for fn in (test_reads_timers, test_watcher_states_and_scale, test_countdown_locks_and_runs,
               test_learns_missing_digit, test_energy_bar, test_profiles,
               test_profile_switches_by_icons):
        fn()
        print("ok", fn.__name__)
