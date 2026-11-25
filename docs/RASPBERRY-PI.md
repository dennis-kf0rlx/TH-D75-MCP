# Raspberry Pi support

**Verdict: it runs unmodified on a Raspberry Pi — no fork is needed.** The Pi is
Linux on ARM, and the project has no compiled native code: the whole runtime is
Python 3 (standard library) plus `pyserial` (pure-Python wheel), so ARMv7 and
ARM64 are served by the same code as x86_64. The only Linux-specific pieces are
udev, systemd user units, and the serial group, and those work identically on
Raspberry Pi OS.

A fork would only make sense for a different OS (Windows, Android), not for a
different Linux CPU. Keeping Pi support in this repository avoids a second copy
of the menu map and backend to maintain.

## Tested / supported

| Item | Status |
|---|---|
| Raspberry Pi 3B+ / 4 / 5 / Zero 2 W | **Raspberry Pi OS Bookworm or Trixie** (Python 3.10+) |
| 64-bit (aarch64) | recommended; fully tested (Pi 3B+) |
| 32-bit armhf | expected to work (no compiled dependencies); not tested |
| Pi 1 / Zero v1 | not supported: single core and 512 MB is untested territory |
| Python 3.9 (Bullseye) or older | rejected by the preflight — upgrade the OS |
| 1 GB RAM | enough; 904 MiB Pi 3B+ ran both tools at ~50 MB RSS |

## Validated configuration (2026-11-25)

Fully exercised on **Raspberry Pi 3B+ Rev 1.3**, Raspberry Pi OS Lite
**Trixie (Debian 13)**, aarch64, Python 3.13.5, using the `raspberry-pi`
branch build (commit `6b5e129`, the changes described here):

| Check | Result |
|---|---|
| Installer check (`install.sh --local-tarball … --check`) | checksum + extraction OK, `make check` **9/9** |
| User services + lingering | `d75settings`/`d75mon` active; `Linger=yes`; still active after reboot |
| Radio over USB | `lsusb` `2166:9023 JVC Kenwood TH-D75`; `/dev/thd75 -> ttyACM0`; monitor `serialPresent: true` |
| Settings read | **255 values**, model `TH-D75`, firmware `1.03`, no errors |
| Settings write | `radio.Beep` off then on, `written: 1, verified: 1` both directions |
| UI access | settings `:8098` and monitor `:8099` **HTTP 200** through an SSH tunnel |
| Load | 88–99% idle, ~50 MB RSS for both tools, 690 MB RAM available |

Not exercised on a Pi yet: Bluetooth SPP, 32-bit armhf, and Pi 4/5/Zero 2 W
hardware (same OS family, expected to work). Report model, OS, `uname -m`,
`python3 -V`, and `--check` output when you test them.

## Prerequisites

Raspberry Pi OS is Debian-based, so use the Debian path:

```bash
sudo apt-get update
sudo apt-get install -y git make python3-venv python3-pip ca-certificates usbutils
```

The interactive `--setup` does this for you after asking.

## Install

Same installer as any other Linux host:

```bash
curl -fsSL -o thd75-install.sh \
  https://github.com/dennis-kf0rlx/thd75-web-console/releases/latest/download/install.sh
less thd75-install.sh
bash thd75-install.sh --no-browser
```

Use `--no-browser` on a headless Pi: there is no desktop browser to open the
install report, and the installer prints its path instead. Install into the
default `~/thd75-web-console`.

After setup, see **Accessing the interfaces** below: a local or RDP/VNC session
needs no tunnel; only a headless machine browsed from another computer does.

## Accessing the interfaces

Both services bind **loopback only** by default (`127.0.0.1`) and have **no
authentication** — do not bind them to the LAN. How you reach them depends on
where you are:

| Where the console runs | How to open it |
|---|---|
| Same machine — a Linux laptop or desktop | `http://127.0.0.1:8098/` in that machine's browser. **No tunnel.** |
| A Pi you control through a remote desktop (RDP/VNC) | `http://127.0.0.1:8098/` in a browser *inside* that remote desktop. **No tunnel.** |
| A headless machine you browse from a different computer | SSH tunnel (see below), or deliberately bind to the LAN. |

Headless machine, browsing from another computer:

```bash
ssh -N -L 8098:127.0.0.1:8098 -L 8099:127.0.0.1:8099 <user>@<pi-address>
```

Then open `http://127.0.0.1:8098/` (settings) and `http://127.0.0.1:8099/`
(monitor) in your local browser. Keep the SSH session open while you use them.

**Tunnels are only for the third case.** If you are sitting at the machine
directly, or you are inside an RDP/VNC session to it, you are already "on" that
machine and never need a tunnel.

If you deliberately want LAN access, set `D75SETTINGS_HOST=0.0.0.0` (settings)
or `host` in `d75mon/config.json`, and firewall the ports to your LAN — but the
no-auth warning still applies.

## Services at boot: enable systemd lingering

This is the one thing that bites headless Pis. The installer creates **systemd
user** units; by default the user's service manager exits at logout, so the
tools stop when your SSH session ends and do **not** start at boot.

```bash
sudo loginctl enable-linger "$USER"
loginctl show-user "$USER" -p Linger        # must print Linger=yes
systemctl --user enable --now d75mon.service d75settings.service
```

`scripts/bootstrap.sh --setup` now offers to do the lingering step for you and
warns if it stays off. Check after a reboot:

```bash
systemctl --user is-active d75mon.service d75settings.service
```

## Serial device

