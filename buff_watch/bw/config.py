"""Settings and data paths."""

import copy
import json
import os
import sys


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DATA_DIR = os.path.join(app_dir(), "data")
ICON_DIR = os.path.join(DATA_DIR, "icons")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
LIBRARY_FILE = os.path.join(DATA_DIR, "library.json")

DEFAULTS = {
    # What to capture: a whole monitor (mss index, 1 = primary) or a window by title.
    "source": {"kind": "monitor", "monitor": 1, "window_title": "Warframe"},
    # Buff area as fractions (x0, y0, x1, y1) of the captured monitor/window.
    "roi": [0.60, 0.02, 0.905, 0.16],
    "fps": 8,
    # Template matching.
    "match_threshold": 0.70,
    "scales": [0.95, 1.0, 1.05],
    # A buff counts as gone only after this many frames without a match (stops flicker).
    "miss_frames": 4,
    # Discovery of unknown icons.
    "discovery": True,
    "icon_min_frac": 0.012,  # icon size limits as a fraction of the captured height
    "icon_max_frac": 0.040,
    "stable_frames": 12,  # an unknown must sit still this many frames before it is reported
    "preview": True,
    # Catalog (catalog/catalog.json, imported from semlar.com/buffs).
    "catalog_auto_name": True,  # name a new icon by itself when the match is certain
    "catalog_auto_threshold": 0.72,
    "catalog_only": False,  # drop new icons that look like nothing in the catalog
    "icon_frac": None,  # on-screen icon size / capture height, learned automatically
    # Overlay window.
    "overlay": {
        "visible": True,
        "x": 60,
        "y": 200,
        "zoom": 3.0,
        "orientation": "vertical",  # or "horizontal"
        "show_missing": True,
        "show_names": True,
        "click_through": False,
        "hide_from_capture": True,
    },
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings():
    data = {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        pass
    return _merge(DEFAULTS, data)


def save_settings(settings):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = SETTINGS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, SETTINGS_FILE)
