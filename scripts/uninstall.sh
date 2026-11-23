#!/usr/bin/env bash
# Remove a TH-D75 tools installation, its user services, and optionally the
# udev rule. Never removes system packages or radio settings.
set -euo pipefail

PREFIX="${THD75_PREFIX:-$HOME/thd75-web-console}"
UNIT_DIR="$HOME/.config/systemd/user"
UDEV_RULE="/etc/udev/rules.d/99-kenwood-thd75.rules"
DRY_RUN=0
YES=0
REMOVE_UDEV=0
KEEP_DATA=0
PURGE=0
FORCE=0

usage() {
  cat <<'USAGE'
Usage: scripts/uninstall.sh [options]

Options:
  --prefix DIR        Installation to remove (default: ~/thd75-web-console)
  --remove-udev       Also remove /etc/udev/rules.d/99-kenwood-thd75.rules
  --keep-data         Archive settings-ui/values.json and backups before removal
  --purge             Do not archive values/backups
  --yes               Non-interactive; does not remove udev unless asked
  --dry-run           Show actions without changing anything
  --force             Allow removal of a directory without the install marker
  --help              This message

Never removes system packages, the serial group membership, or radio data.
USAGE
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
note() { printf '==> %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }

confirm() {
  local prompt="$1" default="${2:-n}" answer=""
  if [ "$YES" -eq 1 ]; then
    return 0
  fi
  read -r -p "$prompt [y/N] " answer || true
  [ -n "$answer" ] || answer="$default"
  [[ "$answer" =~ ^[Yy]$ ]]
}

do_cmd() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf 'DRY: '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    --remove-udev) REMOVE_UDEV=1; shift ;;
    --keep-data) KEEP_DATA=1; shift ;;
    --purge) PURGE=1; shift ;;
    --yes) YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
done

[ "$(id -u)" -ne 0 ] || die "run as the normal user, not root"
[ -n "$PREFIX" ] || die "--prefix cannot be empty"

case "$PREFIX" in
  "~") PREFIX="$HOME" ;;
  "~/"*) PREFIX="$HOME/${PREFIX#\~/}" ;;
esac

[ -d "$PREFIX" ] || {
  # Preserve removal of installs created under the old repo name.
  if [ -d "$HOME/TH-D75-MCP" ] && [ "$PREFIX" = "$HOME/thd75-web-console" ]; then
    warn "new prefix not found; using legacy install at $HOME/TH-D75-MCP"
    PREFIX="$HOME/TH-D75-MCP"
  else
    die "install path not found: $PREFIX"
  fi
}

REAL="$(realpath "$PREFIX")"
case "$REAL" in
  /|"$HOME") die "refusing to remove unsafe path: $REAL" ;;
esac

if [ ! -f "$PREFIX/.thd75-install" ]; then
  if [ -f "$PREFIX/scripts/bootstrap.sh" ] && \
     [ -f "$PREFIX/settings-ui/server.py" ] && \
     [ -f "$PREFIX/d75mon/backend/d75mon.py" ]; then
    warn "install marker missing; recognized TH-D75 tree"
  elif [ "$FORCE" -eq 1 ]; then
    warn "install marker missing; --force allows removal"
  else
    die "not a TH-D75 install (missing .thd75-install); use --force only if certain"
  fi
fi

note "install: $REAL"
[ "$DRY_RUN" -eq 1 ] && note "dry run: no changes will be made"
# Leaving the install directory while deleting it avoids a deleted cwd.
cd "$HOME"

# Stop/remove only user units that actually point at this install.
for svc in d75mon d75settings; do
  unit="$UNIT_DIR/$svc.service"
  if [ ! -f "$unit" ]; then
    continue
  fi
  unit_match=0
  grep -qF "$PREFIX" "$unit" && unit_match=1
  if [ "$PREFIX" = "$HOME/thd75-web-console" ] && \
     { grep -qF '%h/thd75-web-console' "$unit" || grep -qF '%h/TH-D75-MCP' "$unit"; }; then
    unit_match=1
  fi
  if [ "$unit_match" -eq 0 ]; then
    warn "$unit does not reference $PREFIX; leaving it alone"
    continue
  fi
  note "found $unit"
  if confirm "Stop and disable $svc?" y; then
    do_cmd systemctl --user disable --now "$svc" || warn "systemctl disable/stop $svc failed"
  fi
  if confirm "Remove $unit?" y; then
    do_cmd rm -f -- "$unit"
  fi
done

if [ "$DRY_RUN" -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload >/dev/null 2>&1 || true
fi

# udev rule is optional and privileged. Never remove it under --yes unless asked.
if [ -f "$UDEV_RULE" ]; then
  if [ "$REMOVE_UDEV" -eq 1 ] || { [ "$YES" -eq 0 ] && confirm "Remove the TH-D75 udev rule? [y/N]" n; }; then
    do_cmd sudo rm -f -- "$UDEV_RULE"
    do_cmd sudo udevadm control --reload-rules || true
  else
    note "leaving udev rule: $UDEV_RULE"
  fi
fi

# Preserve local values/backups unless purging.
DATA="$PREFIX/settings-ui"
if [ "$PURGE" -eq 0 ] && { [ -f "$DATA/values.json" ] || [ -d "$DATA/backups" ]; }; then
  if [ "$KEEP_DATA" -eq 1 ] || confirm "Archive values/backups to $HOME before removal?" y; then
    STAMP="$(date +%Y%m%d-%H%M%S)"
    ARCHIVE="$HOME/thd75-data-$STAMP.tar.gz"
    note "archiving data to $ARCHIVE"
    if [ "$DRY_RUN" -eq 1 ]; then
      printf 'DRY: tar -czf %q -C %q settings-ui/values.json settings-ui/backups\n' "$ARCHIVE" "$PREFIX"
    else
      TMP_ARCHIVE="$(mktemp "${TMPDIR:-/tmp}/thd75-data.XXXXXX.tar.gz")"
      TAR_ARGS=()
      [ -f "$DATA/values.json" ] && TAR_ARGS+=(settings-ui/values.json)
      [ -d "$DATA/backups" ] && TAR_ARGS+=(settings-ui/backups)
      if tar -czf "$TMP_ARCHIVE" -C "$PREFIX" "${TAR_ARGS[@]}"; then
        mv -- "$TMP_ARCHIVE" "$ARCHIVE"
        chmod 600 "$ARCHIVE" 2>/dev/null || true
      else
        rm -f "$TMP_ARCHIVE"
        warn "data archive failed; keeping install"
        exit 1
      fi
    fi
  else
    note "data not archived"
  fi
fi

if confirm "Delete the installation at $REAL?" y; then
  do_cmd rm -rf -- "$REAL"
else
  note "installation left in place"
  exit 0
fi

cat <<EOF

------------------------------------------------------------
Uninstall complete: $REAL
Left alone: system packages, serial group membership, radio data.
$( [ "$REMOVE_UDEV" -eq 1 ] && echo "Removed udev rule." || echo "Udev rule not removed." )
------------------------------------------------------------
EOF
