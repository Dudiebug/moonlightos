#!/usr/bin/python3
"""Full-screen terminal launcher for the MoonlightOS appliance."""

from __future__ import annotations

import curses
import os
import pathlib
import subprocess
import sys
import textwrap
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import moonlightos_display as display
import moonlightos_support as support


RUN = pathlib.Path("/run/moonlightos")
MENU = (
    ("MOONLIGHT", "moonlight"),
    ("CHIAKI-NG", "chiaki"),
    ("FIREFOX", "firefox"),
    ("TAILSCALE", "tailscale"),
    ("SETTINGS", "settings"),
    ("REBOOT", "reboot"),
    ("SHUTDOWN", "poweroff"),
)
GAP_BEFORE = {4, 5}
SETTINGS_MENU = (
    "RESOLUTION",
    "REFRESH RATE",
    "APPLY DISPLAY MODE",
    "GENERATE SUPPORT FILE",
    "SYSTEM DIAGNOSTICS",
    "BACK",
)


def move_selection(selected: int, key: int, count: int) -> int:
    if key in (curses.KEY_UP, ord("k")):
        return (selected - 1) % count
    if key in (curses.KEY_DOWN, ord("j")):
        return (selected + 1) % count
    return selected


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
        elif action == "firefox":
            self.request("start-firefox")
        elif action == "tailscale":
            self.request("tailscale-enroll")
            self.terminal_command(["moonlightos-tailscale-enrollment"])
        elif action == "settings":
            Settings(self.screen, self.terminal_command).run()
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
        display.restore_saved_mode()
        self.draw()
        while True:
            key = self.screen.getch()
            self.selected = move_selection(self.selected, key, len(MENU))
            if key in (curses.KEY_ENTER, 10, 13):
                self.activate()
            elif key == curses.KEY_RESIZE:
                pass

            now = time.monotonic()
            if now - self.last_status_update >= 5:
                self.status = network_summary()
                self.last_status_update = now
            self.draw()


