#!/usr/bin/python3
"""Full-screen terminal launcher for the MoonlightOS appliance."""

from __future__ import annotations

import curses
import dataclasses
import ipaddress
import os
import pathlib
import shlex
import subprocess
import sys
import textwrap
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import moonlightos_display as display
import moonlightos_audio as audio
import moonlightos_support as support
import moonlightos_bluetooth as bluetooth
import moonlightos_apps as apps
import moonlightos_setup as setup


RUN = pathlib.Path("/run/moonlightos")
HOME_REQUEST = RUN / "home.request"
SOURCE_MANIFESTS = pathlib.Path(__file__).resolve().parents[1] / "config/apps.d"
FIXED_CONTROLS = (("SETTINGS", "settings"), ("REBOOT", "reboot"), ("SHUTDOWN", "poweroff"))
SETTINGS_MENU = (
    "DISPLAY",
    "AUDIO",
    "BLUETOOTH",
    "APPLICATIONS",
    "ACTIVE APPLICATIONS",
    "TAILSCALE",
    "SETUP WIZARD",
    "GENERATE SUPPORT FILE",
    "SYSTEM DIAGNOSTICS",
    "BACK",
)
SPINNER = "|/-\\"
SUPPORT_EXPORT_TIMEOUT = 180.0
SUPPORT_EXPORT_START_TIMEOUT = 12.0
SUPPORT_EXPORT_POLL_MS = 100


def application_result() -> apps.LoadResult:
    system_dir = apps.SYSTEM_DIR if apps.SYSTEM_DIR.exists() else SOURCE_MANIFESTS
    return apps.load_applications(system_dir=system_dir)


def request_osk() -> None:
    (RUN / "start-osk").touch()


def read_key(screen: curses.window) -> int:
    key = screen.getch()
    if key == curses.KEY_F12:
        request_osk()
        return -1
    return key


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


def bluetooth_summary() -> str:
    try:
        adapter = bluetooth.BluetoothClient().snapshot().get("adapter")
    except bluetooth.BluetoothError:
        return "BLUETOOTH STATUS UNAVAILABLE"
    if not isinstance(adapter, dict):
        return "NO BLUETOOTH ADAPTER"
    return "BLUETOOTH ON" if adapter.get("powered") else "BLUETOOTH OFF"


def display_summary() -> str:
    try:
        output = display.active_output(display.query_outputs())
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return "DISPLAY STATUS UNAVAILABLE"
    if output is None or output.current_mode is None:
        return "NO ACTIVE DISPLAY"
    return f"{output.name}  {output.current_mode.argument}"


