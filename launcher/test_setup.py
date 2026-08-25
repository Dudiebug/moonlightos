import pathlib
import tempfile
import unittest
from unittest import mock

import moonlightos_setup as setup


class WizardTest(unittest.TestCase):
    def wizard(self, marker):
        return setup.SetupWizard(mock.Mock(), {}, {}, marker=marker)

    def test_missing_marker_opens_wizard_and_skip_writes_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = pathlib.Path(directory) / "setup-complete"
            wizard = self.wizard(marker)
            wizard.choose = mock.Mock(return_value=1)
            self.assertTrue(wizard.run())
            self.assertEqual(marker.read_text(), "1\n")
            self.assertEqual(marker.stat().st_mode & 0o777, 0o640)

    def test_exit_does_not_write_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = pathlib.Path(directory) / "setup-complete"
            wizard = self.wizard(marker)
            wizard.choose = mock.Mock(return_value=2)
            wizard.run()
            self.assertFalse(marker.exists())

    def test_completed_setup_does_not_automatically_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = pathlib.Path(directory) / "setup-complete"
            marker.write_text("1\n")
            wizard = self.wizard(marker)
            wizard.choose = mock.Mock()
            self.assertFalse(wizard.run())
            wizard.choose.assert_not_called()

    def test_finish_writes_marker_and_step_action_uses_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = pathlib.Path(directory) / "setup-complete"
            action = mock.Mock()
            wizard = setup.SetupWizard(mock.Mock(), {"network": action}, {}, marker=marker)
            # Welcome/start, network action, then continue/skip through each step, finish.
            choices = [0, 0, *([2] * len(setup.STEPS)), 1]
            wizard.choose = mock.Mock(side_effect=choices)
            wizard.run()
            action.assert_called_once_with()
            self.assertTrue(marker.exists())

    def test_every_normal_step_has_back_continue_and_skip(self):
        for _step_id, _title, action in setup.STEPS:
            controls = setup.SetupWizard.controls(action)
            self.assertEqual(controls[-3:], ["BACK", "CONTINUE", "SKIP"])

    def test_back_from_network_returns_to_welcome(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = pathlib.Path(directory) / "setup-complete"
            wizard = self.wizard(marker)
            wizard.choose = mock.Mock(side_effect=[0, 1, 2])
            wizard.run()
            self.assertEqual(wizard.choose.call_count, 3)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
