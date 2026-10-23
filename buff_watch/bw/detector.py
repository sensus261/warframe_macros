"""Finds known icons (template matching) and reports unknown ones (blob discovery).

Everything here works on plain numpy images, so it can be tested on screenshots.
"""

import cv2
import numpy as np

from .library import KIND_BUFF


def white_map(bgr):
    """Bright, unsaturated pixels -> high. Warframe buff icons are white/grey, while
    the scenery behind them is usually coloured or dark, so this drops most of it."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s = hsv[..., 1].astype(np.float32) / 255.0
    v = hsv[..., 2].astype(np.float32) / 255.0
    w = np.clip((v - 0.35) / 0.6, 0, 1) * np.clip(1 - (s - 0.15) / 0.3, 0, 1)
    return (w * 255).astype(np.uint8)


def feature(bgr, mode):
    if mode == "gray":
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return white_map(bgr)


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def overlaps(a, b):
    """True if either box's centre lies inside the other."""
    def inside(p, box):
        return box[0] <= p[0] <= box[0] + box[2] and box[1] <= p[1] <= box[1] + box[3]
    ca = (a[0] + a[2] / 2, a[1] + a[3] / 2)
    cb = (b[0] + b[2] / 2, b[1] + b[3] / 2)
    return inside(ca, b) or inside(cb, a)


