#!/usr/bin/python3
"""PipeWire output discovery and selection for the launcher."""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess


@dataclasses.dataclass(frozen=True)
class Sink:
    id: int
    name: str
    default: bool = False


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
SINK_RE = re.compile(r"^[\s│├└─]*(\*)?\s*(\d+)\.\s+(.+?)(?:\s+\[[^]]*\])?\s*$")


def parse_sinks(output: str) -> list[Sink]:
    sinks: list[Sink] = []
    in_sinks = False
    for raw in output.splitlines():
        line = ANSI_RE.sub("", raw)
        if re.search(r"\bSinks:\s*$", line):
            in_sinks = True
            continue
        if in_sinks and re.match(r"^[\s│├└─]*[A-Za-z][A-Za-z ]+:\s*$", line):
            break
        if not in_sinks:
            continue
        match = SINK_RE.match(line)
        if match:
            name = re.sub(r"\s+\[[^]]*\]\s*$", "", match.group(3)).strip()
            sinks.append(Sink(int(match.group(2)), name, bool(match.group(1))))
    return sinks


def query_sinks() -> list[Sink]:
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    result = subprocess.run(
        ["wpctl", "status"], text=True, capture_output=True, check=False,
        timeout=5, env=environment,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or "wpctl status failed").strip())
    return parse_sinks(result.stdout)


def set_default(sink_id: int) -> None:
    result = subprocess.run(
        ["wpctl", "set-default", str(sink_id)], text=True, capture_output=True,
        check=False, timeout=5,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or "wpctl set-default failed").strip())
