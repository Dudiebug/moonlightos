# Third-party notices

MoonlightOS aggregates unmodified open-source software. It does not claim
ownership of third-party names, trademarks, or code. Debian package copyright
and source records remain installed under `/usr/share/doc/*/copyright`.

| Component | Upstream | License / source obligation |
|---|---|---|
| Debian 13 and packages | https://www.debian.org/ | Per-package licenses; corresponding source is available from Debian repositories configured for the image |
| Linux kernel | https://kernel.org/ | GPL-2.0-only |
| Moonlight Qt | https://github.com/moonlight-stream/moonlight-qt | GPL-3.0-only; v6.1.0 unmodified payload extracted from pinned AppImage |
| chiaki-ng | https://github.com/streetpea/chiaki-ng | AGPL-3.0-only; v1.10.0 unmodified payload extracted from pinned AppImage |
| Mozilla Firefox ESR | https://www.mozilla.org/firefox/ | MPL-2.0 and component-specific terms; installed unmodified from Debian repositories |
| Mesa | https://mesa3d.org/ | Primarily MIT and other permissive licenses; Debian copyright file is authoritative |
| Gamescope | https://github.com/ValveSoftware/gamescope | BSD-2-Clause |
| Cage | https://www.hjdskes.nl/projects/cage/ | MIT |
| PipeWire | https://pipewire.org/ | MIT/LGPL-2.1-or-later, by component |
| USB/IP tools and kernel support | https://www.kernel.org/ | GPL-2.0-only and Debian package terms |
| Tailscale | https://github.com/tailscale/tailscale | BSD-3-Clause; official stable Debian package version 1.102.3 |

Moonlight and chiaki-ng binaries are fetched from their official GitHub
releases by `scripts/fetch-apps.sh` and verified against
`build/applications.lock`. Their corresponding source is available at the
tagged upstream repositories. Firefox ESR is installed as a Debian package, and
its Debian copyright and source records remain in the image. MoonlightOS does
not bundle Sony, NVIDIA, Steam, or other proprietary game/service binaries,
credentials, keys, firmware from unapproved sources, or user pairing material.

Names such as Moonlight, Firefox, Mozilla, PlayStation, Sunshine, Intel, Dell,
and Gamescope are the property of their respective owners. This project is not
endorsed by Sony Interactive Entertainment, Mozilla, Moonlight, Dell, Intel, or
Valve.
