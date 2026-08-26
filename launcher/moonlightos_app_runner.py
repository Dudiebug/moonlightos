#!/usr/bin/python3
"""Run one validated configured application without a shell."""

from __future__ import annotations

import os
import pathlib
import shlex
import signal
import subprocess
import sys
import tempfile
import time

import moonlightos_apps as apps


RUN = pathlib.Path("/run/moonlightos")
REQUEST = RUN / "launch-app.request"
READY_SECONDS = 5.0


def atomic_status(path: pathlib.Path, value: str) -> None:
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o640)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value.rstrip("\n") + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def read_request(path: pathlib.Path = REQUEST) -> str:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 64:
            raise ValueError("request is not a bounded regular file")
        app_id = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as error:
        raise ValueError(f"cannot read request: {error}") from error
    if not apps.ID_RE.fullmatch(app_id):
        raise ValueError("invalid application id")
    return app_id


def command_vector(app: apps.Application) -> list[str]:
    if app.kind != "command" or not pathlib.PurePath(app.command).is_absolute():
        raise ValueError("application is not a configured command")
    try:
        arguments = shlex.split(app.arguments, posix=True)
    except ValueError as error:
        raise ValueError(f"invalid command arguments: {error}") from error
    command = [app.command, *arguments]
    if app.terminal:
        return ["/usr/bin/foot", "--fullscreen", "--title", app.name, "--", *command]
    return command


def configured_environment(app: apps.Application) -> dict[str, str]:
    environment = os.environ.copy()
    for name, value in app.environment.items():
        if not apps.ENV_RE.fullmatch(name):
            raise ValueError(f"invalid environment name: {name}")
        environment[name] = value
    return environment


def run(request_path: pathlib.Path = REQUEST) -> int:
    app_id = "configured-app"
    status = RUN / f"{app_id}-status"
    ready = RUN / f"{app_id}-ready"
    active = RUN / "app-active"
    close = RUN / f"close-{app_id}"
    process: subprocess.Popen[bytes] | None = None
    received_signal = 0
    close_requested = False

    def stop(signum: int, _frame: object) -> None:
        nonlocal received_signal
        received_signal = signum
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signum)
            except ProcessLookupError:
                pass

    previous = {signum: signal.signal(signum, stop) for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        try:
            app_id = read_request(request_path)
        finally:
            request_path.unlink(missing_ok=True)
        status = RUN / f"{app_id}-status"
        ready = RUN / f"{app_id}-ready"
        result = apps.load_applications()
        app = next((item for item in result.applications if item.id == app_id), None)
        if app is None or not app.enabled:
            raise ValueError("requested application is missing or disabled")
        # Reload the selected file itself so the runner never trusts launcher state.
        if app.path is None:
            raise ValueError("requested application has no manifest")
        app = apps.read_manifest(app.path, system=app.system)
        if app.id != app_id:
            raise ValueError("application manifest changed during launch")
        status = RUN / f"{app.status_id}-status"
        ready = RUN / f"{app.status_id}-ready"
        close = RUN / f"close-{app.status_id}"
        close.unlink(missing_ok=True)
        ready.unlink(missing_ok=True)
        atomic_status(status, "starting")
        if not pathlib.Path(app.command).is_file() or not os.access(app.command, os.X_OK):
            raise FileNotFoundError("application executable is missing")
        vector = command_vector(app)
        active.write_text(app.id + "\n", encoding="ascii")
        os.chmod(active, 0o640)
        process = subprocess.Popen(
            vector,
            env=configured_environment(app),
            start_new_session=True,
        )
        deadline = time.monotonic() + READY_SECONDS
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        if process.poll() is None:
            ready.touch(mode=0o640)
            atomic_status(status, "started")
        while process.poll() is None:
            if close.exists():
                close_requested = True
                close.unlink(missing_ok=True)
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                break
            time.sleep(0.1)
        rc = process.wait()
        if close_requested:
            rc = 0
        if received_signal:
            rc = 128 + received_signal
        if ready.exists():
            atomic_status(status, f"exited: status {rc}")
        else:
            atomic_status(status, f"failed: exited before the application became ready (status {rc})")
        return rc
    except (OSError, ValueError, apps.ManifestError) as error:
        atomic_status(status, f"failed: {error}")
        print(f"Configured application failed: {error}", file=sys.stderr)
        return 66
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        ready.unlink(missing_ok=True)
        close.unlink(missing_ok=True)
        try:
            if active.read_text(encoding="ascii").strip() == app_id:
                active.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(run())