The radio uses the kernel's built-in `cdc_acm` driver, so no extra module is
needed on any Pi. With the radio in **Menu 980 = COM + AF/IF Output** it appears
as `/dev/ttyACM0`; the udev rule from the installer adds `/dev/thd75`.

- Raspberry Pi OS uses the **`dialout`** group, which is what the installer
  writes into the udev rule (Arch/CachyOS uses `uucp`).
- Add yourself after installing the rule: `sudo usermod -aG dialout "$USER"`
  then log out/in.
- If udev was skipped, both tools fall back to `/dev/ttyACM0` automatically.
- The radio drops off USB when it enters settings mode; both tools already wait
  for re-enumeration.

## Bluetooth (optional)

Pi 3B+, Pi 4, Pi 5, and Zero 2 W have Bluetooth with Classic SPP, which the
TH-D75 needs; `bluez` and `rfcomm` are already in Raspberry Pi OS. Pair and
trust the radio, then bind SPP channel 2 with the documented unit:

```bash
sudo install -m 0755 infra/systemd/thd75-bt-bind.sh /usr/local/sbin/thd75-bt-bind
sudo cp infra/systemd/thd75-bt-bind.service.example /etc/systemd/system/thd75-bt-bind.service
sudoedit /etc/systemd/system/thd75-bt-bind.service   # set THD75_BT_MAC and THD75_BT_OWNER
sudo systemctl daemon-reload
sudo systemctl enable --now thd75-bt-bind.service
```

Then tell the tools to use it:

- monitor: `"transport": "bluetooth"` and `"bluetooth": "/dev/rfcomm0"` in
  `d75mon/config.json`
- settings: `D75_TRANSPORT=bluetooth D75_SERIAL=/dev/rfcomm0` in the unit
  environment (see `BLUETOOTH.md`)

Note: on the Pi 3B+ and Zero 2 W, Wi-Fi and Bluetooth share the same 2.4 GHz
radio. Prefer USB serial, or 5 GHz Wi-Fi, if you see dropped Bluetooth links.

## Power and cabling

- Power the **radio from its own battery or the DC IN jack**. Charging it from
  the Pi's USB port while it is on can draw more current than the port provides
  and is not a supported arrangement.
- Use a proper Pi power supply (5 V / 2.5 A or better for a 3B+; the official
  PSU for a 4/5). Under-voltage shows up first as flaky USB serial.
- Use a short, data-capable USB cable. Unpowered hubs can drop the CDC device
  during settings mode.
- The radio is **not** powered by the Pi in any supported setup; the console
  only needs the data lines.

## SD card life

Writes are minimal and user-driven:

- settings backups are up to ten small JSON files (`settings-ui/backups/`,
  mode 0600) and only appear when you apply a setting
- the monitor is read-only
- nothing logs in a loop

That is negligible wear for a Pi SD card. If you want zero local writes, install
to a USB SSD or an NFS-mounted home instead.

## No router? Direct link to a laptop

The UIs only need TCP; the Pi can run on a point-to-point Ethernet link to a
laptop instead of a LAN. On the laptop, make its Ethernet interface a shared
connection so it hands out DHCP:

```bash
nmcli con add type ethernet ifname <laptop-eth-iface> con-name pi-link \
  ipv4.method shared ipv6.method ignore
nmcli con up pi-link
```

Then SSH to the address the Pi receives (the laptop's NetworkManager dnsmasq
lease file shows it, typically `10.42.0.x`). If the laptop runs a host firewall,
allow DHCP (UDP 67) and DNS (UDP/TCP 53) inbound on that interface, and allow
routed traffic out to the internet if the Pi should reach PyPI for the install.
No router configuration is required.

## Power is part of the test

A 3B+ with a USB radio attached needs a solid 5 V supply. During the validated
run the Pi logged `hwmon hwmon1: Undervoltage detected!` and
`vcgencmd get_throttled` returned `0x50005` while everything still worked — it
is a real warning, not noise. If you see those lines, use a 5.1 V / 2.5 A+
official-class PSU and a short data-capable cable before blaming the software.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Python 3.10+ required, found 3.9...` | Bullseye or older — use Bookworm/Trixie, or upgrade |
| `Temporary failure resolving` / TLS errors during apt or pip | clock not NTP-synced yet on a fresh Pi; check `timedatectl`, set the time, retry |
| Installer appears to hang before installing packages | fixed: setup no longer waits on cloud-init (its final stage can stall on `network-online` on isolated links); update to v0.1.14+ |
| `python3 venv unavailable` | `sudo apt-get install -y python3-venv` |
| `ls: /dev/thd75: No such file` | udev rule not installed, or radio not in COM+AF/IF mode (Menu 980); replug |
| `Permission denied: /dev/ttyACM0` | not in `dialout`: `sudo usermod -aG dialout "$USER"`, log out/in |
| Settings UI not reachable from laptop | it binds loopback — use the SSH tunnel above |
| Services die after closing SSH | enable lingering (above) |
| Services gone after reboot | same — check `loginctl show-user "$USER" -p Linger` |
| Radio not found over Bluetooth | `rfcomm -a`; rebind unit; check `bluetoothctl info <MAC>` shows `Connected: yes` |
| `make` not found | `sudo apt-get install -y make` |

## Reporting a Pi result

Include: Pi model, OS image and version, `uname -m`, `python3 -V`, the
`install.sh --check` output, and what you tried (USB or Bluetooth, settings
apply or monitor only). That is enough to tell platform problems apart from
radio problems.
