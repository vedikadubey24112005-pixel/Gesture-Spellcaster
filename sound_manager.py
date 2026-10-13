"""
sound_manager.py - synthesises every sound effect + background music with NumPy
the first time you run the game, saves them as .wav files in /sounds and loads them.

Want your own sounds?  Just replace any .wav in the sounds/ folder (same file name).
Delete the sounds/ folder to regenerate the originals.
"""
import os
import time
import wave

import numpy as np
import pygame

import config

SR = 22050
rng = np.random.default_rng(7)


# ----------------------------------------------------------------- tiny synth toolkit
def T(d):
    return np.arange(int(SR * d)) / SR


def noise(d):
    return rng.uniform(-1, 1, int(SR * d))


def lowpass(x, a):
    n = min(int(6 / a) + 1, 400)
    k = a * (1 - a) ** np.arange(n)
    return np.convolve(x, k)[:len(x)]


def highpass(x, a):
    return x - lowpass(x, a)


def sweep(f0, f1, d):
    f = np.linspace(f0, f1, int(SR * d))
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def decay(d, rate):
    return np.exp(-rate * T(d))


def attack(d, a):
    return np.minimum(1.0, T(d) / a)


def tone(f, d, rate=4.0, harm=(1.0, 0.35, 0.15)):
    t = T(d)
    y = sum(h * np.sin(2 * np.pi * f * (i + 1) * t) for i, h in enumerate(harm))
    return y * np.exp(-rate * t) * np.minimum(1.0, t / 0.005)


def place(buf, x, at):
    i = int(at * SR)
    end = min(len(buf), i + len(x))
    if i < len(buf):
        buf[i:end] += x[:end - i]


def echo(x, delay, fb, n=3):
    out = np.zeros(len(x) + int(SR * delay * n))
    for i in range(n + 1):
        d = int(SR * delay * i)
        out[d:d + len(x)] += x * (fb ** i)
    return out


