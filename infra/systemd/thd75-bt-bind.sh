#!/usr/bin/env bash
# Recreate /dev/rfcomm0 for the paired TH-D75. Runs as root from systemd.
set -euo pipefail

MAC="${THD75_BT_MAC:-}"
DEV="${THD75_BT_DEV:-/dev/rfcomm0}"
CHANNEL="${THD75_BT_CHANNEL:-2}"
OWNER="${THD75_BT_OWNER:-}"

[ -n "$MAC" ] || { echo "THD75_BT_MAC is required" >&2; exit 2; }
command -v rfcomm >/dev/null 2>&1 || { echo "rfcomm not found" >&2; exit 1; }

# Drop any stale tty consumers first; release alone can fail while attached.
if [ -e "$DEV" ]; then
  fuser -k "$DEV" >/dev/null 2>&1 || true
  sleep 0.5
  rfcomm release "$DEV" >/dev/null 2>&1 || true
fi

rfcomm bind "$DEV" "$MAC" "$CHANNEL"
sleep 0.2
if ! rfcomm -a | grep -q "^$(basename "$DEV"):.*$MAC.*channel $CHANNEL"; then
  echo "rfcomm bind verification failed for $MAC channel $CHANNEL" >&2
  exit 1
fi

if [ -n "$OWNER" ]; then
  chown "$OWNER:$OWNER" "$DEV"
fi
ls -l "$DEV"
