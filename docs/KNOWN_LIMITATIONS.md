# Known limitations

- No physical DCC36X3 test has been recorded in this repository yet.
- Moonlight uses XWayland under Cage because the pinned Moonlight Qt build does
  not include a Wayland Qt platform plugin. Cage itself owns DRM/KMS directly.
- Moonlight and chiaki-ng come from hash-pinned upstream AppImages, but their
  payloads are extracted into the image at build time. Native source-built
  Debian packages remain a future goal.
- 4K60 SDR is best effort. HDR is unverified and unsupported for acceptance.
- The installed root filesystem is writable; A/B read-only updates are deferred.
- Wi-Fi and Bluetooth configuration are outside v1.1.
- Tailscale is installed but unauthenticated and optional. No subnet router,
  exit node, Serve, Funnel, public ingress, route acceptance, or advertised
  route is configured.
- Moonlight Qt cannot open an arbitrary paired host's app grid from a host-only
  CLI argument. Manual host entry is documented; setting a profile `app`
  enables direct CLI streaming.
- Tailscale relay paths may not sustain game streaming or USB/IP latency.
- A remote PlayStation is not reached through Tailscale in v1.1; a deliberately
  designed subnet-router deployment is deferred.
