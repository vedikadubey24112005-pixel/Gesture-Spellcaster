"""
effects.py - glow sprites, particles, lightning bolts, shockwaves.
Everything is drawn with ADDITIVE blending so overlapping light gets brighter (looks like magic).
"""
import math
import random

import pygame
from pygame.math import Vector2 as V

_glow_cache = {}


def glow_sprite(radius, color):
    radius = max(3, int(radius) // 3 * 3)
    key = (radius, color)
    s = _glow_cache.get(key)
    if s is None:
        s = pygame.Surface((radius * 2, radius * 2))
        s.fill((0, 0, 0))
        steps = max(5, radius // 2)
        for i in range(steps):
            f = i / steps
            k = f ** 2.2
            col = (int(color[0] * k), int(color[1] * k), int(color[2] * k))
            pygame.draw.circle(s, col, (radius, radius), max(1, int(radius * (1 - f))))
        _glow_cache[key] = s
    return s


def draw_glow(surf, pos, radius, color, strength=1.0):
    q = round(max(0.0, min(1.0, strength)) * 6) / 6
    if q <= 0:
        return
    col = (min(255, int(color[0] * q)), min(255, int(color[1] * q)), min(255, int(color[2] * q)))
    spr = glow_sprite(radius, col)
    surf.blit(spr, (pos[0] - spr.get_width() // 2, pos[1] - spr.get_height() // 2),
              special_flags=pygame.BLEND_RGB_ADD)


class Particle:
    __slots__ = ("pos", "vel", "life", "max_life", "color", "size", "end_size", "gravity", "drag")

    def __init__(self, pos, vel, life, color, size, end_size=0, gravity=0.0, drag=0.0):
        self.pos = V(pos)
        self.vel = V(vel)
        self.life = self.max_life = life
        self.color = color
        self.size = size
        self.end_size = end_size
        self.gravity = gravity
        self.drag = drag


class ParticleSystem:
    MAX = 900

    def __init__(self):
        self.items = []

    def add(self, *args, **kw):
        if len(self.items) < self.MAX:
            self.items.append(Particle(*args, **kw))

    def burst(self, pos, color, n=30, speed=300, life=0.8, size=14, gravity=0.0, spread=1.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = speed * random.uniform(0.25, 1.0) * spread
            self.add(pos, (math.cos(a) * s, math.sin(a) * s), life * random.uniform(0.6, 1.2),
                     color, size * random.uniform(0.6, 1.2), 2, gravity, 2.0)

    def update(self, dt):
        alive = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            p.vel.y += p.gravity * dt
            if p.drag:
                p.vel *= max(0.0, 1 - p.drag * dt)
            p.pos += p.vel * dt
            alive.append(p)
        self.items = alive

    def draw(self, surf):
        for p in self.items:
            t = p.life / p.max_life
            r = p.end_size + (p.size - p.end_size) * t
            if r >= 2:
                draw_glow(surf, p.pos, r, p.color, t ** 0.7)


def jagged(a, b, depth=5):
    a, b = V(a), V(b)
    pts = [a, b]
    scale = (b - a).length() * 0.16
    for _ in range(depth):
        new = [pts[0]]
        for p, q in zip(pts[:-1], pts[1:]):
            d = q - p
            n = V(-d.y, d.x)
            if n.length() > 0:
                n = n.normalize()
            new.append((p + q) / 2 + n * random.uniform(-1, 1) * scale)
            new.append(q)
        pts = new
        scale *= 0.55
    return pts


class Bolt:
    """A lightning bolt through a chain of points that flickers for a fraction of a second."""

    def __init__(self, chain, life=0.32, color=(110, 160, 255)):
        self.chain = [V(p) for p in chain]
        self.life = self.max = life
        self.color = color
        self.t = 0.0
        self._build()

    def _build(self):
        pts = []
        for a, b in zip(self.chain[:-1], self.chain[1:]):
            seg = jagged(a, b)
            pts.extend(seg if not pts else seg[1:])
        self.pts = pts

    def update(self, dt):
        self.life -= dt
        self.t += dt
        if self.t > 0.045:
            self.t = 0
            self._build()

    def draw(self, surf):
        f = max(0.0, self.life / self.max)
        if f <= 0 or len(self.pts) < 2:
            return
        xs = [p.x for p in self.pts]
        ys = [p.y for p in self.pts]
        m = 20
        x0, y0 = int(min(xs)) - m, int(min(ys)) - m
        w, h = int(max(xs)) - x0 + m, int(max(ys)) - y0 + m
        if w <= 0 or h <= 0:
            return
        tmp = pygame.Surface((w, h))
        pts = [(p.x - x0, p.y - y0) for p in self.pts]
        c = self.color
        for width, mul in ((13, 0.25), (7, 0.55), (3, 1.0)):
            col = tuple(int(v * mul * f) for v in c)
            pygame.draw.lines(tmp, col, False, pts, width)
        pygame.draw.lines(tmp, (int(255 * f),) * 3, False, pts, 1)
        surf.blit(tmp, (x0, y0), special_flags=pygame.BLEND_RGB_ADD)
        for p in self.chain:
            draw_glow(surf, p, 55, c, f)


class Shockwave:
    def __init__(self, pos, max_r, color, dur=0.55):
        self.pos = V(pos)
        self.max_r = max_r
        self.color = color
        self.dur = dur
        self.t = 0.0

    @property
    def done(self):
        return self.t >= self.dur

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        f = min(1.0, self.t / self.dur)
        r = int(self.max_r * (1 - (1 - f) ** 3))
        fade = 1 - f
        if r < 4:
            return
        size = r * 2 + 40
        tmp = pygame.Surface((size, size))
        c = (size // 2, size // 2)
        fill = tuple(int(v * 0.22 * fade) for v in self.color)
        pygame.draw.circle(tmp, fill, c, r)
        ring = tuple(int(v * fade) for v in self.color)
        pygame.draw.circle(tmp, ring, c, r, max(2, int(20 * fade)))
        surf.blit(tmp, (self.pos.x - c[0], self.pos.y - c[1]), special_flags=pygame.BLEND_RGB_ADD)
