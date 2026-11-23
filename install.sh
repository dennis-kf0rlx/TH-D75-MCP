#!/usr/bin/env bash
# TH-D75 tools installer.
# Downloads a checksum-verified release tarball and runs the public bootstrap
# helper. No curl|bash; no sudo in this script.
set -euo pipefail

REPO_SLUG="${THD75_REPO_SLUG:-dennis-kf0rlx/thd75-web-console}"
RELEASE_BASE="${THD75_RELEASE_BASE:-https://github.com/$REPO_SLUG/releases}"
PREFIX="${THD75_PREFIX:-$HOME/thd75-web-console}"
VERSION="latest"
LOCAL_TARBALL=""
SHA_FILE=""
RUN_MODE="setup"       # setup | check | none
NO_BROWSER="${D75_NO_BROWSER:-0}"
TMPDIR_PATH=""

usage() {
  cat <<'USAGE'
Usage: install.sh [options]

Downloads a checksum-verified TH-D75 tools release and installs it.

Options:
  --prefix DIR            Install directory (default: ~/thd75-web-console)
  --version X.Y.Z         Release version (default: latest)
  --local-tarball FILE    Use a local tarball (testing/offline)
  --sha256 FILE           Checksum file for --local-tarball
  --check                 Fetch/extract; run non-privileged checks only
  --setup                 Run interactive setup (default if no --check/--no-setup)
  --no-setup              Do not run the interactive udev/systemd setup
  --no-browser            Do not open the install report
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

html_escape() {
  printf '%s' "$1" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g'
}

open_report() {
  local report="$1"
  if [ "$NO_BROWSER" = "1" ]; then
    note "browser launch disabled (--no-browser)"
    return 0
  fi
  if [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    note "no desktop session detected; open this file manually: $report"
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "file://$report" >/dev/null 2>&1 &
  elif command -v gio >/dev/null 2>&1; then
    gio open "file://$report" >/dev/null 2>&1 &
  elif command -v sensible-browser >/dev/null 2>&1; then
    sensible-browser "file://$report" >/dev/null 2>&1 &
  else
    note "no browser opener found; open this file manually: $report"
  fi
}

write_report() {
  local prefix="$1" mode="$2"
  local report="$prefix/install-report.html"
  local escaped_prefix
  escaped_prefix="$(html_escape "$prefix")"
  mkdir -p "$(dirname "$report")"

  local title="TH-D75 tools installed"
  local redirect=""
  local status="Installed and checked."
  local next_steps=""
  case "$mode" in
    setup)
      title="TH-D75 tools installed — opening settings"
      redirect='<meta http-equiv="refresh" content="5;url=http://127.0.0.1:8098/">'
      status="Installed, checked, and the optional setup completed."
      next_steps='<p><a href="http://127.0.0.1:8098/">Open the settings UI</a> &middot; <a href="http://127.0.0.1:8099/">Open the monitor</a></p><p class="big">Redirecting to the settings UI in 5 seconds…</p>'
      ;;
    check)
      title="TH-D75 tools installed — checks complete"
      status="Installed and non-privileged checks passed. Services were not started."
      next_steps='<p>Start later with:</p><pre>cd '"$escaped_prefix"'
./scripts/bootstrap.sh --setup</pre>'
      ;;
    none)
      title="TH-D75 tools installed — setup skipped"
      status="Installed; setup was skipped."
      next_steps='<p>Run setup later:</p><pre>cd '"$escaped_prefix"'
./scripts/bootstrap.sh --setup</pre>'
      ;;
  esac

  cat >"$report" <<EOF
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
$redirect
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TH-D75 tools</title>
<style>
 body{font-family:system-ui,sans-serif;background:#0b0e13;color:#e8eef7;margin:0;padding:2rem;line-height:1.5}
 main{max-width:760px;margin:auto}
 h1{font-size:1.6rem} h2{font-size:1.1rem;margin-top:1.6rem;color:#63e0b2}
 a{color:#7db5ff} code,pre{background:#121821;border:1px solid #263140;border-radius:6px;padding:.15rem .35rem}
 pre{padding:.8rem;overflow:auto} .warn{border-left:3px solid #f3bd64;padding:.6rem 1rem;background:#201a10}
 .big{font-size:1.1rem;color:#63e0b2} .muted{color:#93a2b7}
</style></head><body><main>
<h1>TH-D75 tools</h1>
<p class="big">$status</p>
<p class="muted">Installed to: <code>$escaped_prefix</code></p>
<p>Uninstall later: <code>cd $escaped_prefix &amp;&amp; ./scripts/uninstall.sh</code></p>
$next_steps
<h2>Safety</h2>
<div class="warn">No authentication. Keep the UI on localhost or use an SSH tunnel. Do not expose it to the internet. The installer never wrote radio settings.</div>
<h2>Before using</h2>
<ul>
<li>Connect the TH-D75 over USB and verify <code>/dev/thd75</code>.</li>
<li>Settings mode pauses the monitor and can require one USB reset on exit.</li>
<li>If MCP wedges the radio, power-cycle it physically.</li>
<li>Read <code>SECURITY.md</code> and <code>docs/SAFETY.md</code> in the install directory.</li>
</ul>
<h2>Docs</h2>
<p><a href="file://$escaped_prefix/README.md">README</a> &middot;
<a href="file://$escaped_prefix/docs/INSTALL.md">Install notes</a> &middot;
<a href="file://$escaped_prefix/docs/SAFETY.md">Safety</a></p>
</main></body></html>
EOF
  note "install report: $report"
  open_report "$report"
}

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
    --no-browser) NO_BROWSER=1; shift ;;
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
    die "download failed; check the release URL and network, or use --local-tarball"
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
cat > "$PREFIX/.thd75-install" <<MARKER
version=$VERSION
installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
source=$RELEASE_BASE
MARKER
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

write_report "$PREFIX" "$RUN_MODE"

cat <<EOF

------------------------------------------------------------
Settings: http://127.0.0.1:8098/
Monitor:  http://127.0.0.1:8099/

No authentication. Use localhost or an SSH tunnel; do not expose to the internet.
Settings mode is entered from the UI; this installer never writes radio settings.
Review SECURITY.md and docs/SAFETY.md in $PREFIX.
------------------------------------------------------------
EOF
