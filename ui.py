"""
ui.py - fonts, icons, HUD widgets, spell book and the hand overlay.
"""
import math

import pygame

import config
from effects import draw_glow
from gesture_recognition import POINT, PALM, FIST, PINCH, UNKNOWN, LABELS
from hand_tracking import HAND_CONNECTIONS

_fonts = {}


def font(size, bold=True):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont("segoeui,arial,helveticaneue,dejavusans,liberationsans", size, bold=bold)
    return _fonts[key]


def text(surf, txt, size, color, pos, anchor="center", bold=True, shadow=True, alpha=255):
    f = font(size, bold)
    img = f.render(txt, True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        sh = f.render(txt, True, (0, 0, 0))
        sh.set_alpha(min(alpha, 170))
        surf.blit(sh, rect.move(2, 2))
    surf.blit(img, rect)
    return rect


# name, gesture label, icon, colour, cost text
SPELLS = [
    ("FIREBALL", "POINT", "fireball", (255, 140, 50), "6 mana"),
    ("SHIELD", "OPEN PALM", "shield", (90, 190, 255), "12 / sec"),
    ("EXPLOSION", "FIST", "explosion", (255, 90, 60), "30 mana"),
    ("LIGHTNING", "SWIPE", "lightning", (150, 180, 255), "20 mana"),
    ("TELEKINESIS", "PINCH", "telekinesis", (210, 130, 255), "free"),
]
SPELL_KEYS = ["fireball", "shield", "explosion", "lightning", "telekinesis"]

GESTURE_COLORS = {POINT: (255, 150, 60), PALM: (100, 200, 255), FIST: (255, 90, 70),
                  PINCH: (210, 130, 255), UNKNOWN: (200, 200, 220)}


def icon(surf, name, c, s, color):
    x, y = c
    dark = tuple(int(v * 0.45) for v in color)
    if name == "fireball":
        pygame.draw.polygon(surf, color, [(x - .38 * s, y), (x + .38 * s, y), (x + .05 * s, y - .85 * s)])
        pygame.draw.circle(surf, color, (x, y + .12 * s), .44 * s)
        pygame.draw.circle(surf, (255, 235, 170), (x, y + .18 * s), .2 * s)
    elif name == "shield":
        pts = [(x - .6 * s, y - .6 * s), (x + .6 * s, y - .6 * s), (x + .6 * s, y + .05 * s),
               (x, y + .78 * s), (x - .6 * s, y + .05 * s)]
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, dark, pts, 3)
        pygame.draw.line(surf, dark, (x, y - .5 * s), (x, y + .6 * s), 3)
    elif name == "explosion":
        pts = []
        for i in range(16):
            r = .85 * s if i % 2 == 0 else .42 * s
            a = i * math.tau / 16
            pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.circle(surf, (255, 240, 190), (x, y), .22 * s)
    elif name == "lightning":
        pts = [(x + .15 * s, y - .85 * s), (x - .5 * s, y + .12 * s), (x - .05 * s, y + .12 * s),
               (x - .25 * s, y + .85 * s), (x + .55 * s, y - .18 * s), (x + .08 * s, y - .18 * s)]
        pygame.draw.polygon(surf, color, pts)
    elif name == "telekinesis":
        pygame.draw.circle(surf, color, (x, y), .3 * s)
        pygame.draw.circle(surf, color, (x, y), .72 * s, 3)
        pygame.draw.line(surf, color, (x - .95 * s, y - .5 * s), (x - .55 * s, y - .25 * s), 3)
        pygame.draw.line(surf, color, (x + .95 * s, y - .5 * s), (x + .55 * s, y - .25 * s), 3)


def heart(surf, c, s, color):
    x, y = c
    pygame.draw.circle(surf, color, (x - s * .25, y - s * .15), s * .3)
    pygame.draw.circle(surf, color, (x + s * .25, y - s * .15), s * .3)
    pygame.draw.polygon(surf, color, [(x - s * .53, y - s * .02), (x + s * .53, y - s * .02), (x, y + s * .58)])


def draw_hearts(surf, hearts):
    for i in range(config.MAX_HEARTS):
        col = (235, 50, 80) if i < hearts else (70, 30, 45)
        heart(surf, (44 + i * 44, 44), 34, col)


