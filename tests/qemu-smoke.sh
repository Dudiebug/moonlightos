#!/bin/bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ISO=${1:-$ROOT/build/out/moonlightos-0.1.0-alpha-amd64.iso}
command -v qemu-system-x86_64 >/dev/null || { echo 'qemu-system-x86_64 is required' >&2; exit 127; }
[[ -f "$ISO" ]] || { echo "ISO not found: $ISO" >&2; exit 66; }

if [[ -n ${MOONLIGHTOS_QEMU_LOG:-} ]]; then
  log=$MOONLIGHTOS_QEMU_LOG
  install -D -m 0644 /dev/null "$log"
else
  log=$(mktemp)
  trap 'find "$log" -delete' EXIT
fi
args=(
  -m 2048 -smp 2 -boot d -cdrom "$ISO"
  -device virtio-vga -display none -serial stdio -no-reboot
  -netdev "user,id=net0" -device "e1000,netdev=net0"
)
[[ -r /dev/kvm ]] && args=(-enable-kvm -cpu host "${args[@]}")
if [[ -r /usr/share/OVMF/OVMF_CODE.fd ]]; then
  args=(-drive "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE.fd" "${args[@]}")
fi

qemu-system-x86_64 "${args[@]}" > "$log" 2>&1 &
pid=$!
for _ in $(seq 1 180); do
  if grep -q 'MOONLIGHTOS_LAUNCHER_STARTING' "$log"; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    echo 'QEMU smoke test passed: launcher start marker observed.'
    exit 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    cat "$log"
    echo 'QEMU exited before the launcher marker.' >&2
    exit 1
  fi
  sleep 1
done
kill "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true
cat "$log"
echo 'Timed out waiting for launcher marker.' >&2
exit 1
