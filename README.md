# 🪄 Gesture Spellcaster

Control a magical battle with your **bare hands** through a webcam.
Computer vision (MediaPipe) finds 21 landmarks on your hand → geometry + motion tracking recognise
gestures → gestures cast spells against waves of ghosts, bats and warlocks.

No image or sound files to download: **all graphics are drawn in code and all sound effects + music
are synthesised with NumPy** on first run (saved into `sounds/`).

---

## ✅ Step-by-step setup (beginner friendly)

### 1. Install Python
Any of **Python 3.10, 3.11, 3.12 or 3.13** works (python.org).
On Windows tick **"Add Python to PATH"** in the installer.

### 2. Open a terminal inside this folder
Windows: open the folder → click the address bar → type `cmd` → Enter.
Mac/Linux: open Terminal and `cd` into `GestureSpellcaster`.

### 3. (Recommended) create a virtual environment
```
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac / Linux
```

### 4. Install the libraries
```
pip install -r requirements.txt
```

### 5. Run it
```
python main.py
```
Allow camera access if asked. **Hold your open palm up for 2 seconds** to start (or press SPACE).

> **Python 3.13 note:** the first time you run, the game downloads a small hand-detection model
> (`hand_landmarker.task`, ~7 MB) into this folder, so you need internet once.
> If the download fails, the game tells you the link – save the file into the project folder with that exact name.

> No webcam, or want to test first?  `python main.py --sim`
> (mouse = your hand, keys 1-5 = gestures, see below)

---

## 🎮 How to play

Stand/sit about an arm's length from the camera, with **good front lighting** and your hand clearly visible.
Enemies fall from the top and try to reach the rune at the bottom. Each one that touches it costs a heart.

| Gesture | Spell | What it does |
|---|---|---|
| ☝️ **Point** (index only) | 🔥 Fireball | Shoots along your finger. Hold to keep firing. 6 mana |
| ✋ **Open palm** (hold) | 🛡️ Shield | Bubble at your palm; blocks warlock orbs and shoves enemies away. Drains mana while up |
| ✊ **Fist** | 💥 Explosion | Shockwave at your hand – heavy damage in a big radius. 30 mana |
| 👉 **Swipe** (open hand, fast left/right) | ⚡ Chain Lightning | Jumps between the 4 nearest enemies and stuns them. 20 mana |
| 🤏 **Pinch** | 🔮 Telekinesis | Pinch near an enemy to grab it, move it, **release while moving fast to throw it** into others |

### ⭐ Combos (temporal gesture sequences – finish within 3.5 s)
| Sequence | Combo |
|---|---|
| ☝️ → ✊ → ✋ | 🔥 **FIRESTORM** – 16 homing fireballs rain from the sky |
| ✋ → 🤏 → ✋ | ❄️ **FROST NOVA** – freezes every enemy for 4 s and clears all orbs |

Other rules: mana regenerates (not while shield is up). Each cleared wave heals 1 heart and refills some mana.
Warlocks (from wave 2) shoot orbs – block them with the shield or shoot them down.
Menu and game-over screens are a **practice mode** – try every spell before you start.

### Keyboard
`SPACE` start/restart · `D` debug overlay (shows raw vs stable gesture, finger states, FPS) ·
`H` hide spell book · `M` music on/off · `F` fullscreen · `ESC` quit

### Simulation mode (`--sim`)
Mouse = hand · hold `1` point · hold `2` open palm · hold `3` fist · hold `5` pinch · tap `4` swipe.

---

## 📁 Project structure

