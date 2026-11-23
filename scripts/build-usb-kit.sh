#!/usr/bin/env bash
# Build a self-contained USB-style installer kit for a generic Linux desktop.
# The GitHub release is not public yet; this kit uses --local-tarball.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$REPO_ROOT/dist-usb-kit}"
VERSION="${D75_TEST_VERSION:-0.0.0-local}"

rm -rf "$OUT"
mkdir -p "$OUT/release"
"$REPO_ROOT/scripts/build-release.sh" "$OUT/release"

cat >"$OUT/README.txt" <<EOF
TH-D75 tools — USB test kit
Version: $VERSION
Built:   $(date -u +%Y-%m-%dT%H:%M:%SZ)

This is not a GitHub release. The repo/release is currently private, so use
the local-tarball path below. Internet access is still needed for distro
packages and PyPI.

CachyOS / Arch:

  cd /run/media/\$USER/<USB-LABEL>/thd75-usb-kit/release
  bash install.sh \\
    --local-tarball latest/download/thd75-tools.tar.gz \\
    --sha256 latest/download/thd75-tools.tar.gz.sha256 \\
    --setup

Debian / Ubuntu:

  cd /media/\$USER/<USB-LABEL>/thd75-usb-kit/release
  bash install.sh \\
    --local-tarball latest/download/thd75-tools.tar.gz \\
    --sha256 latest/download/thd75-tools.tar.gz.sha256 \\
    --setup

The installer checks the checksum, installs to ~/thd75-web-console, and asks before
package installation, udev, and systemd user services. On a desktop it opens
the install report and then the settings UI.

Headless/check-only:

  bash install.sh --local-tarball latest/download/thd75-tools.tar.gz \\
    --sha256 latest/download/thd75-tools.tar.gz.sha256 \\
    --check --no-browser --prefix /tmp/thd75-check

No lab LAN or public GitHub release is required.

Uninstall:

  cd ~/thd75-web-console
  ./scripts/uninstall.sh --dry-run
  ./scripts/uninstall.sh
EOF

# Also provide a single archive of the kit.
tar -czf "$OUT/../thd75-usb-kit.tar.gz" -C "$OUT" .
echo "USB kit: $OUT"
echo "archive: $OUT/../thd75-usb-kit.tar.gz"
