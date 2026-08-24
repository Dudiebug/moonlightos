import pathlib
import tempfile
import unittest
from unittest import mock

import moonlightos_app_runner as runner
import moonlightos_apps as apps


class RunnerTest(unittest.TestCase):
    def app(self, **changes):
        base = apps.Application(
            id="demo", name="DEMO", kind="command", command="/bin/sleep",
            arguments="0.02", status_id="demo", environment={"DEMO_VALUE": "safe"},
        )
        return apps.dataclasses.replace(base, **changes)

    def test_argument_vector_and_terminal_wrapper(self):
        self.assertEqual(runner.command_vector(self.app(arguments="1 'two words'")), ["/bin/sleep", "1", "two words"])
        self.assertEqual(
            runner.command_vector(self.app(terminal=True))[:6],
            ["/usr/bin/foot", "--fullscreen", "--title", "DEMO", "--", "/bin/sleep"],
        )

    def test_environment_is_applied_without_losing_base_environment(self):
        with mock.patch.dict(runner.os.environ, {"BASE": "kept"}, clear=True):
            environment = runner.configured_environment(self.app())
        self.assertEqual(environment["BASE"], "kept")
        self.assertEqual(environment["DEMO_VALUE"], "safe")

    def test_request_id_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "request"
            path.write_text("../bad\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "invalid"):
                runner.read_request(path)

    def test_run_creates_ready_and_exit_status_and_cleans_active(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = root / "demo.ini"
            manifest.write_text(apps.serialize(self.app()), encoding="utf-8")
            app = apps.read_manifest(manifest)
            request = root / "launch-app.request"
            request.write_text("demo\n", encoding="ascii")
            real_status = runner.atomic_status
            ready_seen = []

            def record_status(path, value):
                if value == "started":
                    ready_seen.append((root / "demo-ready").exists())
                real_status(path, value)

            with mock.patch.object(runner, "RUN", root), mock.patch.object(
                runner, "READY_SECONDS", 0.0
            ), mock.patch.object(
                runner.apps, "load_applications", return_value=apps.LoadResult((app,), ())
            ), mock.patch.object(runner, "atomic_status", side_effect=record_status):
                self.assertEqual(runner.run(request), 0)
            self.assertEqual(ready_seen, [True])
            self.assertEqual((root / "demo-status").read_text(), "exited: status 0\n")
            self.assertFalse((root / "app-active").exists())
            self.assertFalse((root / "demo-ready").exists())

    def test_missing_command_writes_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            app_value = self.app(command="/missing/demo")
            manifest = root / "demo.ini"
            manifest.write_text(apps.serialize(app_value), encoding="utf-8")
            app = apps.read_manifest(manifest)
            request = root / "launch-app.request"
            request.write_text("demo\n", encoding="ascii")
            with mock.patch.object(runner, "RUN", root), mock.patch.object(
                runner.apps, "load_applications", return_value=apps.LoadResult((app,), ())
            ):
                self.assertEqual(runner.run(request), 66)
            self.assertIn("executable is missing", (root / "demo-status").read_text())

    def test_subprocess_is_never_invoked_through_a_shell(self):
        process = mock.Mock()
        process.poll.return_value = 0
        process.wait.return_value = 0
        app = self.app(path=pathlib.Path("/tmp/demo.ini"))
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = root / "demo.ini"
            manifest.write_text(apps.serialize(app), encoding="utf-8")
            loaded = apps.read_manifest(manifest)
            request = root / "request"
            request.write_text("demo\n")
            with mock.patch.object(runner, "RUN", root), mock.patch.object(
                runner.apps, "load_applications", return_value=apps.LoadResult((loaded,), ())
            ), mock.patch.object(runner.pathlib.Path, "is_file", return_value=True), mock.patch.object(
                runner.os, "access", return_value=True
            ), mock.patch.object(runner.subprocess, "Popen", return_value=process) as popen:
                runner.run(request)
        self.assertNotIn("shell", popen.call_args.kwargs)

    def test_signal_is_forwarded_and_markers_are_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = root / "demo.ini"
            manifest.write_text(apps.serialize(self.app()), encoding="utf-8")
            loaded = apps.read_manifest(manifest)
            request = root / "request"
            request.write_text("demo\n")
            handlers = {}
            process = mock.Mock(pid=123)
            process.poll.return_value = None
            process.wait.side_effect = lambda: (handlers[runner.signal.SIGTERM](runner.signal.SIGTERM, None), -15)[1]

            def install(signum, handler):
                handlers[signum] = handler
                return runner.signal.SIG_DFL

            with mock.patch.object(runner, "RUN", root), mock.patch.object(
                runner, "READY_SECONDS", 0.0
            ), mock.patch.object(
                runner.apps, "load_applications", return_value=apps.LoadResult((loaded,), ())
            ), mock.patch.object(runner.subprocess, "Popen", return_value=process), mock.patch.object(
                runner.signal, "signal", side_effect=install
            ), mock.patch.object(runner.os, "killpg") as killpg:
                self.assertEqual(runner.run(request), 143)
            killpg.assert_called_once_with(123, runner.signal.SIGTERM)
            self.assertFalse((root / "app-active").exists())
            self.assertFalse((root / "demo-ready").exists())


if __name__ == "__main__":
    unittest.main()
