#!/bin/bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORK="$ROOT/build/work"
CHROOT="$WORK/config/includes.chroot"

command -v unsquashfs >/dev/null || {
  echo 'squashfs-tools is required to extract pinned application payloads' >&2
  exit 127
}

if [[ -d "$WORK" ]]; then
  find "$WORK" -depth -mindepth 1 -delete
fi
mkdir -p "$WORK/config" "$CHROOT"
cp -a "$ROOT/config/live-build/." "$WORK/config/"
cp -a "$ROOT/overlay/." "$CHROOT/"
install -D -m 0644 "$ROOT/build/downloads/tailscale-archive-keyring.gpg" \
  "$WORK/config/archives/tailscale.key.chroot"
install -D -m 0644 "$ROOT/build/downloads/tailscale-archive-keyring.gpg" \
  "$CHROOT/usr/share/keyrings/tailscale-archive-keyring.gpg"

install -D -m 0755 "$ROOT/launcher/moonlightos-launcher.py" "$CHROOT/usr/libexec/moonlightos-launcher"
install -D -m 0755 "$ROOT/launcher/gamepad-nav.py" "$CHROOT/usr/libexec/moonlightos-gamepad-nav"
install -D -m 0644 "$ROOT/launcher/moonlightos_display.py" "$CHROOT/usr/libexec/moonlightos_display.py"
install -D -m 0644 "$ROOT/launcher/moonlightos_support.py" "$CHROOT/usr/libexec/moonlightos_support.py"
install -D -m 0755 "$ROOT/scripts/moonlightos-run-app" "$CHROOT/usr/libexec/moonlightos-run-app"
install -D -m 0755 "$ROOT/scripts/moonlightos-qemu-smoke" "$CHROOT/usr/libexec/moonlightos-qemu-smoke"
install -D -m 0755 "$ROOT/scripts/moonlightos-support-export" "$CHROOT/usr/libexec/moonlightos-support-export"
install -D -m 0755 "$ROOT/scripts/moonlightos-diagnostics" "$CHROOT/usr/bin/moonlightos-diagnostics"
install -D -m 0755 "$ROOT/scripts/moonlightos-network-ready" "$CHROOT/usr/libexec/moonlightos-network-ready"
install -D -m 0755 "$ROOT/scripts/moonlightos-firewall" "$CHROOT/usr/libexec/moonlightos-firewall"
install -D -m 0755 "$ROOT/scripts/moonlightos-audio" "$CHROOT/usr/libexec/moonlightos-audio"
install -D -m 0755 "$ROOT/scripts/moonlightos-tailscale" "$CHROOT/usr/sbin/moonlightos-tailscale"
install -D -m 0755 "$ROOT/scripts/moonlightos-tailscale-diagnostics" "$CHROOT/usr/bin/moonlightos-tailscale-diagnostics"
install -D -m 0755 "$ROOT/scripts/moonlightos-host-address" "$CHROOT/usr/bin/moonlightos-host-address"
install -D -m 0755 "$ROOT/scripts/moonlightos-tailscale-enrollment" "$CHROOT/usr/bin/moonlightos-tailscale-enrollment"
install -D -m 0755 "$ROOT/usbip/moonlightos-usbip" "$CHROOT/usr/sbin/moonlightos-usbip"
install -D -m 0644 "$ROOT/config/default/moonlightos" "$CHROOT/etc/default/moonlightos"
install -D -m 0644 "$ROOT/config/nftables/moonlightos.nft" "$CHROOT/etc/moonlightos/nftables.template"
install -D -m 0644 "$ROOT/usbip/usbip-allowlist.conf" "$CHROOT/etc/moonlightos/usbip-allowlist.conf"
install -D -m 0644 "$ROOT/build/applications.lock" \
  "$CHROOT/usr/share/moonlightos/applications.lock"
install -D -m 0644 "$ROOT/build/sources.lock" \
  "$CHROOT/usr/share/moonlightos/sources.lock"
build_commit=$(git -C "$ROOT" rev-parse --short=12 HEAD 2>/dev/null || printf unknown)
build_state=clean
git -C "$ROOT" status --porcelain --untracked-files=normal 2>/dev/null | grep -q . && build_state=modified
printf 'MoonlightOS: %s\nSource commit: %s\nSource state: %s\nBuild date: %s\n' \
  "$(< "$ROOT/VERSION")" "$build_commit" "$build_state" "$(date --utc --iso-8601=seconds)" \
  > "$CHROOT/usr/share/moonlightos/build-info"

for unit in "$ROOT"/services/*; do
  install -D -m 0644 "$unit" "$CHROOT/etc/systemd/system/$(basename "$unit")"
done

install -d -m 0755 "$CHROOT/opt/moonlightos/apps"
while IFS='|' read -r name _version _url filename; do
  [[ -z "$name" || "$name" == \#* ]] && continue
  extract=$(mktemp -d "$ROOT/build/.appimage.XXXXXX")
  trap 'find "$extract" -depth -delete' EXIT
  install -m 0755 "$ROOT/build/downloads/$filename" "$extract/application.AppImage"
  offset=$("$extract/application.AppImage" --appimage-offset)
  unsquashfs -quiet -offset "$offset" -dest "$extract/squashfs-root" \
    "$extract/application.AppImage"
  install -d -m 0755 "$CHROOT/opt/moonlightos/apps/$name"
  cp -a "$extract/squashfs-root/." "$CHROOT/opt/moonlightos/apps/$name/"
  case "$name" in
    moonlight)
      test -x "$CHROOT/opt/moonlightos/apps/$name/usr/bin/moonlight"
      test -f "$CHROOT/opt/moonlightos/apps/$name/usr/plugins/platforms/libqxcb.so"
      ;;
    chiaki-ng)
      test -x "$CHROOT/opt/moonlightos/apps/$name/usr/bin/chiaki"
      test -f "$CHROOT/opt/moonlightos/apps/$name/usr/plugins/platforms/libqwayland-egl.so"
      ;;
  esac
  find "$extract" -depth -delete
  trap - EXIT
done < "$ROOT/build/applications.lock"

printf 'Prepared %s\n' "$WORK"
