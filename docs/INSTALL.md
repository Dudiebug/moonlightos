# Installation

## Create the USB installer

Write the hybrid ISO to a whole USB device. **The selected device is erased.**
Resolve the exact target with `lsblk` before running this example:

```bash
sudo dd if=moonlightos-0.1.7-amd64.iso of=/dev/sdX bs=4M \
  status=progress conv=fsync
```

## Install to the OptiPlex SSD

1. Back up the SSD. Disconnect other writable drives where practical.
2. Press `F12` at power-on and select the entry beginning with `UEFI` for the
   USB device. The live appliance starts automatically after three seconds.
3. Choose `Install` from the boot menu. The image includes Debian Installer in
   live mode; it copies the configured appliance system to the SSD.
4. Select the 256 GB NVMe only. Guided partitioning with an EFI System
   Partition and ext4 root is the v0.1.7 reference layout.
5. Reboot, remove the USB, and confirm the MoonlightOS launcher appears.
6. Run `moonlightos-diagnostics`, pair applications, reboot, and confirm the
   host lists remain.

The first-boot wizard can open the existing `nmtui` network setup; wired DHCP
remains automatic and IPv6 is disabled.
The launcher is deliberately not held behind network-online, so it must appear
even with Ethernet unplugged. Streaming applications wait briefly for IPv4 but
remain launchable after a DHCP timeout.

If the USB is absent from the `F12` menu, rewrite the ISO directly to the whole
USB device (not a partition), and try another USB port.
Do not use a file-copy operation. If the boot menu appears but the launcher does
not, photograph the last screen and include it in an issue.

The installed root filesystem is writable in v0.1.7. Pairings, settings, and
logs live beneath `/var/lib/moonlightos` and `/var/log/moonlightos`.

## Optional live-USB persistence

Installation is preferred. For testing, create an ext4 partition labeled
`persistence` in the USB's remaining space and put this at its root:

```text
/var/lib/moonlightos source=.
/var/log/moonlightos source=.
/var/lib/tailscale source=.
```

The ISO already boots with the `persistence` parameter. Do not use an
unencrypted persistent USB for sensitive pairing data outside a trusted lab.
