import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock


class Screen:
    def __init__(self, keys=()):
        self.keys = list(keys)

    def getmaxyx(self):
        return 30, 100

    def erase(self):
        pass

    def border(self, *_args):
        pass

    def addstr(self, *_args):
        pass

    def addnstr(self, *_args):
        pass

    def refresh(self):
        pass

    def timeout(self, *_args):
        pass

    def keypad(self, *_args):
        pass

    def getch(self):
        if not self.keys:
            raise RuntimeError("stop")
        return self.keys.pop(0)


class LauncherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).with_name("moonlightos-launcher.py")
        spec = importlib.util.spec_from_file_location("launcher", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def launcher(self):
        with mock.patch.object(self.module, "network_summary", return_value="OFFLINE"):
            return self.module.Launcher(Screen())

    def test_ipv4_helpers(self):
        sample = "lo UNKNOWN 127.0.0.1/8\nenp2s0 UP 192.168.50.27/24\n"
        self.assertEqual(self.module.get_ipv4(sample), "192.168.50.27")
        self.assertEqual(self.module.get_ipv4(""), "NO IPV4")

    def test_default_application_order_includes_terminal(self):
        launcher = self.launcher()
        self.assertEqual(
            [label for label, _action in launcher.menu],
            ["MOONLIGHT", "CHIAKI-NG", "FIREFOX", "TERMINAL", "TAILSCALE", "SETTINGS", "REBOOT", "SHUTDOWN"],
        )

    def test_custom_order_and_disabled_visibility(self):
        application = self.module.apps.Application
        result = self.module.apps.LoadResult(
            (
                application(id="disabled", name="DISABLED", kind="command", command="/bin/true", status_id="disabled", enabled=False, order=1),
                application(id="custom", name="CUSTOM", kind="command", command="/bin/true", status_id="custom", order=2),
            ),
            (),
        )
        with mock.patch.object(self.module, "application_result", return_value=result), mock.patch.object(
            self.module, "network_summary", return_value="OFFLINE"
        ):
            launcher = self.module.Launcher(Screen())
        self.assertEqual(launcher.menu[0], ("CUSTOM", "custom"))
        self.assertNotIn("DISABLED", [label for label, _action in launcher.menu])
        self.assertEqual(launcher.menu[-3:], list(self.module.FIXED_CONTROLS))

    def test_invalid_manifests_do_not_crash_startup(self):
        result = self.module.apps.LoadResult((), ("bad.ini: invalid",))
        with mock.patch.object(self.module, "application_result", return_value=result), mock.patch.object(
            self.module, "network_summary", return_value="OFFLINE"
        ):
            launcher = self.module.Launcher(Screen())
        self.assertIn("INVALID", launcher.status)

    def test_request_application_retains_request_marker(self):
        app = self.module.apps.Application(
            id="moonlight", name="MOONLIGHT", kind="request", request="start-moonlight",
            status_id="moonlight",
        )
        launcher = self.launcher()
        launcher.screen = Screen()
        with tempfile.TemporaryDirectory() as directory:
            run = pathlib.Path(directory)
            launcher.request = mock.Mock(side_effect=lambda _name: (run / "moonlight-ready").touch())
            with mock.patch.object(self.module, "RUN", run):
                self.assertTrue(launcher.launch_app(app))
        launcher.request.assert_called_once_with("start-moonlight")

    def test_command_application_uses_configured_request(self):
        app = self.module.apps.Application(
            id="terminal", name="TERMINAL", kind="command", command="/bin/bash",
            status_id="terminal", terminal=True,
        )
        launcher = self.launcher()
        launcher.screen = Screen()
        with tempfile.TemporaryDirectory() as directory:
            run = pathlib.Path(directory)

            def write(_path, content):
                self.assertEqual(content, "terminal\n")
                (run / "terminal-ready").touch()

            with mock.patch.object(self.module, "RUN", run), mock.patch.object(
                self.module.apps, "atomic_write", side_effect=write
            ):
                self.assertTrue(launcher.launch_app(app))

    def test_application_settings_reload_launcher_menu(self):
        launcher = self.launcher()
        launcher.selected = len(launcher.applications)
        launcher.reload_applications = mock.Mock()
        with mock.patch.object(self.module.Settings, "run"):
            launcher.activate()
        launcher.reload_applications.assert_called_once_with()

    def test_launcher_ready_precedes_first_boot_wizard(self):
        launcher = self.launcher()
        launcher.screen = Screen()
        launcher.prepare_session = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            run = pathlib.Path(directory)
            launcher.setup_wizard = mock.Mock(side_effect=lambda: self.assertTrue((run / "launcher-ready").exists()))
            with mock.patch.object(self.module, "RUN", run), mock.patch.object(
                self.module.display, "restore_saved_mode"
            ), mock.patch.object(self.module.curses, "curs_set"), mock.patch.object(
                self.module.curses, "use_default_colors"
            ):
                with self.assertRaisesRegex(RuntimeError, "stop"):
                    launcher.run()
        launcher.setup_wizard.assert_called_once_with()

    def test_settings_contains_applications_and_setup(self):
        self.assertIn("APPLICATIONS", self.module.SETTINGS_MENU)
        self.assertIn("SETUP WIZARD", self.module.SETTINGS_MENU)
        self.assertFalse(hasattr(self.module.Launcher, "terminal_command"))

    def test_progress_helpers(self):
        self.assertEqual(len(self.module.indeterminate_progress_bar(24, 0)), 24)
        self.assertEqual(self.module.format_elapsed(65.9), "01:05")


if __name__ == "__main__":
    unittest.main()
