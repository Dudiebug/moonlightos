# Support export

Open **Settings → Generate Support File** with a keyboard or controller. If
more than one safe destination is present, choose one with the D-pad and south
button. The launcher writes only
`/run/moonlightos/support-export.request`; the root-owned
`moonlightos-support-export.path` unit starts the narrowly scoped exporter.
The launcher has no sudo permission.

## Destination rules

The exporter accepts:

- an already mounted, writable partition on removable/USB storage;
- an unmounted removable partition whose exact filesystem label is
  `MOONLIGHTOS_SUPPORT` (mounted temporarily without SUID, device, or executable
  permissions); or
- a mounted writable `persistence` partition on the live boot USB.

It rejects ISO9660, squashfs, UDF, read-only media, the live ISO mount, and
internal SATA/NVMe filesystems. It does not format, repartition, run fsck, or
repair media. The selected device and mount are checked again immediately
before the archive is copied.

Keep at least 64 MiB free. A successful export creates exactly:

```text
moonlightos-support-YYYYMMDD-HHMMSSZ-<machine-id-prefix>.tar.gz
moonlightos-support-YYYYMMDD-HHMMSSZ-<machine-id-prefix>.tar.gz.sha256
```

The screen reports the final path. For a temporarily mounted labeled partition,
it reports the device and filename because the temporary mount is removed after
the export.

## Archive contents

The archive contains version/build time, date, uptime, kernel information, CPU,
memory, PCI/USB inventory, loaded modules, GPU/DRM/wlroots output state, Vulkan,
VA-API, PipeWire/WirePlumber, ALSA, NetworkManager, IPv4 addresses, routes, link
and DNS state, sanitized Tailscale state, USB/IP, nftables, relevant package
versions, MoonlightOS service status, failed units, the current-boot journal,
kernel log when permitted, regular text files from `/var/log/moonlightos`, and
a sanitized copy of `/var/lib/moonlightos/config.ini`.

`MANIFEST.sha256` hashes every collected file. The exporter verifies that
manifest before copying, copies to a hidden `.partial`, verifies the copied
archive and its hash, then atomically publishes the archive and checksum.
Incomplete output is removed on failure.

## Privacy boundary

The exporter omits browser/application profiles, pairing and registration
state, `/var/lib/moonlightos/home`, and `/var/lib/tailscale`. Its systemd unit
also makes both private-state directories inaccessible. Structured and plain
text redaction removes private keys, credentials, passwords, cookies, bearer
tokens, auth/API tokens, Tailscale keys, and Tailscale enrollment URLs. LAN IP
addresses and hardware/service failures remain because they are needed for
diagnosis.

Before sharing an archive, verify it on another system:

```bash
sha256sum --check moonlightos-support-*.tar.gz.sha256
mkdir extracted-support
tar -xzf moonlightos-support-*.tar.gz -C extracted-support
cd extracted-support/moonlightos-support
sha256sum --check MANIFEST.sha256
```
