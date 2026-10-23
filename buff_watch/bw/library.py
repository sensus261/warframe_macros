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
                 mode="white", alert_missing=False):
        self.id = id
        self.name = name
        self.kind = kind
        self.pinned = pinned
        self.threshold = threshold  # None = use the global threshold
        self.mode = mode  # "white" for normal white icons, "gray" for coloured icons
        self.alert_missing = alert_missing  # highlight in red while a pinned buff is missing
        self.image = None  # BGR numpy array

    @property
    def icon_path(self):
        return os.path.join(config.ICON_DIR, self.id + ".png")

    def to_json(self):
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "pinned": self.pinned,
            "threshold": self.threshold, "mode": self.mode,
            "alert_missing": self.alert_missing,
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

    def add(self, name, image, kind=KIND_BUFF, pinned=False):
        os.makedirs(config.ICON_DIR, exist_ok=True)
        with self.lock:
            e = Entry(uuid.uuid4().hex[:12], name, kind=kind, pinned=pinned)
            e.image = image.copy()
            if not cv2.imwrite(e.icon_path, e.image):
                raise OSError("could not write " + e.icon_path)
            self.entries.append(e)
            self.version += 1
            self.save()
            return e

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

    def move(self, entry_id, delta):
        with self.lock:
            e = self.get(entry_id)
            if e is None:
                return
            i = self.entries.index(e)
            j = max(0, min(len(self.entries) - 1, i + delta))
            self.entries.insert(j, self.entries.pop(i))
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
