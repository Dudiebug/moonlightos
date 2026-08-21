# Hardware support

## Dell OptiPlex 7010 Micro DCC36X3

| Component | v1.1 design |
|---|---|
| Core i5-13500T / UHD 770 | Standard Debian kernel `i915`, Mesa, Intel media driver |
| 16 GB 1x16 DDR4-3200 | Supported; 2x8 GB dual-channel preferred for iGPU bandwidth |
| 256 GB NVMe | Supported installation target |
| Gigabit Ethernet | NetworkManager DHCP, wired-first |
| DisplayPort 1.4a | Preferred for 4K60 SDR testing |
| HDMI 1.4b | Suitable for lower modes; 4K60 depends on the physical port/path |
| No factory Wi-Fi/Bluetooth | Expected; not required in v1.1 |
| USB controllers | Wired supported; wireless needs a USB Bluetooth adapter |

The UHD 770 generation can expose hardware H.264, HEVC, and AV1 decode through
VA-API, but the diagnostic output on the actual machine is the source of truth.
Run `vainfo` and confirm decoder profiles before accepting a test result.

4K60 SDR is best effort. Do not infer HDR support from EDID, Vulkan, or VA-API
alone; HDR requires an end-to-end physical test.

MoonlightOS v1.1 is IPv4-only. IPv6 is disabled on the live kernel command line,
in the installed GRUB configuration, in NetworkManager, and through sysctl.
