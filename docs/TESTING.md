# Testing

## Automated source tests

```bash
make test
```

These tests validate shell/Python syntax, service references, no obvious secret
patterns, fixed artifact versions/URLs, default-deny Tailscale/USB-IP settings, and a
fake-sysfs USB allowlist case. Focused tests also cover display-mode parsing,
valid resolution/refresh pairs, missing connectors/modes, changed display
identity, malformed configuration preservation, Settings navigation, controller
mapping, support redaction, removable-media policy, safe archive streaming,
atomic copy, checked unmount ordering, failed-copy cleanup, Bluetooth protocol
validation, BlueZ object parsing, pairing-agent callbacks, and Bluetooth UI
recovery. They do not require a tailnet or Bluetooth adapter.
The v0.1.11 cases also cover manifest isolation and atomic state, configured-app
argv/environment construction, separate Foot wrapping, setup completion,
buffered-keyboard navigation and payload validation, and the Guide+X chord.

## QEMU ISO smoke test

```bash
sudo apt install qemu-system-x86 ovmf
make qemu-smoke
```

The script boots `build/out/moonlightos-0.1.11-amd64.iso` with serial
output, a virtual Ethernet NIC, and UEFI when OVMF is available. Success means
the boot reached the MoonlightOS launcher service marker. QEMU does not prove
Intel VA-API, physical Bluetooth behavior, display audio, gamepad, USB/IP
hardware, or streaming.

The test boots through UEFI rather than injecting the kernel directly. It must
reach the launcher marker without depending on DHCP. GRUB also mirrors output
to a 115200-baud serial console so bootloader failures appear in CI logs. The
test creates a disposable writable copy of `OVMF_VARS`; supplying OVMF code
without its variable store is not a valid UEFI test setup.
On systems where OVMF is unpacked outside the standard locations, set both
`MOONLIGHTOS_OVMF_CODE` and `MOONLIGHTOS_OVMF_VARS` to readable firmware files.

On failure, CI retains the serial log and a QEMU framebuffer screenshot. The
test also extracts `/boot/grub/grub.cfg` from the ISO and verifies the appliance
timeout and serial settings before starting the VM.

Success requires `MOONLIGHTOS_LAUNCHER_READY`, emitted only after foot presents
the full-screen curses launcher. A QEMU-only firmware flag then starts the three
production application services and requires `MOONLIGHTOS_APP_STARTED moonlight`,
`MOONLIGHTOS_APP_STARTED chiaki-ng`, `MOONLIGHTOS_APP_STARTED firefox`, and a
five-second `google-chrome-ready` marker from the generic application runner
after each real application remains alive for five seconds. It also proves the
Bluetooth control service handles an absent adapter and survives restarts of
BlueZ and its own service without changing the launcher or audio-session PID
and restart counts.
Launcher output is
mirrored to the boot console and remains available in
`/var/log/moonlightos/launcher.log`.

## Installed-system QEMU smoke test

```bash
make qemu-install-smoke
```

This test starts in OVMF, boots the built ISO as removable media, selects the
ISO's visible `Install MoonlightOS` GRUB entry, and adds only a test-preseed URL
to that entry. It installs to a disposable 32 GiB UEFI virtual disk, boots that
disk without the ISO, writes a configuration marker, cold-boots the disk again,
and requires the marker and `MOONLIGHTOS_LAUNCHER_READY`. Passing an extracted
kernel or initrd directly to QEMU is forbidden by the static suite.
The install and installed-boot logs default to
`/tmp/moonlightos-qemu-install.log` and
`/tmp/moonlightos-qemu-installed-boot.log`; the selected menu, edited kernel
line, dark installer, installed launcher, and exact VM command are captured
beside them.

For an interactive install, create a disposable disk, boot the ISO with a
graphical QEMU display, and complete Debian Installer manually:

```bash
qemu-img create -f qcow2 build/out/moonlightos-install-test.qcow2 32G
qemu-system-x86_64 -enable-kvm -m 4096 -cpu host \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE.fd \
  -cdrom build/out/moonlightos-0.1.11-amd64.iso \
  -drive file=build/out/moonlightos-install-test.qcow2,if=virtio \
  -device virtio-vga -display gtk \
  -netdev user,id=net0 -device virtio-net-pci,netdev=net0
```

After reboot, verify launcher/app exit/crash recovery and confirm the saved
`/var/lib/moonlightos/config.ini` values remain unchanged.

The automated install test proves the public UEFI ISO/menu installation path,
an independent installed boot, and configuration persistence across a cold
reboot. It does not prove
physical NVMe, USB destination selection, Rufus, or Ventoy behavior.

## Live-persistence QEMU smoke test

```bash
make qemu-persistence-smoke
```

This test creates an ext4 backend with the documented `persistence.conf`, boots
the release ISO twice, and verifies MoonlightOS, Moonlight, chiaki-ng,
Tailscale, BlueZ, and log state across reboot. A third boot passes
`nopersistence` while the same backend remains attached and verifies that none
of its test state is visible.

## Deployment-mode checklist

- [x] One `iso-hybrid` artifact contains live and Debian Installer paths
- [x] UEFI QEMU live boot reaches the launcher
- [x] UEFI QEMU installs to a virtual disk
- [x] Installed virtual disk boots without the ISO and reaches the launcher
- [x] Installed virtual-disk configuration survives a cold reboot
- [x] Live boot without a persistence device
- [x] Live persistence survives reboot for Moonlight, chiaki-ng, Tailscale,
      and BlueZ state
