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
    # Opt-in auto-press of a buff's key when it runs out (see README).
    "autokey": {
        "enabled": True,  # master switch, also flipped by the toggle hotkey
        "toggle_hotkey": "f8",
        "only_when_focused": True,  # never send keys unless the game window has focus
        # Frames a buff may be unseen before auto-press counts it as expired. Kept below
        # the overlay's miss_frames so the first press lands right after expiry.
        "miss_frames": 1,
    },
    # Ability watching: the four ability slots in the bottom-right HUD (see README).
    "skills": {
        "enabled": True,
        # The four slots as fractions (x0, y0, x1, y1) of the capture, split in four columns.
        "roi": [0.8819, 0.9167, 0.9431, 0.9511],
        "digit_scale": None,  # learned automatically from the first clear timer
        "miss_frames": 2,  # scans the number may be missing before the timer counts as over
        "slots": [],  # per slot: see SKILL_SLOT_DEFAULTS, plus "name" and "key"
    },
    # Buffs list groups (list only, the overlay ignores them): names in display order, and
    # the collapsed ones ("" = the Ungrouped section). A buff's group is stored on its entry.
    "groups": [],
    "groups_collapsed": [],
    # Overlay window.
    "overlay": {
        "visible": True,
        "x": 60,
        "y": 200,
        # x, y is the screen position of the anchor corner, which stays put while the
        # overlay grows or shrinks as buffs come and go.
        "anchor": "top-left",  # top-left, top-right, bottom-left, bottom-right
        "zoom": 3.0,
        "orientation": "vertical",  # "horizontal", or "grid" (wraps after `columns`)
        "columns": 3,
        "cell_gap": 4,  # pixels between cells
        "cell_padding": 2,  # pixels between a cell's border and its content
        "border_width": 2,  # alert / flash border, 0 hides it
        "show_missing": True,
        "show_names": True,
        "name_position": "below",  # or "right"
        "font_family": "Segoe UI",
        "font_size": 10,
        "font_bold": True,
        "text_color": "#e8e8e8",
        "off_text_color": "#8a8a8a",
        "alert_color": "#ff5050",  # text and border of an off buff set to alert
        "flash_color": "#ffd400",  # border flash when a buff turns on or off
        "flash_seconds": 0.6,
        "cell_color": "#101014",
        "solid_background": False,  # fill the gaps between cells instead of see-through
        "background_color": "#101014",
        "opacity": 1.0,
        "dim_missing": 0.33,  # brightness of a buff's icon while it is off
        "click_through": False,
        "hide_from_capture": True,
    },
}


# The skills overlay is a second overlay window with the same options as the buff one.
DEFAULTS["skills_overlay"] = dict(
    DEFAULTS["overlay"], x=60, y=600, orientation="horizontal", zoom=3.0,
    dim_missing=0.6,  # brightness of a slot while its ability is ready
)

# Per ability slot (settings["skills"]["slots"][i]). "name" defaults to "Ability N" and
# "key" to the slot number, the game's default binding.
SKILL_SLOT_DEFAULTS = {
    "auto": False,  # auto-press this slot's key
    "early": 0.0,  # seconds before the timer ends to press (0 = when it ends)
    "interval": 1500,  # ms between presses while the ability doesn't come back
    "max": 5,  # presses before giving up until the timer is seen again
    "hold": 50,  # ms to hold the key (longer for hold-to-cast abilities)
    "show": True,  # show the slot in the skills overlay
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
