"""
spell_system.py - what each gesture DOES.

    POINT  -> Fireball        (held: keeps shooting along your finger)
    PALM   -> Shield          (held: drains mana, blocks orbs, pushes enemies)
    FIST   -> Explosion       (fires once when you close your hand)
    SWIPE  -> Chain Lightning (fast horizontal hand movement)
    PINCH  -> Telekinesis     (grab an enemy, move it, release with speed to throw it)

    COMBOS:  POINT -> FIST -> PALM   = FIRESTORM     PALM -> PINCH -> PALM = FROST NOVA
"""
import math
import random

import pygame
from pygame.math import Vector2 as V

import config
from effects import Bolt, Shockwave, draw_glow
from gesture_recognition import NONE, POINT, PALM, FIST, PINCH


class Fireball:
    def __init__(self, pos, vel, damage=config.FIREBALL_DAMAGE, homing=None, radius=15):
        self.pos = V(pos)
        self.vel = V(vel)
        self.damage = damage
        self.homing = homing
        self.radius = radius
        self.life = 3.0
        self.dead = False

    def draw(self, surf):
        draw_glow(surf, self.pos, int(self.radius * 3.4), (255, 90, 20), 0.9)
        draw_glow(surf, self.pos, int(self.radius * 1.9), (255, 190, 60), 1.0)
        pygame.draw.circle(surf, (255, 250, 210), self.pos, self.radius * 0.45)


