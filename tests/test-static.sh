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

boot_test=$(mktemp -d)
mkdir -p "$boot_test/binary/boot/grub" "$boot_test/binary/isolinux"
printf 'menuentry "Live system (amd64)" --hotkey=l {\n linux /live/vmlinuz boot=live components persistence ipv6.disable=1\n initrd /live/initrd.img\n}\n' > "$boot_test/binary/boot/grub/grub.cfg"
printf "menuentry 'Start installer' {}\n" > "$boot_test/binary/boot/grub/install_start.cfg"
printf 'include menu.cfg\nprompt 0\ntimeout 0\n' > "$boot_test/binary/isolinux/isolinux.cfg"
printf 'label live-amd64\n menu label ^Live system (amd64)\n menu default\n linux /live/vmlinuz\n initrd /live/initrd.img\n append boot=live components persistence ipv6.disable=1\n' > "$boot_test/binary/isolinux/live.cfg"
printf 'label installstart\n menu label Start ^installer\n' > "$boot_test/binary/isolinux/install.cfg"
(cd "$boot_test" && bash "$ROOT/config/live-build/hooks/live/0100-autoboot.hook.binary")
(cd "$boot_test" && bash "$ROOT/config/live-build/hooks/live/0100-autoboot.hook.binary")
rg -q '^set default=0$' "$boot_test/binary/boot/grub/grub.cfg"
rg -q '^set timeout=3$' "$boot_test/binary/boot/grub/grub.cfg"
rg -q '^terminal_output console serial$' "$boot_test/binary/boot/grub/grub.cfg"
rg -q '^menuentry "Start MoonlightOS"' "$boot_test/binary/boot/grub/grub.cfg"
rg -q '^menuentry "Start MoonlightOS \(No Persistence\)"' "$boot_test/binary/boot/grub/grub.cfg"
[[ $(rg -c '^menuentry "Start MoonlightOS \(No Persistence\)"' "$boot_test/binary/boot/grub/grub.cfg") == 1 ]]
rg -q 'boot=live components nopersistence ipv6.disable=1' "$boot_test/binary/boot/grub/grub.cfg"
rg -q "menuentry 'Install MoonlightOS'" "$boot_test/binary/boot/grub/install_start.cfg"
rg -q '^timeout 30$' "$boot_test/binary/isolinux/isolinux.cfg"
! rg -q '^timeout 0$' "$boot_test/binary/isolinux/isolinux.cfg"
rg -q 'menu label \^Start MoonlightOS$' "$boot_test/binary/isolinux/live.cfg"
rg -q 'menu label Start MoonlightOS \(No Persistence\)$' "$boot_test/binary/isolinux/live.cfg"
[[ $(rg -c 'menu label Start MoonlightOS \(No Persistence\)$' "$boot_test/binary/isolinux/live.cfg") == 1 ]]
rg -q 'boot=live components nopersistence ipv6.disable=1' "$boot_test/binary/isolinux/live.cfg"
rg -q 'menu label \^Install MoonlightOS$' "$boot_test/binary/isolinux/install.cfg"
find "$boot_test" -depth -delete