def draw_mana(surf, mana, shield_on, t):
    x, y, w, h = 24, 76, 240, 20
    pygame.draw.rect(surf, (15, 20, 50), (x, y, w, h), border_radius=10)
    fill = int(w * max(0.0, mana) / config.MAX_MANA)
    if fill > 4:
        col = (70, 140, 255) if mana > 25 else (255, 110, 90)
        pygame.draw.rect(surf, col, (x, y, fill, h), border_radius=10)
        pygame.draw.rect(surf, (200, 230, 255), (x + 4, y + 3, max(0, fill - 8), 5), border_radius=3)
    pygame.draw.rect(surf, (140, 170, 255), (x, y, w, h), 2, border_radius=10)
    text(surf, "MANA", 15, (200, 220, 255), (x + w + 10, y + h // 2), anchor="midleft")


def draw_spellbook(surf, active_key, caster, now):
    x, y, w, row = config.WIDTH - 292, 96, 272, 66
    panel = pygame.Surface((w, 48 + row * len(SPELLS) + 12), pygame.SRCALPHA)
    pygame.draw.rect(panel, (10, 8, 30, 175), panel.get_rect(), border_radius=14)
    pygame.draw.rect(panel, (150, 120, 255, 200), panel.get_rect(), 2, border_radius=14)
    surf.blit(panel, (x, y))
    text(surf, "SPELL BOOK", 22, (230, 210, 255), (x + w // 2, y + 24))
    for i, (name, gest, ic, col, cost) in enumerate(SPELLS):
        ry = y + 48 + i * row
        key = SPELL_KEYS[i]
        active = key == active_key
        if active:
            hl = pygame.Surface((w - 16, row - 8), pygame.SRCALPHA)
            pygame.draw.rect(hl, (*col, 70), hl.get_rect(), border_radius=10)
            pygame.draw.rect(hl, (*col, 230), hl.get_rect(), 2, border_radius=10)
            surf.blit(hl, (x + 8, ry))
        icon(surf, ic, (x + 40, ry + 27), 17, col if active else tuple(int(v * .7) for v in col))
        text(surf, name, 20, (255, 255, 255) if active else (200, 200, 225), (x + 74, ry + 16), anchor="midleft")
        text(surf, f"{gest}  -  {cost}", 15, col, (x + 74, ry + 40), anchor="midleft", bold=False)
        cd = caster.cooldown_frac(key, now)
        if cd > 0:
            pygame.draw.rect(surf, col, (x + 14, ry + row - 12, int((w - 28) * (1 - cd)), 4), border_radius=2)


def draw_hand(surf, hand, t, label=True):
    if not hand.present:
        return
    col = GESTURE_COLORS.get(hand.gesture, (200, 200, 220))
    if hand.landmarks:
        lm = hand.landmarks
        for a, b in HAND_CONNECTIONS:
            pygame.draw.line(surf, tuple(int(v * .55) for v in col), lm[a], lm[b], 6)
            pygame.draw.line(surf, col, lm[a], lm[b], 2)
        for i, p in enumerate(lm):
            r = 6 if i in (4, 8, 12, 16, 20) else 3
            pygame.draw.circle(surf, (255, 255, 255), p, r)
        for i in (4, 8, 12, 16, 20):
            draw_glow(surf, lm[i], 26, col, 0.7)
    else:  # mouse simulation cursor
        draw_glow(surf, hand.palm, 60, col, 0.9)
        pygame.draw.circle(surf, (255, 255, 255), hand.palm, 8, 2)
    draw_glow(surf, hand.palm, int(hand.size * 1.1), col, 0.28 + 0.06 * math.sin(t * 6))
    if label:
        name = LABELS.get(hand.gesture, "")
        px, py = hand.palm
        text(surf, name, 22, col, (px, py + hand.size * 1.25))
        if hand.swipe_progress > 0.3:      # swipe meter: fills as your hand sweeps sideways
            bx, by, bw = px - 50, py + hand.size * 1.25 + 24, 100
            pygame.draw.rect(surf, (20, 20, 50), (bx, by, bw, 8), border_radius=4)
            pygame.draw.rect(surf, (150, 190, 255), (bx, by, int(bw * hand.swipe_progress), 8), border_radius=4)
