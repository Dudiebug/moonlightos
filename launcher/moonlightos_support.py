#!/usr/bin/python3
"""Discover safe support-export destinations and submit export requests."""

from __future__ import annotations

import json
import os
import pathlib
import re
import secrets
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from typing import Callable


RUN = pathlib.Path("/run/moonlightos")
REQUEST = RUN / "support-export.request"
STATUS = RUN / "support-export.status"
UNWRITABLE_FILESYSTEMS = {"", "iso9660", "squashfs", "udf"}


@dataclass(frozen=True)
class Destination:
    device: str
    mountpoint: str
    label: str
    fstype: str
    mounted: bool
    majmin: str = ""
    uuid: str = ""

    @property
    def display_name(self) -> str:
        label = safe_terminal_text(self.label or pathlib.Path(self.device).name)
        location = safe_terminal_text(self.mountpoint or self.device)
        return f"{label}  {location}"


def safe_terminal_text(value: str, limit: int = 96) -> str:
    value = re.sub(r"[^A-Za-z0-9 /_.:+()-]", "?", value)
    return value[:limit]


def _bool(value: object) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes"}


def _mountpoints(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.startswith("/")]
    if isinstance(value, str) and value.startswith("/"):
        return [value]
    return []


def destinations_from_lsblk(
    data: dict[str, object], writable: Callable[[str], bool]
) -> list[Destination]:
    found: list[Destination] = []

    def walk(node: dict[str, object], parent_external: bool = False) -> None:
        transport = str(node.get("tran") or "").lower()
        path = str(node.get("path") or "")
        removable = _bool(node.get("rm"))
        external = parent_external or removable or transport == "usb"
        explicitly_internal = transport in {"ata", "sata", "nvme"} and not removable
        if explicitly_internal:
            external = False

        fstype = str(node.get("fstype") or "").lower()
        label = str(node.get("label") or "")
        read_only = _bool(node.get("ro"))
        node_type = str(node.get("type") or "")
        majmin = str(node.get("maj:min") or node.get("maj_min") or "")
        uuid = str(node.get("uuid") or "")
        mountpoints = _mountpoints(node.get("mountpoints") or node.get("mountpoint"))
        eligible_type = node_type in {"part", "crypt", "lvm"} or (
            node_type == "disk" and bool(fstype)
        )
        if external and eligible_type and not read_only and fstype not in UNWRITABLE_FILESYSTEMS:
            for mountpoint in mountpoints:
                if mountpoint != "/run/live/medium" and writable(mountpoint):
                    found.append(Destination(path, mountpoint, label, fstype, True, majmin, uuid))
            if not mountpoints and label == "MOONLIGHTOS_SUPPORT":
                found.append(Destination(path, "", label, fstype, False, majmin, uuid))

        for child in node.get("children") or []:
            if isinstance(child, dict):
                walk(child, external)

    for device in data.get("blockdevices") or []:
        if isinstance(device, dict):
            walk(device)

    unique = {(item.device, item.mountpoint): item for item in found}
    return sorted(
        unique.values(),
        key=lambda item: (
            not item.mounted,
            item.label != "MOONLIGHTOS_SUPPORT",
            item.label != "persistence",
            item.device,
            item.mountpoint,
        ),
    )


def path_is_writable(path: str) -> bool:
    try:
        stats = os.statvfs(path)
        return pathlib.Path(path).is_dir() and not bool(stats.f_flag & os.ST_RDONLY)
    except OSError:
        return False


def discover_destinations() -> list[Destination]:
    result = subprocess.run(
        [
            "lsblk",
            "--json",
            "--output",
            "PATH,TYPE,TRAN,RM,RO,FSTYPE,LABEL,UUID,MAJ:MIN,MOUNTPOINTS",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=8,
    )
    if result.returncode:
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return destinations_from_lsblk(data, path_is_writable)


def submit_request(destination: Destination) -> str:
    RUN.mkdir(mode=0o750, parents=True, exist_ok=True)
    request_id = secrets.token_hex(12)
    payload = asdict(destination) | {"request_id": request_id}
    descriptor, temporary = tempfile.mkstemp(prefix=".support-request.", dir=RUN)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, REQUEST)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return request_id


def read_status(request_id: str) -> dict[str, str] | None:
    try:
        if STATUS.stat().st_size > 8192 or STATUS.is_symlink():
            return None
        payload = json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("request_id") != request_id:
        return None
    return {str(key): safe_terminal_text(str(value), 240) for key, value in payload.items()}
