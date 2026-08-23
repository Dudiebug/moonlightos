import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEWER = ROOT / "scripts" / "moonlightos-tailscale-enrollment"


class TailscaleEnrollmentViewerTest(unittest.TestCase):
    def run_viewer(self, tailscale_script: str, url: str = "") -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            commands = root / "bin"
            commands.mkdir()
            counter = root / "counter"
            url_file = root / "auth-url"
            if url:
                url_file.write_text(url + "\n", encoding="utf-8")

            (commands / "tailscale").write_text(tailscale_script, encoding="utf-8")
            (commands / "systemctl").write_text(
                "#!/bin/bash\nexit 1\n", encoding="utf-8"
            )
            (commands / "qrencode").write_text(
                "#!/bin/bash\necho '[QR]'\n", encoding="utf-8"
            )
            for command in commands.iterdir():
                command.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{commands}:{environment['PATH']}",
                    "MOONLIGHTOS_TAILSCALE_URL_FILE": str(url_file),
                    "MOONLIGHTOS_TAILSCALE_POLL_SECONDS": "0",
                    "MOONLIGHTOS_TAILSCALE_URL_WAIT_SECONDS": "4",
                    "TEST_COUNTER": str(counter),
                }
            )
            return subprocess.run(
                [str(VIEWER)], text=True, capture_output=True, env=environment, timeout=5
            )

    def test_already_connected_ignores_old_url(self):
        result = self.run_viewer(
            '#!/bin/bash\nprintf \'%s\\n\' \'{"BackendState":"Running"}\'\n',
            "https://login.tailscale.com/a/stale",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Tailscale is connected", result.stdout)
        self.assertNotIn("stale", result.stdout)

    def test_successful_authentication_returns_automatically(self):
        result = self.run_viewer(
            """#!/bin/bash
count=0
[[ -r $TEST_COUNTER ]] && count=$(< "$TEST_COUNTER")
count=$((count + 1))
printf '%s\n' "$count" > "$TEST_COUNTER"
if ((count >= 2)); then
  printf '%s\n' '{"BackendState":"Running"}'
else
  printf '%s\n' '{"BackendState":"NeedsLogin"}'
fi
""",
            "https://login.tailscale.com/a/current",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Or open this address:"), 1)
        self.assertIn("Tailscale is connected", result.stdout)


if __name__ == "__main__":
    unittest.main()
