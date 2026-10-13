"""
game.py - the world: enemies, waves, score, HUD, menu / game-over screens and all drawing.
"""
import math
import os
import random

import numpy as np
import pygame
from pygame.math import Vector2 as V

import config
import ui
from effects import ParticleSystem, draw_glow
from enemies import Enemy, Orb
from gesture_recognition import PALM, LABELS
from spell_system import SpellCaster

MENU, PLAYING, GAMEOVER = "MENU", "PLAYING", "GAMEOVER"
W, H = config.WIDTH, config.HEIGHT
PLAYER = V(config.PLAYER_POS)


def make_vignette():
    ys, xs = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xs - W / 2) / (W / 2)) ** 2 + ((ys - H / 2) / (H / 2)) ** 2)
    v = np.clip(1.15 - 0.55 * d ** 1.6, 0.25, 1.0)
    arr = (np.stack([v, v, v], axis=2) * 255).astype(np.uint8)
    surf = pygame.Surface((W, H))
    pygame.surfarray.blit_array(surf, arr.swapaxes(0, 1))
    return surf


def make_night_bg():
    ys = np.linspace(0, 1, H)[:, None]
    r = (12 + 30 * ys) * np.ones((1, W))
    g = (8 + 14 * ys) * np.ones((1, W))
    b = (34 + 50 * ys) * np.ones((1, W))
    arr = np.stack([r, g, b], axis=2).astype(np.uint8)
    surf = pygame.Surface((W, H))
    pygame.surfarray.blit_array(surf, arr.swapaxes(0, 1))
    rnd = random.Random(3)
    for _ in range(140):
        c = rnd.randint(90, 220)
        pygame.draw.circle(surf, (c, c, min(255, c + 30)), (rnd.randint(0, W), rnd.randint(0, H)), rnd.choice((1, 1, 2)))
    return surf


