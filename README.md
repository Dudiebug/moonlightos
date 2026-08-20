# MoonlightOS v0.1.0-alpha

MoonlightOS is a Debian 13 (Trixie) x86_64 gaming-streaming appliance. It boots
directly into a small controller-friendly launcher for Moonlight and chiaki-ng,
with an allowlist-only Linux USB/IP server. It is not a general-purpose desktop.

> Alpha status: source/static tests are automated. The ISO and physical Dell
> OptiPlex DCC36X3 validation matrix must be completed before calling this a
> production image. See [TESTING.md](docs/TESTING.md).

## What v0.1 contains

- Debian standard kernel, systemd, NetworkManager, nftables, PipeWire, ALSA
- Intel i915, Mesa Vulkan, VA-API, and Intel media-driver packages
- Cage as the direct DRM/KMS Wayland kiosk compositor; no desktop environment
- Moonlight Qt 6.1.0 and chiaki-ng 1.10.0 pinned by SHA256
- GTK 4 launcher with keyboard and common gamepad navigation
- systemd crash recovery for the launcher and both streaming applications
- explicit USB/IP allowlist, hotplug reconciliation, and fail-closed TCP/3240
- optional, unauthenticated-by-default Tailscale overlay and native Tailscale SSH
- persistent settings and pairing data under `/var/lib/moonlightos`
- logs and diagnostic snapshots under `/var/log/moonlightos`
- Debian Installer integration for installation to an internal SSD

## Exact build command

On Debian 13 x86_64:

```bash
sudo apt update
sudo apt install --yes live-build curl ca-certificates xorriso squashfs-tools \
  grub-pc-bin grub-efi-amd64-bin mtools dosfstools
sudo make build
```

Output:

```text
build/out/moonlightos-0.1.0-alpha-amd64.iso
build/out/moonlightos-0.1.0-alpha-amd64.iso.sha256
```

`scripts/fetch-apps.sh` downloads only the versions in
`build/applications.lock` and rejects a hash mismatch. `build/configure.sh`
stages the live-build tree; no application binary is committed to Git.

## First boot

1. Prefer DisplayPort for 4K testing; connect wired Ethernet and a controller.
2. Boot the ISO in UEFI mode. It automatically enters the live appliance.
3. Moonlight opens by default. Exit it to return to the launcher.
4. Pair Sunshine from Moonlight's UI; no Sunshine IP is hardcoded.
5. For an installed, durable system, use the ISO boot menu's `Install` entry.
   Follow [INSTALL.md](docs/INSTALL.md) before selecting a target disk.

The installed system preserves application configuration normally. A live USB
needs a separate persistence partition; installation is the supported durable
mode for v0.1.

## Configuration map

| Purpose | Persistent path |
|---|---|
| Launcher/default profile | `/var/lib/moonlightos/config.ini` |
| Network, host profiles, and Tailscale | `/var/lib/moonlightos/config.ini` |
| Moonlight host list/pairing | `/var/lib/moonlightos/home/.config/` |
| chiaki-ng registration | `/var/lib/moonlightos/home/.config/` |
| Launcher controller identity | `/var/lib/moonlightos/launcher-controller.id` |
| USB/IP allowlist policy | `/etc/moonlightos/usbip-allowlist.conf` |
| Logs and diagnostics | `/var/log/moonlightos/` |

More documentation:

- [Installation](docs/INSTALL.md)
- [Hardware and performance](docs/HARDWARE.md)
- [Sunshine and Moonlight](docs/SUNSHINE.md)
- [chiaki-ng registration](docs/CHIAKI.md)
- [USB/IP server and Linux host client](docs/USBIP.md)
- [Optional Tailscale overlay](docs/networking/tailscale.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Testing and QEMU](docs/TESTING.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Roadmap](ROADMAP.md)

## License

Original MoonlightOS code is GPL-3.0-or-later. Bundled programs retain their
own licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
