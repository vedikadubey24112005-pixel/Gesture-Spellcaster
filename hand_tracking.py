"""
hand_tracking.py - wraps MediaPipe hand detection.

MediaPipe finds the hand in the picture and returns 21 landmark points
(wrist, 4 points per finger...). We convert them to screen pixel coordinates
and smooth them a little so the drawing does not jitter.

Two MediaPipe generations are supported automatically:
  * old  (<= 0.10.21, Python 3.9-3.12): mp.solutions.hands, model is built in
  * new  (>= 0.10.31, needed for Python 3.13): "Tasks" HandLandmarker, which needs the model
    file  hand_landmarker.task  -> downloaded automatically the first time you run the game.
"""
import os
import time
import urllib.request

import numpy as np

import config

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_PATH = os.path.join(config.BASE_DIR, "hand_landmarker.task")

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]


def ensure_model():
    """Download the hand model once (about 7 MB) if it is not next to the game."""
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 1_000_000:
        return
    print("[model] downloading hand_landmarker.task (~7 MB, first run only)...")
    tmp = MODEL_PATH + ".part"
    try:
        urllib.request.urlretrieve(MODEL_URL, tmp)
        os.replace(tmp, MODEL_PATH)
        print("[model] done.")
    except Exception as exc:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(
            f"Could not download the hand model ({exc}).\n"
            f"    Download it manually from:\n      {MODEL_URL}\n"
            f"    and save it as:\n      {MODEL_PATH}") from exc


class HandTracker:
    def __init__(self):
        import mediapipe as mp
        self.mp = mp
        self.prev = None
        self.legacy = hasattr(mp, "solutions")
        if self.legacy:
            self.hands = mp.solutions.hands.Hands(
                static_image_mode=False, max_num_hands=1, model_complexity=1,
                min_detection_confidence=0.6, min_tracking_confidence=0.5)
        else:
            ensure_model()
            from mediapipe.tasks.python import BaseOptions, vision
            with open(MODEL_PATH, "rb") as f:          # load bytes: avoids Windows non-ASCII path problems
                model_bytes = f.read()
            options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_buffer=model_bytes),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5)
            self.landmarker = vision.HandLandmarker.create_from_options(options)
            self._t0 = time.monotonic()
            self._last_ts = -1

    def _detect(self, rgb):
        """Return list of landmark objects with .x / .y (normalised 0-1) or None."""
        if self.legacy:
            rgb.flags.writeable = False
            res = self.hands.process(rgb)
            return res.multi_hand_landmarks[0].landmark if res.multi_hand_landmarks else None
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        ts = max(int((time.monotonic() - self._t0) * 1000), self._last_ts + 1)   # must strictly increase
        self._last_ts = ts
        res = self.landmarker.detect_for_video(img, ts)
        return res.hand_landmarks[0] if res.hand_landmarks else None

    def process(self, rgb_small):
        """rgb_small: RGB image. Returns list of 21 (x, y) screen-pixel points, or None."""
        lm = self._detect(rgb_small)
        if lm is None:
            self.prev = None
            return None
        pts = [(p.x * config.WIDTH, p.y * config.HEIGHT) for p in lm]
        if self.prev is not None:
            a = config.LANDMARK_SMOOTHING
            pts = [(a * x + (1 - a) * px, a * y + (1 - a) * py)
                   for (x, y), (px, py) in zip(pts, self.prev)]
        self.prev = pts
        return pts

    def close(self):
        if self.legacy:
            self.hands.close()
        else:
            self.landmarker.close()