rg -q -- '--uefi-secure-boot enable' build/build.sh
rg -q -- "--bootappend-live '.*ipv6.disable=1" build/build.sh
[[ "$(< VERSION)" == 0.1.8 ]]
cmp -s VERSION overlay/etc/moonlightos-version
rg -q 'moonlightos-0\.1\.8-amd64\.iso' Makefile build/build.sh .github/workflows/build.yml
rg -q '^  actions: read$' .github/workflows/release-v0.1.8.yml
rg -q 'git/matching-refs/tags/0\.1\.8' .github/workflows/release-v0.1.8.yml
rg -q 'docs/releases/v0\.1\.8\.md' .github/workflows/release-v0.1.8.yml
! rg -q 'git/ref/tags/v1\.1' .github/workflows/release-v0.1.8.yml
rg -q '^ipv6.method=disabled$' overlay/etc/NetworkManager/conf.d/10-moonlightos.conf
rg -q '^net.ipv6.conf.all.disable_ipv6=1$' overlay/etc/sysctl.d/90-moonlightos.conf
! rg -q 'moonlightos-network-ready.service' services/moonlightos-launcher.service
! rg -q 'Before=.*moonlightos-launcher.service' services/moonlightos-network-ready.service
! rg -q 'moonlightos-network-ready.service' services/moonlightos-{moonlight,chiaki,firefox}.service
rg -q 'MOONLIGHTOS_LAUNCHER_READY' services/moonlightos-launcher.service tests/qemu-smoke.sh
rg -q 'StandardOutput=journal\+console' services/moonlightos-launcher.service
! rg -q '^Environment=WAYLAND_DISPLAY=' services/moonlightos-launcher.service
rg -q '/usr/bin/cage -s -- /usr/bin/foot --fullscreen' services/moonlightos-launcher.service
rg -q '^Environment=QT_QPA_PLATFORM=xcb$' services/moonlightos-moonlight.service
rg -q '^Environment=QT_QPA_PLATFORM=wayland$' services/moonlightos-chiaki.service
rg -q '^Environment=MOZ_ENABLE_WAYLAND=1$' services/moonlightos-firefox.service
rg -q '^EnvironmentFile=-/run/moonlightos/session.env$' services/moonlightos-{moonlight,chiaki,firefox}.service
rg -q '^ConditionFileIsExecutable=/opt/moonlightos/apps/moonlight/usr/bin/moonlight$' services/moonlightos-moonlight.service
rg -q '^ConditionFileIsExecutable=/opt/moonlightos/apps/chiaki-ng/usr/bin/chiaki$' services/moonlightos-chiaki.service
rg -q '^ConditionFileIsExecutable=/usr/bin/firefox-esr$' services/moonlightos-firefox.service
rg -q 'binary=\$appdir/usr/bin/moonlight' scripts/moonlightos-run-app
rg -q 'binary=\$appdir/usr/bin/chiaki' scripts/moonlightos-run-app
rg -q 'binary=/usr/bin/firefox-esr' scripts/moonlightos-run-app
rg -q 'write_status starting' scripts/moonlightos-run-app
rg -q 'failed: exited before the application became ready' scripts/moonlightos-run-app
rg -q 'unsquashfs -quiet -offset' build/configure.sh
removed_units='moonlightos-escape''-guard|moonlightos-stop''-active-app'
! rg -q "$removed_units" build/configure.sh
rg -q '^firefox-esr$' config/live-build/package-lists/moonlightos.list.chroot
rg -q '^wpasupplicant$' config/live-build/package-lists/moonlightos.list.chroot
rg -q '^qrencode$' config/live-build/package-lists/moonlightos.list.chroot
rg -q '^bluez$' config/live-build/package-lists/moonlightos.list.chroot
rg -q '^steam-devices$' config/live-build/package-lists/moonlightos.list.chroot
! rg -q '^steam(-installer)?$|i386|multilib' config/live-build/package-lists/moonlightos.list.chroot build
! rg -q '\bwvkbd\b' config build launcher scripts services
rg -q '^libspa-0\.2-bluetooth$' config/live-build/package-lists/moonlightos.list.chroot
rg -q '^python3-dbus$' config/live-build/package-lists/moonlightos.list.chroot
rg -q '^python3-gi$' config/live-build/package-lists/moonlightos.list.chroot
rg -q '^rfkill$' config/live-build/package-lists/moonlightos.list.chroot
rg -q '^wlr-randr$' config/live-build/package-lists/moonlightos.list.chroot
rg -q 'qrencode -t ANSIUTF8' scripts/moonlightos-tailscale-enrollment
rg -q "trap 'rm -f --.*URL_FILE.*' EXIT" scripts/moonlightos-tailscale
! rg -q 'gir1.2-gtk|libfuse' config/live-build/package-lists/moonlightos.list.chroot
rg -q 'OVMF_VARS_4M.fd' tests/qemu-smoke.sh
rg -q 'unit=1,file=' tests/qemu-smoke.sh
rg -q 'screendump' tests/qemu-smoke.sh
rg -q '/boot/grub/grub.cfg' tests/qemu-smoke.sh
rg -q 'MOONLIGHTOS_APP_STARTED' scripts/moonlightos-run-app
rg -q 'moonlight-ready' scripts/moonlightos-qemu-smoke
rg -q 'chiaki-ng-ready' scripts/moonlightos-qemu-smoke
rg -q 'firefox-ready' scripts/moonlightos-qemu-smoke
rg -q 'systemctl start --no-block moonlightos-firefox.service' scripts/moonlightos-qemu-smoke
rg -q 'name=opt/moonlightos.smoke,string=apps' tests/qemu-smoke.sh
rg -q 'qemu-persistence-smoke' Makefile .github/workflows/build.yml
rg -q 'live-persistence-write' scripts/moonlightos-qemu-smoke tests/qemu-persistence-smoke.sh
rg -q 'live-persistence-absent' scripts/moonlightos-qemu-smoke tests/qemu-persistence-smoke.sh
rg -q 'ConditionPathExists=/sys/firmware/qemu_fw_cfg' services/moonlightos-qemu-smoke.service
rg -q 'MOONLIGHTOS_SMOKE_APPS_READY' scripts/moonlightos-qemu-smoke tests/qemu-smoke.sh
rg -q 'moonlightos-firefox.path' config/live-build/hooks/live/0100-moonlightos.hook.chroot
rg -q 'moonlightos-support-export.path' config/live-build/hooks/live/0100-moonlightos.hook.chroot
rg -q 'moonlightos-configured-app.path moonlightos-osk.path' config/live-build/hooks/live/0100-moonlightos.hook.chroot
rg -q 'bluetooth.service moonlightos-bluetooth.service' config/live-build/hooks/live/0100-moonlightos.hook.chroot
! rg -q "$removed_units" config/live-build/hooks/live/0100-moonlightos.hook.chroot
rg -q '^PathExists=/run/moonlightos/support-export.request$' services/moonlightos-support-export.path
rg -q '^ExecStart=/usr/libexec/moonlightos-support-export$' services/moonlightos-support-export.service
removed_feature='TRIPLE[- ]?TAP|triple[- ]?tap|escape''-guard|stop''-active-app'
! rg -q -g '!tests/test-static.sh' "$removed_feature" launcher scripts services build config docs tests
rg -q 'EXIT THE APP TO RETURN' launcher/moonlightos-launcher.py
rg -q 'WILL MOUNT TEMPORARILY' launcher/moonlightos_support.py
rg -q 'InaccessiblePaths=.*\/var\/lib\/moonlightos\/home.*\/var\/lib\/tailscale.*-\/var\/lib\/bluetooth' services/moonlightos-support-export.service
rg -q '^RuntimeDirectoryMode=0700$' services/moonlightos-bluetooth.service
rg -q '^User=moonlightos$' services/moonlightos-bluetooth.service
rg -q '^ExecStart=/usr/libexec/moonlightos-bluetoothd$' services/moonlightos-bluetooth.service
rg -q '^After=.*dbus.service.*bluetooth.service$' services/moonlightos-audio.service
for unit in audio bluetooth moonlight chiaki firefox; do
  rg -q '^Environment=PIPEWIRE_RUNTIME_DIR=/run/moonlightos$' "services/moonlightos-$unit.service"
