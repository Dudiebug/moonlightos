# Known limitations

- No physical DCC36X3 test has been recorded in this repository yet.
- Moonlight uses native Wayland under Cage, not a claimed direct-KMS Moonlight
  client. Cage itself owns DRM/KMS directly.
- AppImages are pinned upstream binaries; native source-built Debian packages
  are a v0.2 goal.
- 4K60 SDR is best effort. HDR is unverified and unsupported for acceptance.
- The installed root filesystem is writable; A/B read-only updates are v0.2.
- Wi-Fi and Bluetooth configuration are outside v0.1.
- Tailscale is installed but unauthenticated and optional. No subnet router,
  exit node, Serve, Funnel, public ingress, route acceptance, or advertised
  route is configured.
- Moonlight Qt cannot open an arbitrary paired host's app grid from a host-only
  CLI argument. Manual host entry is documented; setting a profile `app`
  enables direct CLI streaming.
- Tailscale relay paths may not sustain game streaming or USB/IP latency.
- A remote PlayStation is not reached through Tailscale in v0.1; a deliberately
  designed subnet-router deployment is deferred.