def audio_summary() -> str:
    try:
        result = subprocess.run(
            ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
            text=True, capture_output=True, check=False, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return "AUDIO STATUS UNAVAILABLE"
    return result.stdout.strip().upper()[:96] if result.returncode == 0 else "AUDIO STATUS UNAVAILABLE"


def controller_summary() -> str:
    identity = pathlib.Path("/var/lib/moonlightos/launcher-controller.id")
    try:
        value = identity.read_text(encoding="ascii").strip()
    except OSError:
        return "NO CONTROLLER IDENTITY SAVED"
    return f"CONTROLLER DETECTED  {value[:64]}"


def configuration_summary(name: str) -> str:
    root = pathlib.Path("/var/lib/moonlightos/home/.config")
    try:
        configured = any(name in path.name.casefold() for path in root.iterdir())
    except OSError:
        configured = False
    return f"{name.upper()} {'CONFIGURATION FOUND' if configured else 'NOT CONFIGURED'}"


def tailscale_summary() -> str:
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"], text=True, capture_output=True,
            check=False, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return "TAILSCALE DISCONNECTED"
    return "TAILSCALE CONNECTED" if result.returncode == 0 else "TAILSCALE DISCONNECTED"


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
        self.applications: tuple[apps.Application, ...] = ()
        self.menu: list[tuple[str, str]] = []
        self.reload_applications()

    def reload_applications(self) -> None:
        result = application_result()
        self.applications = tuple(
            app for app in result.applications if app.visible and app.enabled
        )
        self.menu = [(app.name, app.id) for app in self.applications] + list(FIXED_CONTROLS)
        self.selected = min(self.selected, max(0, len(self.menu) - 1))
        if result.errors:
            self.status = f"{len(result.errors)} INVALID APPLICATION(S) SKIPPED"

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
        gap_before = {len(self.applications), len(self.applications) + 1}
        for index, (label, _action) in enumerate(self.menu):
            if index in gap_before:
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
        add_centered(self.screen, height - 3, "EXIT THE APP TO RETURN")
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
            if read_key(self.screen) in (curses.KEY_ENTER, 10, 13, 27):
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

    def launch_app(self, app: apps.Application) -> bool:
        label, app_id = app.name, app.status_id
        ready = RUN / f"{app_id}-ready"
        if ready.exists():
            if self.focus_app(app):
                self.status = f"RESUMED {label}"
                return True
            self.status = f"{label} IS RUNNING BUT HAS NO MANAGED WINDOW"
            return False
        state = RUN / f"{app_id}-status"
        ready.unlink(missing_ok=True)
        state.unlink(missing_ok=True)
        if app.kind == "request":
            self.request(app.request)
        else:
            apps.atomic_write(RUN / "launch-app.request", app.id + "\n")

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
                read_key(self.screen)  # permits curses to process resize/input state
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

    def app_by_id(self, app_id: str) -> apps.Application | None:
        return next(
            (app for app in application_result().applications if app.id == app_id and app.enabled),
            None,
        )

    def launch_by_id(self, app_id: str) -> bool:
        app = self.app_by_id(app_id)
        if app is None:
            self.status = f"{app_id.upper()} IS UNAVAILABLE"
            return False
        return self.launch_app(app)

    @staticmethod
    def focus_app(app: apps.Application) -> bool:
        matches = {
            "firefox": ("app_id:firefox-esr", "app_id:firefox", "title:Mozilla Firefox"),
            "google-chrome": ("app_id:google-chrome", "title:Google Chrome"),
            "moonlight": ("app_id:moonlight", "title:Moonlight"),
            "chiaki-ng": ("app_id:chiaki", "app_id:io.github.streetpea.Chiaki4deck", "title:Chiaki"),
        }.get(app.id, (f"title:{app.name}",))
        for match in matches:
            try:
                result = subprocess.run(
                    ["wlrctl", "toplevel", "focus", match], check=False,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2,
                )
            except (OSError, subprocess.SubprocessError):
                return False
            if result.returncode == 0:
                return True
        return False

    def running_applications(self) -> list[apps.Application]:
        return [
            app for app in application_result().applications
            if app.enabled and (RUN / f"{app.status_id}-ready").exists()
        ]

    def active_applications(self) -> None:
        selected = 0
        status = "ENTER RESUMES  ·  X CLOSES"
        while True:
            running = self.running_applications()
            rows = [f"{app.name:<32} RUNNING" for app in running] + ["RETURN TO MAIN LAUNCHER"]
            selected = min(selected, len(rows) - 1)
            self.screen.erase()
            height, width = self.screen.getmaxyx()
            draw_border(self.screen)
            add_centered(self.screen, max(2, height // 8), "ACTIVE APPLICATIONS")
            first = max(5, height // 3)
            left = max(2, (width - max(map(len, rows), default=1) - 3) // 2)
            for index, row in enumerate(rows):
                marker = ">" if index == selected else " "
                try:
                    self.screen.addnstr(first + index, left, f"{marker}  {row}", width - left - 1)
                except curses.error:
                    pass
            add_centered(self.screen, height - 3, status if running else "NO MANAGED APPLICATIONS ARE RUNNING")
            self.screen.refresh()
            key = read_key(self.screen)
            selected = move_selection(selected, key, len(rows))
            if key == 27 or (key in (curses.KEY_ENTER, 10, 13) and selected == len(running)):
                return
            if selected >= len(running):
                continue
            app = running[selected]
            if key in (curses.KEY_ENTER, 10, 13):
                if self.focus_app(app):
                    self.status = f"RESUMED {app.name}"
                    return
                status = f"COULD NOT FOCUS {app.name}"
            elif key in (curses.KEY_DC, ord("x")):
                (RUN / f"close-{app.status_id}").touch()
                status = f"CLOSING {app.name}"

    def activate(self) -> None:
        _label, action = self.menu[self.selected]
        app = next((item for item in self.applications if item.id == action), None)
        if app:
            self.launch_app(app)
        elif action == "settings":
            Settings(self.screen, self).run()
            self.reload_applications()
        elif action in {"reboot", "poweroff"}:
            self.request(action)

    def setup_wizard(self, *, force: bool = False) -> None:
        settings = Settings(self.screen, self)
        actions = {
            "osk": request_osk,
            "network": lambda: self.launch_by_id("network-setup"),
            "bluetooth": lambda: bluetooth.run_bluetooth(self.screen),
            "display": settings.run_display,
            "audio": lambda: self.launch_by_id("audio-test"),
            "moonlight": lambda: self.launch_by_id("moonlight"),
            "chiaki-ng": lambda: self.launch_by_id("chiaki-ng"),
            "tailscale": lambda: self.launch_by_id("tailscale"),
            "applications": settings.run_applications,
        }
        statuses = {
            "network": network_summary,
            "bluetooth": bluetooth_summary,
            "display": display_summary,
            "audio": audio_summary,
            "controller": controller_summary,
            "moonlight": lambda: configuration_summary("moonlight"),
            "chiaki-ng": lambda: configuration_summary("chiaki"),
            "tailscale": tailscale_summary,
            "applications": lambda: f"{len(application_result().applications)} APPLICATIONS CONFIGURED",
        }
        setup.SetupWizard(self.screen, actions, statuses).run(force=force)
        self.reload_applications()

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
        self.setup_wizard()
        while True:
            key = read_key(self.screen)
            if HOME_REQUEST.exists() or key == curses.KEY_HOME:
                HOME_REQUEST.unlink(missing_ok=True)
                self.active_applications()
                self.draw()
                continue
            self.selected = move_selection(self.selected, key, len(self.menu))
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
    def __init__(self, screen: curses.window, launcher: Launcher) -> None:
        self.screen = screen
        self.launcher = launcher
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
            rows = list(SETTINGS_MENU)
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
            key = read_key(self.screen)
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
            if read_key(self.screen) in (curses.KEY_ENTER, 10, 13, 27):
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
            key = read_key(self.screen)
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
                        result_message = state.get("message", "") or "SUPPORT FILE CREATED"
                        self.screen.timeout(1000)
                        self.show_message(
                            "SUPPORT FILE CREATED",
                            f"{result_message}. SAVED: {destination_name}",
                        )
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
                read_key(self.screen)  # process resize/input state; export cannot be cancelled safely
        finally:
            self.screen.timeout(1000)

    def activate(self) -> bool:
        if self.selected == 0:
            self.run_display()
        elif self.selected == 1:
            self.run_audio()
        elif self.selected == 2:
            bluetooth.run_bluetooth(self.screen)
        elif self.selected == 3:
            self.run_applications()
        elif self.selected == 4:
            self.launcher.active_applications()
        elif self.selected == 5:
            self.launcher.launch_by_id("tailscale")
        elif self.selected == 6:
            self.launcher.setup_wizard(force=True)
        elif self.selected == 7:
            self.generate_support_file()
        elif self.selected == 8:
            self.launcher.launch_by_id("system-diagnostics")
        else:
            return False
        return True

    def run_display(self) -> None:
        self.refresh_outputs()
        selected = 0
        while True:
            refresh = f"{self.refresh_mhz / 1000:g} HZ" if self.refresh_mhz else "UNAVAILABLE"
            rows = [f"RESOLUTION  {self.resolution or 'UNAVAILABLE'}", f"REFRESH RATE  {refresh}", "APPLY DISPLAY MODE", "BACK"]
            self.draw("DISPLAY SETTINGS", rows, selected)
            key = read_key(self.screen)
            selected = move_selection(selected, key, len(rows))
            if key == 27 or (key in (curses.KEY_ENTER, 10, 13) and selected == 3):
                return
            if key not in (curses.KEY_ENTER, 10, 13):
                continue
            if selected == 0:
                resolutions = self.resolutions()
                chosen = self.choose("RESOLUTION", [(item, item) for item in resolutions], self.resolution)
                if isinstance(chosen, str):
                    self.resolution = chosen
                    rates = self.refresh_rates()
                    if self.refresh_mhz not in rates and rates:
                        self.refresh_mhz = rates[0]
            elif selected == 1:
                rates = self.refresh_rates()
                chosen = self.choose(
                    "REFRESH RATE",
                    [(f"{value / 1000:g} HZ", value) for value in rates],
                    self.refresh_mhz,
                )
                if isinstance(chosen, int):
                    self.refresh_mhz = chosen
            else:
                self.apply_preview()

    def run_audio(self) -> None:
        selected = 0
        while True:
            try:
                sinks = audio.query_sinks()
                rows = [f"{'*' if sink.default else ' '}  {sink.name}" for sink in sinks] + ["BACK"]
                self.status = "* IS THE CURRENT DEFAULT OUTPUT" if sinks else "NO AUDIO OUTPUTS AVAILABLE"
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                sinks = []
                rows = ["BACK"]
                self.status = f"AUDIO QUERY FAILED: {error}"
            selected = min(selected, len(rows) - 1)
            self.draw("AUDIO OUTPUT", rows, selected)
            key = read_key(self.screen)
            selected = move_selection(selected, key, len(rows))
            if key == 27 or (key in (curses.KEY_ENTER, 10, 13) and selected == len(sinks)):
                return
            if key not in (curses.KEY_ENTER, 10, 13) or selected >= len(sinks):
                continue
            try:
                audio.set_default(sinks[selected].id)
                self.status = f"DEFAULT OUTPUT: {sinks[selected].name}"
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                self.status = f"OUTPUT NOT CHANGED: {error}"

    def run_applications(self) -> None:
        ApplicationsSettings(self.screen, self.launcher).run()
        self.launcher.reload_applications()

    def run(self) -> None:
        self.refresh_outputs()
        while True:
            self.draw()
            key = read_key(self.screen)
            self.selected = move_selection(self.selected, key, len(SETTINGS_MENU))
            if key in (curses.KEY_ENTER, 10, 13) and not self.activate():
                return
            if key == 27:
                return


class ApplicationsSettings:
    def __init__(self, screen: curses.window, launcher: Launcher) -> None:
        self.screen = screen
        self.launcher = launcher
        self.selected = 0
        self.status = ""

    def result(self) -> apps.LoadResult:
        return application_result()

    def draw(self, title: str, rows: list[str], selected: int | None = None) -> None:
        self.screen.erase()
        height, width = self.screen.getmaxyx()
        draw_border(self.screen)
        add_centered(self.screen, max(2, height // 8), title)
        first = max(5, height // 4)
        left = max(2, (width - max((len(row) for row in rows), default=1) - 3) // 2)
        count = max(1, height - first - 4)
        offset = 0 if selected is None else min(max(0, selected - count + 1), max(0, len(rows) - count))
        for index, row in enumerate(rows[offset:offset + count], start=offset):
            marker = ">" if index == selected else " "
            try:
                self.screen.addnstr(first + index - offset, left, f"{marker}  {row}", max(1, width - left - 1))
            except curses.error:
                pass
        add_centered(self.screen, height - 3, self.status or "LEFT/RIGHT MOVES  ·  ENTER EDITS  ·  F12 KEYBOARD")
        self.screen.refresh()

    def text_input(self, title: str, prompt: str, limit: int) -> str | None:
        value = ""
        self.screen.timeout(-1)
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        try:
            while True:
                shown = value[-limit:] or "_"
                self.draw(title, [prompt, shown], None)
                key = self.screen.get_wch()
                if isinstance(key, str):
                    if key in {"\n", "\r"}:
                        return value
                    if key == "\x1b":
                        return None
                    if key in {"\b", "\x7f"}:
                        value = value[:-1]
                    elif key.isprintable() and key not in "\r\n" and len(value) < limit:
                        value += key
                elif key == curses.KEY_F12:
                    request_osk()
                elif key in (curses.KEY_BACKSPACE,):
                    value = value[:-1]
        finally:
            self.screen.timeout(1000)
            try:
                curses.curs_set(0)
            except curses.error:
                pass

    def yes_no(self, title: str, prompt: str) -> bool | None:
        selected = 0
        while True:
            rows = [prompt, "YES", "NO"]
            self.draw(title, rows, selected + 1)
            key = read_key(self.screen)
            selected = move_selection(selected, key, 2)
            if key in (curses.KEY_ENTER, 10, 13):
                return selected == 0
            if key == 27:
                return None

    def _write_user(self, app: apps.Application) -> None:
        system_dir = apps.SYSTEM_DIR if apps.SYSTEM_DIR.exists() else SOURCE_MANIFESTS
        apps.write_user_application(app, system_dir=system_dir)

    def add_command(self) -> None:
        name = self.text_input("ADD COMMAND APPLICATION", "NAME", apps.MAX_NAME)
        if not name:
            return
        command = self.text_input("ADD COMMAND APPLICATION", "ABSOLUTE COMMAND", apps.MAX_COMMAND)
        if command is None:
            return
        arguments = self.text_input("ADD COMMAND APPLICATION", "ARGUMENTS (OPTIONAL)", apps.MAX_ARGUMENTS)
        if arguments is None:
            return
        terminal = self.yes_no("ADD COMMAND APPLICATION", "RUN IN TERMINAL?")
        if terminal is None:
            return
        environment_text = self.text_input(
            "ADD COMMAND APPLICATION", "ENVIRONMENT KEY=value;OTHER=value (OPTIONAL)", 2048
        )
        if environment_text is None:
            return
        try:
            result = self.result()
            app_id = apps.application_id(name, {item.id for item in result.applications})
            order = max([50, *(item.order for item in result.applications if item.visible)]) + 10
            self._write_user(
                apps.Application(
                    id=app_id, name=name.strip().upper(), kind="command", command=command.strip(),
                    arguments=arguments, status_id=app_id, terminal=terminal, order=order,
                    environment=apps.parse_environment(environment_text),
                )
            )
            self.status = f"ADDED {name.strip().upper()}"
        except (OSError, apps.ManifestError) as error:
            self.status = f"APPLICATION NOT ADDED: {error}"

    def add_web(self) -> None:
        name = self.text_input("ADD WEB APPLICATION", "NAME", apps.MAX_NAME)
        if not name:
            return
        url = self.text_input("ADD WEB APPLICATION", "HTTP:// OR HTTPS:// URL", 2048)
        if url is None:
            return
        try:
            url = apps.validate_web_url(url)
            result = self.result()
            app_id = apps.application_id(name, {item.id for item in result.applications})
            order = max([50, *(item.order for item in result.applications if item.visible)]) + 10
            self._write_user(
                apps.Application(
                    id=app_id, name=name.strip().upper(), kind="command",
                    command="/usr/bin/google-chrome-stable",
                    arguments=shlex.join(["--ozone-platform=wayland", "--kiosk", "--no-first-run", url]),
                    status_id=app_id, order=order,
                )
            )
            self.status = f"ADDED {name.strip().upper()}"
        except (OSError, apps.ManifestError) as error:
            self.status = f"WEB APPLICATION NOT ADDED: {error}"

    def edit(self, app: apps.Application) -> None:
        while True:
            rows = ["DISABLE" if app.enabled else "ENABLE"]
            if not app.system:
                rows.append("DELETE")
            rows.append("BACK")
            selected = 0
            while True:
                self.draw(app.name, rows, selected)
                key = read_key(self.screen)
                selected = move_selection(selected, key, len(rows))
                if key == 27:
                    return
                if key in (curses.KEY_ENTER, 10, 13):
                    break
            choice = rows[selected]
            result = self.result()
            current = list(result.applications)
            index = next((number for number, item in enumerate(current) if item.id == app.id), -1)
            if index < 0 or choice == "BACK":
                return
            try:
                if choice in {"ENABLE", "DISABLE"}:
                    current[index] = dataclasses.replace(current[index], enabled=choice == "ENABLE")
                elif choice == "DELETE":
                    system_dir = apps.SYSTEM_DIR if apps.SYSTEM_DIR.exists() else SOURCE_MANIFESTS
                    apps.delete_user_application(app.id, system_dir=system_dir)
                    self.status = f"DELETED {app.name}"
                    self.launcher.reload_applications()
                    return
                apps.write_state(current)
                self.launcher.reload_applications()
                app = next(item for item in self.result().applications if item.id == app.id)
                self.status = f"UPDATED {app.name}"
            except (OSError, apps.ManifestError) as error:
                self.status = f"APPLICATION NOT UPDATED: {error}"

    def move(self, visible: list[apps.Application], direction: int) -> None:
        target = self.selected + direction
        if not 0 <= target < len(visible):
            self.status = "APPLICATION IS ALREADY AT THE EDGE"
            return
        visible[self.selected], visible[target] = visible[target], visible[self.selected]
        order_by_id = {item.id: (number + 1) * 10 for number, item in enumerate(visible)}
        current = [
            dataclasses.replace(item, order=order_by_id.get(item.id, item.order))
            for item in self.result().applications
        ]
        apps.write_state(current)
        self.selected = target
        self.launcher.reload_applications()
        self.status = f"MOVED {visible[target].name}"

    def run(self) -> None:
        while True:
            result = self.result()
            visible = [app for app in result.applications if app.visible]
            rows = [f"{app.name:<28} {'ENABLED' if app.enabled else 'DISABLED'}" for app in visible]
            rows += ["ADD COMMAND APPLICATION", "ADD WEB APPLICATION", "BACK"]
            self.selected = min(self.selected, len(rows) - 1)
            if result.errors:
                self.status = f"{len(result.errors)} INVALID APPLICATION(S) SKIPPED"
            self.draw("EDIT APPLICATIONS", rows, self.selected)
            key = read_key(self.screen)
            self.selected = move_selection(self.selected, key, len(rows))
            if self.selected < len(visible) and key in (curses.KEY_LEFT, ord("h"), curses.KEY_RIGHT, ord("l")):
                try:
                    self.move(visible, -1 if key in (curses.KEY_LEFT, ord("h")) else 1)
                except (OSError, apps.ManifestError) as error:
                    self.status = f"APPLICATION NOT MOVED: {error}"
                continue
            if key == 27:
                return
            if key not in (curses.KEY_ENTER, 10, 13):
                continue
            if self.selected < len(visible):
                self.edit(visible[self.selected])
            elif self.selected == len(visible):
                self.add_command()
            elif self.selected == len(visible) + 1:
                self.add_web()
            else:
                return


def main(screen: curses.window) -> None:
    Launcher(screen).run()


if __name__ == "__main__":
    curses.wrapper(main)
