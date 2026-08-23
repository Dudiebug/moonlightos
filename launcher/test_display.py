import pathlib
import tempfile
import unittest
from unittest import mock

import moonlightos_display as display


SAMPLE = '''DP-1 "Dell Inc. DELL U2723QE ABC123"
  Enabled: yes
  Modes:
    3840x2160 px, 60.000000 Hz (preferred, current)
    3840x2160 px, 30.000000 Hz
    1920x1080 px, 120.000000 Hz
    1920x1080 px, 60.000000 Hz
HDMI-A-1 "Sony TV XYZ"
  Enabled: no
  Modes:
    1920x1080 px, 60.000000 Hz (preferred)
'''


class DisplayTest(unittest.TestCase):
    def test_parses_only_advertised_output_modes(self):
        outputs = display.parse_wlr_randr(SAMPLE)
        self.assertEqual([item.name for item in outputs], ["DP-1", "HDMI-A-1"])
        self.assertEqual(outputs[0].current_mode.argument, "3840x2160@60Hz")
        self.assertEqual(len(outputs[0].modes), 4)
        self.assertFalse(outputs[1].enabled)

    def test_invalid_resolution_refresh_combination_is_absent(self):
        output = display.parse_wlr_randr(SAMPLE)[0]
        self.assertIsNone(display.find_mode(output, "3840x2160", 120000))
        self.assertIsNotNone(display.find_mode(output, "1920x1080", 120000))

    def test_connector_disappearance_prevents_restore(self):
        saved = {
            "output": "DP-1",
            "identity": display.parse_wlr_randr(SAMPLE)[0].identity,
            "resolution": "1920x1080",
            "refresh_mhz": "120000",
        }
        with mock.patch.object(display, "load_saved_display", return_value=saved), mock.patch.object(
            display, "query_outputs", return_value=[]
        ), mock.patch.object(display, "apply_mode") as apply:
            self.assertFalse(display.restore_saved_mode())
            apply.assert_not_called()

    def test_saved_mode_disappearance_prevents_restore(self):
        output = display.parse_wlr_randr(SAMPLE)[0]
        saved = {
            "output": "DP-1",
            "identity": output.identity,
            "resolution": "2560x1440",
            "refresh_mhz": "60000",
        }
        with mock.patch.object(display, "load_saved_display", return_value=saved), mock.patch.object(
            display, "query_outputs", return_value=[output]
        ), mock.patch.object(display, "apply_mode") as apply:
            self.assertFalse(display.restore_saved_mode())
            apply.assert_not_called()

    def test_changed_display_identity_prevents_restore(self):
        output = display.parse_wlr_randr(SAMPLE)[0]
        saved = {
            "output": "DP-1",
            "identity": "different-display",
            "resolution": "1920x1080",
            "refresh_mhz": "120000",
        }
        with mock.patch.object(display, "load_saved_display", return_value=saved), mock.patch.object(
            display, "query_outputs", return_value=[output]
        ), mock.patch.object(display, "apply_mode") as apply:
            self.assertFalse(display.restore_saved_mode())
            apply.assert_not_called()

    def test_save_preserves_malformed_unrelated_config(self):
        output = display.parse_wlr_randr(SAMPLE)[0]
        mode = display.find_mode(output, "1920x1080", 120000)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "config.ini"
            path.write_text("orphan malformed line\n[launcher]\nautostart = none\n", encoding="utf-8")
            display.save_display(output, mode, path)
            result = path.read_text(encoding="utf-8")
            self.assertIn("orphan malformed line", result)
            self.assertIn("[launcher]\nautostart = none", result)
            self.assertIn("[display]", result)
            self.assertIn("refresh_mhz = 120000", result)

    def test_apply_runs_dryrun_before_real_change(self):
        output = display.parse_wlr_randr(SAMPLE)[0]
        mode = display.find_mode(output, "1920x1080", 120000)
        completed = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(display.subprocess, "run", return_value=completed) as run:
            display.apply_mode(output, mode, dryrun=True)
            self.assertIn("--dryrun", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
