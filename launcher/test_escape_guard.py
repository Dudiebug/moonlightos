import importlib.util
import pathlib
import unittest


class EscapeGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).with_name("escape-guard.py")
        spec = importlib.util.spec_from_file_location("escape_guard", path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_three_fast_taps_trigger_once(self):
        detector = self.module.TripleTapDetector(window=0.85)
        self.assertFalse(detector.press(1.00))
        self.assertFalse(detector.press(1.25))
        self.assertTrue(detector.press(1.60))
        self.assertFalse(detector.press(1.70))

    def test_slow_taps_do_not_trigger(self):
        detector = self.module.TripleTapDetector(window=0.85)
        self.assertFalse(detector.press(1.00))
        self.assertFalse(detector.press(1.50))
        self.assertFalse(detector.press(2.00))

    def test_new_sequence_can_trigger_after_reset(self):
        detector = self.module.TripleTapDetector(window=0.85)
        detector.reset()
        self.assertFalse(detector.press(5.00))
        self.assertFalse(detector.press(5.20))
        self.assertTrue(detector.press(5.40))


if __name__ == "__main__":
    unittest.main()