```
GestureSpellcaster/
├── main.py                 entry point, main loop, keyboard
├── config.py               ALL tweakable numbers (difficulty, thresholds, mana costs)
├── camera.py               threaded webcam capture, crop/mirror/resize
├── hand_tracking.py        MediaPipe wrapper (old + new API) -> 21 smoothed landmarks
├── gesture_recognition.py  landmarks -> POINT / PALM / FIST / PINCH, swipe, combos
├── sim_hand.py             mouse/keyboard fake hand (no webcam needed)
├── spell_system.py         what each gesture does (fireball, shield, ...)
├── enemies.py              ghost, bat, warlock + orbs (drawn with shapes)
├── effects.py              additive-glow particles, lightning, shockwaves
├── ui.py                   spell book, hearts, mana bar, hand skeleton overlay
├── game.py                 waves, score, menu/game-over, rendering
├── sound_manager.py        NumPy sound synthesiser + audio playback
├── requirements.txt
└── sounds/                 (auto-created) .wav files – replace any with your own!
```

---

## 🧠 How it works (great for your viva)

```
WEBCAM ─► frame ─► crop 16:9 + mirror ─► resize ─► MediaPipe Hands ─► 21 landmarks
      ─► smoothing ─► finger-state geometry ─► majority vote (5 frames) ─► stable gesture
      ─► motion history ─► swipe / combo ─► spell system ─► game + effects ─► screen
```

**Image processing concepts**
1. *Image acquisition* – OpenCV reads webcam frames (in a separate thread so the game never waits).
2. *Pre-processing* – centre crop to 16:9, horizontal flip (mirror), resize to 640×360 for faster detection, BGR→RGB colour conversion.
3. *Hand detection & landmark extraction* – MediaPipe's palm detector + landmark CNN give 21 keypoints.
4. *Geometric analysis* – a finger is **extended** when tip-to-wrist distance > joint-to-wrist distance × 1.12
   (distance-based, so it works at any hand rotation); **pinch** = thumb-tip↔index-tip distance / palm size < 0.30;
   pointing direction = knuckle→fingertip vector.
5. *Temporal smoothing* – exponential smoothing of landmarks + majority vote over 5 frames removes flicker;
   pinch has hysteresis (harder to enter than to stay in) so grabs don't drop.

**Video processing concepts**
6. *Motion tracking* – palm centre tracked every frame; velocity in px/s is used to **throw** grabbed enemies.
7. *Gesture-sequence recognition* – swipe = ≥22 % of screen width travelled, mostly horizontal, within 0.35 s;
   combos = a specific ordered gesture sequence within 3.5 s (a tiny state machine).
8. *Real-time processing* – camera thread + 60 FPS render loop, detection only on new frames.

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| "Could not read from the webcam" | Close Zoom/Teams/browser tabs using the camera, or run `python main.py --camera 1` |
| Gestures flicker / misdetected | Better lighting, plain background, hand ~50–80 cm from camera, palm facing camera. Press `D` to see what is detected |
| Swipe fires too easily / never fires | Edit `SWIPE_DIST_FRAC` in `config.py` (smaller = easier, default 0.16). Watch the **swipe meter** under your hand – it fills as you sweep sideways. Lightning also needs 20 mana, so don't hold the shield right before |
| Pinch hard to hold | Increase `PINCH_RATIO` slightly (e.g. 0.35) |
| Game too hard/easy | Change `MAX_HEARTS`, `MANA_REGEN`, spell costs in `config.py` |
| Low FPS | In `hand_tracking.py` set `model_complexity=0` (only on Python ≤3.12) or lower `DETECT_WIDTH` in `config.py` to 480 |
| `pip install` fails | Upgrade pip first: `python -m pip install --upgrade pip`, then retry |
| "Could not download the hand model" | Download the link shown in the message, save it as `hand_landmarker.task` in the project folder |
| No sound | Check speakers; run without audio using `--no-sound`. Delete `sounds/` to regenerate |
| Old error `mediapipe has no attribute solutions` | Fixed – the game now supports both MediaPipe APIs. Just re-run `pip install -r requirements.txt` |

## 💡 Ideas to extend it
* Two-hand support (`max_num_hands=2`) – one hand shields, the other attacks
* Boss enemy at wave 10
* Circle-drawing gesture for a heal spell (track fingertip path)
* Record a demo video with your screen recorder for the presentation
