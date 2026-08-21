# USB/IP

USB/IP is for wheels, HOTAS devices, specialty controllers, and hardware that
needs its original Linux host driver. Normal gamepads should stay local and use
Moonlight's native input path.

## Appliance server

Nothing is exported by default. Edit `/etc/moonlightos/usbip-allowlist.conf`:

```text
VID:PID:SERIAL
VID:PID:*                 # only if the device exposes no serial
VID:PID:SERIAL:risky      # explicit override for a blocked class
```

Then run:

```bash
sudo moonlightos-usbip list
sudo moonlightos-usbip reconcile
sudo moonlightos-usbip status
sudo moonlightos-usbip unbind-all
```

Storage, video/webcam, audio/microphone, HID keyboard, and HID mouse interfaces
are refused unless the exact entry ends in `:risky`. Security keys must never
be added. The controller identity in
`/var/lib/moonlightos/launcher-controller.id` is always refused. Hotplug udev
events reconcile the allowlist; removing and reinserting a device does not
turn arbitrary hardware into an export.

Set the Linux gaming PC's literal LAN IPv4 in `[host:gaming-pc] lan_address`,
then reload:

```bash
sudo systemctl reload moonlightos-firewall
```

TCP/3240 is blocked from every other LAN source.

## Linux gaming-PC client

```bash
sudo apt install usbip
sudo modprobe vhci_hcd
sudo install -m 0755 host/moonlightos-usbip-client /usr/local/sbin/
sudo install -m 0644 host/moonlightos-usbip-client.service /etc/systemd/system/
sudo install -m 0600 host/moonlightos-usbip-client.conf.example \
  /etc/moonlightos-usbip-client.conf
sudoedit /etc/moonlightos-usbip-client.conf
sudo systemctl enable --now moonlightos-usbip-client.service
```

The client attaches only devices already exported by the appliance's exact
VID/PID/serial policy. Use `moonlightos-usbip-client status` and `detach-all`
for explicit control.

## Optional Tailscale remote mode

Remote USB/IP is disabled. To opt in, set these existing INI keys:

```ini
[tailscale]
remote_usbip = true
allowed_usbip_peer = 100.64.x.y
```

The peer must be one literal Tailscale IPv4 inside `100.64.0.0/10`. Reload the
firewall and point the host client at the appliance's Tailscale IPv4. Tailnet
ACLs must also permit only `tag:gaming-host` to the appliance on TCP/3240.
Neither control replaces the device allowlist.

USB/IP has no built-in encryption or authentication. Tailscale supplies the
encrypted overlay and identity policy, but DERP or peer-relay paths can still
be too jittery for wheels/HOTAS devices. v1.1 does not add a separate remote
USB/IP automation daemon.
