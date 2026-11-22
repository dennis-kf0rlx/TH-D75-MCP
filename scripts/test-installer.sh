#!/usr/bin/env bash
# One-command local installer test: build a local release fixture, serve it on
# loopback, and run install.sh --check into a temp prefix. No GitHub, no sudo,
# no services, no radio.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$REPO_ROOT/dist"
PREFIX=""
KEEP=0

usage() {
  cat <<'USAGE'
Usage: scripts/test-installer.sh [--keep]

Builds dist/, serves it on a free loopback port, then runs:

  install.sh --check --no-browser --prefix <temp>

Verifies the checksum, extraction, report, and 9 build tests. No sudo, no
services, no radio. Use --keep to preserve the temp install for inspection.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --keep) KEEP=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

command -v python3 >/dev/null 2>&1 || { echo "python3 required" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl required" >&2; exit 1; }

"$REPO_ROOT/scripts/build-release.sh" "$DIST"

PORT="$(python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
)"

SERVER_LOG="$(mktemp)"
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DIST" \
  >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

TMP_ROOT="$(mktemp -d)"
if [ "$KEEP" -eq 0 ]; then
  PREFIX="$TMP_ROOT/TH-D75-MCP"
else
  PREFIX="${D75_TEST_PREFIX:-$HOME/thd75-install-test}"
  [ ! -e "$PREFIX" ] || { echo "keep prefix already exists: $PREFIX" >&2; exit 1; }
fi

cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
  rm -f "$SERVER_LOG"
  if [ "$KEEP" -eq 0 ]; then
    rm -rf "$TMP_ROOT"
  fi
}
trap cleanup EXIT

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$PORT/install.sh" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

echo "==> local release server: http://127.0.0.1:$PORT"
echo "==> installing into: $PREFIX"
THD75_RELEASE_BASE="http://127.0.0.1:$PORT" \
  bash "$REPO_ROOT/install.sh" --check --no-browser --prefix "$PREFIX"

echo
echo "==> installer report:"
grep -E '<title>|Installed to|checks complete' "$PREFIX/install-report.html" | head -5
[ -x "$PREFIX/scripts/bootstrap.sh" ] || { echo "bootstrap missing" >&2; exit 1; }
[ -x "$PREFIX/.venv/bin/python" ] || { echo "venv missing" >&2; exit 1; }

if [ "$KEEP" -eq 1 ]; then
  echo "==> kept install: $PREFIX"
else
  echo "==> PASS: local installer check complete (temp install removed)"
fi
