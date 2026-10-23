"""Shared Tk helpers."""

import cv2
import numpy as np
from PIL import Image, ImageTk


def to_photo(bgr, scale=1.0, interp=cv2.INTER_NEAREST):
    if scale != 1.0:
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=interp)
    return ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))


def thumb(bgr, size):
    """Letterbox `bgr` into a size x size square."""
    h, w = bgr.shape[:2]
    s = size / max(h, w)
    img = cv2.resize(bgr, (max(1, int(w * s)), max(1, int(h * s))),
                     interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_NEAREST)
    out = np.zeros((size, size, 3), np.uint8)
    y, x = (size - img.shape[0]) // 2, (size - img.shape[1]) // 2
    out[y:y + img.shape[0], x:x + img.shape[1]] = img
    return out


def context_crop(img, box, out_w=None, out_h=None):
    """The icon plus the number printed under it, on a fixed-size canvas so the
    result does not change size when the icon is near the edge of the ROI."""
    x, y, w, h = box
    cw = out_w or int(w * 1.8)
    ch = out_h or int(h * 2.1)
    x0 = int(x + w / 2 - cw / 2)
    y0 = int(y - h * 0.15)
    out = np.zeros((ch, cw, 3), np.uint8)
    H, W = img.shape[:2]
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(W, x0 + cw), min(H, y0 + ch)
    if sx1 > sx0 and sy1 > sy0:
        out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = img[sy0:sy1, sx0:sx1]
    return out
