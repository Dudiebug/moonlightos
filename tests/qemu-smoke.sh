#!/bin/bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ISO=${1:-$ROOT/build/out/moonlightos-0.1.0-alpha-amd64.iso}
SCREENSHOT=${MOONLIGHTOS_QEMU_SCREENSHOT:-/tmp/moonlightos-qemu-smoke.ppm}
command -v qemu-system-x86_64 >/dev/null || { echo 'qemu-system-x86_64 is required' >&2; exit 127; }
[[ -f "$ISO" ]] || { echo "ISO not found: $ISO" >&2; exit 66; }

if [[ -n ${MOONLIGHTOS_QEMU_LOG:-} ]]; then
  log=$MOONLIGHTOS_QEMU_LOG
  install -D -m 0644 /dev/null "$log"
else
  log=$(mktemp)
fi
temporary_files=()
[[ -z ${MOONLIGHTOS_QEMU_LOG:-} ]] && temporary_files+=("$log")
monitor_socket=$(mktemp /tmp/moonlightos-qemu-monitor.XXXXXX)
find "$monitor_socket" -delete
cleanup() {
  ((${#temporary_files[@]} == 0)) || find "${temporary_files[@]}" -delete
  [[ ! -e "$monitor_socket" ]] || find "$monitor_socket" -delete
}
trap cleanup EXIT

if command -v xorriso >/dev/null; then
  grub_cfg=$(mktemp)
  temporary_files+=("$grub_cfg")
  xorriso -osirrox on -indev "$ISO" -extract /boot/grub/grub.cfg "$grub_cfg" >/dev/null 2>&1
  grep -q '^set timeout=3$' "$grub_cfg" || { echo 'ISO GRUB config lacks the appliance timeout' >&2; exit 65; }
  grep -q '^terminal_output console serial$' "$grub_cfg" || { echo 'ISO GRUB config lacks serial output' >&2; exit 65; }
fi

capture_screen() {
  python3 - "$monitor_socket" "$SCREENSHOT" <<'PY' || true
import socket
import sys
import time

monitor, screenshot = sys.argv[1:]
client = socket.socket(socket.AF_UNIX)
client.settimeout(2)
client.connect(monitor)
client.recv(4096)
client.sendall(f"screendump {screenshot}\n".encode())
time.sleep(1)
client.close()
PY
}

args=(
  -m 2048 -smp 2 -boot d -cdrom "$ISO"
  -device virtio-vga -display none -serial stdio -no-reboot
  -monitor "unix:$monitor_socket,server=on,wait=off"
  -netdev "user,id=net0" -device "e1000,netdev=net0"
)
[[ -r /dev/kvm ]] && args=(-enable-kvm -cpu host "${args[@]}")

# OVMF requires a private writable variable store in addition to its read-only
# code image. A code-only pflash drive can stall before GRUB with no serial log.
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
if [[ -n "$ovmf_code" ]]; then
  ovmf_vars=$(mktemp)
  temporary_files+=("$ovmf_vars")
  cp "$ovmf_vars_template" "$ovmf_vars"
  args=(
    -drive "if=pflash,format=raw,unit=0,readonly=on,file=$ovmf_code"
    -drive "if=pflash,format=raw,unit=1,file=$ovmf_vars"
    "${args[@]}"
  )
else
  echo 'OVMF code/variable pair not found; UEFI smoke test cannot run.' >&2
  exit 69
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
    capture_screen
    cat "$log"
    echo 'QEMU exited before the launcher marker.' >&2
    exit 1
  fi
  sleep 1
done
capture_screen
kill "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true
cat "$log"
echo 'Timed out waiting for launcher marker.' >&2
exit 1
