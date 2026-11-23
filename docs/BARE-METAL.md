# Bare-metal test on a generic Linux desktop

Use this when the test machine is **not on the lab LAN** or when you prefer an
offline kit over downloading from GitHub.

## What you need

- Linux desktop with a browser
- Internet for distro packages and PyPI
- USB cable for the radio later
- The USB kit:

```bash
make usb-kit
# copy dist-usb-kit/ or thd75-usb-kit.tar.gz to the test machine
```

On CachyOS/Arch, the setup helper installs:

```bash
sudo pacman -S --needed git make python python-pip ca-certificates usbutils
```

Debian/Ubuntu equivalent:

```bash
sudo apt-get install -y git make python3-venv python3-pip ca-certificates usbutils
```

## Run

From the kit directory:

```bash
cd /run/media/$USER/<USB-LABEL>/thd75-usb-kit/release
bash install.sh \
  --local-tarball latest/download/thd75-tools.tar.gz \
  --sha256 latest/download/thd75-tools.tar.gz.sha256 \
  --setup
```

On a desktop this opens `install-report.html`, then redirects to
`http://127.0.0.1:8098/` after setup.

## Verify

```bash
systemctl --user is-active d75mon d75settings
ss -ltn | grep -E '8098|8099'
curl -s http://127.0.0.1:8098/api/status
```

Expected: both services active, both ports loopback-only, no radio attached
means `serialPresent:false`.

## Radio

Connect the TH-D75, confirm `/dev/thd75`, and make sure your user is in the
serial group (`uucp` on Arch/CachyOS, `dialout` on Debian/Ubuntu). Log out/in if
the group was just added.

## Remove

```bash
cd ~/thd75-web-console
./scripts/uninstall.sh --dry-run
./scripts/uninstall.sh
```

## GitHub curl

The tools repo and releases are public; the curl installer in `docs/INSTALL.md`
is the normal path. Use the USB kit above only when the test machine has no
GitHub access.
