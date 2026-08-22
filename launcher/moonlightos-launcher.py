#!/usr/bin/python3
"""Full-screen terminal launcher for the MoonlightOS appliance."""

from __future__ import annotations

import curses
import ipaddress
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
APP_LAUNCH = {
    "moonlight": ("MOONLIGHT", "moonlight", "start-moonlight"),
    "chiaki": ("CHIAKI-NG", "chiaki-ng", "start-chiaki"),
    "firefox": ("FIREFOX", "firefox", "start-firefox"),
}
GAP_BEFORE = {4, 5}
SETTINGS_MENU = (
    "RESOLUTION",
    "REFRESH RATE",
    "APPLY DISPLAY MODE",
    "GENERATE SUPPORT FILE",
    "SYSTEM DIAGNOSTICS",
    "BACK",
)
SPINNER = "|/-\\"
SUPPORT_EXPORT_TIMEOUT = 180.0
SUPPORT_EXPORT_START_TIMEOUT = 12.0
SUPPORT_EXPORT_POLL_MS = 100


def move_selection(selected: int, key: int, count: int) -> int:
    if key in (curses.KEY_UP, ord("k")):
        return (selected - 1) % count
    if key in (curses.KEY_DOWN, ord("j")):
        return (selected + 1) % count
    return selected


