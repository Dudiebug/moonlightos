#!/bin/bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

command -v rg >/dev/null || {
  echo 'ripgrep (rg) is required for the static test suite' >&2
  exit 127
}

while IFS= read -r file; do
  bash -n "$file"
done < <(rg -l '^#!/bin/bash' build host scripts tests usbip config/live-build/hooks)

python3 -m py_compile launcher/moonlightos-launcher.py launcher/gamepad-nav.py \
  scripts/moonlightos-host-address

python3 - <<'PY'
import configparser, pathlib, re
hook = pathlib.Path('config/live-build/hooks/live/0100-moonlightos.hook.chroot').read_text()
assert hook.index('groupadd --system seat') < hook.index('useradd --uid 1000')
block = hook.split("cat > /var/lib/moonlightos/config.ini <<'EOF'", 1)[1].split('\nEOF', 1)[0]
c = configparser.ConfigParser(); c.read_string(block)
assert c.getboolean('tailscale', 'enabled') is False
assert c.getboolean('tailscale', 'ssh_enabled') is False
assert c.getboolean('tailscale', 'remote_usbip') is False
assert c.get('tailscale', 'allowed_usbip_peer') == ''
assert c.get('host:gaming-pc', 'address_mode') == 'auto'
for lock in ('build/applications.lock', 'build/sources.lock'):
    for line in pathlib.Path(lock).read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        fields = line.split('|')
        assert len(fields) == 5, (lock, line)
        assert re.fullmatch(r'[0-9a-f]{64}', fields[3]), (lock, line)
PY

if rg -n --hidden -g '!tests/test-static.sh' \
  'tskey-(auth|api|client|scim|webhook)-[A-Za-z0-9]{8,}' .; then
  echo 'Possible Tailscale secret found in source tree' >&2
  exit 1
fi

for required in \
  services/moonlightos-launcher.service \
  services/moonlightos-moonlight.service \
  services/moonlightos-chiaki.service \
  services/moonlightos-usbipd.service \
  services/moonlightos-network-ready.service \
  services/moonlightos-tailscale-enroll.service; do
  test -s "$required"
done

tmp=$(mktemp -d)
trap 'find "$tmp" -depth -delete' EXIT
mkdir -p "$tmp/sys/bus/usb/devices/1-2/1-2:1.0" "$tmp/log"
printf '046d\n' > "$tmp/sys/bus/usb/devices/1-2/idVendor"
printf 'c262\n' > "$tmp/sys/bus/usb/devices/1-2/idProduct"
printf 'wheel-01\n' > "$tmp/sys/bus/usb/devices/1-2/serial"
printf '00\n' > "$tmp/sys/bus/usb/devices/1-2/bDeviceClass"
printf '03\n' > "$tmp/sys/bus/usb/devices/1-2/1-2:1.0/bInterfaceClass"
printf '00\n' > "$tmp/sys/bus/usb/devices/1-2/1-2:1.0/bInterfaceProtocol"
printf '046d:c262:wheel-01\n' > "$tmp/allowlist"
MOONLIGHTOS_SYSFS_ROOT="$tmp/sys" \
MOONLIGHTOS_USBIP_ALLOWLIST="$tmp/allowlist" \
MOONLIGHTOS_USBIP_LOG="$tmp/log/usbip.log" \
  bash usbip/moonlightos-usbip list | grep -q 'allowed'

printf 'Static tests passed.\n'
