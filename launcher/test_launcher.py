import importlib.util
import pathlib
import unittest


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
            ["MOONLIGHT", "CHIAKI-NG", "TAILSCALE", "SETTINGS", "REBOOT", "SHUTDOWN"],
        )


if __name__ == "__main__":
    unittest.main()
