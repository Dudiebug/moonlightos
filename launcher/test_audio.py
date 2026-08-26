import unittest
from unittest import mock

import moonlightos_audio as audio


STATUS = """PipeWire 'pipewire-0' [1.2.7]
 └─ Clients:
Audio
 ├─ Devices:
 ├─ Sinks:
 │  *   42. Built-in Audio Analog Stereo  [vol: 0.50]
 │      57. WH-1000XM5                    [vol: 1.00]
 ├─ Sources:
"""


class AudioTest(unittest.TestCase):
    def test_parse_sinks_preserves_friendly_names_and_default(self):
        self.assertEqual(
            audio.parse_sinks(STATUS),
            [
                audio.Sink(42, "Built-in Audio Analog Stereo", True),
                audio.Sink(57, "WH-1000XM5", False),
            ],
        )

    def test_set_default_uses_wpctl_without_shell(self):
        with mock.patch.object(audio.subprocess, "run") as run:
            run.return_value.returncode = 0
            audio.set_default(57)
        self.assertEqual(run.call_args.args[0], ["wpctl", "set-default", "57"])


if __name__ == "__main__":
    unittest.main()