class Game:
    def __init__(self, sound, sim_mode=False):
        self.sound = sound
        self.sim_mode = sim_mode
        self.canvas = pygame.Surface((W, H))
        self.vignette = make_vignette()
        self.night = make_night_bg()
        self.particles = ParticleSystem()
        self.enemies, self.orbs = [], []
        self.caster = SpellCaster(self)
        self.motes = [[random.uniform(0, W), random.uniform(0, H), random.uniform(6, 22),
                       random.uniform(0, 6.28), random.uniform(6, 14)] for _ in range(45)]
        self.floaters = []
        self.banner = None
        self.shake = self.flash = self.hurt = self.frost = 0.0
        self.hold = 0.0
        self.time = 0.0
        self.state = MENU
        self.over_time = 0.0
        self.show_book = True
        self.debug = False
        self.fps = 0.0
        self.hand = None
        self.highscore = self._load_high()
        self.reset()

    # ------------------------------------------------------------ persistence
    def _load_high(self):
        try:
            with open(config.HIGHSCORE_FILE) as f:
                return int(f.read().strip())
        except Exception:
            return 0

    def _save_high(self):
        try:
            with open(config.HIGHSCORE_FILE, "w") as f:
                f.write(str(self.highscore))
        except Exception:
            pass

    # ------------------------------------------------------------ state
    def reset(self):
        self.hearts = config.MAX_HEARTS
        self.score = 0
        self.wave = 1
        self.wave_kills = 0
        self.enemies.clear()
        self.orbs.clear()
        self.spawn_timer = 1.5
        self.caster.reset()

    def start(self):
        self.reset()
        self.state = PLAYING
        self.hold = 0.0
        self.sound.play("start")
        self.sound.start_music()
        self.show_banner("WAVE 1", (255, 230, 140), big=True)

    def game_over(self):
        self.state = GAMEOVER
        self.over_time = 0.0
        self.hold = 0.0
        self.sound.stop_loop("shield_loop")
        self.sound.play("gameover")
        for e in self.enemies:
            self.particles.burst(e.pos, e.color, 20, 300, 0.8, 16)
        self.enemies.clear()
        self.orbs.clear()
        if self.score > self.highscore:
            self.highscore = self.score
            self._save_high()

    def show_banner(self, txt, color, big=False):
        self.banner = {"text": txt, "color": color, "t": 0.0, "big": big}

    # ------------------------------------------------------------ world helpers
    def spawn_enemy(self):
        wv = self.wave
        choices, weights = ["ghost", "bat"], [5, 3]
        if wv >= 2:
            choices.append("warlock")
            weights.append(2 + min(3, wv // 2))
        kind = random.choices(choices, weights)[0]
        x = random.uniform(70, W - 70)
        self.enemies.append(Enemy(kind, (x, -50), wv))

    def spawn_orb(self, pos, target):
        self.orbs.append(Orb(pos, target, 250 + 12 * self.wave))

    def damage_enemy(self, e, dmg):
        if e.dead:
            return
        e.hp -= dmg
        e.hit_flash = 0.12
        if e.hp <= 0:
            self.kill(e)
        else:
            self.sound.play("hit")

    def kill(self, e):
        e.dead = True
        self.score += e.points
        self.wave_kills += 1
        self.particles.burst(e.pos, e.color, 34, 380, 0.9, 20)
        self.particles.burst(e.pos, (255, 255, 255), 10, 220, 0.4, 12)
        self.floaters.append([f"+{e.points}", V(e.pos), 1.0])
        self.sound.play("enemy_die")

    def hurt_player(self):
        self.hearts -= 1
        self.hurt = 0.6
        self.shake = max(self.shake, 14)
        self.sound.play("hurt")
        self.particles.burst(PLAYER, (255, 60, 80), 40, 420, 0.8, 18)
        if self.hearts <= 0:
            self.game_over()

    def _thrown_collisions(self):
        for e in self.enemies:
            if e.dead or e.thrown <= 0 or e.hit_cd > 0:
                continue
            for o in self.enemies:
                if o is e or o.dead:
                    continue
                if e.pos.distance_to(o.pos) < e.radius + o.radius:
                    n = (e.pos - o.pos)
                    n = n.normalize() if n.length() > 0 else V(0, -1)
                    e.throw_vel = e.throw_vel.reflect(n) * 0.8
                    o.knock = -n * 500
                    e.hit_cd = 0.3
                    self.particles.burst((e.pos + o.pos) / 2, (255, 230, 120), 20, 320, 0.5, 16)
                    self.sound.play("hit")
                    self.shake = max(self.shake, 6)
                    self.damage_enemy(o, 2)
                    self.damage_enemy(e, 1)
                    self.floaters.append(["CRASH!", V(o.pos), 0.8])
                    break
            for orb in self.orbs:
                if e.pos.distance_to(orb.pos) < e.radius + orb.radius:
                    orb.dead = True

    # ------------------------------------------------------------ update
    def update(self, hand, dt, now):
        self.time += dt
        self.hand = hand
        self.particles.update(dt)
        self.shake = max(0.0, self.shake - 40 * dt)
        self.flash = max(0.0, self.flash - 2.5 * dt)
        self.hurt = max(0.0, self.hurt - 1.4 * dt)
        self.frost = max(0.0, self.frost - 0.5 * dt)
        for m in self.motes:
            m[1] -= m[4] * dt
            m[0] += math.sin(self.time + m[3]) * 10 * dt
            if m[1] < -10:
                m[0], m[1] = random.uniform(0, W), H + 10
        for f in self.floaters:
            f[1].y -= 50 * dt
            f[2] -= dt
        self.floaters = [f for f in self.floaters if f[2] > 0]
        if self.banner:
            self.banner["t"] += dt
            if self.banner["t"] > 1.6:
                self.banner = None

        if self.state == PLAYING:
            self._update_play(hand, dt, now)
        else:
            self.caster.update(hand, dt, now)        # practice mode on menu / game-over
            self.over_time += dt
            ready = self.state == MENU or self.over_time > 1.5
            if ready and hand.present and hand.gesture == PALM:
                self.hold = min(config.HOLD_TIME, self.hold + dt)
            else:
                self.hold = max(0.0, self.hold - 2 * dt)
            if self.hold >= config.HOLD_TIME:
                self.start()

    def _update_play(self, hand, dt, now):
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_enemy()
            self.spawn_timer = max(0.6, 2.4 - 0.18 * self.wave) * random.uniform(0.7, 1.3)

        self.caster.update(hand, dt, now)
        for e in self.enemies:
            e.update(dt, now, PLAYER, self)
        self._thrown_collisions()
        for o in self.orbs:
            o.update(dt)
            if not o.dead and o.pos.distance_to(PLAYER) < 40:
                o.dead = True
                self.hurt_player()
        for e in self.enemies:
            if not e.dead and not e.grabbed and e.thrown <= 0 and e.pos.distance_to(PLAYER) < e.radius + 34:
                e.dead = True
                self.particles.burst(e.pos, e.color, 25, 300, 0.7, 16)
                self.hurt_player()
        if self.state != PLAYING:
            return
        self.enemies = [e for e in self.enemies if not e.dead]
        self.orbs = [o for o in self.orbs if not o.dead]

        need = 6 + 3 * self.wave
        if self.wave_kills >= need:
            self.wave += 1
            self.wave_kills = 0
            self.hearts = min(config.MAX_HEARTS, self.hearts + 1)
            self.caster.mana = min(config.MAX_MANA, self.caster.mana + 30)
            self.sound.play("wave")
            self.show_banner(f"WAVE {self.wave}", (255, 230, 140), big=True)

    # ------------------------------------------------------------ drawing
    def draw(self, screen, bg_rgb, hand, now):
        c = self.canvas
        t = self.time
        # 1. background
        if bg_rgb is not None:
            frame = pygame.image.frombuffer(bg_rgb, (W, H), "RGB")
            c.blit(frame, (0, 0))
            c.fill((150, 140, 185), special_flags=pygame.BLEND_RGB_MULT)   # dim + purple tint
            c.blit(self.vignette, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        else:
            c.blit(self.night, (0, 0))
        for m in self.motes:
            draw_glow(c, (m[0], m[1]), int(m[2]), (110, 90, 220), 0.5)

        self._draw_player(c, t)
        for e in sorted(self.enemies, key=lambda e: e.pos.y):
            e.draw(c, now)
        for o in self.orbs:
            o.draw(c)
        self.caster.draw_shield(c, t)
        for fb in self.caster.fireballs:
            fb.draw(c)
        for b in self.caster.bolts:
            b.draw(c)
        for s in self.caster.waves:
            s.draw(c)
        self.particles.draw(c)
        self.caster.draw_tether(c, hand)
        ui.draw_hand(c, hand, t)

        # HUD
        ui.draw_hearts(c, self.hearts)
        ui.draw_mana(c, self.caster.mana, self.caster.shield_on, t)
        ui.text(c, f"SCORE  {self.score}", 30, (255, 240, 200), (W // 2, 34))
        ui.text(c, f"WAVE {self.wave}   BEST {self.highscore}", 18, (200, 200, 235), (W // 2, 66), bold=False)
        if self.show_book:
            active = self.caster.SPELL_OF.get(hand.gesture) if hand.present else None
            if self.caster.bolts:
                active = "lightning"
            ui.draw_spellbook(c, active, self.caster, now)
        for txt, pos, life in self.floaters:
            ui.text(c, txt, 26, (255, 230, 120), pos, alpha=int(255 * min(1, life * 1.5)))
        self._draw_banner(c)
        if self.state == MENU:
            self._draw_menu(c, hand)
        elif self.state == GAMEOVER:
            self._draw_gameover(c, hand)
        if self.debug:
            self._draw_debug(c, hand)

        # screen effects
        if self.flash > 0:
            v = int(255 * min(1, self.flash))
            c.fill((v, v, v), special_flags=pygame.BLEND_RGB_ADD)
        if self.hurt > 0:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.rect(ov, (255, 0, 30, int(150 * self.hurt)), (0, 0, W, H), 60)
            c.blit(ov, (0, 0))
        if self.frost > 0:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.rect(ov, (120, 210, 255, int(120 * min(1, self.frost))), (0, 0, W, H), 70)
            c.blit(ov, (0, 0))

        sx = random.uniform(-self.shake, self.shake) if self.shake > 0.5 else 0
        sy = random.uniform(-self.shake, self.shake) if self.shake > 0.5 else 0
        screen.fill((0, 0, 0))
        screen.blit(c, (sx, sy))

    def _draw_player(self, c, t):
        x, y = PLAYER
        draw_glow(c, (x, y), 110, (110, 70, 255), 0.55 + 0.1 * math.sin(t * 3))
        for r, sp, col in ((52, 0.6, (170, 130, 255)), (36, -0.9, (120, 190, 255))):
            pygame.draw.circle(c, col, (x, y), r, 2)
            for i in range(5):
                a = t * sp + i * math.tau / 5
                b = t * sp + (i + 2) * math.tau / 5
                pygame.draw.line(c, col, (x + math.cos(a) * r, y + math.sin(a) * r),
                                 (x + math.cos(b) * r, y + math.sin(b) * r), 2)
        draw_glow(c, (x, y), 30, (220, 200, 255), 0.9)

    def _draw_banner(self, c):
        b = self.banner
        if not b:
            return
        t = b["t"]
        alpha = int(255 * max(0.0, min(1.0, (1.6 - t) / 0.5, t / 0.08)))
        scale = 1.0 + max(0.0, 0.25 - t) * 1.5
        size = int((70 if b["big"] else 48) * scale)
        pos = (W // 2, 170 if not b["big"] else 200)
        draw_glow(c, pos, 150 if b["big"] else 110, b["color"], alpha / 255 * 0.5)
        ui.text(c, b["text"], size, b["color"], pos, alpha=alpha)

    def _draw_menu(self, c, hand):
        ov = pygame.Surface((W, 250), pygame.SRCALPHA)
        ov.fill((5, 3, 25, 150))
        c.blit(ov, (0, 110))
        draw_glow(c, (W // 2, 190), 260, (120, 80, 255), 0.5)
        ui.text(c, "GESTURE SPELLCASTER", 74, (255, 235, 170), (W // 2, 190))
        ui.text(c, "Your hands are the wand.", 24, (200, 190, 255), (W // 2, 248), bold=False)
        if self.sim_mode:
            msg = "SIM MODE: mouse = hand.  Hold key 2 (open palm) for 2s, or press SPACE"
        elif not hand.present:
            msg = "Show your hand to the camera"
        else:
            msg = "Hold your OPEN PALM for 2 seconds to begin  (or press SPACE)"
        ui.text(c, msg, 26, (255, 255, 255), (W // 2, 306))
        ui.text(c, "Practice the spells below first!  Enemies come from above - protect the rune.",
                20, (180, 180, 220), (W // 2, 340), bold=False)
        self._draw_hold_ring(c, hand)

    def _draw_gameover(self, c, hand):
        ov = pygame.Surface((W, 260), pygame.SRCALPHA)
        ov.fill((30, 0, 10, 170))
        c.blit(ov, (0, 110))
        ui.text(c, "YOUR RUNE HAS FALLEN", 64, (255, 90, 110), (W // 2, 180))
        ui.text(c, f"Score {self.score}     Best {self.highscore}", 34, (255, 240, 200), (W // 2, 250))
        ui.text(c, "Hold OPEN PALM for 2 seconds (or press SPACE) to play again", 24, (255, 255, 255), (W // 2, 310))
        self._draw_hold_ring(c, hand)

    def _draw_hold_ring(self, c, hand):
        if self.hold <= 0.02:
            return
        frac = self.hold / config.HOLD_TIME
        cx, cy = (hand.palm if hand.present else (W // 2, H // 2))
        rect = pygame.Rect(0, 0, 130, 130)
        rect.center = (cx, cy)
        pygame.draw.arc(c, (255, 230, 140), rect, math.pi / 2, math.pi / 2 + math.tau * frac, 8)

    def _draw_debug(self, c, hand):
        lines = [f"FPS {self.fps:4.0f}", f"raw: {hand.raw_gesture}   stable: {hand.gesture}   swipe: {hand.swipe_progress*100:3.0f}%",
                 f"mana {self.caster.mana:5.1f}   enemies {len(self.enemies)}   orbs {len(self.orbs)}"]
        if hand.fingers:
            lines.append("fingers: " + " ".join(k[0].upper() if v else k[0] for k, v in hand.fingers.items()))
        for i, l in enumerate(lines):
            ui.text(c, l, 18, (120, 255, 160), (20, H - 110 + i * 22), anchor="midleft", bold=False)
