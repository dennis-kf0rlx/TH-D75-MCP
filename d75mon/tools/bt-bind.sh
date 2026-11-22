#!/usr/bin/env bash
# Bind the TH-D75 Bluetooth SPP channel (RFCOMM 2) to /dev/rfcomm0.
# Usage: tools/bt-bind.sh <MAC> [channel]
set -euo pipefail

MAC="${1:-}"
CHANNEL="${2:-2}"

if [[ -z "$MAC" ]]; then
  echo "usage: $0 <MAC> [channel=2]" >&2
  exit 2
fi

if ! command -v rfcomm >/dev/null 2>&1; then
  echo "rfcomm not found: sudo pacman -S bluez-deprecated-tools" >&2
  exit 1
fi

# Rebind cleanly if a stale channel exists.
sudo rfcomm release /dev/rfcomm0 2>/dev/null || true
sudo rfcomm bind /dev/rfcomm0 "$MAC" "$CHANNEL"
ls -l /dev/rfcomm0
