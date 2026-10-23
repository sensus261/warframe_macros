"""Background thread: capture -> detect -> hand results to the UI."""

import copy
import queue
import threading
import time

from .capture import CaptureError, ImageSource, ScreenSource
from .detector import Detector
from .skills import SkillWatcher


class Result:
    def __init__(self):
        self.roi = None  # BGR image of the buff area
        self.capture_h = 0
        self.detections = []
        self.new_unknowns = []
        self.recognised = []  # Unknowns the catalog named by itself
        self.learned = []  # (entry_id, crop) for catalog buffs first seen on screen
        self.present = {}  # entry_id -> Detection (latest box) for buffs currently up
        self.present_fast = set()  # same, with auto-press's shorter miss_frames
        self.scores = {}  # entry_id -> best score this frame
        self.skill_roi = None  # BGR image of the ability slots (None = skills off)
        self.skills = []  # skills.SlotState per slot
        self.error = None
        self.fps = 0.0


class Worker(threading.Thread):
    def __init__(self, settings, library, catalog=None, image_path=None):
        super().__init__(daemon=True)
        self.settings = settings
        self.library = library
        self.image_path = image_path
        self.detector = Detector(settings)
        self.detector.catalog = catalog
        self.skills = SkillWatcher(settings)
        self.lock = threading.Lock()  # guards self.detector
        self.results = queue.Queue(maxsize=2)
        self.running = threading.Event()
        self.running.set()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def capture_skill_icons(self):
        self.skills.request_capture()

    def resolve_unknown(self, uid):
        with self.lock:
            self.detector.resolve(uid)

    def pending_unknowns(self):
        with self.lock:
            return list(self.detector.pending)

    def _push(self, res):
        try:
            self.results.put_nowait(res)
        except queue.Full:
            try:
                old = self.results.get_nowait()
                # Keep the one-off events of the frame we drop.
                res.new_unknowns = old.new_unknowns + res.new_unknowns
                res.recognised = old.recognised + res.recognised
                res.learned = old.learned + res.learned
            except queue.Empty:
                pass
            self.results.put_nowait(res)

    def run(self):
        source, source_cfg = None, None
        t_last = time.perf_counter()
        fps = 0.0
        while not self._stop.is_set():
            period = 1.0 / max(1, float(self.settings.get("fps", 8)))
            t0 = time.perf_counter()
            if not self.running.is_set():
                time.sleep(0.1)
                continue
            res = Result()
            try:
                if self.image_path:
                    if source is None:
                        source = ImageSource(self.image_path)
                elif source is None or source_cfg != self.settings["source"]:
                    if source is not None:
                        source.close()
                    source_cfg = copy.deepcopy(self.settings["source"])
                    source = ScreenSource(source_cfg)
                roi, cap_h = source.grab_roi(self.settings["roi"])
                entries, version = self.library.snapshot()
                with self.lock:
                    self.detector.sync_library(entries, version)
                    dets, new = self.detector.process(roi, cap_h)
                    res.recognised, self.detector.recognised = self.detector.recognised, []
                    res.learned, self.detector.learned = self.detector.learned, []
                    ak_miss = self.settings["autokey"]["miss_frames"]
                    for e in entries:
                        if self.detector.is_present(e.id):
                            res.present[e.id] = self.detector.last_det[e.id]
                        if self.detector.is_present(e.id, ak_miss):
                            res.present_fast.add(e.id)
                sk = self.settings["skills"]
                if sk["enabled"]:
                    sroi, _ = source.grab_roi(sk["roi"])
                    miss_s = (int(sk["miss_frames"]) + 0.5) * period
                    res.skills = self.skills.process(sroi, cap_h, time.monotonic(), miss_s)
                    res.skill_roi = sroi
                res.roi, res.capture_h = roi, cap_h
                res.detections, res.new_unknowns = dets, new
                for d in dets:
                    res.scores[d.entry_id] = max(res.scores.get(d.entry_id, 0), d.score)
            except CaptureError as ex:
                res.error = str(ex)
            except Exception as ex:  # keep the loop alive, show the problem in the UI
                res.error = "%s: %s" % (type(ex).__name__, ex)
                source = None
            now = time.perf_counter()
            dt = now - t_last
            t_last = now
            fps = fps * 0.8 + (1.0 / dt if dt > 0 else 0) * 0.2
            res.fps = fps
            self._push(res)
            spare = period - (time.perf_counter() - t0)
            self._stop.wait(max(0.005, spare) if not res.error else 1.0)
        if source is not None:
            source.close()
        self.skills.reader.save(force=True)
