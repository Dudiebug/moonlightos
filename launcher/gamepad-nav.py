#!/usr/bin/python3
"""Translate common gamepad navigation to keys only while the launcher is active."""

from __future__ import annotations

import glob
import pathlib
import time

from evdev import InputDevice, UInput, ecodes

KEYS = [ecodes.KEY_UP, ecodes.KEY_DOWN, ecodes.KEY_LEFT, ecodes.KEY_RIGHT,
        ecodes.KEY_ENTER, ecodes.KEY_ESC]
_last_state_check = 0.0
_last_state = False


def app_active() -> bool:
    global _last_state_check, _last_state
    now = time.monotonic()
    if now - _last_state_check < 0.5:
        return _last_state
    _last_state_check = now
    _last_state = pathlib.Path("/run/moonlightos/app-active").exists()
    return _last_state


def find_gamepad() -> InputDevice | None:
    for path in glob.glob("/dev/input/event*"):
        try:
            dev = InputDevice(path)
            keys = set(dev.capabilities().get(ecodes.EV_KEY, []))
            if ecodes.BTN_GAMEPAD in keys or ecodes.BTN_SOUTH in keys:
                serial = (dev.uniq or "*").lower()
                identity = f"{dev.info.vendor:04x}:{dev.info.product:04x}:{serial}\n"
                pathlib.Path("/var/lib/moonlightos/launcher-controller.id").write_text(identity)
                return dev
        except OSError:
            continue
    return None


def emit(ui: UInput, key: int) -> None:
    ui.write(ecodes.EV_KEY, key, 1)
    ui.write(ecodes.EV_KEY, key, 0)
    ui.syn()


def run() -> None:
    ui = UInput({ecodes.EV_KEY: KEYS}, name="MoonlightOS Launcher Navigation")
    while True:
        dev = find_gamepad()
        if dev is None:
            time.sleep(2)
            continue
        try:
            for event in dev.read_loop():
                if app_active():
                    continue
                key = None
                if event.type == ecodes.EV_KEY and event.value == 1:
                    key = {ecodes.BTN_SOUTH: ecodes.KEY_ENTER,
                           ecodes.BTN_EAST: ecodes.KEY_ESC,
                           ecodes.BTN_DPAD_UP: ecodes.KEY_UP,
                           ecodes.BTN_DPAD_DOWN: ecodes.KEY_DOWN,
                           ecodes.BTN_DPAD_LEFT: ecodes.KEY_LEFT,
                           ecodes.BTN_DPAD_RIGHT: ecodes.KEY_RIGHT}.get(event.code)
                elif event.type == ecodes.EV_ABS:
                    if event.code == ecodes.ABS_HAT0X and event.value:
                        key = ecodes.KEY_RIGHT if event.value > 0 else ecodes.KEY_LEFT
                    elif event.code == ecodes.ABS_HAT0Y and event.value:
                        key = ecodes.KEY_DOWN if event.value > 0 else ecodes.KEY_UP
                if key:
                    emit(ui, key)
        except OSError:
            time.sleep(1)


if __name__ == "__main__":
    run()
