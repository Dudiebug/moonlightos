# Troubleshooting

Run `moonlightos-diagnostics`. It prints and saves OS, kernel, CPU/GPU,
Vulkan, VA-API, audio, network, USB/IP, Tailscale, USB, and display-mode data.

| Symptom | Check |
|---|---|
| Launcher does not appear | `systemctl status moonlightos-launcher seatd`; inspect `/var/log/moonlightos/launcher.log` |
| Moonlight returns immediately | `/var/log/moonlightos/moonlight.log`; verify XWayland and VA-API output |
| chiaki-ng black screen | Try Vulkan then OpenGL; optionally set `gamescope = true`; keep HDR off |
| No HDMI/DP audio | `wpctl status`, `aplay -l`; select the display sink in application settings |
| No DHCP | `nmcli device`, `ip route`, cable/switch link, `/var/log/moonlightos/network.log` |
| USB/IP refused | `moonlightos-usbip list`; confirm exact serial and risky-class policy |
| Tailscale is offline | `moonlightos-tailscale-diagnostics`; local LAN remains usable |
| Tailscale stream is slow | Check direct/peer-relay/DERP result and approximate latency; reduce bitrate before changing router policy |

Do not open UDP/41641 unconditionally. Run `tailscale netcheck` and
`tailscale ping` first. Do not port-forward Sunshine or USB/IP to the public
internet.

## USB does not boot

1. Verify the ISO SHA256, then write it to the whole USB device with the `dd`
   command in `INSTALL.md`.
2. Use Dell `F12` and choose the `UEFI` USB entry. The image requires x86_64
   UEFI and has Secure Boot support enabled.
3. Wait for the three-second GRUB timeout. The launcher is not allowed to wait
   for DHCP, so unplugged Ethernet must not prevent it from appearing.
4. If it still stops, capture the exact last message or a photo. Serial boot
   output is available at 115200 8N1 for development builds.

IPv6 is intentionally unavailable in v1.1. Use `ip -4 address` and `ip -4
route` when troubleshooting networking.
