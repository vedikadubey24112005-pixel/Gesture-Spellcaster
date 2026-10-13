"""
gesture_recognition.py - turns 21 landmarks into a gesture name.

Static gestures use GEOMETRY:
    a finger is "extended" if its tip is farther from the wrist than its middle joint.
    (this works whichever way the hand is rotated)
Dynamic gestures use MOTION over time:
    SWIPE  = palm travelled far and fast horizontally within a short window
    COMBO  = a specific sequence of gestures performed within a few seconds
"""
import math
from collections import Counter, deque
from dataclasses import dataclass

import config

NONE, UNKNOWN = "NONE", "UNKNOWN"
POINT, PALM, FIST, PINCH = "POINT", "PALM", "FIST", "PINCH"
LABELS = {POINT: "POINT", PALM: "OPEN PALM", FIST: "FIST", PINCH: "PINCH",
          UNKNOWN: "...", NONE: "-"}


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class HandState:
    present: bool = False
    landmarks: list = None
    gesture: str = NONE          # stabilised gesture
    raw_gesture: str = NONE      # this-frame guess (for debug)
    palm: tuple = (0, 0)
    size: float = 100.0          # wrist -> middle knuckle length in px
    tip: tuple = (0, 0)          # index fingertip
    aim: tuple = (0, -1)         # unit vector the index finger points along
    pinch_pos: tuple = (0, 0)
    velocity: tuple = (0, 0)     # px / second
    swipe: str = None            # "left" / "right" for ONE frame
    swipe_progress: float = 0.0  # 0..1 how close the current motion is to a swipe (for feedback)
    combo: str = None            # combo name for ONE frame
    fingers: dict = None


def analyse(lm):
    """Return (raw_gesture, finger_dict, palm_size, pinch_ratio)."""
    wrist = lm[0]
    size = max(dist(lm[0], lm[9]), 1.0)
    f = {}
    for name, tip, pip in (("index", 8, 6), ("middle", 12, 10), ("ring", 16, 14), ("pinky", 20, 18)):
        f[name] = dist(lm[tip], wrist) > dist(lm[pip], wrist) * 1.12
    f["thumb"] = dist(lm[4], lm[5]) > 0.55 * size
    pinch_ratio = dist(lm[4], lm[8]) / size
    return f, size, pinch_ratio


class GestureRecognizer:
    def __init__(self):
        self.history = deque(maxlen=config.GESTURE_HISTORY)
        self.stable = NONE
        self.palm_track = deque()
        self.last_swipe = 0.0
        self.sequence = deque(maxlen=6)
        self.prev_palm = None
        self.prev_t = None
        self.vel = (0.0, 0.0)
        self.aim = (0.0, -1.0)

    # ---- combos (shared with the mouse-simulation mode) ----
    def track_sequence(self, gesture, now):
        if gesture not in (POINT, PALM, FIST, PINCH):
            return None
        if self.sequence and self.sequence[-1][0] == gesture:
            return None
        self.sequence.append((gesture, now))
        seq = list(self.sequence)
        for name, pattern in config.COMBOS.items():
            n = len(pattern)
            if len(seq) >= n and tuple(g for g, _ in seq[-n:]) == pattern \
                    and now - seq[-n][1] <= config.COMBO_WINDOW:
                self.sequence.clear()
                return name
        return None

    def _lost(self):
        self.history.clear()
        self.stable = NONE
        self.prev_palm = None
        self.vel = (0.0, 0.0)
        # palm_track is deliberately KEPT: a fast swipe often makes the camera lose the hand
        # for a few frames, and we still want to remember where the hand started.

    def update(self, lm, now):
        if lm is None:
            self._lost()
            return HandState()

        fingers, size, pinch_ratio = analyse(lm)
        n_ext = sum(fingers[k] for k in ("index", "middle", "ring", "pinky"))

        # ---- classify this frame ----
        pinch_limit = config.PINCH_RATIO * (1.5 if self.stable == PINCH else 1.0)  # hysteresis
        if pinch_ratio < pinch_limit:
            raw = PINCH
        elif fingers["index"] and n_ext == 1:
            raw = POINT
        elif n_ext == 4:
            raw = PALM
        elif n_ext == 0:
            raw = FIST
        else:
            raw = UNKNOWN

        # ---- majority vote to remove flicker ----
        self.history.append(raw)
        gesture, votes = Counter(self.history).most_common(1)[0]
        prev_stable = self.stable
        if votes >= config.GESTURE_MIN_VOTES:
            self.stable = gesture
        combo = self.track_sequence(self.stable, now) if self.stable != prev_stable else None

        # ---- palm centre + velocity ----
        palm = ((lm[0][0] + lm[9][0]) / 2, (lm[0][1] + lm[9][1]) / 2)
        if self.prev_palm is not None and now > self.prev_t:
            dt = now - self.prev_t
            v = ((palm[0] - self.prev_palm[0]) / dt, (palm[1] - self.prev_palm[1]) / dt)
            self.vel = (0.5 * self.vel[0] + 0.5 * v[0], 0.5 * self.vel[1] + 0.5 * v[1])
        self.prev_palm, self.prev_t = palm, now

        # ---- swipe detection ----
        # Look at every palm position of the last SWIPE_WINDOW seconds and compare the current
        # position with the FURTHEST one horizontally. Tolerates tracking drops and blurred fingers:
        # the hand only needs to look "open" in at least 2 of the recent frames.
        swipe = None
        progress = 0.0
        self.palm_track.append((now, palm[0], palm[1], n_ext >= 3))
        while self.palm_track and now - self.palm_track[0][0] > config.SWIPE_WINDOW:
            self.palm_track.popleft()
        if len(self.palm_track) >= 3 and sum(1 for smp in self.palm_track if smp[3]) >= 2:
            start_pt = max(self.palm_track, key=lambda smp: abs(palm[0] - smp[1]))
            dx, dy = palm[0] - start_pt[1], palm[1] - start_pt[2]
            if abs(dx) > 1.5 * abs(dy):
                progress = abs(dx) / (config.SWIPE_DIST_FRAC * config.WIDTH)
                if progress >= 1.0 and now - self.last_swipe > config.SWIPE_COOLDOWN:
                    swipe = "right" if dx > 0 else "left"
                    self.last_swipe = now
                    self.palm_track.clear()

        # ---- pointing direction (knuckle -> fingertip), lightly smoothed ----
        ax, ay = lm[8][0] - lm[5][0], lm[8][1] - lm[5][1]
        length = math.hypot(ax, ay)
        if length > 1:
            ax, ay = ax / length, ay / length
            self.aim = (0.6 * ax + 0.4 * self.aim[0], 0.6 * ay + 0.4 * self.aim[1])
            l2 = math.hypot(*self.aim) or 1
            self.aim = (self.aim[0] / l2, self.aim[1] / l2)

        return HandState(
            present=True, landmarks=lm, gesture=self.stable, raw_gesture=raw,
            palm=palm, size=size, tip=lm[8], aim=self.aim,
            pinch_pos=((lm[4][0] + lm[8][0]) / 2, (lm[4][1] + lm[8][1]) / 2),
            velocity=self.vel, swipe=swipe, swipe_progress=min(progress, 1.0),
            combo=combo, fingers=fingers,
        )
