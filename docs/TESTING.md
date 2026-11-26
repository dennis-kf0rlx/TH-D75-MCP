# Testing the installer locally

The public release exists, but this loop tests a local release fixture so you
do not depend on GitHub or publish a tag to check installer changes.

## One command

```bash
make test-installer
```

This:

1. builds a **temporary** public-style release fixture
2. serves it on a free loopback port
3. runs `install.sh --check` against that local mirror
4. verifies checksum, extraction, install report, and the 9 build tests
5. cleans up, including the fixture and temporary install

No GitHub release, sudo, services, radio, or leftover `dist/` are involved.

`make dist` is the explicit command when you want a persistent local release
artifact; `make dist-clean` removes it.

## Exact curl-style test

```bash
make dist
python3 -m http.server 8097 --bind 127.0.0.1 --directory dist
```

In another terminal:

```bash
THD75_RELEASE_BASE=http://127.0.0.1:8097 \
  bash install.sh --check --no-browser --prefix /tmp/thd75-local-test
```

The installer uses the same `latest/download/` path as the real release.

## Desktop browser preview

On a graphical desktop, omit `--no-browser`:

```bash
THD75_RELEASE_BASE=http://127.0.0.1:8097 \
  bash install.sh --check --prefix /tmp/thd75-preview
```

It runs checks, writes `/tmp/thd75-preview/install-report.html`, and opens the
install-notes page. Check mode does not redirect to the settings UI because the
services are not started.

To preview the real post-setup report, run the installer in a disposable VM or
test host and choose the setup prompts.

## Disposable VM full path

```bash
bash install.sh \
  --local-tarball dist/latest/download/thd75-tools.tar.gz \
  --sha256 dist/latest/download/thd75-tools.tar.gz.sha256 \
  --setup --prefix ~/thd75-web-console
```

This exercises package installation, udev, services, and the report redirect.
Do this only in a throwaway VM or a machine where those changes are acceptable.

## ARM / Raspberry Pi

There is no separate ARM code path (pure Python + `pyserial`), but the platform
is worth checking explicitly:

```bash
uname -m
python3 -V
bash install.sh --check --no-browser --prefix /tmp/thd75-pi-check
```

Full validation on **Raspberry Pi 3B+ Rev 1.3**, Raspberry Pi OS Lite
**Trixie (Debian 13)**, aarch64, Python 3.13.5, branch build `6b5e129`:

- installer checksum verified, extraction OK
- venv created, `pyserial` installed from piwheels
- `make check` **9/9**
- user services active, `Linger=yes`, still active **after reboot**
- radio on USB: `2166:9023`, `/dev/thd75 -> ttyACM0`, monitor `serialPresent: true`
- settings **read: 255 values**; **write verified**: `radio.Beep` off/on
  (`written: 1, verified: 1` both ways)
- settings `:8098` and monitor `:8099` returned **HTTP 200** through an SSH tunnel
- host: 88–99% idle, ~50 MB RSS total, 690 MB RAM available, 36.5 °C

Observed and expected on that rig: `get_throttled=0x50005` (under-voltage; test
PSU) — the tools worked, but a proper supply is recommended.

Beta findings (2026-11-25, Pi 3B+/1 GB, Raspberry Pi OS Lite Trixie):

- settings write verified end-to-end: Background Color set to White, applied,
  radio restarted, colour persisted;
- monitor UI over an SSH tunnel to another machine: no unexpected latency;
- xrdp remote desktop **plus a browser on the Pi** is too heavy: Firefox grew to
  ~670 MB RSS and the session swapped; the console server itself answers pages
  in ~18–52 ms. Use the tunnel from another machine (or a Pi 4/5 for local GUI).

Additional checks (2026-11-26, Pi 3B+):

- **uninstall**: interactive no-arg run removed both user services, the install
  tree and the udev rule; values/backups deleted (none existed); systemd
  lingering left enabled by design. The script deletes itself with the tree, so
  a second run fails with "No such file" — expected.
- **reinstall**: `install.sh` refuses an existing prefix and prints the uninstall
  steps; `./scripts/uninstall.sh` then `bash thd75-install.sh` reinstalls cleanly.
- **RDP + XFCE**: needs `startwm.sh` to `exec startxfce4` on this image; the
  default `/etc/X11/Xsession` path exited after ~2 s and closed the client.
  Stale Xorg sessions must be cleared. An alphanumeric account password avoids
  RDP keyboard-layout mangling of characters such as `!`.

Not yet exercised on a Pi: Bluetooth SPP, 32-bit armhf, Pi 4/5/Zero 2 W
hardware. Record model, OS, `uname -m`, `python3 -V`, and `--check` output when
you test them.
