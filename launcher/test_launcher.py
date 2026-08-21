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

    def test_ipv4_extracts_first_address(self):
        sample = "2: eno1    inet 192.0.2.12/24 brd 192.0.2.255 scope global\n"
        self.assertEqual(self.get_ipv4(sample), "192.0.2.12")

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

    def test_firefox_menu_requests_service(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            self.module, "RUN", pathlib.Path(directory)
        ):
            launcher = object.__new__(self.module.Launcher)
            launcher.selected = 2
            launcher.activate()
            self.assertTrue((pathlib.Path(directory) / "start-firefox").exists())

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
