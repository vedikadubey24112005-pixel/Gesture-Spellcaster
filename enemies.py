"""
enemies.py - Ghost, Bat and Warlock enemies + the dark orbs Warlocks shoot.
All art is drawn with pygame shapes, so no image files are needed.
"""
import math
import random

import pygame
from pygame.math import Vector2 as V

import config
from effects import draw_glow

KINDS = {
    #          hp  speed radius points colour
    "ghost":   (3, 62, 34, 10, (120, 170, 255)),
    "bat":     (1, 150, 22, 15, (190, 90, 255)),
    "warlock": (3, 34, 36, 30, (255, 70, 70)),
}


class Enemy:
    def __init__(self, kind, pos, wave):
        hp, speed, radius, points, color = KINDS[kind]
        self.kind = kind
        self.pos = V(pos)
        self.hp = self.max_hp = hp + (wave // 4 if kind != "bat" else 0)
        self.speed = speed * (1 + 0.05 * wave)
        self.radius = radius
        self.points = points
        self.color = color
        self.t = random.uniform(0, 10)
        self.phase = random.uniform(0, math.tau)
        self.hit_flash = 0.0
        self.hit_cd = 0.0
        self.frozen_until = 0.0
        self.stun = 0.0
        self.knock = V(0, 0)
        self.grabbed = False
        self.thrown = 0.0
        self.throw_vel = V(0, 0)
        self.dead = False
        self.shoot_timer = random.uniform(1.5, 2.8)
        self.wave = wave

    # ------------------------------------------------------------ logic
    def update(self, dt, now, player_pos, world):
        self.t += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.hit_cd = max(0.0, self.hit_cd - dt)
        if self.grabbed:
            return
        if self.thrown > 0:
            self.thrown -= dt
            self.pos += self.throw_vel * dt
            self.throw_vel *= max(0.0, 1 - 0.5 * dt)
            r = self.radius
            if self.pos.x < r or self.pos.x > config.WIDTH - r:
                self.throw_vel.x *= -0.85
                self.pos.x = max(r, min(config.WIDTH - r, self.pos.x))
            if self.pos.y < r or self.pos.y > config.HEIGHT - r:
                self.throw_vel.y *= -0.85
                self.pos.y = max(r, min(config.HEIGHT - r, self.pos.y))
            return
        if now < self.frozen_until:
            return
        self.pos += self.knock * dt
        self.knock *= max(0.0, 1 - 5 * dt)
        if self.stun > 0:
            self.stun -= dt
            return

        to = V(player_pos) - self.pos
        d = to.length()
        direction = to / d if d > 0 else V(0, 1)
        perp = V(-direction.y, direction.x)
        if self.kind == "ghost":
            self.pos += direction * self.speed * dt + perp * math.sin(self.t * 2 + self.phase) * 45 * dt
        elif self.kind == "bat":
            self.pos += direction * self.speed * dt + perp * math.sin(self.t * 7 + self.phase) * 230 * dt
        else:  # warlock: keeps its distance and shoots
            if d > 340:
                self.pos += direction * self.speed * dt
            else:
                self.pos += perp * math.sin(self.t * 0.9 + self.phase) * 60 * dt
            self.shoot_timer -= dt
            if self.shoot_timer <= 0 and self.pos.y > 30:
                world.spawn_orb(self.pos, player_pos)
                self.shoot_timer = max(1.4, 2.9 - 0.1 * self.wave)

    # ------------------------------------------------------------ drawing
    def _tint(self, col):
        f = min(1.0, self.hit_flash / 0.12)
        return tuple(int(c + (255 - c) * f) for c in col)

    def draw(self, surf, now):
        x, y = self.pos
        r = self.radius
        frozen = now < self.frozen_until
        draw_glow(surf, (x, y), int(r * 2.3), (90, 200, 255) if frozen else self.color, 0.55)
        if self.kind == "ghost":
            self._draw_ghost(surf, x, y, r)
        elif self.kind == "bat":
            self._draw_bat(surf, x, y, r)
        else:
            self._draw_warlock(surf, x, y, r)
        if frozen:
            pygame.draw.circle(surf, (170, 230, 255), (x, y), r + 6, 3)
        if self.grabbed:
            pygame.draw.circle(surf, (220, 140, 255), (x, y), r + 10, 3)
        if self.hp < self.max_hp:
            w = 46
            pygame.draw.rect(surf, (40, 10, 10), (x - w / 2, y - r - 18, w, 6))
            pygame.draw.rect(surf, (90, 230, 110), (x - w / 2, y - r - 18, w * self.hp / self.max_hp, 6))

    def _draw_ghost(self, surf, x, y, r):
        body = self._tint((215, 232, 255))
        pts = [(x - r, y), (x - r, y + r * 0.95)]
        n = 6
        for i in range(n + 1):
            px = x - r + 2 * r * i / n
            py = y + r * 0.95 + (math.sin(self.t * 7 + i * 1.6) * 6 + (7 if i % 2 else -3))
            pts.append((px, py))
        pts += [(x + r, y)]
        pygame.draw.polygon(surf, body, pts)
        pygame.draw.circle(surf, body, (x, y), r)
        for ex in (-0.38, 0.38):
            pygame.draw.ellipse(surf, (25, 30, 70), (x + ex * r - 6, y - 8, 12, 18))
        pygame.draw.ellipse(surf, (25, 30, 70), (x - 6, y + 14, 12, 10))

    def _draw_bat(self, surf, x, y, r):
        body = self._tint((70, 20, 110))
        flap = math.sin(self.t * 20)
        for s in (-1, 1):
            wing = [(x, y), (x + s * r * 1.9, y - r * 0.8 - flap * r * 0.9),
                    (x + s * r * 1.5, y + r * 0.1 - flap * r * 0.3),
                    (x + s * r * 1.0, y + r * 0.5), (x + s * r * 0.6, y + r * 0.2)]
            pygame.draw.polygon(surf, body, wing)
        pygame.draw.circle(surf, self._tint((100, 40, 150)), (x, y), r * 0.7)
        for s in (-1, 1):
            pygame.draw.polygon(surf, body, [(x + s * r * 0.2, y - r * 0.5),
                                             (x + s * r * 0.55, y - r * 1.1),
                                             (x + s * r * 0.65, y - r * 0.4)])
            pygame.draw.circle(surf, (255, 240, 80), (x + s * r * 0.28, y - r * 0.1), 3)

    def _draw_warlock(self, surf, x, y, r):
        robe = self._tint((70, 12, 34))
        hood = self._tint((100, 20, 45))
        sway = math.sin(self.t * 2) * 4
        pygame.draw.polygon(surf, robe, [(x - r * 0.9 + sway, y + r), (x + r * 0.9 + sway, y + r),
                                         (x + r * 0.35, y - r * 0.4), (x - r * 0.35, y - r * 0.4)])
        pygame.draw.circle(surf, hood, (x, y - r * 0.5), r * 0.55)
        pygame.draw.circle(surf, (10, 0, 10), (x, y - r * 0.45), r * 0.36)
        for s in (-1, 1):
            pygame.draw.circle(surf, (255, 60, 40), (x + s * r * 0.14, y - r * 0.47), 3)
        sx = x + r * 1.05
        pygame.draw.line(surf, (110, 80, 50), (sx, y + r), (sx, y - r * 0.9), 4)
        charge = 1.0 - max(0.0, min(1.0, self.shoot_timer / 0.8))
        draw_glow(surf, (sx, y - r), int(16 + 18 * charge), (255, 60, 60), 0.6 + 0.4 * charge)


class Orb:
    """Dark projectile fired by warlocks. Shield / fireballs / explosions destroy it."""

    def __init__(self, pos, target, speed):
        self.pos = V(pos)
        d = V(target) - self.pos
        self.vel = d.normalize() * speed if d.length() > 0 else V(0, speed)
        self.radius = 13
        self.dead = False
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        self.pos += self.vel * dt
        if not (-80 < self.pos.x < config.WIDTH + 80 and -80 < self.pos.y < config.HEIGHT + 80):
            self.dead = True

    def draw(self, surf):
        r = 12 + math.sin(self.t * 14) * 2
        draw_glow(surf, self.pos, 34, (255, 40, 90), 0.9)
        pygame.draw.circle(surf, (40, 0, 20), self.pos, r)
        draw_glow(surf, self.pos, 16, (255, 120, 160), 0.8)
