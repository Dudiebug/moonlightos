# Testing

## Automated source tests

```bash
make test
```

These tests validate shell/Python syntax, service references, no obvious secret
patterns, locked artifact hashes, default-deny Tailscale/USB-IP settings, and a
fake-sysfs USB allowlist case. They do not require a tailnet.

## QEMU ISO smoke test

```bash
sudo apt install qemu-system-x86 ovmf
make qemu-smoke
```

The script boots `build/out/moonlightos-0.1.0-alpha-amd64.iso` with serial
output, a virtual Ethernet NIC, and UEFI when OVMF is available. Success means
the boot reached the MoonlightOS launcher service marker. QEMU does not prove
Intel VA-API, display audio, gamepad, USB/IP hardware, or streaming.

The test boots through UEFI rather than injecting the kernel directly. It must
reach the launcher marker without depending on DHCP. GRUB also mirrors output
to a 115200-baud serial console so bootloader failures appear in CI logs. The
test creates a disposable writable copy of `OVMF_VARS`; supplying OVMF code
without its variable store is not a valid UEFI test setup.

On failure, CI retains the serial log and a QEMU framebuffer screenshot. The
test also extracts `/boot/grub/grub.cfg` from the ISO and verifies the appliance
timeout and serial settings before starting the VM.

Success requires `MOONLIGHTOS_LAUNCHER_READY`, emitted only after GTK presents
the full-screen launcher window. Launcher output is mirrored to the boot console
for CI while remaining available in `/var/log/moonlightos/launcher.log`.

## Installed-system QEMU procedure

Create a disposable 24 GB disk, boot the ISO with a graphical QEMU display,
and complete Debian Installer manually:

```bash
qemu-img create -f qcow2 build/out/moonlightos-install-test.qcow2 24G
qemu-system-x86_64 -enable-kvm -m 4096 -cpu host \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE.fd \
  -cdrom build/out/moonlightos-0.1.0-alpha-amd64.iso \
  -drive file=build/out/moonlightos-install-test.qcow2,if=virtio \
  -device virtio-vga -display gtk \
  -netdev user,id=net0 -device virtio-net-pci,netdev=net0
```

After reboot, verify launcher/app exit/crash recovery and compare hashes of
`/var/lib/moonlightos/config.ini` before/after reboot.

## Physical DCC36X3 checklist (must be recorded, never inferred)

- [ ] 1080p60 Moonlight stream for 30 minutes
- [ ] 1080p120 on a compatible display
- [ ] 1440p60 on a compatible display
- [ ] 4K60 SDR best effort over DisplayPort
- [ ] chiaki-ng registration, connection, and gameplay
- [ ] HDMI/DP audio and wired controller input
- [ ] One exact allowlisted specialty USB/IP device
- [ ] Ethernet interruption and recovery
- [ ] Pairing/configuration survives cold reboot

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
