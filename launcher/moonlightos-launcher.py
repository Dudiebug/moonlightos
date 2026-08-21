#!/usr/bin/python3
"""Full-screen terminal launcher for the MoonlightOS appliance."""

from __future__ import annotations

import curses
import os
import pathlib
import subprocess
import time


RUN = pathlib.Path("/run/moonlightos")
MENU = (
    ("MOONLIGHT", "moonlight"),
    ("CHIAKI-NG", "chiaki"),
    ("TAILSCALE", "tailscale"),
    ("SETTINGS", "settings"),
    ("REBOOT", "reboot"),
    ("SHUTDOWN", "poweroff"),
)
GAP_BEFORE = {3, 4}


def get_ipv4(output: str) -> str:
    for line in output.splitlines():
        fields = line.split()
        if "inet" in fields:
            value = fields[fields.index("inet") + 1]
            return value.split("/", 1)[0]
    return "NO IPV4"


def network_summary() -> str:
    result = subprocess.run(
        ["ip", "-brief", "-4", "address", "show", "up"],
        text=True,
        capture_output=True,
        check=False,
    )
    address = get_ipv4(result.stdout)
    state = "ONLINE" if address != "NO IPV4" else "OFFLINE"
    return f"{address}  {state}"


def add_centered(screen: curses.window, row: int, text: str) -> None:
    height, width = screen.getmaxyx()
    if not 0 <= row < height or width < 2:
        return
    clipped = text[: max(0, width - 4)]
    column = max(1, (width - len(clipped)) // 2)
    try:
        screen.addstr(row, column, clipped)
    except curses.error:
        pass


class Launcher:
    def __init__(self, screen: curses.window) -> None:
        self.screen = screen
        self.selected = 0
        self.status = network_summary()
        self.last_status_update = time.monotonic()

    def prepare_session(self) -> None:
        RUN.mkdir(mode=0o750, parents=True, exist_ok=True)
        display = os.environ.get("DISPLAY", ":0")
        wayland = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        if not display.startswith(":") or "/" in display or "/" in wayland:
            raise RuntimeError("Cage supplied an invalid display environment")
        (RUN / "session.env").write_text(
            f"DISPLAY={display}\nWAYLAND_DISPLAY={wayland}\n", encoding="utf-8"
        )
        os.chmod(RUN / "session.env", 0o640)

    def request(self, name: str) -> None:
        (RUN / name).touch()

    def draw(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        if height >= 8 and width >= 24:
            try:
                self.screen.border(
                    ord("|"), ord("|"), ord("-"), ord("-"),
                    ord("+"), ord("+"), ord("+"), ord("+"),
                )
            except curses.error:
                pass

        title_row = max(2, height // 8)
        add_centered(self.screen, title_row, "MOONLIGHTOS")

        rows = []
        row = max(title_row + 3, height // 3)
        for index, (label, _action) in enumerate(MENU):
            if index in GAP_BEFORE:
                row += 1
            rows.append((row, label))
            row += 1

        menu_width = max(len(label) for _row, label in rows) + 3
        menu_left = max(2, (width - menu_width) // 2)
        for index, (menu_row, label) in enumerate(rows):
            if menu_row >= height - 3:
                break
            marker = ">" if index == self.selected else " "
            try:
                self.screen.addnstr(
                    menu_row, menu_left, f"{marker}  {label}", max(1, width - menu_left - 1)
                )
            except curses.error:
                pass

        add_centered(self.screen, max(row + 2, height - 4), self.status)
        self.screen.refresh()

    def terminal_command(self, command: list[str], wait_message: str | None = None) -> int:
        curses.def_prog_mode()
        curses.endwin()
        try:
            result = subprocess.run(command, check=False)
            if wait_message:
                print()
                print(wait_message)
                input()
            return result.returncode
        finally:
            curses.reset_prog_mode()
            self.screen.clear()
            self.screen.refresh()

    def activate(self) -> None:
        _label, action = MENU[self.selected]
        if action == "moonlight":
            self.request("start-moonlight")
        elif action == "chiaki":
            self.request("start-chiaki")
        elif action == "tailscale":
            self.request("tailscale-enroll")
            self.terminal_command(["moonlightos-tailscale-enrollment"])
        elif action == "settings":
            self.terminal_command(
                ["moonlightos-diagnostics"], "Press ENTER to return to the launcher."
            )
        elif action in {"reboot", "poweroff"}:
            self.request(action)

    def run(self) -> None:
        self.prepare_session()
        curses.curs_set(0)
        self.screen.keypad(True)
        self.screen.timeout(1000)
        try:
            curses.use_default_colors()
        except curses.error:
            pass

        self.draw()
        (RUN / "launcher-ready").touch()
        while True:
            key = self.screen.getch()
            if key in (curses.KEY_UP, ord("k")):
                self.selected = (self.selected - 1) % len(MENU)
            elif key in (curses.KEY_DOWN, ord("j")):
                self.selected = (self.selected + 1) % len(MENU)
            elif key in (curses.KEY_ENTER, 10, 13):
                self.activate()
            elif key == curses.KEY_RESIZE:
                pass

            now = time.monotonic()
            if now - self.last_status_update >= 5:
                self.status = network_summary()
                self.last_status_update = now
            self.draw()


def main(screen: curses.window) -> None:
    Launcher(screen).run()


if __name__ == "__main__":
    curses.wrapper(main)