- [x] `No Persistence` ignores an existing persistence backend
- [ ] Invalid and full persistence backends fail diagnostically
- [ ] Rufus DD/Image-mode USB boot on physical UEFI hardware
- [ ] Ventoy normal-mode live boot and installer entry
- [ ] Ventoy persistence backend across reboot
- [ ] Install to physical internal NVMe/SATA
- [ ] Install from USB #1 to USB #2 and boot USB #2 independently

## Physical DCC36X3 checklist (must be recorded, never inferred)

Display settings:

- [ ] Change to another advertised resolution and confirm within 15 seconds
- [ ] Change refresh rate to another advertised rate and confirm
- [ ] Let a preview time out and verify automatic rollback
- [ ] Cancel a preview with Escape/controller east and verify rollback
- [ ] Confirm a non-default mode, reboot, and verify persistence
- [ ] Change the monitor/adapter and verify compositor-default fallback/no black screen
- [ ] Navigate every Settings action using the intended controller

Applications and acceleration:

- [ ] 1080p60 Moonlight stream for 30 minutes
- [ ] 1080p120 on a compatible display
- [ ] 1440p60 on a compatible display
- [ ] 4K60 SDR best effort over DisplayPort
- [ ] chiaki-ng registration, connection, and gameplay
- [ ] HDMI/DP audio and wired controller input
- [ ] One exact allowlisted specialty USB/IP device
- [ ] Ethernet interruption and recovery
- [ ] Pairing/configuration survives cold reboot
- [ ] Closing Moonlight returns to the launcher
- [ ] Closing chiaki-ng returns to the launcher
- [ ] Closing Firefox returns to the launcher
- [ ] Closing Google Chrome returns to the launcher
- [ ] Confirm Widevine protected playback in Google Chrome and record Disney+ behavior separately
- [ ] Exit and Ctrl+D close Terminal and return to the launcher
- [ ] Ctrl+C in Terminal, nmtui, diagnostics, and Tailscale does not interrupt the launcher
- [ ] Guide/Home + X/Square opens the buffered keyboard over each supported application
- [ ] TYPE and TYPE + ENTER inject expected text after focus returns
- [ ] Record `vainfo`, `vulkaninfo --summary`, `wpctl status`, and `aplay -l`

Support export:

- [ ] Export to a second writable removable USB and verify exactly one readable archive
- [ ] Inspect the extracted archive for secrets
- [ ] Export to a configured boot-USB persistence partition
- [ ] Confirm the ISO9660 boot filesystem is not offered
- [ ] Attach two writable removable targets and use the controller selector
- [ ] Confirm the internal NVMe is never offered, without writing test data to it

Bluetooth (record every unperformed item as untested):

- [ ] Detect the Bluetooth adapter and turn Bluetooth off/on
- [ ] Scan, cancel scanning, and confirm discovery stops
- [ ] Pair an Xbox Wireless Controller, if available
- [ ] Pair a DualSense controller, if available
- [ ] Pair a Switch Pro Controller, if available
- [ ] Pair a second controller while the first continues navigating the launcher
- [ ] Pair a Bluetooth keyboard
- [ ] Complete numeric-confirmation and PIN/passkey pairing
- [ ] Pair Bluetooth headphones or a speaker and select its audio sink
- [ ] Confirm HDMI/DP audio remains selectable
- [ ] Disconnect, reconnect, forget, and re-pair a device
- [ ] Reboot and confirm pairing state and automatic reconnection survive
- [ ] Confirm Bluetooth audio reconnects without forcibly becoming the default
- [ ] Restart `bluetooth.service` and `moonlightos-bluetooth.service`
- [ ] Unplug the adapter while scanning, reinsert it, and recover
- [ ] Unplug the adapter while pairing, reinsert it, and recover
- [ ] Confirm the launcher PID and restart count do not change
- [ ] Launch and exit Moonlight after Bluetooth configuration
- [ ] Launch and exit chiaki-ng after Bluetooth configuration
- [ ] Launch and exit Firefox after Bluetooth configuration

Installed systems retain BlueZ state under `/var/lib/bluetooth`. Live USB
persistence must include that directory for pairings to survive reboot. Never
copy its contents into a support archive because it contains link keys.

## Opt-in live Tailscale checklist

- [ ] Moonlight launches normally with Tailscale disabled
- [ ] Local enrollment displays a URL and state survives reboot
- [ ] MagicDNS resolves when `accept_dns = true`
- [ ] Tailscale IP fallback works without MagicDNS
- [ ] Sunshine streams over a direct Tailscale path
- [ ] Relay warning appears for peer-relay or DERP
- [ ] Tailscale SSH is unavailable before opt-in
- [ ] Authorized admin SSH works; unauthorized identity is denied by policy
- [ ] Unauthorized peer cannot reach TCP/3240
- [ ] USB/IP stays LAN-only until both remote guards are set
- [ ] Tailscale/tailscaled failure does not stop local streaming
- [ ] chiaki-ng still reaches the local PlayStation
- [ ] No auth key, login URL, or machine key appears in persistent logs/artifacts

Live tailnet tests are intentionally absent from CI and must be invoked only in
a disposable, explicitly authorized test tailnet.
