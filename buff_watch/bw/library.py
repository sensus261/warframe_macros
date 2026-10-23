"""The user's library of named icons (buffs to track and icons to ignore)."""

import json
import os
import threading
import uuid

import cv2

from . import config

KIND_BUFF = "buff"
KIND_IGNORE = "ignore"


class Entry:
    def __init__(self, id, name, kind=KIND_BUFF, pinned=False, threshold=None,
                 mode="white", alert_missing=False, catalog=None, learned=True,
                 key=None, key_interval=1500, key_max=5, group=None, description=""):
        self.id = id
        self.name = name
        self.kind = kind
        self.pinned = pinned
        self.threshold = threshold  # None = use the global threshold
        self.mode = mode  # "white" for normal white icons, "gray" for coloured icons
        self.alert_missing = alert_missing  # highlight in red while a pinned buff is missing
        self.catalog = catalog  # catalog icon file this entry came from, if any
        self.learned = learned  # False while the image is still the catalog artwork
        self.key = key  # auto-press this key while the buff is off (None = feature off)
        self.key_interval = key_interval  # ms between presses
        self.key_max = key_max  # presses before giving up until the buff is seen again
        self.group = group  # Buffs list group name (None = ungrouped)
        self.description = description  # free-text note, e.g. what the buff does
        self.image = None  # BGR numpy array

    @property
    def icon_path(self):
        return os.path.join(config.ICON_DIR, self.id + ".png")

    def to_json(self):
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "pinned": self.pinned,
            "threshold": self.threshold, "mode": self.mode,
            "alert_missing": self.alert_missing, "catalog": self.catalog,
            "learned": self.learned, "key": self.key, "key_interval": self.key_interval,
            "key_max": self.key_max, "group": self.group,
            "description": self.description,
        }


class Library:
    """Thread-safe list of entries. `version` changes whenever templates change."""

    def __init__(self):
        self.lock = threading.RLock()
        self.entries = []
        self.version = 0

    def load(self):
        with self.lock:
            self.entries = []
            try:
                with open(config.LIBRARY_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except (OSError, ValueError):
                raw = []
            for item in raw:
                e = Entry(**item)
                e.image = cv2.imread(e.icon_path, cv2.IMREAD_COLOR)
                if e.image is not None:
                    self.entries.append(e)
            self.version += 1

    def save(self):
        with self.lock:
            os.makedirs(config.DATA_DIR, exist_ok=True)
            tmp = config.LIBRARY_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump([e.to_json() for e in self.entries], f, indent=2)
            os.replace(tmp, config.LIBRARY_FILE)

    def add(self, name, image, kind=KIND_BUFF, pinned=False, catalog=None, learned=True):
        os.makedirs(config.ICON_DIR, exist_ok=True)
        with self.lock:
            e = Entry(uuid.uuid4().hex[:12], name, kind=kind, pinned=pinned,
                      catalog=catalog, learned=learned)
            e.image = image.copy()
            if not cv2.imwrite(e.icon_path, e.image):
                raise OSError("could not write " + e.icon_path)
            self.entries.append(e)
            self.version += 1
            self.save()
            return e

    def set_image(self, entry_id, image):
        """Replace the catalog artwork with how the icon really looks on screen."""
        with self.lock:
            e = self.get(entry_id)
            if e is None or image.size == 0:
                return
            e.image = image.copy()
            e.learned = True
            cv2.imwrite(e.icon_path, e.image)
            self.version += 1
            self.save()

    def find_catalog(self, file):
        with self.lock:
            return [e for e in self.entries if e.catalog == file]

    def remove(self, entry_id):
        with self.lock:
            e = self.get(entry_id)
            if e is None:
                return
            self.entries.remove(e)
            try:
                os.remove(e.icon_path)
            except OSError:
                pass
            self.version += 1
            self.save()

    def update(self, entry_id, **fields):
        with self.lock:
            e = self.get(entry_id)
            if e is None:
                return
            for k, v in fields.items():
                setattr(e, k, v)
            if {"threshold", "mode", "kind"} & set(fields):
                self.version += 1
            self.save()

    def reorder(self, ids):
        """Put the given entries in this order. Entries not listed (e.g. hidden ignored
        rows) keep their positions; the listed ones fill the slots they already occupy."""
        with self.lock:
            pos = {i: n for n, i in enumerate(ids)}
            slots = [n for n, e in enumerate(self.entries) if e.id in pos]
            moving = sorted((self.entries[n] for n in slots), key=lambda e: pos[e.id])
            for n, e in zip(slots, moving):
                self.entries[n] = e
            self.save()

    def rename_group(self, old, new):
        """Move every entry of group `old` to `new` (None = ungrouped)."""
        with self.lock:
            for e in self.entries:
                if e.group == old:
                    e.group = new
            self.save()

    def touch(self):
        """Force the detector to rebuild its templates (e.g. after a settings change)."""
        with self.lock:
            self.version += 1

    def get(self, entry_id):
        with self.lock:
            for e in self.entries:
                if e.id == entry_id:
                    return e
        return None

    def snapshot(self):
        with self.lock:
            return list(self.entries), self.version
