# Sunshine and Moonlight

1. Install and configure Sunshine on the Ryzen 5 7600X / RTX 5070 Linux gaming
   PC using Sunshine's official documentation.
2. Keep the host and appliance on wired gigabit Ethernet where possible.
3. Start Moonlight, add the host by name or address, and complete the PIN on the
   Sunshine web UI. The host address is never built into MoonlightOS.
4. Start at 1920x1080, 60 FPS, automatic codec, and fullscreen. Confirm hardware
   decoding in the Moonlight statistics overlay.
5. Then test 1080p120, 1440p60, and finally 4K60 SDR if the display path allows.

Moonlight Qt stores its host list, last-used host, pairing material, and stream
settings below `/var/lib/moonlightos/home/.config`. Exiting Moonlight returns to
the launcher. Non-zero exits are logged and retried by systemd up to three
times. NetworkManager restores DHCP after link loss; Moonlight's own reconnect
UI handles an interrupted stream.

Moonlight Qt is run as a native Wayland application under Cage. A direct-KMS
client is not enabled because feature parity and reliability have not yet been
physically verified on DCC36X3; this avoids falsely claiming that path is ready.