done
rg -q '^d /run/moonlightos 0700 moonlightos moonlightos -$' overlay/etc/tmpfiles.d/moonlightos.conf
! rg -q '^RuntimeDirectory=' services/moonlightos-launcher.service
rg -q '^/usr/bin/wireplumber --profile main-systemwide ' scripts/moonlightos-audio
rg -q '^PIPEWIRE_DAEMON=true PIPEWIRE_CORE=pipewire-0 /usr/bin/pipewire ' scripts/moonlightos-audio
rg -q 'moonlightos_bluetooth.py' build/configure.sh
rg -q 'moonlightos-bluetoothd' build/configure.sh
rg -q 'moonlightos-run-configured-app' build/configure.sh
rg -q 'moonlightos-osk-session' build/configure.sh
rg -q 'usr/share/moonlightos/apps.d' build/configure.sh
! rg -q 'terminal_command|curses\.endwin' launcher/moonlightos-launcher.py
! rg -q 'shell=True|\beval\b' launcher/moonlightos_apps.py launcher/moonlightos_app_runner.py launcher/moonlightos-launcher.py launcher/moonlightos_osk.py
for forbidden in 'bluetooth''ctl' 'curses\.endwin' 'terminal_''command' 'SIG''INT' 'kill\(' 'shell=True'; do
  ! rg -n "$forbidden" launcher/moonlightos_bluetooth.py scripts/moonlightos-bluetoothd
