import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock


class LauncherHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).with_name("moonlightos-launcher.py")
        spec = importlib.util.spec_from_file_location("launcher", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.get_ipv4 = staticmethod(cls.module.get_ipv4)

    def test_ipv4_extracts_first_address_from_legacy_output(self):
        sample = "2: eno1    inet 192.0.2.12/24 brd 192.0.2.255 scope global\n"
        self.assertEqual(self.get_ipv4(sample), "192.0.2.12")

    def test_ipv4_extracts_brief_address_and_ignores_loopback(self):
        sample = (
            "lo               UNKNOWN        127.0.0.1/8\n"
            "enp2s0           UP             192.168.50.27/24\n"
        )
        self.assertEqual(self.get_ipv4(sample), "192.168.50.27")

    def test_ipv4_loopback_only_is_offline(self):
        self.assertEqual(
            self.get_ipv4("lo               UNKNOWN        127.0.0.1/8\n"),
            "NO IPV4",
        )

    def test_ipv4_absent(self):
        self.assertEqual(self.get_ipv4(""), "NO IPV4")

    def test_reference_style_menu_order(self):
        labels = [label for label, _action in self.module.MENU]
        self.assertEqual(
            labels,
            [
                "MOONLIGHT",
                "CHIAKI-NG",
                "FIREFOX",
                "TAILSCALE",
                "SETTINGS",
                "REBOOT",
                "SHUTDOWN",
            ],
        )

    def test_firefox_menu_uses_launch_feedback_path(self):
        launcher = object.__new__(self.module.Launcher)
        launcher.selected = 2
        launcher.launch_app = mock.Mock(return_value=True)
        launcher.activate()
        launcher.launch_app.assert_called_once_with("firefox")

    def test_terminal_command_keyboard_interrupt_restores_launcher(self):
        launcher = object.__new__(self.module.Launcher)
        launcher.restore_curses = mock.Mock()
        with mock.patch.object(self.module.curses, "def_prog_mode"), mock.patch.object(
            self.module.curses, "endwin"
        ), mock.patch.object(
            self.module.subprocess, "run", side_effect=KeyboardInterrupt
        ):
            self.assertEqual(launcher.terminal_command(["example"]), 130)
        launcher.restore_curses.assert_called_once_with()

    def test_tailscale_return_restores_launcher_runtime_state(self):
        launcher = object.__new__(self.module.Launcher)
        launcher.selected = 3
        launcher.request = mock.Mock()
        launcher.terminal_command = mock.Mock(return_value=0)
        launcher.prepare_session = mock.Mock()
        with mock.patch.object(self.module.time, "monotonic", return_value=55.0), mock.patch.object(
            self.module.os, "getuid", return_value=1000
        ), mock.patch.object(self.module.pathlib.Path, "lstat", side_effect=FileNotFoundError):
            launcher.activate()
        launcher.request.assert_called_once_with("tailscale-enroll")
        launcher.terminal_command.assert_called_once_with(["moonlightos-tailscale-enrollment"])
        launcher.prepare_session.assert_called_once_with()
        self.assertEqual(launcher.status, "TAILSCALE CONNECTED")
        self.assertEqual(launcher.last_status_update, 55.0)

    def test_tailscale_interrupt_leaves_useful_status(self):
        launcher = object.__new__(self.module.Launcher)
        launcher.selected = 3
        launcher.request = mock.Mock()
        launcher.terminal_command = mock.Mock(return_value=130)
        launcher.prepare_session = mock.Mock()
        with mock.patch.object(self.module.time, "monotonic", return_value=55.0), mock.patch.object(
            self.module.os, "getuid", return_value=1000
        ), mock.patch.object(self.module.pathlib.Path, "lstat", side_effect=FileNotFoundError):
            launcher.activate()
        self.assertEqual(launcher.status, "TAILSCALE SETUP CLOSED")
        launcher.prepare_session.assert_called_once_with()

    def test_tailscale_removes_stale_url_before_request(self):
        launcher = object.__new__(self.module.Launcher)
        launcher.selected = 3
        launcher.terminal_command = mock.Mock(return_value=130)
        launcher.prepare_session = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            run = pathlib.Path(directory)
            stale = run / "tailscale-auth-url"
            stale.write_text("https://login.tailscale.com/a/stale\n", encoding="utf-8")
            launcher.request = mock.Mock(side_effect=lambda _name: self.assertFalse(stale.exists()))
            with mock.patch.object(self.module, "RUN", run), mock.patch.object(
                self.module.time, "monotonic", return_value=55.0
            ):
                launcher.activate()
        launcher.request.assert_called_once_with("tailscale-enroll")

    def test_settings_menu_and_keyboard_navigation(self):
        self.assertEqual(
            self.module.SETTINGS_MENU,
            (
                "RESOLUTION",
                "REFRESH RATE",
                "APPLY DISPLAY MODE",
                "GENERATE SUPPORT FILE",
                "SYSTEM DIAGNOSTICS",
                "BACK",
            ),
        )
        self.assertEqual(self.module.move_selection(0, self.module.curses.KEY_DOWN, 6), 1)
        self.assertEqual(self.module.move_selection(0, self.module.curses.KEY_UP, 6), 5)

    def test_settings_entry_opens_curses_screen(self):
        launcher = object.__new__(self.module.Launcher)
        launcher.selected = 4
        launcher.screen = mock.Mock()
        launcher.terminal_command = mock.Mock()
        with mock.patch.object(self.module.Settings, "run") as run:
            launcher.activate()
            run.assert_called_once_with()

    def test_support_progress_bar_is_fixed_width_and_moves(self):
        first = self.module.indeterminate_progress_bar(24, 0)
        later = self.module.indeterminate_progress_bar(24, 5)
        self.assertEqual(len(first), 24)
        self.assertEqual(len(later), 24)
        self.assertTrue(first.startswith("[") and first.endswith("]"))
        self.assertEqual(first.count("="), later.count("="))
        self.assertNotEqual(first, later)

    def test_support_elapsed_time_format(self):
        self.assertEqual(self.module.format_elapsed(0), "00:00")
        self.assertEqual(self.module.format_elapsed(65.9), "01:05")

    def support_destination(self):
        return self.module.support.Destination(
            "/dev/sdb1", "/media/usb", "SUPPORT", "vfat", True
        )

    def support_settings(self):
        screen = mock.Mock()
        screen.getmaxyx.return_value = (24, 80)
        settings = self.module.Settings(screen, mock.Mock())
        settings.draw_support_progress = mock.Mock()
        settings.show_message = mock.Mock()
        return settings, screen

    def test_support_export_success_is_reported(self):
        settings, screen = self.support_settings()
        destination = self.support_destination()
        with mock.patch.object(
            self.module.support, "discover_destinations", return_value=[destination]
        ), mock.patch.object(
            self.module.support, "submit_request", return_value="request-id"
        ), mock.patch.object(
            self.module.support,
            "read_status",
            return_value={
                "request_id": "request-id",
                "state": "success",
                "message": "Support file created",
                "destination": "/media/usb/support.tar.gz",
            },
        ), mock.patch.object(
            self.module.time, "monotonic", side_effect=[100.0, 100.1]
        ):
            settings.generate_support_file()
        settings.show_message.assert_called_once_with(
            "SUPPORT FILE CREATED", "Support file created. SAVED: /media/usb/support.tar.gz"
        )
        self.assertEqual(settings.status, "SAVED: /media/usb/support.tar.gz")
        self.assertIn(mock.call(1000), screen.timeout.call_args_list)

    def test_support_export_worker_failure_is_reported(self):
        settings, _screen = self.support_settings()
        destination = self.support_destination()
        with mock.patch.object(
            self.module.support, "discover_destinations", return_value=[destination]
        ), mock.patch.object(
            self.module.support, "submit_request", return_value="request-id"
        ), mock.patch.object(
            self.module.support,
            "read_status",
            return_value={
                "request_id": "request-id",
                "state": "failed",
                "message": "destination disappeared",
                "destination": "",
            },
        ), mock.patch.object(
            self.module.time, "monotonic", side_effect=[100.0, 100.1]
        ):
            settings.generate_support_file()
        settings.show_message.assert_called_once_with(
            "SUPPORT EXPORT FAILED", "destination disappeared"
        )
        self.assertEqual(settings.status, "EXPORT FAILED: destination disappeared")

    def test_support_export_missing_service_is_reported(self):
        settings, _screen = self.support_settings()
        destination = self.support_destination()
        with mock.patch.object(
            self.module.support, "discover_destinations", return_value=[destination]
        ), mock.patch.object(
            self.module.support, "submit_request", return_value="request-id"
        ), mock.patch.object(
            self.module.support, "read_status", return_value=None
        ), mock.patch.object(
            self.module, "SUPPORT_EXPORT_START_TIMEOUT", 0.0
        ), mock.patch.object(
            self.module.time, "monotonic", side_effect=[100.0, 100.0]
        ):
            settings.generate_support_file()
        title, failure = settings.show_message.call_args.args
        self.assertEqual(title, "SUPPORT EXPORT FAILED")
        self.assertIn("DID NOT REPORT STARTUP", failure)
        self.assertEqual(settings.status, "EXPORT FAILED: SERVICE DID NOT START")

    def test_support_export_missing_usb_is_reported(self):
        settings, _screen = self.support_settings()
        with mock.patch.object(
            self.module.support, "discover_destinations", return_value=[]
        ):
            settings.generate_support_file()
        settings.show_message.assert_called_once_with(
            "USB DRIVE NOT FOUND", "CONNECT A WRITABLE REMOVABLE USB DRIVE AND TRY AGAIN"
        )
        self.assertEqual(settings.status, "SUPPORT EXPORT FAILED: NO WRITABLE USB DRIVE")

    def display_fixture(self):
        mode_type = self.module.display.Mode
        output_type = self.module.display.Output
        old = mode_type(3840, 2160, 60000, current=True)
        target = mode_type(1920, 1080, 120000)
        original = output_type("DP-1", "Dell ABC123", True, (old, target))
        target_current = mode_type(1920, 1080, 120000, current=True)
        applied = output_type(
            "DP-1",
            "Dell ABC123",
            True,
            (mode_type(3840, 2160, 60000), target_current),
        )
        return original, old, target, applied

    def test_display_preview_timeout_rolls_back(self):
        original, old, target, applied = self.display_fixture()
        screen = mock.Mock()
        screen.getch.return_value = -1
        settings = self.module.Settings(screen, mock.Mock())
        settings.output = original
        settings.original_mode = old
        settings.resolution = target.resolution
        settings.refresh_mhz = target.refresh_mhz
        settings.draw = mock.Mock()

        def validate(_name, _identity, requested):
            return (original, old) if requested.resolution == old.resolution else (applied, target)

        with mock.patch.object(
            self.module.display, "valid_output_mode", side_effect=validate
        ), mock.patch.object(self.module.display, "apply_mode") as apply, mock.patch.object(
            self.module.display, "log"
        ), mock.patch.object(
            self.module.time, "monotonic", side_effect=[0, 0, 0, 16]
        ):
            settings.apply_preview()
        self.assertEqual(apply.call_count, 4)
        self.assertEqual(apply.call_args_list[-1].args[1].resolution, old.resolution)
        self.assertFalse(apply.call_args_list[-1].kwargs.get("dryrun", False))

    def test_display_preview_enter_confirms_and_saves(self):
        original, old, target, applied = self.display_fixture()
        screen = mock.Mock()
        screen.getch.return_value = 10
        settings = self.module.Settings(screen, mock.Mock())
        settings.output = original
        settings.original_mode = old
        settings.resolution = target.resolution
        settings.refresh_mhz = target.refresh_mhz
        settings.draw = mock.Mock()

        with mock.patch.object(
            self.module.display, "valid_output_mode", return_value=(applied, target)
        ), mock.patch.object(self.module.display, "apply_mode"), mock.patch.object(
            self.module.display, "save_display"
        ) as save, mock.patch.object(self.module.display, "log"), mock.patch.object(
            self.module.time, "monotonic", side_effect=[0, 0, 0]
        ), mock.patch.object(settings, "refresh_outputs", return_value=True):
            settings.apply_preview()
        save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
