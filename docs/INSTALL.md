# Install with curl

## Public-release gate

This path requires the tools repo/release to be **public**. The request-only
Agent Skill must already be moved to its private repo; the release archive does
not contain it.

If the repo is private, use `LAZY.md`'s clone path instead.

## The command

```bash
curl -fsSL -o thd75-install.sh \
  https://github.com/dennis-kf0rlx/TH-D75-MCP/releases/latest/download/install.sh
less thd75-install.sh
bash thd75-install.sh
```

Do **not** pipe `curl` directly to Bash as the default instruction. Download,
review, then run.

## What it does

1. downloads the versioned tools tarball and its checksum
2. verifies SHA-256 **before** extraction
3. refuses to overwrite an existing install
4. extracts to `~/TH-D75-MCP`
5. runs `scripts/bootstrap.sh --setup` interactively
6. asks before package installation, udev, and systemd user units

No sudo is used by `install.sh` itself. No radio settings are written.

## Options

```text
--prefix DIR            Install directory (default: ~/TH-D75-MCP)
--version X.Y.Z         Release version (default: latest)
--local-tarball FILE    Use a local tarball (testing/offline)
--sha256 FILE           Checksum for --local-tarball
--check                 Extract and run non-privileged checks only
--no-setup              Skip the interactive udev/systemd setup
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

## Release assets

A release contains:

- `thd75-tools-vX.Y.Z.tar.gz` and `.sha256`
- `thd75-tools.tar.gz` and `.sha256` (latest alias)
- `install.sh`

The tarball has a single top-level `thd75-tools/` directory and includes
`scripts/bootstrap.sh`, the apps, docs, and the request stub. It does not include
the request-only skill, firmware, clone images, values, or backups.

## Failure behavior

- checksum mismatch → abort before extraction
- unsafe archive path → abort
- existing prefix → refuse overwrite
- no TTY for `--setup` → tell the user to use `--check` or `--no-setup`
- private/inaccessible release → clear access guidance
- no radio → installation still valid; radio-less installs are supported

See `SECURITY.md` and `docs/SAFETY.md` before exposing any port.
