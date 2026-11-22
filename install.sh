#!/usr/bin/env bash
# TH-D75 tools installer.
# Downloads a checksum-verified release tarball and runs the public bootstrap
# helper. No curl|bash; no sudo in this script.
set -euo pipefail

REPO_SLUG="${THD75_REPO_SLUG:-dennis-kf0rlx/TH-D75-MCP}"
RELEASE_BASE="${THD75_RELEASE_BASE:-https://github.com/$REPO_SLUG/releases}"
PREFIX="${THD75_PREFIX:-$HOME/TH-D75-MCP}"
VERSION="latest"
LOCAL_TARBALL=""
SHA_FILE=""
RUN_MODE="setup"       # setup | check | none
TMPDIR_PATH=""

usage() {
  cat <<'USAGE'
Usage: install.sh [options]

Downloads a checksum-verified TH-D75 tools release and installs it.

Options:
  --prefix DIR            Install directory (default: ~/TH-D75-MCP)
  --version X.Y.Z         Release version (default: latest)
  --local-tarball FILE    Use a local tarball (testing/offline)
  --sha256 FILE           Checksum file for --local-tarball
  --check                 Fetch/extract; run non-privileged checks only
  --setup                 Run interactive setup (default if no --check/--no-setup)
  --no-setup              Do not run the interactive udev/systemd setup
  --help                  This message

Environment:
  THD75_RELEASE_BASE      Release URL base
  THD75_PREFIX            Default install prefix

This installer never uses sudo. The optional setup helper asks before any
privileged action. Review this script before running it.
USAGE
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
note() { printf '==> %s\n' "$*"; }

cleanup() {
  [ -n "$TMPDIR_PATH" ] && rm -rf "$TMPDIR_PATH"
}
trap cleanup EXIT

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    --version) VERSION="${2:-}"; shift 2 ;;
    --local-tarball) LOCAL_TARBALL="${2:-}"; shift 2 ;;
    --sha256) SHA_FILE="${2:-}"; shift 2 ;;
    --check) RUN_MODE="check"; shift ;;
    --setup) RUN_MODE="setup"; shift ;;
    --no-setup) RUN_MODE="none"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
done

[ "$(id -u)" -ne 0 ] || die "run as the normal user, not root"
[ -n "$PREFIX" ] || die "--prefix cannot be empty"

# Expand a leading ~ without eval.
case "$PREFIX" in
  "~") PREFIX="$HOME" ;;
  "~/"*) PREFIX="$HOME/${PREFIX#\~/}" ;;
esac

[ ! -e "$PREFIX" ] || die "install path already exists: $PREFIX
Move it away or choose a different --prefix; this installer will not overwrite."

case "$VERSION" in
  *[!A-Za-z0-9._-]*) die "invalid version string" ;;
esac

TMPDIR_PATH="$(mktemp -d "${TMPDIR:-/tmp}/thd75-install.XXXXXX")"
TARBALL="$TMPDIR_PATH/thd75-tools.tar.gz"
CHECKSUM="$TMPDIR_PATH/thd75-tools.tar.gz.sha256"

if [ -n "$LOCAL_TARBALL" ]; then
  [ -f "$LOCAL_TARBALL" ] || die "local tarball not found: $LOCAL_TARBALL"
  [ -z "$SHA_FILE" ] && SHA_FILE="$LOCAL_TARBALL.sha256"
  [ -f "$SHA_FILE" ] || die "checksum file not found: $SHA_FILE (use --sha256)"
  cp -- "$LOCAL_TARBALL" "$TARBALL"
  cp -- "$SHA_FILE" "$CHECKSUM"
  note "using local tarball: $LOCAL_TARBALL"
else
  command -v curl >/dev/null 2>&1 || die "curl not found; install curl or use --local-tarball"
  command -v sha256sum >/dev/null 2>&1 || die "sha256sum not found (coreutils)"
  if [ "$VERSION" = "latest" ]; then
    TARBALL_URL="$RELEASE_BASE/latest/download/thd75-tools.tar.gz"
    CHECKSUM_URL="$TARBALL_URL.sha256"
  else
    TARBALL_URL="$RELEASE_BASE/download/v$VERSION/thd75-tools-v$VERSION.tar.gz"
    CHECKSUM_URL="$TARBALL_URL.sha256"
  fi
  note "downloading $TARBALL_URL"
  curl -fL --retry 3 --connect-timeout 15 -o "$TARBALL" "$TARBALL_URL" || \
    die "download failed; private repo/release needs access, or use a public release"
  curl -fL --retry 3 --connect-timeout 15 -o "$CHECKSUM" "$CHECKSUM_URL" || \
    die "checksum download failed"
fi

command -v sha256sum >/dev/null 2>&1 || die "sha256sum not found (coreutils)"
command -v tar >/dev/null 2>&1 || die "tar not found"
[ -s "$TARBALL" ] || die "tarball is empty"
[ -s "$CHECKSUM" ] || die "checksum file is empty"

EXPECTED="$(awk 'NF {print $1; exit}' "$CHECKSUM")"
[[ "$EXPECTED" =~ ^[0-9a-fA-F]{64}$ ]] || die "malformed checksum file"
ACTUAL="$(sha256sum "$TARBALL" | awk '{print $1}')"
[ "$ACTUAL" = "$EXPECTED" ] || die "SHA-256 mismatch: expected $EXPECTED, got $ACTUAL"
note "SHA-256 verified: $ACTUAL"

if tar -tzf "$TARBALL" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
  die "tarball contains unsafe paths"
fi

EXTRACT="$TMPDIR_PATH/extract"
mkdir -p "$EXTRACT"
tar --no-same-owner -xzf "$TARBALL" -C "$EXTRACT"

# The release uses a single top-level directory. Be permissive for test tarballs.
mapfile -t TOPS < <(find "$EXTRACT" -mindepth 1 -maxdepth 1 -printf '%f\n')
[ "${#TOPS[@]}" -eq 1 ] || die "unexpected tarball layout (expected one top-level directory)"
SRC="$EXTRACT/${TOPS[0]}"
[ -x "$SRC/scripts/bootstrap.sh" ] || die "tarball is missing executable scripts/bootstrap.sh"

if [ "$RUN_MODE" = "setup" ] && [ ! -t 0 ]; then
  die "interactive setup requires a terminal; use --check or --no-setup"
fi

mkdir -p "$(dirname "$PREFIX")"
mv -- "$SRC" "$PREFIX"
note "installed to $PREFIX"

if [ "$RUN_MODE" = "check" ]; then
  note "running non-privileged checks only"
  ( cd "$PREFIX" && ./scripts/bootstrap.sh --check )
elif [ "$RUN_MODE" = "none" ]; then
  note "setup skipped (--no-setup)"
else
  note "starting interactive setup"
  ( cd "$PREFIX" && ./scripts/bootstrap.sh --setup )
fi

cat <<EOF

------------------------------------------------------------
Settings: http://127.0.0.1:8098/
Monitor:  http://127.0.0.1:8099/

No authentication. Use localhost or an SSH tunnel; do not expose to the internet.
Settings mode is entered from the UI; this installer never writes radio settings.
Review SECURITY.md and docs/SAFETY.md in $PREFIX.
------------------------------------------------------------
EOF
