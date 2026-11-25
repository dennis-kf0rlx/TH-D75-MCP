# Install with curl

## Public release

The tools repo and its releases are **public**, so this path works as written.
The request-only Agent Skill is not in the release; request it via
`skills/REQUEST-ACCESS.md`.

For a fork/private mirror, set `THD75_RELEASE_BASE` or use `LAZY.md`'s clone
path instead.

## The command

```bash
curl -fsSL -o thd75-install.sh \
  https://github.com/dennis-kf0rlx/thd75-web-console/releases/latest/download/install.sh
less thd75-install.sh
bash thd75-install.sh
```

Do **not** pipe `curl` directly to Bash as the default instruction. Download,
review, then run.

## Desktop experience

Run the installer from a terminal in a graphical desktop session. After the
checks/setup it writes:

```text
~/thd75-web-console/install-report.html
```

and opens it in the default browser. The report contains installation notes,
the safety warning, links to the docs, and — after interactive setup — redirects
to the settings UI at `http://127.0.0.1:8098/` after five seconds.

Headless/SSH users get the file path printed instead. Use `--no-browser` to
suppress the launch. No VM desktop is needed.

## What it does

1. downloads the versioned tools tarball and its checksum
2. verifies SHA-256 **before** extraction
3. refuses to overwrite an existing install
4. extracts to `~/thd75-web-console`
5. runs `scripts/bootstrap.sh --setup` interactively
6. asks before package installation, udev, and systemd user units; after the
   units are installed it offers `loginctl enable-linger` (needed on headless
   hosts such as a Raspberry Pi, harmless on a desktop)

No sudo is used by `install.sh` itself. No radio settings are written.

## Options

```text
--prefix DIR            Install directory (default: ~/thd75-web-console)
--version X.Y.Z         Release version (default: latest)
--local-tarball FILE    Use a local tarball (testing/offline)
--sha256 FILE           Checksum for --local-tarball
--check                 Extract and run non-privileged checks only
--setup                 Run the interactive setup (default)
--no-setup              Skip the interactive udev/systemd setup
--no-browser            Do not open the install report
```

Examples:

```bash
# Check-only install from a local release artifact
bash install.sh --local-tarball ./thd75-tools.tar.gz --check --prefix /tmp/thd75

# Install without touching udev/systemd
bash install.sh --no-setup
```

`--check` still needs the build prerequisites (`git`, `make`,
`python3-venv`/`python3-pip`) and PyPI access for pyserial. `--setup` installs
them after asking.

Arch/CachyOS:

```bash
sudo pacman -S --needed git make python python-pip ca-certificates usbutils
```

Debian/Ubuntu:

```bash
sudo apt-get install -y git make python3-venv python3-pip ca-certificates usbutils
```

Raspberry Pi: Raspberry Pi OS is Debian-based, so use the Debian line above.
It needs **Bookworm or Trixie** (Python 3.10+); Bullseye fails the preflight.
On a headless Pi the installer prints the install report path instead of opening
it, and the service setup offers the `loginctl enable-linger` step that keeps
the user services running at boot. Full guide:
[RASPBERRY-PI.md](RASPBERRY-PI.md).

## Release assets

A release contains:

- `thd75-tools-vX.Y.Z.tar.gz` and `.sha256`
- `thd75-tools.tar.gz` and `.sha256` (latest alias)
- `install.sh`

The tarball has a single top-level `thd75-tools/` directory and includes
`scripts/bootstrap.sh`, the apps, docs, `infra/` (Bluetooth bind unit), and the
request stub. It does not include the request-only skill, firmware, clone
images, values, or backups.

## Validation

End-to-end tested on a fresh Debian 13 VM with no git/make:

- `install.sh --local-tarball ... --sha256 ... --setup --prefix ~/thd75-web-console`
- checksum verified before extraction
- interactive setup installed packages, udev rule, and both user services
- `d75mon` and `d75settings` active and bound only to
  **127.0.0.1:8099/8098**
- no radio or settings writes; VM destroyed afterward

## Uninstall

From the install directory:

```bash
cd ~/thd75-web-console
./scripts/uninstall.sh --dry-run     # preview
./scripts/uninstall.sh               # prompts
```

It stops/removes only user services whose unit files point at that install.
It does **not** remove system packages or your serial-group membership.

Useful flags:

```text
--remove-udev   also remove the TH-D75 udev rule (sudo)
--keep-data     archive values/backups under ~ before removal
--purge         do not archive values/backups
--yes           non-interactive; does not remove udev unless asked
--force         allow a tree without the install marker
```

Data is archived to `~/thd75-data-<timestamp>.tar.gz` by default when present.
The script refuses `/`, `$HOME`, and non-TH-D75 directories unless forced.

## Failure behavior

- checksum mismatch → abort before extraction
- unsafe archive path → abort
- existing prefix → refuse overwrite
- no TTY for `--setup` → tell the user to use `--check` or `--no-setup`
- unreachable release (bad URL/network) → clear download error with guidance
- no radio → installation still valid; radio-less installs are supported

See `SECURITY.md` and `docs/SAFETY.md` before exposing any port.
