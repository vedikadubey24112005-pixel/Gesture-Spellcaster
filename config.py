"""
config.py - every tweakable number in one place.
Change values here to make the game easier / harder or to tune gesture detection.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOUND_DIR = os.path.join(BASE_DIR, "sounds")
HIGHSCORE_FILE = os.path.join(BASE_DIR, "highscore.txt")

# ---------------- window / camera ----------------
WIDTH, HEIGHT = 1280, 720
FPS = 60
CAMERA_INDEX = 0            # try 1 if you have several cameras
DETECT_WIDTH = 640          # frames are shrunk to this width before hand detection (faster)
LANDMARK_SMOOTHING = 0.65   # 1.0 = no smoothing, lower = smoother but laggier

# ---------------- gesture recognition ----------------
GESTURE_HISTORY = 5         # majority vote over the last N frames (removes flicker)
GESTURE_MIN_VOTES = 3
PINCH_RATIO = 0.30          # thumb-tip to index-tip distance / palm size to count as pinch
SWIPE_WINDOW = 0.45         # seconds in which the swipe must happen
SWIPE_DIST_FRAC = 0.16      # fraction of screen width the hand must travel (smaller = easier)
SWIPE_COOLDOWN = 0.7
COMBO_WINDOW = 3.5          # seconds allowed to finish a 3-gesture combo
HOLD_TIME = 2.0             # seconds to hold OPEN PALM on menu to start

COMBOS = {
    "FIRESTORM": ("POINT", "FIST", "PALM"),
    "FROSTNOVA": ("PALM", "PINCH", "PALM"),
}

# ---------------- gameplay ----------------
PLAYER_POS = (WIDTH // 2, HEIGHT - 70)
MAX_HEARTS = 5
MAX_MANA = 100.0
MANA_REGEN = 8.0

FIREBALL_COST = 6
FIREBALL_COOLDOWN = 0.40
FIREBALL_DAMAGE = 1
FIREBALL_SPEED = 950

SHIELD_DRAIN = 12.0         # mana per second while shield is up
SHIELD_MIN_MANA = 5

EXPLOSION_COST = 30
EXPLOSION_COOLDOWN = 2.0
EXPLOSION_RADIUS = 290
EXPLOSION_DAMAGE = 3

LIGHTNING_COST = 20
LIGHTNING_COOLDOWN = 1.0
LIGHTNING_CHAIN = 4
LIGHTNING_DAMAGE = 2

GRAB_RANGE = 95             # how close (px) your pinch must be to an enemy to grab it
THROW_MIN_SPEED = 300
THROW_MAX_SPEED = 1800

FROST_TIME = 4.0