class Settings:
    def __init__(self, screen: curses.window, terminal_command) -> None:
        self.screen = screen
        self.terminal_command = terminal_command
        self.selected = 0
        self.status = ""
        self.output: display.Output | None = None
        self.original_mode: display.Mode | None = None
        self.resolution = ""
        self.refresh_mhz = 0

    def refresh_outputs(self) -> bool:
        try:
            current = display.active_output(display.query_outputs())
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            self.status = f"DISPLAY QUERY FAILED: {error}"
            return False
        if current is None or current.current_mode is None:
            self.status = "NO ACTIVE COMPOSITOR OUTPUT"
            return False
        self.output = current
        self.original_mode = current.current_mode
        self.resolution = current.current_mode.resolution
        self.refresh_mhz = current.current_mode.refresh_mhz
        self.status = f"CURRENT: {self.resolution} @ {current.current_mode.refresh} HZ"
        return True

    def resolutions(self) -> list[str]:
        if self.output is None:
            return []
        return list(dict.fromkeys(mode.resolution for mode in self.output.modes))

    def refresh_rates(self) -> list[int]:
        if self.output is None:
            return []
        return list(
            dict.fromkeys(
                mode.refresh_mhz
                for mode in self.output.modes
                if mode.resolution == self.resolution
            )
        )

    def draw(self, title: str = "SETTINGS", rows: list[str] | None = None, selected: int | None = None) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        if height >= 8 and width >= 24:
            try:
                self.screen.border()
            except curses.error:
                pass
        add_centered(self.screen, max(2, height // 8), title)
        if rows is None:
            refresh = f"{self.refresh_mhz / 1000:g} HZ" if self.refresh_mhz else "UNAVAILABLE"
            resolution = self.resolution or "UNAVAILABLE"
            rows = [
                f"RESOLUTION                 {resolution}",
                f"REFRESH RATE               {refresh}",
                "APPLY DISPLAY MODE",
                "GENERATE SUPPORT FILE",
                "SYSTEM DIAGNOSTICS",
                "BACK",
            ]
            selected = self.selected
        row = max(5, height // 3)
        left = max(2, (width - max((len(item) for item in rows), default=1) - 3) // 2)
        for index, label in enumerate(rows):
            marker = ">" if index == selected else " "
            if row + index >= height - 4:
                break
            try:
                self.screen.addnstr(row + index, left, f"{marker}  {label}", width - left - 1)
            except curses.error:
                pass
        add_centered(self.screen, height - 3, self.status)
        self.screen.refresh()

    def choose(self, title: str, choices: list[tuple[str, object]], current: object) -> object | None:
        if not choices:
            self.status = "NO ADVERTISED CHOICES"
            return None
        selected = next((index for index, item in enumerate(choices) if item[1] == current), 0)
        while True:
            self.draw(title, [label for label, _value in choices], selected)
            key = self.screen.getch()
            selected = move_selection(selected, key, len(choices))
            if key in (curses.KEY_ENTER, 10, 13):
                return choices[selected][1]
            if key == 27:
                return None

    def show_message(self, title: str, message: str) -> None:
        while True:
            _height, width = self.screen.getmaxyx()
            rows = textwrap.wrap(message, width=max(8, width - 8)) or [""]
            self.status = "ENTER OR ESC RETURNS TO SETTINGS"
            self.draw(title, rows, None)
            if self.screen.getch() in (curses.KEY_ENTER, 10, 13, 27):
                return

    def rollback(self, old_output: display.Output, old_mode: display.Mode) -> None:
        try:
            validated = display.valid_output_mode(old_output.name, old_output.identity, old_mode)
            if not validated:
                display.log("Rollback skipped because the original display or mode disappeared")
                self.status = "DISPLAY CHANGED; COMPOSITOR DEFAULT RETAINED"
                return
            display.apply_mode(validated[0], validated[1], dryrun=True)
            validated = display.valid_output_mode(old_output.name, old_output.identity, old_mode)
            if not validated:
                raise RuntimeError("original display changed after rollback dry-run")
            display.apply_mode(*validated)
            display.log(f"Rolled back preview on {old_output.name} to {old_mode.argument}")
            self.status = "DISPLAY MODE ROLLED BACK"
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            display.log(f"Display rollback failed: {error}")
            self.status = f"ROLLBACK FAILED: {error}"

    def apply_preview(self) -> None:
        if self.output is None or self.original_mode is None:
            self.status = "NO ACTIVE DISPLAY MODE"
            return
        requested = display.Mode(
            *map(int, self.resolution.split("x")), self.refresh_mhz
        )
        old_output, old_mode = self.output, self.original_mode
        try:
            validated = display.valid_output_mode(old_output.name, old_output.identity, requested)
            if not validated:
                raise RuntimeError("selected output or advertised mode is no longer available")
            display.apply_mode(validated[0], validated[1], dryrun=True)
            validated = display.valid_output_mode(old_output.name, old_output.identity, requested)
            if not validated:
                raise RuntimeError("display changed after dry-run")
            display.apply_mode(*validated)
            display.log(f"Previewing {requested.argument} on {old_output.name}")
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            display.log(f"Display preview rejected: {error}")
            self.status = f"MODE NOT APPLIED: {error}"
            return

        deadline = time.monotonic() + 15
        old_timeout = 250
        self.screen.timeout(old_timeout)
        confirmed = False
        while time.monotonic() < deadline:
            seconds = max(1, int(deadline - time.monotonic() + 0.999))
            self.status = f"ENTER CONFIRMS; ESC ROLLS BACK ({seconds}S)"
            self.draw("CONFIRM DISPLAY MODE", [requested.argument], 0)
            key = self.screen.getch()
            if key in (curses.KEY_ENTER, 10, 13):
                confirmed = True
                break
            if key == 27:
                break
        self.screen.timeout(1000)

        if not confirmed:
            self.rollback(old_output, old_mode)
            self.refresh_outputs()
            return
        try:
            validated = display.valid_output_mode(old_output.name, old_output.identity, requested)
            if not validated or validated[0].current_mode is None:
                raise RuntimeError("display disappeared before confirmation")
            current = validated[0].current_mode
            if (current.width, current.height, current.refresh_mhz) != (
                requested.width,
                requested.height,
                requested.refresh_mhz,
            ):
                raise RuntimeError("compositor did not retain the requested mode")
            display.save_display(validated[0], requested)
            display.log(f"Confirmed and saved {requested.argument} on {old_output.name}")
            self.status = "DISPLAY MODE CONFIRMED AND SAVED"
            self.refresh_outputs()
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            display.log(f"Display confirmation failed: {error}")
            self.rollback(old_output, old_mode)

    def generate_support_file(self) -> None:
        destinations = support.discover_destinations()
        if not destinations:
            self.status = "A WRITABLE REMOVABLE USB PARTITION IS REQUIRED"
            return
        destination = destinations[0]
        if len(destinations) > 1:
            selected = self.choose(
                "SELECT SUPPORT DESTINATION",
                [(item.display_name, item) for item in destinations],
                destination,
            )
            if selected is None:
                self.status = "SUPPORT EXPORT CANCELLED"
                return
            destination = selected
        try:
            request_id = support.submit_request(destination)
        except OSError as error:
            self.status = f"SUPPORT REQUEST FAILED: {error}"
            return
        deadline = time.monotonic() + 180
        self.screen.timeout(250)
        try:
            while time.monotonic() < deadline:
                self.status = "COLLECTING SUPPORT FILE... ESC RETURNS TO SETTINGS"
                self.draw()
                state = support.read_status(request_id)
                if state and state.get("state") == "success":
                    destination_name = state.get("destination", "")
                    self.show_message("SUPPORT FILE CREATED", f"SAVED: {destination_name}")
                    self.status = f"SAVED: {destination_name}"
                    return
                if state and state.get("state") == "failed":
                    failure = state.get("message", "")
                    self.show_message("SUPPORT EXPORT FAILED", failure)
                    self.status = f"EXPORT FAILED: {failure}"
                    return
                if self.screen.getch() == 27:
                    self.status = "SUPPORT EXPORT CONTINUES IN THE BACKGROUND"
                    return
        finally:
            self.screen.timeout(1000)
        self.status = "SUPPORT EXPORT TIMED OUT; CHECK SERVICE STATUS"

    def activate(self) -> bool:
        if self.selected == 0:
            resolutions = self.resolutions()
            chosen = self.choose("RESOLUTION", [(item, item) for item in resolutions], self.resolution)
            if isinstance(chosen, str):
                self.resolution = chosen
                rates = self.refresh_rates()
                if self.refresh_mhz not in rates and rates:
                    self.refresh_mhz = rates[0]
        elif self.selected == 1:
            rates = self.refresh_rates()
            choices = [
                (f"{value / 1000:g} HZ", value)
                for value in rates
            ]
            chosen = self.choose("REFRESH RATE", choices, self.refresh_mhz)
            if isinstance(chosen, int):
                self.refresh_mhz = chosen
        elif self.selected == 2:
            self.apply_preview()
        elif self.selected == 3:
            self.generate_support_file()
        elif self.selected == 4:
            self.terminal_command(
                ["moonlightos-diagnostics"], "Press ENTER to return to Settings."
            )
        else:
            return False
        return True

    def run(self) -> None:
        self.refresh_outputs()
        while True:
            self.draw()
            key = self.screen.getch()
            self.selected = move_selection(self.selected, key, len(SETTINGS_MENU))
            if key in (curses.KEY_ENTER, 10, 13) and not self.activate():
                return
            if key == 27:
                return


def main(screen: curses.window) -> None:
    Launcher(screen).run()


if __name__ == "__main__":
    curses.wrapper(main)
