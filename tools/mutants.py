#!/usr/bin/env python3
"""Small auditable mutation check for the real-ISO keyboard driver."""

from __future__ import annotations

import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests" / "qemu_iso_boot.py"
MUTANTS = (
    (
        "wrong installer menu index",
        'commands = [("sendkey home", 0.25)] * 60\n    commands += [("sendkey down", 0.15)] * 3',
        'commands = [("sendkey home", 0.25)] * 60\n    commands += [("sendkey down", 0.15)] * 2',
    ),
    (
        "skip editor line movement",
        '("sendkey down", 0.5),\n        ("sendkey end", 0.1),',
        '("sendkey end", 0.1),',
    ),
    (
        "drop uppercase modifier",
        'return f"shift-{character.lower()}"',
        'return character.lower()',
    ),
    (
        "type underscore as hyphen",
        '"_": "shift-minus",',
        '"_": "minus",',
    ),
)


def clear_bytecode() -> None:
    for cache in (TARGET.parent / "__pycache__").glob("qemu_iso_boot.*.pyc"):
        cache.unlink()


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")
    killed = 0
    try:
        for name, before, after in MUTANTS:
            if original.count(before) != 1:
                raise RuntimeError(f"mutation anchor is not unique: {name}")
            TARGET.write_text(original.replace(before, after), encoding="utf-8")
            clear_bytecode()
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "-q", "tests/test_qemu_iso_boot.py"],
                cwd=ROOT,
                check=False,
            )
            if result.returncode == 0:
                print(f"SURVIVED: {name}", file=sys.stderr)
            else:
                killed += 1
                print(f"killed: {name}")
            TARGET.write_text(original, encoding="utf-8")
            clear_bytecode()
    finally:
        TARGET.write_text(original, encoding="utf-8")
        clear_bytecode()

    print(f"manual mutation: {killed}/{len(MUTANTS)} killed")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
