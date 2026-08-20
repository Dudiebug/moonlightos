import importlib.util
import pathlib
import unittest


class LauncherHelpersTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).with_name("moonlightos-launcher.py")
        spec = importlib.util.spec_from_file_location("launcher", path)
        cls.module = importlib.util.module_from_spec(spec)
        # Avoid importing GTK in this host-side helper test.
        source = path.read_text()
        prefix = source.split("import gi", 1)[0]
        namespace = {}
        exec(prefix, namespace)
        cls.get_ipv4 = staticmethod(namespace["get_ipv4"])

    def test_ipv4_extracts_first_address(self):
        sample = "2: eno1    inet 192.0.2.12/24 brd 192.0.2.255 scope global\n"
        self.assertEqual(self.get_ipv4(sample), "192.0.2.12")

    def test_ipv4_absent(self):
        self.assertEqual(self.get_ipv4(""), "No IPv4 address")


if __name__ == "__main__":
    unittest.main()
