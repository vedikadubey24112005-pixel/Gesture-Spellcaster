"""
sim_hand.py - "fake hand" driven by mouse + keyboard.

Used automatically if no webcam / MediaPipe is available (or with:  python main.py --sim)
so you can develop and test the game without a camera.

    mouse  = your hand position
    1      = POINT (hold)      2 = OPEN PALM (hold)     3 = FIST (hold)
    5      = PINCH (hold)      4 = SWIPE (tap)
"""
import math

import pygame

import config
from gesture_recognition import HandState, POINT, PALM, FIST, PINCH, UNKNOWN


class SimHand:
    def __init__(self, recognizer):
        self.rec = recognizer
        self.stable = UNKNOWN
        self.prev = None
        self.prev_t = None
        self.vel = (0.0, 0.0)

    def update(self, now, events):
        if not pygame.mouse.get_focused():
            return HandState()
        mx, my = pygame.mouse.get_pos()
        keys = pygame.key.get_pressed()
        g = UNKNOWN
        if keys[pygame.K_1]:
            g = POINT
        elif keys[pygame.K_2]:
            g = PALM
        elif keys[pygame.K_3]:
            g = FIST
        elif keys[pygame.K_5]:
            g = PINCH

        combo = self.rec.track_sequence(g, now) if g != self.stable else None
        self.stable = g

        if self.prev is not None and now > self.prev_t:
            dt = now - self.prev_t
            v = ((mx - self.prev[0]) / dt, (my - self.prev[1]) / dt)
            self.vel = (0.6 * self.vel[0] + 0.4 * v[0], 0.6 * self.vel[1] + 0.4 * v[1])
        self.prev, self.prev_t = (mx, my), now

        swipe = None
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_4:
                swipe = "left" if self.vel[0] < -50 else "right"

        px, py = config.PLAYER_POS
        ax, ay = mx - px, my - py
        l = math.hypot(ax, ay) or 1.0
        return HandState(
            present=True, landmarks=None, gesture=g, raw_gesture=g,
            palm=(mx, my), size=90.0, tip=(mx, my), aim=(ax / l, ay / l),
            pinch_pos=(mx, my), velocity=self.vel, swipe=swipe, combo=combo,
        )