def save(path, x, gain=0.85):
    x = np.asarray(x, dtype=np.float64)
    peak = np.abs(x).max()
    if peak > 0:
        x = x / peak * gain
    data = (x * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


# ----------------------------------------------------------------- the sounds
def s_fireball():
    d = 0.6
    whoosh = lowpass(noise(d), 0.12) * np.sin(np.pi * np.clip(T(d) / d, 0, 1)) ** 0.7
    return whoosh * 1.4 + sweep(700, 180, d) * decay(d, 5) * 0.35


def s_shield_on():
    d = 0.7
    y = sum(np.sin(2 * np.pi * f * T(d)) for f in (440, 660, 880, 1320))
    y = y * attack(d, 0.25) * decay(d, 3.5) * (1 + 0.3 * np.sin(2 * np.pi * 14 * T(d)))
    return y + sweep(300, 1400, d) * decay(d, 4) * 0.5


def s_shield_loop():
    d = 2.0  # integer number of cycles => loops seamlessly
    t = T(d)
    y = np.sin(2 * np.pi * 110 * t) + 0.6 * np.sin(2 * np.pi * 165 * t) + 0.25 * np.sin(2 * np.pi * 440 * t)
    return y * (1 + 0.25 * np.sin(2 * np.pi * 6 * t))


def s_explosion():
    d = 1.5
    boom = lowpass(noise(d), 0.05) * decay(d, 2.8) * 3
    thump = sweep(140, 28, d) * decay(d, 2.5)
    crack = noise(0.08) * decay(0.08, 40)
    y = boom + thump * 1.3
    y[:len(crack)] += crack * 0.9
    return y


def s_lightning():
    d = 1.3
    y = np.zeros(int(SR * d))
    crack = highpass(noise(0.25), 0.2) * decay(0.25, 22)
    zap = np.sign(sweep(2600, 250, 0.3)) * 0.3 * decay(0.3, 8)
    rumble = lowpass(noise(1.0), 0.03) * decay(1.0, 2.6) * 4
    place(y, crack * 1.4, 0)
    place(y, zap, 0)
    place(y, rumble, 0.08)
    return y


def s_grab():
    d = 0.3
    return sweep(280, 720, d) * np.sin(np.pi * T(d) / d) + 0.3 * sweep(560, 1440, d) * decay(d, 8)


def s_throw():
    d = 0.5
    return lowpass(noise(d), 0.2) * np.sin(np.pi * T(d) / d) * 1.3 + sweep(900, 150, d) * decay(d, 6) * 0.4


def s_hit():
    d = 0.18
    return sweep(230, 70, d) * decay(d, 16) + noise(d) * decay(d, 60) * 0.5


def s_enemy_die():
    d = 0.5
    t = T(d)
    vib = 1 + 0.05 * np.sin(2 * np.pi * 18 * t)
    return sweep(620, 90, d) * vib * decay(d, 5) + lowpass(noise(d), 0.3) * decay(d, 14) * 0.6


def s_hurt():
    d = 0.6
    t = T(d)
    saw = 2 * ((90 * t) % 1) - 1
    return np.tanh(saw * 3) * decay(d, 5) + noise(d) * decay(d, 30) * 0.4


def s_block():
    d = 0.35
    t = T(d)
    return sum(np.sin(2 * np.pi * f * t) * a for f, a in ((1250, 1), (1870, 0.6), (2730, 0.4))) * decay(d, 14)


def s_wave():
    d = 1.4
    y = np.zeros(int(SR * d))
    for i, f in enumerate((523.3, 659.3, 784.0, 1046.5)):
        place(y, tone(f, 0.7, 3.5), 0.12 * i)
    return echo(y, 0.16, 0.35, 2)


def s_gameover():
    y = np.zeros(int(SR * 3.2))
    for i, f in enumerate((440, 392, 349.2, 293.7, 220)):
        place(y, tone(f, 1.0, 2.2, (1, 0.5, 0.3)), 0.32 * i)
    return echo(y, 0.25, 0.4, 2)


def s_start():
    y = np.zeros(int(SR * 1.6))
    for i, f in enumerate((392, 494, 587, 784, 988)):
        place(y, tone(f, 0.9, 3.0), 0.09 * i)
    return echo(y, 0.2, 0.4, 2) + sweep(200, 1600, 1.0)[:int(SR * 1.0)].mean() * 0


def s_fizzle():
    d = 0.35
    return lowpass(noise(d), 0.25) * decay(d, 9) * 0.8 + sweep(400, 90, d) * decay(d, 9) * 0.4


def s_combo():
    d = 1.5
    y = sweep(200, 1500, 0.9) * attack(0.9, 0.6) * 0.5
    y = np.concatenate([y, np.zeros(int(SR * (d - 0.9)))])
    for f in (523.3, 659.3, 784.0, 1046.5):
        place(y, tone(f, 0.6, 3), 0.85)
    return echo(y, 0.15, 0.35, 2)


def s_freeze():
    d = 1.2
    t = T(d)
    y = sum(np.sin(2 * np.pi * f * t) * (1 + 0.5 * np.sin(2 * np.pi * (7 + i) * t))
            for i, f in enumerate((2093, 2637, 3136, 3951)))
    return y * decay(d, 3) * 0.3 + highpass(noise(d), 0.3) * decay(d, 5) * 0.5


def s_music():
    """24-second seamless ambient loop: slow minor pads + soft plucked arpeggio."""
    total = 24.0
    N = int(SR * total)
    buf = np.zeros(N)
    chords = [
        [110.0, 164.8, 220.0, 261.6, 329.6],   # Am
        [87.3, 130.8, 174.6, 220.0, 261.6],    # F
        [130.8, 196.0, 261.6, 329.6, 392.0],   # C
        [98.0, 146.8, 196.0, 246.9, 293.7],    # G
    ]
    seg = 8.0
    t = T(seg)
    window = np.sin(np.pi * t / seg) ** 2
    for i, ch in enumerate(chords):
        pad = np.zeros(len(t))
        for f in ch:
            for det in (-0.4, 0.4):
                pad += np.sin(2 * np.pi * (f + det) * t)
        pad *= window * 0.06
        idx = (int(i * 6.0 * SR) + np.arange(len(t))) % N
        buf[idx] += pad
    step = 0.375
    for i, ch in enumerate(chords):
        notes = [ch[1], ch[3], ch[4], ch[3], ch[2] * 2, ch[3], ch[4], ch[3]]
        for k in range(16):
            f = notes[k % len(notes)] * 2
            at = i * 6.0 + k * step
            n = tone(f, 1.2, 4.0, (1, 0.25, 0.1)) * 0.10
            idx = (int(at * SR) + np.arange(len(n))) % N
            buf[idx] += n
    buf += np.roll(buf, int(SR * step * 3)) * 0.35     # cheap echo (wraps => still loops)
    return buf


SOUND_MAKERS = {
    "fireball": s_fireball, "shield_on": s_shield_on, "shield_loop": s_shield_loop,
    "explosion": s_explosion, "lightning": s_lightning, "grab": s_grab, "throw": s_throw,
    "hit": s_hit, "enemy_die": s_enemy_die, "hurt": s_hurt, "block": s_block,
    "wave": s_wave, "gameover": s_gameover, "start": s_start, "fizzle": s_fizzle,
    "combo": s_combo, "freeze": s_freeze, "music": s_music,
}

VOLUME = {"fireball": 0.55, "shield_on": 0.5, "shield_loop": 0.5, "explosion": 0.9, "lightning": 0.85,
          "grab": 0.5, "throw": 0.5, "hit": 0.4, "enemy_die": 0.5, "hurt": 0.8, "block": 0.45,
          "wave": 0.6, "gameover": 0.7, "start": 0.6, "fizzle": 0.5, "combo": 0.7,
          "freeze": 0.6, "music": 0.32}


def generate_all(folder):
    os.makedirs(folder, exist_ok=True)
    missing = [n for n in SOUND_MAKERS if not os.path.exists(os.path.join(folder, n + ".wav"))]
    if missing:
        print(f"[sound] generating {len(missing)} sound files (first run only)...")
    for name in missing:
        save(os.path.join(folder, name + ".wav"), SOUND_MAKERS[name]())


class SoundManager:
    def __init__(self, enabled=True):
        self.enabled = False
        self.sounds = {}
        self.loops = {}
        self.last = {}
        self.music_on = True
        if not enabled:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SR, -16, 1, 512)
            generate_all(config.SOUND_DIR)
            for name in SOUND_MAKERS:
                self.sounds[name] = pygame.mixer.Sound(os.path.join(config.SOUND_DIR, name + ".wav"))
            pygame.mixer.set_num_channels(32)
            self.enabled = True
        except Exception as exc:  # no audio device etc.
            print("[sound] disabled:", exc)

    def play(self, name, vol=1.0):
        if not self.enabled:
            return
        now = time.time()
        if now - self.last.get(name, 0) < 0.05:
            return
        self.last[name] = now
        s = self.sounds[name]
        s.set_volume(min(1.0, VOLUME.get(name, 0.6) * vol))
        s.play()

    def start_loop(self, name, vol=1.0):
        if not self.enabled or name in self.loops:
            return
        s = self.sounds[name]
        s.set_volume(min(1.0, VOLUME.get(name, 0.5) * vol))
        self.loops[name] = s.play(loops=-1)

    def stop_loop(self, name):
        ch = self.loops.pop(name, None)
        if ch is not None:
            ch.stop()

    def start_music(self):
        if self.enabled and self.music_on:
            self.start_loop("music")

    def toggle_music(self):
        self.music_on = not self.music_on
        if self.music_on:
            self.start_music()
        else:
            self.stop_loop("music")