class SpellCaster:
    SPELL_OF = {POINT: "fireball", PALM: "shield", FIST: "explosion", PINCH: "telekinesis"}

    def __init__(self, world):
        self.w = world
        self.reset()

    def reset(self):
        self.mana = config.MAX_MANA
        self.ready_at = {"fireball": 0.0, "explosion": 0.0, "lightning": 0.0}
        self.fireballs, self.bolts, self.waves = [], [], []
        self.shield_on = False
        self.shield_pos = V(0, 0)
        self.shield_r = 0.0
        self.grabbed = None
        self.prev_gesture = NONE
        self.storm_left = 0
        self.storm_timer = 0.0
        self.last_fizzle = 0.0
        self.w.sound.stop_loop("shield_loop")

    # ------------------------------------------------------------ helpers
    def cooldown_frac(self, spell, now):
        """0 = ready, 1 = just used (for the spell-book bars)."""
        total = {"fireball": config.FIREBALL_COOLDOWN, "explosion": config.EXPLOSION_COOLDOWN,
                 "lightning": config.LIGHTNING_COOLDOWN}.get(spell)
        if not total:
            return 0.0
        return max(0.0, min(1.0, (self.ready_at[spell] - now) / total))

    def _fizzle(self, now, why="NOT ENOUGH MANA"):
        if now - self.last_fizzle > 1.0:
            self.last_fizzle = now
            self.w.sound.play("fizzle")
            self.w.show_banner(why, (150, 150, 200))

    # ------------------------------------------------------------ main update
    def update(self, hand, dt, now):
        g = hand.gesture if hand.present else NONE
        if not self.shield_on:
            self.mana = min(config.MAX_MANA, self.mana + config.MANA_REGEN * dt)

        if g == POINT:
            self._fireball(hand, now)
        self._shield(hand, g, dt)
        if g == FIST and self.prev_gesture != FIST:
            self._explosion(hand, now)
        self._telekinesis(hand, g, dt)
        if hand.swipe:
            self._lightning(hand, now)
        if hand.combo:
            self._combo(hand.combo, hand, now)
        self._storm(dt)
        self._update_fireballs(dt)
        for b in self.bolts:
            b.update(dt)
        self.bolts = [b for b in self.bolts if b.life > 0]
        for s in self.waves:
            s.update(dt)
        self.waves = [s for s in self.waves if not s.done]
        self.prev_gesture = g

    # ------------------------------------------------------------ FIREBALL
    def _fireball(self, hand, now):
        if now < self.ready_at["fireball"]:
            return
        if self.mana < config.FIREBALL_COST:
            self._fizzle(now)
            return
        self.mana -= config.FIREBALL_COST
        self.ready_at["fireball"] = now + config.FIREBALL_COOLDOWN
        d = V(hand.aim)
        d = d.normalize() if d.length() > 0.1 else V(0, -1)
        self.fireballs.append(Fireball(hand.tip, d * config.FIREBALL_SPEED))
        self.w.particles.burst(hand.tip, (255, 140, 40), n=10, speed=180, life=0.35, size=14)
        self.w.sound.play("fireball")

    def _update_fireballs(self, dt):
        w = self.w
        for fb in self.fireballs:
            fb.life -= dt
            if fb.homing is not None and not fb.homing.dead:
                want = (fb.homing.pos - fb.pos)
                if want.length() > 0:
                    fb.vel = fb.vel.lerp(want.normalize() * fb.vel.length(), min(1.0, 5 * dt))
            fb.pos += fb.vel * dt
            w.particles.add(fb.pos + V(random.uniform(-5, 5), random.uniform(-5, 5)),
                            -fb.vel * 0.12 + V(random.uniform(-40, 40), random.uniform(-40, 40)),
                            0.45, (255, 110, 30), fb.radius * 1.8, 2)
            if fb.life <= 0 or not (-120 < fb.pos.x < config.WIDTH + 120 and -160 < fb.pos.y < config.HEIGHT + 120):
                fb.dead = True
                continue
            for o in w.orbs:
                if not o.dead and fb.pos.distance_to(o.pos) < fb.radius + o.radius + 6:
                    o.dead = True
                    w.particles.burst(o.pos, (255, 80, 120), 16, 220, 0.5, 14)
                    w.sound.play("block")
            for e in w.enemies:
                if not e.dead and fb.pos.distance_to(e.pos) < fb.radius + e.radius:
                    w.damage_enemy(e, fb.damage)
                    w.particles.burst(fb.pos, (255, 150, 50), 22, 320, 0.6, 16)
                    fb.dead = True
                    break
        self.fireballs = [f for f in self.fireballs if not f.dead]

    # ------------------------------------------------------------ SHIELD
    def _shield(self, hand, g, dt):
        w = self.w
        want = g == PALM and hand.present and (self.mana >= config.SHIELD_MIN_MANA or self.shield_on)
        if want and self.mana <= 0:
            want = False
        if want:
            if not self.shield_on:
                self.shield_on = True
                self.shield_r = 25.0
                w.sound.play("shield_on")
                w.sound.start_loop("shield_loop", 0.5)
                w.show_banner("SHIELD", (90, 190, 255))
            self.mana = max(0.0, self.mana - config.SHIELD_DRAIN * dt)
            target = max(95.0, min(215.0, hand.size * 1.9))
            self.shield_r += (target - self.shield_r) * min(1.0, 10 * dt)
            self.shield_pos = V(hand.palm)
            self._shield_collide(dt)
        elif self.shield_on:
            self.shield_on = False
            w.sound.stop_loop("shield_loop")
            w.particles.burst(self.shield_pos, (90, 190, 255), 24, 260, 0.5, 12)

    def _shield_collide(self, dt):
        w = self.w
        R = self.shield_r
        for o in w.orbs:
            if not o.dead and self.shield_pos.distance_to(o.pos) < R + o.radius:
                o.dead = True
                w.particles.burst(o.pos, (120, 210, 255), 22, 280, 0.5, 14)
                w.sound.play("block")
                self.mana = min(config.MAX_MANA, self.mana + 3)
        for e in w.enemies:
            if e.dead or e.grabbed:
                continue
            d = e.pos - self.shield_pos
            dist = d.length()
            if dist < R + e.radius:
                n = d.normalize() if dist > 0 else V(0, -1)
                e.pos += n * 520 * dt
                e.knock = n * 200
                if random.random() < 0.3:
                    w.particles.add(self.shield_pos + n * R, n * 120, 0.3, (120, 210, 255), 14, 2)

    def draw_shield(self, surf, t):
        if not self.shield_on:
            return
        R = int(self.shield_r)
        size = R * 2 + 40
        tmp = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (size // 2, size // 2)
        pygame.draw.circle(tmp, (70, 150, 255, 46), c, R)
        pygame.draw.circle(tmp, (140, 215, 255, 210), c, R, 4)
        pygame.draw.circle(tmp, (140, 215, 255, 90), c, int(R * 0.86), 2)
        for i in range(6):                       # rotating hexagon
            a0 = t * 1.2 + i * math.tau / 6
            a1 = t * 1.2 + (i + 1) * math.tau / 6
            r2 = R * 0.72
            pygame.draw.line(tmp, (170, 230, 255, 190),
                             (c[0] + math.cos(a0) * r2, c[1] + math.sin(a0) * r2),
                             (c[0] + math.cos(a1) * r2, c[1] + math.sin(a1) * r2), 3)
        surf.blit(tmp, (self.shield_pos.x - c[0], self.shield_pos.y - c[1]))
        draw_glow(surf, self.shield_pos, int(R * 1.25), (60, 130, 255), 0.55 + 0.1 * math.sin(t * 8))

    # ------------------------------------------------------------ EXPLOSION
    def _explosion(self, hand, now):
        w = self.w
        if now < self.ready_at["explosion"]:
            return
        if self.mana < config.EXPLOSION_COST:
            self._fizzle(now)
            return
        self.mana -= config.EXPLOSION_COST
        self.ready_at["explosion"] = now + config.EXPLOSION_COOLDOWN
        pos = V(hand.palm)
        R = config.EXPLOSION_RADIUS
        self.waves.append(Shockwave(pos, R, (255, 120, 40)))
        self.waves.append(Shockwave(pos, R * 0.6, (255, 220, 120), 0.35))
        w.particles.burst(pos, (255, 140, 40), 70, 620, 1.0, 26)
        w.particles.burst(pos, (255, 230, 150), 30, 380, 0.7, 18)
        w.sound.play("explosion")
        w.shake = max(w.shake, 16)
        w.flash = max(w.flash, 0.35)
        w.show_banner("EXPLOSION", (255, 130, 50))
        for o in w.orbs:
            if pos.distance_to(o.pos) < R:
                o.dead = True
        for e in w.enemies:
            if not e.dead and pos.distance_to(e.pos) < R + e.radius:
                n = (e.pos - pos).normalize() if e.pos != pos else V(0, -1)
                e.knock = n * 700
                w.damage_enemy(e, config.EXPLOSION_DAMAGE)

    # ------------------------------------------------------------ LIGHTNING
    def _lightning(self, hand, now):
        w = self.w
        if now < self.ready_at["lightning"]:
            return
        if self.mana < config.LIGHTNING_COST:
            self._fizzle(now)
            return
        self.mana -= config.LIGHTNING_COST
        self.ready_at["lightning"] = now + config.LIGHTNING_COOLDOWN
        origin = V(hand.palm)
        targets = sorted([e for e in w.enemies if not e.dead], key=lambda e: origin.distance_to(e.pos))
        targets = targets[:config.LIGHTNING_CHAIN]
        if targets:
            chain = [origin] + [t.pos.copy() for t in targets]
        else:
            end_x = config.WIDTH + 40 if hand.swipe == "right" else -40
            chain = [origin, V(end_x, origin.y - 50)]
        self.bolts.append(Bolt(chain))
        self.bolts.append(Bolt(chain, life=0.22, color=(200, 220, 255)))
        for t in targets:
            w.particles.burst(t.pos, (150, 190, 255), 20, 320, 0.5, 14)
            t.stun = 0.6
            w.damage_enemy(t, config.LIGHTNING_DAMAGE)
        w.sound.play("lightning")
        w.flash = max(w.flash, 0.5)
        w.shake = max(w.shake, 9)
        w.show_banner("CHAIN LIGHTNING", (140, 180, 255))

    # ------------------------------------------------------------ TELEKINESIS
    def _telekinesis(self, hand, g, dt):
        w = self.w
        if g == PINCH and hand.present:
            pp = V(hand.pinch_pos)
            if self.grabbed is None:
                cands = [e for e in w.enemies if not e.dead and e.pos.distance_to(pp) < e.radius + config.GRAB_RANGE]
                if cands:
                    e = min(cands, key=lambda e: e.pos.distance_to(pp))
                    self.grabbed = e
                    e.grabbed = True
                    e.thrown = 0
                    w.sound.play("grab")
                    w.show_banner("TELEKINESIS", (210, 130, 255))
            e = self.grabbed
            if e is not None:
                if e.dead:
                    self.grabbed = None
                else:
                    e.pos = e.pos.lerp(pp, min(1.0, 14 * dt))
                    e.knock = V(0, 0)
                    if random.random() < 0.7:
                        k = random.random()
                        w.particles.add(pp.lerp(e.pos, k) + V(random.uniform(-6, 6), random.uniform(-6, 6)),
                                        (0, 0), 0.3, (200, 120, 255), 12, 2)
                    return
        if self.grabbed is not None:
            e = self.grabbed
            self.grabbed = None
            e.grabbed = False
            v = V(hand.velocity)
            if hand.present and v.length() > config.THROW_MIN_SPEED:
                v.scale_to_length(min(v.length(), config.THROW_MAX_SPEED))
                e.thrown = 2.2
                e.throw_vel = v
                w.sound.play("throw")

    def draw_tether(self, surf, hand):
        e = self.grabbed
        if e is not None and hand.present and not e.dead:
            pp = V(hand.pinch_pos)
            pygame.draw.line(surf, (200, 130, 255), pp, e.pos, 3)
            draw_glow(surf, pp, 30, (200, 130, 255), 0.9)

    # ------------------------------------------------------------ COMBOS
    def _combo(self, name, hand, now):
        w = self.w
        w.sound.play("combo")
        if name == "FIRESTORM":
            self.storm_left = 16
            self.storm_timer = 0
            w.show_banner("COMBO: FIRESTORM!", (255, 150, 40), big=True)
            w.flash = max(w.flash, 0.3)
        elif name == "FROSTNOVA":
            w.sound.play("freeze")
            w.show_banner("COMBO: FROST NOVA!", (130, 220, 255), big=True)
            w.frost = 0.8
            self.waves.append(Shockwave(hand.palm if hand.present else config.PLAYER_POS,
                                        config.WIDTH * 0.8, (120, 210, 255), 0.9))
            for e in w.enemies:
                e.frozen_until = now + config.FROST_TIME
                w.particles.burst(e.pos, (140, 220, 255), 18, 220, 0.7, 14)
            for o in w.orbs:
                o.dead = True

    def _storm(self, dt):
        if self.storm_left <= 0:
            return
        self.storm_timer -= dt
        if self.storm_timer <= 0:
            self.storm_timer = 0.09
            self.storm_left -= 1
            alive = [e for e in self.w.enemies if not e.dead]
            x = random.uniform(80, config.WIDTH - 80)
            pos = V(x, -30)
            if alive:
                tgt = random.choice(alive)
                vel = (tgt.pos - pos).normalize() * 850
            else:
                tgt, vel = None, V(random.uniform(-100, 100), 850)
            self.fireballs.append(Fireball(pos, vel, damage=2, homing=tgt, radius=17))
            self.w.sound.play("fireball", 0.5)
