# MoonlightOS v1.1

MoonlightOS is a Debian 13 (Trixie) x86_64 gaming-streaming appliance. It boots
directly into a small controller-friendly launcher for Moonlight, chiaki-ng,
and Firefox ESR, with an allowlist-only Linux USB/IP server. It is not a
general-purpose desktop.

> Testing status: source/static and QEMU application tests are automated. The
> physical Dell OptiPlex DCC36X3 validation matrix must be completed before
> calling this a production image. See [TESTING.md](docs/TESTING.md).

## What v1.1 contains

- Debian standard kernel, systemd, NetworkManager, nftables, PipeWire, ALSA
- IPv4-only wired networking; IPv6 is disabled in v1.1
- Intel i915, Mesa Vulkan, VA-API, and Intel media-driver packages
- Cage as the direct DRM/KMS Wayland kiosk compositor; no desktop environment
- Moonlight Qt 6.1.0 and chiaki-ng 1.10.0 pinned by SHA256
- Firefox ESR from Debian 13, running natively on Wayland with a persistent profile
- black-and-white full-screen terminal launcher with keyboard and common gamepad navigation
- systemd crash recovery for the launcher, streaming applications, and Firefox
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
build/out/moonlightos-1.1-amd64.iso
build/out/moonlightos-1.1-amd64.iso.sha256
```

`scripts/fetch-apps.sh` downloads only the versions in
`build/applications.lock` and rejects a hash mismatch. `build/configure.sh`
extracts their pinned payloads into the read-only image so runtime FUSE is not
required. Firefox is installed from Debian's signed repositories during the
image build. No application binary is committed to Git.

## First boot

1. Connect DisplayPort/HDMI, wired Ethernet, and a controller or keyboard.
2. Press `F12` on the Dell, select the UEFI USB device, and wait three seconds.
3. The launcher appears even without network; select Moonlight, chiaki-ng, or
   Firefox.
4. Pair Sunshine once in Moonlight. Tailscale setup, when wanted, uses an
   on-screen QR code.

That is the complete live-image setup. For durable settings, select `Install`
from the boot menu and follow [INSTALL.md](docs/INSTALL.md). Installation keeps
the disk-selection confirmation because silently erasing a disk is unsafe.

The installed system preserves application configuration normally. A live USB
needs a separate persistence partition; installation is the supported durable
mode for v1.1. Local LAN streaming and the launcher do not depend on Tailscale.

## Target hardware

The first target is Dell OptiPlex 7010 Micro, service tag DCC36X3: Core
i5-13500T, UHD 770, 16 GB DDR4-3200, 256 GB NVMe, gigabit Ethernet, and wired
DisplayPort/HDMI. The image works with the current 1x16 GB DIMM. A matched 2x8
GB dual-channel kit is preferred because the integrated GPU shares system
memory bandwidth.

Targets are 1080p60, 1080p120 where supported, 1440p60, and best-effort 4K60
SDR. 4K HDR is deliberately unclaimed until the exact TV, adapter, cable, and
display path are tested.

## Configuration map

| Purpose | Persistent path |
|---|---|
| Launcher/default profile | `/var/lib/moonlightos/config.ini` |
| Network, host profiles, and Tailscale | `/var/lib/moonlightos/config.ini` |
| Moonlight host list/pairing | `/var/lib/moonlightos/home/.config/` |
| chiaki-ng registration | `/var/lib/moonlightos/home/.config/` |
| Firefox profile, bookmarks, and settings | `/var/lib/moonlightos/home/.mozilla/` |
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
