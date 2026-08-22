#!/usr/bin/python3
"""Request a return to the launcher after three fast Escape key taps."""

from __future__ import annotations

import glob
import pathlib
import select
import time

from evdev import InputDevice, ecodes


RUN = pathlib.Path("/run/moonlightos")
ACTIVE = RUN / "app-active"
STOP_REQUEST = RUN / "stop-active-app"
TRIPLE_TAP_WINDOW = 0.85
RESCAN_SECONDS = 2.0
IGNORED_DEVICE_NAMES = {"MoonlightOS Launcher Navigation"}


class TripleTapDetector:
    def __init__(self, window: float = TRIPLE_TAP_WINDOW) -> None:
        self.window = window
        self.presses: list[float] = []

    def reset(self) -> None:
        self.presses.clear()

    def press(self, now: float) -> bool:
        self.presses = [stamp for stamp in self.presses if now - stamp <= self.window]
        self.presses.append(now)
        if len(self.presses) < 3:
            return False
        self.reset()
        return True


def app_active() -> bool:
    try:
        if ACTIVE.is_symlink() or ACTIVE.stat().st_size > 64:
            return False
        return ACTIVE.read_text(encoding="utf-8", errors="replace").strip() in {
            "moonlight",
            "chiaki-ng",
            "firefox",
        }
    except OSError:
        return False


def is_escape_keyboard(device: InputDevice) -> bool:
    if (device.name or "") in IGNORED_DEVICE_NAMES:
        return False
    try:
        keys = set(device.capabilities().get(ecodes.EV_KEY, []))
    except OSError:
        return False
    return ecodes.KEY_ESC in keys


def open_keyboards() -> dict[int, InputDevice]:
    devices: dict[int, InputDevice] = {}
    for path in glob.glob("/dev/input/event*"):
        try:
            device = InputDevice(path)
            if not is_escape_keyboard(device):
                device.close()
                continue
            devices[device.fd] = device
        except OSError:
            continue
    return devices


def close_devices(devices: dict[int, InputDevice]) -> None:
    for device in devices.values():
        try:
            device.close()
        except OSError:
            pass


def request_stop() -> None:
    RUN.mkdir(mode=0o750, parents=True, exist_ok=True)
    STOP_REQUEST.touch()


def run() -> None:
    detector = TripleTapDetector()
    devices: dict[int, InputDevice] = {}
    next_scan = 0.0

    while True:
        now = time.monotonic()
        if now >= next_scan:
            close_devices(devices)
            devices = open_keyboards()
            next_scan = now + RESCAN_SECONDS

        if not app_active():
            detector.reset()

        if not devices:
            time.sleep(0.25)
            continue

        try:
            readable, _writable, _errors = select.select(
                list(devices.values()), [], [], 0.25
            )
        except (OSError, ValueError):
            close_devices(devices)
            devices = {}
            next_scan = 0.0
            continue

        for device in readable:
            try:
                events = device.read()
            except OSError:
                next_scan = 0.0
                continue
            for event in events:
                if (
                    event.type == ecodes.EV_KEY
                    and event.code == ecodes.KEY_ESC
                    and event.value == 1
                    and app_active()
                    and detector.press(time.monotonic())
                ):
                    request_stop()


if __name__ == "__main__":
    run()
