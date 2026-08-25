#!/bin/bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ISO=${1:-$ROOT/build/out/moonlightos-0.1.8-amd64.iso}
INSTALL_LOG=${MOONLIGHTOS_QEMU_INSTALL_LOG:-/tmp/moonlightos-qemu-install.log}
BOOT_LOG=${MOONLIGHTOS_QEMU_INSTALLED_BOOT_LOG:-/tmp/moonlightos-qemu-installed-boot.log}

for command in qemu-system-x86_64 qemu-img xorriso cpio gzip; do
  command -v "$command" >/dev/null || { echo "$command is required" >&2; exit 127; }
done
[[ -f "$ISO" ]] || { echo "ISO not found: $ISO" >&2; exit 66; }

work=$(mktemp -d)
cleanup() {
  [[ -z ${pid:-} ]] || { kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; }
  find "$work" -depth -delete
}
trap cleanup EXIT

xorriso -osirrox on -indev "$ISO" \
  -extract /install/vmlinuz "$work/vmlinuz" \
  -extract /install/initrd.gz "$work/initrd.gz" >/dev/null 2>&1
install -m 0600 "$work/initrd.gz" "$work/initrd-preseed.gz"
cp "$ROOT/tests/installer-preseed.cfg" "$work/preseed.cfg"
(
  cd "$work"
  printf 'preseed.cfg\0' | cpio --null -o -H newc --quiet | gzip -9 >> initrd-preseed.gz
)
qemu-img create -q -f qcow2 "$work/system.qcow2" 24G

ovmf_code=
ovmf_vars_template=
for pair in \
  '/usr/share/OVMF/OVMF_CODE_4M.fd|/usr/share/OVMF/OVMF_VARS_4M.fd' \
  '/usr/share/OVMF/OVMF_CODE.fd|/usr/share/OVMF/OVMF_VARS.fd' \
  '/usr/share/pve-edk2-firmware/OVMF_CODE_4M.fd|/usr/share/pve-edk2-firmware/OVMF_VARS_4M.fd'; do
  code=${pair%%|*}
  vars=${pair#*|}
  if [[ -r "$code" && -r "$vars" ]]; then
    ovmf_code=$code
    ovmf_vars_template=$vars
    break
  fi
done
[[ -n "$ovmf_code" ]] || { echo 'OVMF code/variable pair not found.' >&2; exit 69; }
cp "$ovmf_vars_template" "$work/OVMF_VARS.fd"

common=(
  -m 4096 -smp 4 -machine q35
  -drive "if=pflash,format=raw,unit=0,readonly=on,file=$ovmf_code"
  -drive "if=pflash,format=raw,unit=1,file=$work/OVMF_VARS.fd"
  -drive "file=$work/system.qcow2,if=virtio,format=qcow2"
  -device virtio-vga -display none -monitor none -no-reboot
)
[[ -r /dev/kvm && -w /dev/kvm ]] && common=(-enable-kvm -cpu host "${common[@]}")

install -D -m 0644 /dev/null "$INSTALL_LOG"
if ! timeout 25m qemu-system-x86_64 \
  "${common[@]}" \
  -kernel "$work/vmlinuz" -initrd "$work/initrd-preseed.gz" \
  -append 'auto=true priority=critical console=ttyS0,115200n8 DEBIAN_FRONTEND=text ---' \
  -drive "file=$ISO,media=cdrom,readonly=on" \
  -net none -serial stdio > "$INSTALL_LOG" 2>&1; then
  cat "$INSTALL_LOG"
  echo 'Automated UEFI installation failed.' >&2
  exit 1
fi
grep -q 'Requesting system reboot' "$INSTALL_LOG" || {
  cat "$INSTALL_LOG"
  echo 'Installer exited without completing.' >&2
  exit 1
}

install -D -m 0644 /dev/null "$BOOT_LOG"
boot_and_wait() {
  local mode=$1 marker=$2
  printf '\n=== installed boot: %s ===\n' "$mode" >> "$BOOT_LOG"
  qemu-system-x86_64 \
    "${common[@]}" \
    -netdev user,id=net0 -device e1000,netdev=net0 \
    -fw_cfg "name=opt/moonlightos.smoke,string=$mode" \
    -serial stdio >> "$BOOT_LOG" 2>&1 &
  pid=$!
  for _ in $(seq 1 240); do
    if grep -q "$marker" "$BOOT_LOG"; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      pid=
      return 0
    fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  cat "$BOOT_LOG"
  echo "Installed system did not emit $marker." >&2
  exit 1
}

boot_and_wait persistence-write MOONLIGHTOS_SMOKE_PERSISTENCE_WRITTEN
boot_and_wait persistence-read MOONLIGHTOS_SMOKE_PERSISTENCE_READY
echo 'QEMU install smoke test passed: UEFI install, independent disk boot, launcher readiness, and configuration persistence across a cold reboot.'
