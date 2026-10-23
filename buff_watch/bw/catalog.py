"""Reference icons of every known buff (imported from semlar.com/buffs).

The catalog images are white-on-transparent game textures. An icon on screen is the
same texture drawn at some size S (the "icon size"), so to compare we render the
texture at S and match it against the white map of the screen.
"""

import json
import os
import sys

import cv2
import numpy as np

from . import config
from .detector import white_map


def catalog_dir():
    base = getattr(sys, "_MEIPASS", None) or config.app_dir()  # PyInstaller bundles it
    return os.path.join(base, "catalog")


class Icon:
    def __init__(self, idx, file, names, lum):
        self.idx = idx
        self.file = file
        self.names = names
        self.lum = lum  # float32 luminance * alpha, full texture canvas
        ys, xs = np.nonzero(lum > 20)
        h, w = lum.shape
        # Where the visible symbol sits inside the canvas, as fractions.
        self.content = ((xs.min() / w, ys.min() / h, (xs.max() + 1) / w, (ys.max() + 1) / h)
                        if len(xs) else (0, 0, 1, 1))

    @property
    def label(self):
        n = len(self.names)
        return self.names[0] if n == 1 else "%s (+%d more)" % (self.names[0], n - 1)

    def render(self, size):
        """BGR image of the symbol as it would look at icon size `size` (tight crop)."""
        t = cv2.resize(self.lum, (size, size), interpolation=cv2.INTER_AREA)
        x0, y0, x1, y1 = self.content_box(size)
        g = np.clip(t[y0:y1, x0:x1], 0, 255).astype(np.uint8)
        return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)

    def content_box(self, size):
        cx0, cy0, cx1, cy1 = self.content
        x0, y0 = int(cx0 * size), int(cy0 * size)
        x1, y1 = max(x0 + 4, int(np.ceil(cx1 * size))), max(y0 + 4, int(np.ceil(cy1 * size)))
        return x0, y0, min(size, x1), min(size, y1)

    def thumb(self, size=32):
        t = cv2.resize(self.lum, (size, size), interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(np.clip(t, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


class Match:
    def __init__(self, icon, score, size, box):
        self.icon = icon
        self.score = score
        self.size = size  # icon size S that matched best
        self.box = box  # (x, y, w, h) of the symbol in the searched image


class Catalog:
    def __init__(self):
        self.icons = []
        self._cache = {}  # size -> [(icon, template)]

    def load(self, path=None):
        path = path or catalog_dir()
        try:
            with open(os.path.join(path, "catalog.json"), encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            return self
        for item in raw:
            im = cv2.imread(os.path.join(path, "icons", item["file"]), cv2.IMREAD_UNCHANGED)
            if im is None:
                continue
            if im.ndim == 2:
                lum, alpha = im.astype(np.float32), 255.0
            else:
                lum = cv2.cvtColor(im[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
                alpha = im[..., 3].astype(np.float32) if im.shape[2] == 4 else 255.0
            # Big textures are only ever compared at HUD size; keep them small.
            lum = cv2.resize(lum * alpha / 255.0, (96, 96), interpolation=cv2.INTER_AREA)
            self.icons.append(Icon(len(self.icons), item["file"], item["names"], lum))
        return self

    def __len__(self):
        return len(self.icons)

    def all_names(self):
        """[(name, icon)] sorted by name."""
        return sorted(((n, ic) for ic in self.icons for n in ic.names),
                      key=lambda x: x[0].lower())

    def _templates(self, size):
        if size not in self._cache:
            out = []
            for ic in self.icons:
                t = cv2.resize(ic.lum, (size, size), interpolation=cv2.INTER_AREA)
                if t.std() > 3:
                    out.append((ic, t))
            self._cache[size] = out
        return self._cache[size]

    def identify(self, frame, box, sizes, top=5):
        """Best catalog icons for the symbol around `box` in `frame` (BGR), trying
        each icon size in `sizes`. Returns Matches, best first, one per icon."""
        x, y, w, h = box
        half = max(sizes) // 2 + 4
        cx, cy = x + w // 2, y + h // 2
        H, W = frame.shape[:2]
        px0, py0 = max(0, cx - half), max(0, cy - half)
        patch = frame[py0:min(H, cy + half), px0:min(W, cx + half)]
        wm = white_map(patch).astype(np.float32)
        best = {}
        for s in sizes:
            if s > wm.shape[0] or s > wm.shape[1]:
                continue
            for ic, t in self._templates(s):
                r = cv2.matchTemplate(wm, t, cv2.TM_CCOEFF_NORMED)
                _, mx, _, (lx, ly) = cv2.minMaxLoc(r)
                if not np.isfinite(mx):
                    continue
                cur = best.get(ic.idx)
                if cur is None or mx > cur.score:
                    bx0, by0, bx1, by1 = ic.content_box(s)
                    best[ic.idx] = Match(ic, float(mx), s, (px0 + lx + bx0, py0 + ly + by0,
                                                            bx1 - bx0, by1 - by0))
        return sorted(best.values(), key=lambda m: -m.score)[:top]

    @staticmethod
    def sizes(settings, capture_h):
        """Icon sizes (pixels) to try. Narrow once the real size has been learned."""
        frac = settings.get("icon_frac")
        if frac:
            s = int(round(frac * capture_h))
            return [s - 2, s, s + 2]
        lo, hi = int(0.016 * capture_h), int(0.030 * capture_h)
        step = max(2, (hi - lo) // 7)
        return list(range(lo, hi + 1, step))

    @staticmethod
    def icon_size(settings, capture_h):
        """Best guess of the on-screen icon size, used to render catalog artwork."""
        return int(round((settings.get("icon_frac") or 0.024) * capture_h))
