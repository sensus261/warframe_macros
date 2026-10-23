"""Screen capture of the configured monitor/window (or a test image)."""

import glob
import os

import cv2
import mss
import numpy as np

from . import winutil


_MSS = getattr(mss, "MSS", None) or mss.mss  # mss 10 renamed the class


class CaptureError(Exception):
    pass


def list_monitors():
    with _MSS() as sct:
        return [(i, m) for i, m in enumerate(sct.monitors) if i > 0]


class ScreenSource:
    """Grabs pixels from the desktop, the same way screenshot/recording tools do.
    Create one per thread (mss handles are not thread-safe)."""

    def __init__(self, source_cfg):
        self.cfg = source_cfg
        self.sct = _MSS()

    def target_rect(self):
        if self.cfg.get("kind") == "window":
            r = winutil.find_window_client_rect(self.cfg.get("window_title", ""))
            if r is None:
                raise CaptureError("window '%s' not found (or minimized)"
                                   % self.cfg.get("window_title", ""))
            return r
        mons = self.sct.monitors
        idx = int(self.cfg.get("monitor", 1))
        if idx < 1 or idx >= len(mons):
            idx = 1
        m = mons[idx]
        return (m["left"], m["top"], m["width"], m["height"])

    def grab(self, rect):
        x, y, w, h = rect
        shot = self.sct.grab({"left": int(x), "top": int(y), "width": int(w), "height": int(h)})
        return np.ascontiguousarray(np.asarray(shot)[..., :3])  # BGRA -> BGR

    def grab_roi(self, roi):
        """Returns (roi_image, capture_height)."""
        rect = self.target_rect()
        return self.grab(roi_rect(rect, roi)), rect[3]

    def grab_full(self):
        return self.grab(self.target_rect())

    def close(self):
        self.sct.close()


class ImageSource:
    """Plays back screenshots instead of the screen (for testing / tuning)."""

    def __init__(self, path):
        if os.path.isdir(path):
            files = sorted(f for ext in ("png", "jpg", "jpeg", "bmp", "webp")
                           for f in glob.glob(os.path.join(path, "*." + ext)))
        else:
            files = [path]
        self.images = [img for img in (cv2.imread(f, cv2.IMREAD_COLOR) for f in files)
                       if img is not None]
        if not self.images:
            raise CaptureError("no readable images at " + path)
        self.i = 0

    def grab_full(self):
        img = self.images[self.i // 8 % len(self.images)]
        self.i += 1
        return img

    def grab_roi(self, roi):
        img = self.grab_full()
        h, w = img.shape[:2]
        x, y, rw, rh = roi_rect((0, 0, w, h), roi)
        return img[y:y + rh, x:x + rw].copy(), h

    def close(self):
        pass


def roi_rect(rect, roi):
    x, y, w, h = rect
    x0, y0, x1, y1 = roi
    rx, ry = int(round(x0 * w)), int(round(y0 * h))
    rw, rh = max(8, int(round((x1 - x0) * w))), max(8, int(round((y1 - y0) * h)))
    return (x + rx, y + ry, rw, rh)
