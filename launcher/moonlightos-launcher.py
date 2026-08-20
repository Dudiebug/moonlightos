#!/usr/bin/python3
"""Small GTK appliance launcher; Cage supplies the full-screen Wayland shell."""

from __future__ import annotations

import configparser
import pathlib
import subprocess
import time


def get_ipv4(output: str) -> str:
    for line in output.splitlines():
        fields = line.split()
        if "inet" in fields:
            value = fields[fields.index("inet") + 1]
            return value.split("/", 1)[0]
    return "No IPv4 address"


import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

DATA = pathlib.Path("/var/lib/moonlightos")
RUN = pathlib.Path("/run/moonlightos")
CONFIG = DATA / "config.ini"


class Launcher(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id="org.moonlightos.Launcher")
        self.autostart_done = False

    def do_activate(self) -> None:
        window = Gtk.ApplicationWindow(application=self, title="MoonlightOS")
        window.fullscreen()

        css = Gtk.CssProvider()
        css.load_from_data(b"""
            window { background: #0b1220; color: #eef4ff; }
            .title { font-size: 34px; font-weight: 700; }
            .status { font-size: 17px; color: #9db4d4; }
            button { min-height: 48px; min-width: 390px; margin: 4px; font-size: 19px; }
            button:focus { outline: 4px solid #78b7ff; }
        """)
        Gtk.StyleContext.add_provider_for_display(
            window.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label="MoonlightOS")
        title.add_css_class("title")
        box.append(title)

        self.status = Gtk.Label(label=self._network_status())
        self.status.add_css_class("status")
        box.append(self.status)

        actions = [
            ("Start Moonlight", "moonlight"),
            ("Start Chiaki-ng", "chiaki"),
            ("Settings / diagnostics", "diagnostics"),
            ("Enable Tailscale", "tailscale"),
            ("Tailscale diagnostics", "tailscale-diagnostics"),
            ("Enable Tailscale SSH", "tailscale-ssh"),
            ("Reboot", "reboot"),
            ("Shutdown", "poweroff"),
        ]
        first = None
        for label, action in actions:
            button = Gtk.Button(label=label)
            button.connect("clicked", self._clicked, action)
            box.append(button)
            first = first or button
        window.set_child(box)
        window.present()
        print("MOONLIGHTOS_LAUNCHER_READY", flush=True)
        first.grab_focus()
        GLib.timeout_add_seconds(5, self._refresh_network)
        GLib.idle_add(self._autostart)

    def _network_status(self) -> str:
        result = subprocess.run(
            ["ip", "-brief", "-4", "address", "show", "up"],
            text=True, capture_output=True, check=False
        )
        selected = subprocess.run(
            ["moonlightos-host-address"], text=True, capture_output=True, check=False
        ).stdout.strip()
        return f"Ethernet: {get_ipv4(result.stdout)}\n{selected or 'Sunshine: no host configured'}"

    def _refresh_network(self) -> bool:
        self.status.set_label(self._network_status())
        return True

    def _request(self, name: str) -> None:
        RUN.mkdir(mode=0o750, parents=True, exist_ok=True)
        (RUN / name).touch()

    def _clicked(self, _button: Gtk.Button, action: str) -> None:
        mapping = {
            "moonlight": "start-moonlight",
            "chiaki": "start-chiaki",
            "reboot": "reboot",
            "poweroff": "poweroff",
            "tailscale": "tailscale-enroll",
            "tailscale-ssh": "tailscale-ssh-enable",
        }
        if action in mapping:
            self._request(mapping[action])
        elif action == "diagnostics":
            subprocess.Popen(["foot", "--title=MoonlightOS diagnostics", "moonlightos-diagnostics", "--watch"])
        elif action == "tailscale-diagnostics":
            subprocess.Popen(["foot", "--hold", "--title=Tailscale diagnostics", "moonlightos-tailscale-diagnostics"])
        if action == "tailscale":
            subprocess.Popen(["foot", "--title=Tailscale enrollment", "moonlightos-tailscale-enrollment"])

    def _autostart(self) -> bool:
        if self.autostart_done:
            return False
        self.autostart_done = True
        config = configparser.ConfigParser()
        config.read(CONFIG)
        if config.get("launcher", "autostart", fallback="moonlight") == "moonlight":
            # Give Cage and the path units time to settle.
            time.sleep(1)
            self._request("start-moonlight")
        return False


if __name__ == "__main__":
    raise SystemExit(Launcher().run())