def _peaks(res, thr, w, h, max_n=6):
    res = res.copy()
    out = []
    for _ in range(max_n):
        _, mx, _, (x, y) = cv2.minMaxLoc(res)
        if mx < thr:
            break
        out.append((x, y, float(mx)))
        res[max(0, y - h // 2):y + h // 2 + 1, max(0, x - w // 2):x + w // 2 + 1] = -1
    return out


class Detection:
    __slots__ = ("entry_id", "kind", "box", "score")

    def __init__(self, entry_id, kind, box, score):
        self.entry_id = entry_id
        self.kind = kind
        self.box = box  # (x, y, w, h) in ROI pixels
        self.score = score


class Unknown:
    """An icon nobody has named yet. `frame` is the ROI image it was seen in."""

    _next = 1

    def __init__(self, box, frame):
        self.uid = Unknown._next
        Unknown._next += 1
        self.box = box
        self.frame = frame
        self.suggestions = []  # catalog.Match list, best first

    @property
    def crop(self):
        x, y, w, h = self.box
        return self.frame[y:y + h, x:x + w]


class Detector:
    def __init__(self, settings):
        self.settings = settings
        self._templates = []  # (entry_id, kind, threshold, mode, [(feat, w, h)])
        self._version = None
        self._tracks = []
        self._frame_no = 0
        self.last_seen = {}  # entry_id -> frame number
        self.last_det = {}  # entry_id -> Detection
        self.pending = []  # Unknowns waiting for the user
        self.catalog = None  # optional catalog.Catalog used to name new icons
        self.recognised = []  # Unknowns the catalog named confidently (drained by the worker)
        self.learned = []  # (entry_id, screen crop) for catalog entries seen on screen
        self._learning = set()

    # ------------------------------------------------------------ templates
    def sync_library(self, entries, version):
        if version == self._version:
            return
        self._version = version
        scales = self.settings.get("scales") or [1.0]
        tpls = []
        for e in entries:
            if e.image is None or e.image.shape[0] < 4 or e.image.shape[1] < 4:
                continue
            base = feature(e.image, e.mode)
            variants = []
            for s in scales:
                f = base if s == 1.0 else cv2.resize(
                    base, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
                if f.shape[0] >= 4 and f.shape[1] >= 4 and f.std() > 2:
                    variants.append((f, f.shape[1], f.shape[0]))
            if variants:
                learnable = bool(getattr(e, "catalog", None)) and not getattr(e, "learned", True)
                tpls.append((e.id, e.kind, e.threshold, e.mode, variants, learnable))
        self._templates = tpls
        # Drop pending unknowns that are now known or ignored.
        self.pending = [u for u in self.pending if not self._is_known(u.crop)]

    def _is_known(self, crop):
        if crop.size == 0:
            return True
        feats = {}
        for _, _, thr, mode, variants, _ in self._templates:
            if mode not in feats:
                feats[mode] = cv2.copyMakeBorder(feature(crop, mode), 6, 6, 6, 6,
                                                 cv2.BORDER_CONSTANT, value=0)
            f = feats[mode]
            for t, w, h in variants:
                if w > f.shape[1] or h > f.shape[0]:
                    continue
                r = np.nan_to_num(cv2.matchTemplate(f, t, cv2.TM_CCOEFF_NORMED))
                if r.max() >= (thr or self.settings["match_threshold"]):
                    return True
        return False

    # ------------------------------------------------------------ per frame
    def process(self, roi, capture_h):
        """Returns (detections, new_unknowns). `capture_h` is the full capture height,
        used to scale the icon size limits."""
        self._frame_no += 1
        feats = {"white": white_map(roi)}
        dets = []
        g_thr = self.settings["match_threshold"]
        learnable = set()
        for entry_id, kind, thr, mode, variants, learn in self._templates:
            if learn:
                learnable.add(entry_id)
            if mode not in feats:
                feats[mode] = feature(roi, mode)
            f = feats[mode]
            for t, w, h in variants:
                if w > f.shape[1] or h > f.shape[0]:
                    continue
                r = np.nan_to_num(cv2.matchTemplate(f, t, cv2.TM_CCOEFF_NORMED),
                                  nan=0.0, posinf=0.0, neginf=0.0)
                for x, y, sc in _peaks(r, thr or g_thr, w, h):
                    dets.append(Detection(entry_id, kind, (x, y, w, h), sc))

        # Non-max suppression across all templates and scales.
        dets.sort(key=lambda d: d.score, reverse=True)
        kept = []
        for d in dets:
            if all(iou(d.box, k.box) < 0.3 for k in kept):
                kept.append(d)

        for d in kept:
            if d.kind == KIND_BUFF:
                prev = self.last_det.get(d.entry_id)
                if (prev is None or self.last_seen.get(d.entry_id) != self._frame_no
                        or d.score > prev.score):
                    self.last_det[d.entry_id] = d
                self.last_seen[d.entry_id] = self._frame_no
                # A buff added from the catalog starts with the catalog artwork; the first
                # clear sighting replaces it with how the icon really looks on this screen.
                if (d.entry_id in learnable and d.entry_id not in self._learning
                        and d.score >= g_thr + 0.05):
                    x, y, w, h = d.box
                    self._learning.add(d.entry_id)
                    self.learned.append((d.entry_id, roi[y:y + h, x:x + w].copy()))

        new = []
        if self.settings.get("discovery", True):
            new = self._discover(roi, feats["white"], kept, capture_h)
        return kept, new

    def is_present(self, entry_id):
        seen = self.last_seen.get(entry_id)
        return seen is not None and self._frame_no - seen <= self.settings["miss_frames"]

    # ------------------------------------------------------------ discovery
    def candidates(self, white, capture_h):
        lo = max(6, int(self.settings["icon_min_frac"] * capture_h))
        hi = max(lo + 2, int(self.settings["icon_max_frac"] * capture_h))
        m = (white > 90).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        n, _, stats, _ = cv2.connectedComponentsWithStats(m)
        out = []
        H, W = white.shape
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            if h > w * 1.25:  # icon merged with the number under it: keep the top part
                h = w
            if not (lo <= w <= hi and lo <= h <= hi):
                continue
            if w > h * 1.6 or area < 0.12 * w * h:  # text runs, thin lines
                continue
            p = 2
            x0, y0 = max(0, x - p), max(0, y - p)
            x1, y1 = min(W, x + w + p), min(H, y + h + p)
            out.append((int(x0), int(y0), int(x1 - x0), int(y1 - y0)))
        return out

    def _discover(self, roi, white, kept, capture_h):
        cands = [c for c in self.candidates(white, capture_h)
                 if not any(overlaps(c, d.box) for d in kept)]
        stable = self.settings["stable_frames"]
        for c in cands:
            cx, cy = c[0] + c[2] / 2, c[1] + c[3] / 2
            best = None
            for t in self._tracks:
                tx, ty = t["box"][0] + t["box"][2] / 2, t["box"][1] + t["box"][3] / 2
                if abs(tx - cx) <= c[2] * 0.4 and abs(ty - cy) <= c[3] * 0.4:
                    best = t
                    break
            if best is None:
                self._tracks.append({"box": c, "count": 1, "seen": self._frame_no,
                                     "reported": False})
            elif best["seen"] != self._frame_no:
                best["box"] = c
                best["count"] += 1
                best["seen"] = self._frame_no
        self._tracks = [t for t in self._tracks if self._frame_no - t["seen"] <= 3]

        new = []
        for t in self._tracks:
            if t["reported"] or t["count"] < stable or t["seen"] != self._frame_no:
                continue
            t["reported"] = True
            u = Unknown(t["box"], roi.copy())
            if self._is_known(u.crop) or self._is_pending(u.crop):
                continue
            if self.catalog is not None and len(self.catalog):
                if not self._identify(u, capture_h):
                    continue
                if self._is_known(u.crop) or self._is_pending(u.crop):
                    continue
            if len(self.pending) < 50:
                self.pending.append(u)
                new.append(u)
        return new

    def _identify(self, u, capture_h):
        """Look the unknown up in the catalog. Returns False if it should be dropped
        (it was named automatically, or catalog-only mode found nothing)."""
        s = self.settings
        u.suggestions = self.catalog.identify(u.frame, u.box, self.catalog.sizes(s, capture_h))
        best = u.suggestions[0] if u.suggestions else None
        second = u.suggestions[1].score if len(u.suggestions) > 1 else 0.0
        if best is not None and best.score >= 0.6:
            u.box = best.box  # the catalog knows the symbol's exact outline
        if (best is not None and best.score >= s["catalog_auto_threshold"]
                and best.score - second >= 0.08):
            s["icon_frac"] = round(best.size / capture_h, 5)
            if s["catalog_auto_name"] and len(best.icon.names) == 1:
                self.recognised.append(u)
                return False
        if s["catalog_only"] and (best is None or best.score < 0.5):
            return False
        return True

    def _is_pending(self, crop):
        f = cv2.copyMakeBorder(white_map(crop), 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=0)
        for u in self.pending:
            t = white_map(u.crop)
            if t.shape[0] > f.shape[0] or t.shape[1] > f.shape[1] or t.std() < 2:
                continue
            if np.nan_to_num(cv2.matchTemplate(f, t, cv2.TM_CCOEFF_NORMED)).max() > 0.8:
                return True
        return False

    def resolve(self, uid):
        self.pending = [u for u in self.pending if u.uid != uid]
