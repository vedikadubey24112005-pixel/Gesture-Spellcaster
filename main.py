"""
GESTURE SPELLCASTER - control a magical battle with your bare hands.

Run:   python main.py
Keys:  SPACE start/restart   D debug   H hide spell book   M music on/off   F fullscreen   ESC quit
Options:
    --sim         no webcam: mouse = hand, keys 1-5 = gestures (great for testing)
    --camera N    use another webcam index
    --no-sound    disable audio
"""
import argparse
import dataclasses
import sys
import time

import pygame

import config
from game import Game, MENU, GAMEOVER
from gesture_recognition import GestureRecognizer, HandState
from sim_hand import SimHand
from sound_manager import SoundManager, SR


def parse_args():
    p = argparse.ArgumentParser(description="Gesture Spellcaster")
    p.add_argument("--sim", action="store_true", help="mouse/keyboard simulation, no webcam")
    p.add_argument("--camera", type=int, default=config.CAMERA_INDEX)
    p.add_argument("--no-sound", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    pygame.mixer.pre_init(SR, -16, 1, 512)
    pygame.init()
    pygame.display.set_caption("Gesture Spellcaster")
    screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT), pygame.SCALED | pygame.RESIZABLE)
    clock = pygame.time.Clock()

    recognizer = GestureRecognizer()
    cam = tracker = sim = None
    sim_mode = args.sim

    if not sim_mode:
        try:
            from camera import CameraStream
            from hand_tracking import HandTracker
            tracker = HandTracker()            # may download the model on first run
            cam = CameraStream(args.camera)
            if not cam.ok or not cam.wait_first_frame():
                print("[!] Could not read from the webcam (index %d). Falling back to --sim mode." % args.camera)
                print("    Close other apps using the camera, or try:  python main.py --camera 1")
                cam.stop()
                cam, sim_mode = None, True
        except ImportError as exc:
            print("[!] Missing package (%s). Run:  pip install -r requirements.txt" % exc)
            print("    Falling back to --sim mode.")
            sim_mode = True
        except Exception as exc:               # e.g. model download failed
            print("[!] Hand tracking could not start:\n    %s" % exc)
            print("    Falling back to --sim mode.")
            sim_mode = True
    if sim_mode:
        sim = SimHand(recognizer)

    sound = SoundManager(enabled=not args.no_sound)
    game = Game(sound, sim_mode)
    sound.start_music()

    if not sim_mode:
        from camera import prepare_frame

    hand = HandState()
    bg = None
    last_id = 0
    running = True
    while running:
        dt = min(clock.tick(config.FPS) / 1000.0, 0.05)
        now = time.time()
        events = pygame.event.get()
        for e in events:
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_SPACE and game.state in (MENU, GAMEOVER):
                    game.start()
                elif e.key == pygame.K_d:
                    game.debug = not game.debug
                elif e.key == pygame.K_h:
                    game.show_book = not game.show_book
                elif e.key == pygame.K_m:
                    sound.toggle_music()
                elif e.key == pygame.K_f:
                    pygame.display.toggle_fullscreen()

        if sim_mode:
            hand = sim.update(now, events)
        else:
            frame, last_id2 = cam.read(last_id)
            if frame is not None:
                last_id = last_id2
                bg, small = prepare_frame(frame)
                hand = recognizer.update(tracker.process(small), now)
            else:
                # no new camera frame: reuse last hand but clear one-shot events
                hand = dataclasses.replace(hand, swipe=None, combo=None)

        game.fps = clock.get_fps()
        game.update(hand, dt, now)
        game.draw(screen, bg, hand, now)
        pygame.display.flip()

    if cam:
        cam.stop()
    if tracker:
        tracker.close()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
