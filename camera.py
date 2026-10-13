"""
camera.py - webcam capture on a background thread + frame preparation.

Reading the webcam blocks until a frame arrives, so we do it in its own thread.
The game loop then always grabs the *latest* frame and never waits.
"""
import platform
import threading
import time

import cv2

import config


class CameraStream:
    def __init__(self, index=0):
        api = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(index, api)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ok = self.cap.isOpened()
        self._frame = None
        self._id = 0
        self._lock = threading.Lock()
        self._running = self.ok
        if self.ok:
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            with self._lock:
                self._frame = frame
                self._id += 1

    def wait_first_frame(self, timeout=4.0):
        end = time.time() + timeout
        while time.time() < end:
            if self._frame is not None:
                return True
            time.sleep(0.05)
        return False

    def read(self, last_id):
        """Return (frame, id) if a NEW frame exists, otherwise (None, last_id)."""
        with self._lock:
            if self._frame is None or self._id == last_id:
                return None, last_id
            return self._frame.copy(), self._id

    def stop(self):
        self._running = False
        time.sleep(0.05)
        if self.cap is not None:
            self.cap.release()


def prepare_frame(frame):
    """
    Camera frame (BGR) -> (display_rgb, small_rgb)
      1. crop to 16:9 so nothing gets stretched
      2. mirror horizontally (so it behaves like a mirror)
      3. resize to window size for display, and to a small size for detection
    """
    h, w = frame.shape[:2]
    target = config.WIDTH / config.HEIGHT
    if w / h > target:
        new_w = int(h * target)
        x0 = (w - new_w) // 2
        frame = frame[:, x0:x0 + new_w]
    else:
        new_h = int(w / target)
        y0 = (h - new_h) // 2
        frame = frame[y0:y0 + new_h, :]
    frame = cv2.flip(frame, 1)
    display = cv2.resize(frame, (config.WIDTH, config.HEIGHT))
    display = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
    dw = config.DETECT_WIDTH
    small = cv2.resize(display, (dw, dw * config.HEIGHT // config.WIDTH))
    return display, small