done
! rg -q '\bsudo\b' launcher scripts/moonlightos-support-export services/moonlightos-support-export.service
rg -q '\["wlr-randr", "--output"' launcher/moonlightos_display.py
rg -q 'append\("--dryrun"\)' launcher/moonlightos_display.py
rg -q 'support-export.request' launcher/moonlightos_support.py
! rg -q '\brunuser\b|\bresolvectl\b' scripts/moonlightos-support-export
rg -q '/usr/bin/setpriv' scripts/moonlightos-support-export tests/test_support.py
rg -q '^ExecStart=/usr/sbin/usbipd --ipv4$' services/moonlightos-usbipd.service
! rg -q -- '--foreground' services/moonlightos-usbipd.service
rg -q 'MOONLIGHTOS_SMOKE_USBIP_READY' scripts/moonlightos-qemu-smoke tests/qemu-smoke.sh
rg -q 'MOONLIGHTOS_SMOKE_BLUETOOTH_READY' scripts/moonlightos-qemu-smoke tests/qemu-smoke.sh
rg -q 'NRestarts' scripts/moonlightos-qemu-smoke
rg -q 'moonlightos-audio.service' scripts/moonlightos-qemu-smoke
rg -q '^runuser -u moonlightos -- env XDG_RUNTIME_DIR=/run/moonlightos' scripts/moonlightos-qemu-smoke
digest_pattern='s''ha-?256|s''ha256|\.s''ha256'
! rg -n -i "$digest_pattern" -g '!.git/**' -g '!tests/test-static.sh' .
rg -q 'MIN_FREE' scripts/moonlightos-support-export

python3 -m py_compile launcher/moonlightos-launcher.py launcher/moonlightos_apps.py \
  launcher/moonlightos_app_runner.py launcher/moonlightos_setup.py launcher/moonlightos_osk.py \
  launcher/moonlightos_display.py launcher/moonlightos_support.py \
  launcher/moonlightos_bluetooth.py launcher/gamepad-nav.py \
  scripts/moonlightos-host-address scripts/moonlightos-support-export \
  scripts/moonlightos-bluetoothd

python3 - <<'PY'
import configparser, pathlib, re, subprocess
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
        assert len(fields) == 4, (lock, line)
        assert fields[2].startswith('https://'), (lock, line)

for workflow in pathlib.Path('.github/workflows').glob('*.yml'):
    lines = workflow.read_text().splitlines()
    i = 0
    while i < len(lines):
        match = re.match(r'^(\s*)run:\s*\|\s*$', lines[i])
        if not match:
            i += 1
            continue
        start = i
        parent_indent = len(match.group(1))
        i += 1
        block = []
        while i < len(lines):
            indent = len(lines[i]) - len(lines[i].lstrip())
            if lines[i].strip() and indent <= parent_indent:
                break
            block.append(lines[i])
            i += 1
        nonblank = [line for line in block if line.strip()]
        block_indent = min(len(line) - len(line.lstrip()) for line in nonblank)
        script = '\n'.join(line[block_indent:] if line.strip() else '' for line in block)
        result = subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True)
        assert result.returncode == 0, (workflow, start + 1, result.stderr)
PY

if rg -n --hidden -g '!tests/test-static.sh' \
  'tskey-(auth|api|client|scim|webhook)-[A-Za-z0-9]{8,}' .; then
  echo 'Possible Tailscale secret found in source tree' >&2
  exit 1
fi

for required in \
  services/moonlightos-launcher.service \
  services/moonlightos-bluetooth.service \
  services/moonlightos-moonlight.service \
  services/moonlightos-chiaki.service \
  services/moonlightos-firefox.service \
  services/moonlightos-firefox.path \
  services/moonlightos-qemu-smoke.service \
  services/moonlightos-support-export.path \
  services/moonlightos-support-export.service \
  services/moonlightos-configured-app.path \
  services/moonlightos-configured-app.service \
  services/moonlightos-osk.path \
  services/moonlightos-osk.service \
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
MOONLIGHTOS_SYSFS_ROOT="$tmp/sys" \
MOONLIGHTOS_USBIP_ALLOWLIST="$tmp/allowlist" \
MOONLIGHTOS_USBIP_LOG="$tmp/log/usbip.log" \
  bash usbip/moonlightos-usbip unbind-all

printf 'Static tests passed.\n'
