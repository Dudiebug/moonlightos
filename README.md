# MoonlightOS v0.1.10

MoonlightOS is a Debian 13 (Trixie) x86_64 gaming-streaming appliance. It boots
directly into a small controller-friendly launcher for Moonlight, chiaki-ng,
Firefox ESR, and official Google Chrome, with an allowlist-only Linux USB/IP server. It is not a
general-purpose desktop.

> Testing status: source/static and QEMU application tests are automated. The
> physical Dell OptiPlex DCC36X3 validation matrix must be completed before
> calling this a production image. See [TESTING.md](docs/TESTING.md).

## What v0.1.10 contains

- Debian standard kernel, systemd, NetworkManager, nftables, PipeWire, ALSA
- IPv4-only networking; IPv6 is disabled in v0.1.10
- Named-device Bluetooth discovery and PipeWire output selection
- Home/Guide managed application resume and close controls
- Standard Firefox EME/Widevine readiness and safe diagnostics
- Intel i915, Mesa Vulkan, VA-API, and Intel media-driver packages
- Cage as the direct DRM/KMS Wayland kiosk compositor; no desktop environment
- Moonlight Qt 6.1.0 and chiaki-ng 1.10.0 pinned to fixed release URLs
- Firefox ESR from Debian 13, running natively on Wayland with a persistent profile
- Official Google Chrome Stable from Google's signed Debian repository, with a persistent profile
- black-and-white full-screen terminal launcher with keyboard and common gamepad navigation
- matching high-contrast UEFI/BIOS boot menus and dark text installer
- controller-friendly Bluetooth management inside Settings, backed by BlueZ
- continuous Bluetooth discovery while its settings screen is open
- a first-boot Setup Wizard that can be rerun from Settings
- manifest-driven system, custom command, and custom web applications
- isolated full-screen Terminal, Tailscale, network, and diagnostics processes
- a controller-triggered full-screen buffered keyboard (Guide/Home + X/Square)
- broader controller device rules from Debian's `steam-devices` package; Steam itself is not installed
- Bluetooth controller input through evdev and opt-in Bluetooth audio through PipeWire/WirePlumber
- controller-friendly display settings based only on modes advertised by Cage/wlroots
- 15-second display-mode preview with confirmation, rollback, and display-identity-safe persistence
- redacted support archives exported to validated writable removable media by a restricted system service
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
build/out/moonlightos-0.1.10-amd64.iso
```

`scripts/fetch-apps.sh` downloads only the fixed versions and HTTPS URLs in
`build/applications.lock`. `build/configure.sh`
extracts their pinned payloads into the read-only image so runtime FUSE is not
required. Firefox is installed from Debian's signed repositories and Google
Chrome Stable from Google's signed repository during the image build. No
application binary is committed to Git.

## First boot

1. Connect DisplayPort/HDMI, wired Ethernet, and a controller or keyboard.
2. Press `F12` on the Dell, select the UEFI USB device, and wait three seconds.
3. The launcher becomes ready even without network, then the first-boot Setup
   Wizard opens. Complete, skip, or exit it before choosing an application.
4. Pair Sunshine once in Moonlight. Bluetooth devices are managed in Settings.
   Tailscale setup, when wanted, uses an
   on-screen QR code.

That is the complete live-image setup. The same hybrid ISO offers persistent
live boot, an explicit `No Persistence` recovery entry, and `Install
MoonlightOS` for installation to another disk. For durable settings, select
the installer entry and follow [INSTALL.md](docs/INSTALL.md). Installation keeps
the disk-selection confirmation because silently erasing a disk is unsafe.

The installed system preserves application configuration normally. A live USB
needs a separate persistence partition containing `persistence.conf` with
distinct backing directories. A live USB must also persist
`/var/lib/bluetooth` for Bluetooth pairings to survive reboot. UEFI installation
and independent virtual-disk boot are automated; Rufus, Ventoy, physical NVMe,
and second-USB installation remain physical validation items. Local LAN
streaming and the launcher do not depend on Tailscale or Bluetooth.

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
| Google Chrome profile, bookmarks, and settings | `/var/lib/moonlightos/home/.config/google-chrome/` |
| Launcher controller identity | `/var/lib/moonlightos/launcher-controller.id` |
| Bluetooth power preference | `/var/lib/moonlightos/bluetooth-enabled` |
| Application manifests and state | `/var/lib/moonlightos/apps.d/`, `/var/lib/moonlightos/apps-state.ini` |
| Setup completion | `/var/lib/moonlightos/setup-complete` |
| BlueZ pairing state (contains secrets) | `/var/lib/bluetooth/` |
| USB/IP allowlist policy | `/etc/moonlightos/usbip-allowlist.conf` |
| Logs and diagnostics | `/var/log/moonlightos/` |

The Settings screen can generate a support archive on a mounted writable
removable filesystem, an explicitly labeled `MOONLIGHTOS_SUPPORT` partition,
or a writable live-USB persistence partition. It never writes to an internal
SATA/NVMe filesystem. See [Support export](docs/SUPPORT.md).

More documentation:

- [Installation](docs/INSTALL.md)
- [Hardware and performance](docs/HARDWARE.md)
- [Sunshine and Moonlight](docs/SUNSHINE.md)
- [chiaki-ng registration](docs/CHIAKI.md)
- [USB/IP server and Linux host client](docs/USBIP.md)
- [Optional Tailscale overlay](docs/networking/tailscale.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Support export](docs/SUPPORT.md)
- [Testing and QEMU](docs/TESTING.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Roadmap](ROADMAP.md)

## License

Original MoonlightOS code is GPL-3.0-or-later. Bundled programs retain their
own licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
