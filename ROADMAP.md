# Roadmap

## v0.1.0-alpha acceptance

- Reproducible Debian 13 ISO source and pinned application downloads
- Boot-to-launcher flow, persistent application state, logs, diagnostics
- Wayland hardware-decoding path, wired DHCP, fail-closed USB/IP
- QEMU boot smoke test plus the physical DCC36X3 checklist

## v0.2 candidates

1. Replace the AppImage delivery path with reproducible native Debian packages
   built in CI from pinned upstream source tags.
2. Add a settings screen for gaming-host IP, Moonlight stream presets, audio
   sink, and controller identity without editing files.
3. Validate and selectively enable a direct-KMS Moonlight implementation if it
   matches Moonlight Qt features and proves more reliable on UHD 770.
4. Add EDID-aware display selection, refresh-rate switching, and tested
   1080p120/1440p60 presets.
5. Add opt-in USB Bluetooth support and controller pairing UI.
6. Add A/B system updates with rollback; keep user data on a separate durable
   partition.
7. Evaluate HDR only after SDR reliability and the DCC36X3 physical matrix are
   complete.
8. Evaluate a narrowly scoped PlayStation subnet-router design only as an
   explicit opt-in; never enable route advertisement as a side effect.