def indeterminate_progress_bar(width: int, frame: int) -> str:
    """Return a fixed-width, bouncing ASCII progress indicator."""
    width = max(8, width)
    inner_width = width - 2
    segment_width = max(2, min(8, inner_width // 4))
    travel = max(0, inner_width - segment_width)
    if travel:
        cycle = frame % (travel * 2)
        position = cycle if cycle <= travel else travel * 2 - cycle
    else:
        position = 0
    body = (
        " " * position
        + "=" * segment_width
        + " " * (inner_width - position - segment_width)
    )
    return f"[{body}]"


def format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, remaining = divmod(total, 60)
    return f"{minutes:02d}:{remaining:02d}"


def get_ipv4(output: str) -> str:
    """Return the first non-loopback IPv4 from normal or `ip -brief` output."""
    for line in output.splitlines():
        fields = line.split()
        if not fields:
            continue
        candidates: list[str] = []
        if "inet" in fields:
            index = fields.index("inet") + 1
            if index < len(fields):
                candidates.append(fields[index])
        else:
            # `ip -brief -4 address` prints: IFACE STATE ADDRESS/PREFIX ...
            candidates.extend(fields[2:])
        for candidate in candidates:
            value = candidate.split("/", 1)[0]
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                continue
            if isinstance(address, ipaddress.IPv4Address) and not address.is_loopback:
                return str(address)
    return "NO IPV4"


def network_summary() -> str:
    try:
        result = subprocess.run(
            ["ip", "-brief", "-4", "address", "show", "up"],
            text=True,
            capture_output=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return "NO IPV4  OFFLINE"
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


def draw_border(screen: curses.window) -> None:
    height, width = screen.getmaxyx()
    if height < 8 or width < 24:
        return
    try:
        screen.border(
            ord("|"), ord("|"), ord("-"), ord("-"),
            ord("+"), ord("+"), ord("+"), ord("+"),
        )
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
        display_name = os.environ.get("DISPLAY", ":0")
        wayland = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        if not display_name.startswith(":") or "/" in display_name or "/" in wayland:
            raise RuntimeError("Cage supplied an invalid display environment")
        (RUN / "session.env").write_text(
            f"DISPLAY={display_name}\nWAYLAND_DISPLAY={wayland}\n", encoding="utf-8"
        )
        os.chmod(RUN / "session.env", 0o640)

    def request(self, name: str) -> None:
        (RUN / name).touch()

    def draw(self) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        draw_border(self.screen)
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

    def draw_launching(self, label: str, frame: str) -> None:
        self.screen.erase()
        height, _width = self.screen.getmaxyx()
        draw_border(self.screen)
        add_centered(self.screen, max(2, height // 8), "MOONLIGHTOS")
        center = max(6, height // 2 - 1)
        add_centered(self.screen, center, f"STARTING {label}  {frame}")
        add_centered(self.screen, center + 2, "PLEASE WAIT")
        add_centered(self.screen, height - 3, "TRIPLE-TAP ESC IN AN APP TO RETURN")
        self.screen.refresh()

    def show_launch_failure(self, label: str, message: str) -> None:
        self.screen.timeout(1000)
        while True:
            self.screen.erase()
            height, width = self.screen.getmaxyx()
            draw_border(self.screen)
            add_centered(self.screen, max(2, height // 8), f"{label} FAILED TO START")
            rows = textwrap.wrap(message, width=max(8, width - 8)) or ["UNKNOWN ERROR"]
            first = max(6, height // 2 - len(rows) // 2)
            for offset, row in enumerate(rows[: max(1, height - first - 5)]):
                add_centered(self.screen, first + offset, row)
            add_centered(self.screen, height - 3, "ENTER OR ESC RETURNS TO LAUNCHER")
            self.screen.refresh()
            if self.screen.getch() in (curses.KEY_ENTER, 10, 13, 27):
                return

    @staticmethod
    def read_app_status(app_id: str) -> str:
        path = RUN / f"{app_id}-status"
        try:
            if path.is_symlink() or path.stat().st_size > 512:
                return ""
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        return lines[0][:240] if lines else ""

    def launch_app(self, action: str) -> bool:
        label, app_id, request = APP_LAUNCH[action]
        ready = RUN / f"{app_id}-ready"
        state = RUN / f"{app_id}-status"
        ready.unlink(missing_ok=True)
        state.unlink(missing_ok=True)
        self.request(request)

        deadline = time.monotonic() + 18
        failure_since: float | None = None
        frame = 0
        self.screen.timeout(100)
        try:
            while time.monotonic() < deadline:
                self.draw_launching(label, SPINNER[frame % len(SPINNER)])
                frame += 1
                if ready.exists():
                    self.status = f"{label} STARTED"
                    return True

                app_state = self.read_app_status(app_id)
                now = time.monotonic()
                if app_state.startswith("failed:"):
                    if failure_since is None:
                        failure_since = now
                    # App units retry after two seconds. A persistent failure for
                    # longer than that means retries have not recovered startup.
                    if now - failure_since >= 2.75:
                        self.show_launch_failure(label, app_state.removeprefix("failed:").strip())
                        self.status = f"{label} FAILED TO START"
                        return False
                else:
                    failure_since = None
                self.screen.getch()  # permits curses to process resize/input state
        finally:
            self.screen.timeout(1000)

        last_state = self.read_app_status(app_id)
        message = (
            last_state.removeprefix("failed:").strip()
            if last_state.startswith("failed:")
            else "THE APPLICATION DID NOT BECOME READY BEFORE THE STARTUP TIMEOUT"
        )
        self.show_launch_failure(label, message)
        self.status = f"{label} START TIMED OUT"
        return False

    def restore_curses(self) -> None:
        try:
            curses.reset_prog_mode()
        except curses.error:
            pass
        for operation in (curses.noecho, curses.cbreak):
            try:
                operation()
            except curses.error:
                pass
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        try:
            curses.flushinp()
        except curses.error:
            pass
        self.screen.keypad(True)
        self.screen.timeout(1000)
        try:
            self.screen.clearok(True)
        except curses.error:
            pass
        self.screen.clear()
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
            self.restore_curses()

    def activate(self) -> None:
        _label, action = MENU[self.selected]
        if action in APP_LAUNCH:
            self.launch_app(action)
        elif action == "tailscale":
            self.request("tailscale-enroll")
            self.terminal_command(["moonlightos-tailscale-enrollment"])
            # Rebuild runtime state after the external terminal UI. This avoids
            # the broken input/app-launch state seen after enrollment returns.
            self.prepare_session()
            self.status = network_summary()
            self.last_status_update = time.monotonic()
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

    def draw_support_progress(
        self,
        destination: support.Destination,
        frame: int,
        message: str,
        elapsed: float,
    ) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        draw_border(self.screen)
        title_row = max(2, height // 8)
        add_centered(self.screen, title_row, "EXPORTING SUPPORT FILE")

        stage_rows = textwrap.wrap(
            (message or "COLLECTING SUPPORT INFORMATION").upper(),
            width=max(8, width - 8),
        )[:2]
        stage_row = max(title_row + 3, height // 2 - 4)
        spinner = SPINNER[frame % len(SPINNER)]
        for index, row in enumerate(stage_rows):
            prefix = f"{spinner}  " if index == 0 else ""
            add_centered(self.screen, stage_row + index, prefix + row)

        bar_width = min(50, max(8, width - 12))
        add_centered(
            self.screen,
            stage_row + len(stage_rows) + 1,
            indeterminate_progress_bar(bar_width, frame),
        )

        destination_rows = textwrap.wrap(
            f"USB: {destination.display_name}", width=max(8, width - 8)
        )[:2]
        destination_row = stage_row + len(stage_rows) + 3
        for index, row in enumerate(destination_rows):
            add_centered(self.screen, destination_row + index, row)
        add_centered(
            self.screen,
            destination_row + len(destination_rows) + 1,
            f"ELAPSED {format_elapsed(elapsed)}",
        )
        add_centered(self.screen, height - 3, "PLEASE WAIT - DO NOT REMOVE USB DRIVE")
        self.screen.refresh()

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
        try:
            destinations = support.discover_destinations()
        except (OSError, subprocess.SubprocessError) as error:
            failure = f"USB DESTINATION CHECK FAILED: {error}"
            self.show_message("SUPPORT EXPORT FAILED", failure)
            self.status = failure
            return
        if not destinations:
            failure = "CONNECT A WRITABLE REMOVABLE USB DRIVE AND TRY AGAIN"
            self.show_message("USB DRIVE NOT FOUND", failure)
            self.status = "SUPPORT EXPORT FAILED: NO WRITABLE USB DRIVE"
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
            failure = f"COULD NOT START THE SUPPORT EXPORT: {error}"
            self.show_message("SUPPORT EXPORT FAILED", failure)
            self.status = f"EXPORT FAILED: {error}"
            return

        started_at = time.monotonic()
        start_deadline = started_at + SUPPORT_EXPORT_START_TIMEOUT
        deadline = started_at + SUPPORT_EXPORT_TIMEOUT
        frame = 0
        message = "WAITING FOR EXPORT SERVICE"
        self.screen.timeout(SUPPORT_EXPORT_POLL_MS)
        try:
            while True:
                now = time.monotonic()
                state = support.read_status(request_id)
                if state:
                    export_state = state.get("state", "")
                    if export_state == "success":
                        destination_name = state.get("destination", "") or destination.display_name
                        self.screen.timeout(1000)
                        self.show_message("SUPPORT FILE CREATED", f"SAVED: {destination_name}")
                        self.status = f"SAVED: {destination_name}"
                        return
                    if export_state == "failed":
                        failure = state.get("message", "") or "THE EXPORTER REPORTED AN UNKNOWN FAILURE"
                        self.screen.timeout(1000)
                        self.show_message("SUPPORT EXPORT FAILED", failure)
                        self.status = f"EXPORT FAILED: {failure}"
                        return
                    if export_state == "working":
                        message = state.get("message", "") or "COLLECTING SUPPORT INFORMATION"
                elif now >= start_deadline:
                    failure = (
                        "THE EXPORT SERVICE DID NOT REPORT STARTUP. THE FILE WAS NOT CREATED. "
                        "REBOOT MOONLIGHTOS AND TRY AGAIN; IF IT FAILS AGAIN, RUN SYSTEM DIAGNOSTICS."
                    )
                    self.screen.timeout(1000)
                    self.show_message("SUPPORT EXPORT FAILED", failure)
                    self.status = "EXPORT FAILED: SERVICE DID NOT START"
                    return

                if now >= deadline:
                    failure = (
                        "THE EXPORT DID NOT REPORT COMPLETION WITHIN 3 MINUTES. "
                        "DO NOT REMOVE THE USB DRIVE WHILE ITS ACTIVITY LIGHT IS FLASHING. "
                        "REBOOT MOONLIGHTOS BEFORE TRYING AGAIN."
                    )
                    self.screen.timeout(1000)
                    self.show_message("SUPPORT EXPORT TIMED OUT", failure)
                    self.status = "SUPPORT EXPORT TIMED OUT"
                    return

                self.draw_support_progress(destination, frame, message, now - started_at)
                frame += 1
                self.screen.getch()  # process resize/input state; export cannot be cancelled safely
        finally:
            self.screen.timeout(1000)

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
