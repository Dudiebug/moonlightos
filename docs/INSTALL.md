# Installation

## Create the USB installer

Verify the image first:

```bash
cd build/out
sha256sum --check moonlightos-0.1.0-alpha-amd64.iso.sha256
```

Write the hybrid ISO to a whole USB device. **The selected device is erased.**
Resolve the exact target with `lsblk` before running this example:

```bash
sudo dd if=moonlightos-0.1.0-alpha-amd64.iso of=/dev/sdX bs=4M \
  status=progress conv=fsync
```

## Install to the OptiPlex SSD

1. Back up the SSD. Disconnect other writable drives where practical.
2. Enter Dell firmware setup, select UEFI boot, and boot the USB device.
3. Choose `Install` from the boot menu. The image includes Debian Installer in
   live mode; it copies the configured appliance system to the SSD.
4. Select the 256 GB NVMe only. Guided partitioning with an EFI System
   Partition and ext4 root is the v0.1 reference layout.
5. Reboot, remove the USB, and confirm the MoonlightOS launcher appears.
6. Run `moonlightos-diagnostics`, pair applications, reboot, and confirm the
   host lists remain.

The installed root filesystem is writable in v0.1. Pairings, settings, and
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
