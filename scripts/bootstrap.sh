#!/usr/bin/env bash
# TH-D75 tools bootstrap — safe checks by default; optional interactive setup.
# --check/--install never use sudo. --setup asks before every privileged action.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
MODE="check"
TARGET="settings"

usage() {
  cat <<'USAGE'
Usage: bootstrap.sh [MODE]

Modes:
  --check             Default. Verify prerequisites, validate SKILL.md, and run
                      `make check` (which creates .venv if needed).
  --install           Create .venv and install requirements. No service,
                      udev, sudo, or radio changes.
  --setup             Interactive lazy path: install missing packages, run
                      checks, then ask before udev/service setup. Never writes
                      radio settings. Requires a terminal.
  --print-service     Print the systemd user-unit steps for review. Installs
                      nothing.
  --target settings|monitor   Used by --print-service.
  --help              This message.

--check and --install never perform privileged or radio-writing actions.
USAGE
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
note() { printf '==> %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }

confirm() {
  local answer=""
  read -r -p "$1 [y/N] " answer || true
  [[ "$answer" =~ ^[Yy]$ ]]
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --check) MODE="check" ;;
    --install) MODE="install" ;;
    --setup) MODE="setup" ;;
    --print-service) MODE="print-service" ;;
    --target) shift; TARGET="${1:-}" ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
  shift
done

[ "$(id -u)" -ne 0 ] || die "run as the normal user, not root"
[ -f "$REPO_ROOT/Makefile" ] || die "repo root not found from $SCRIPT_DIR"

need() {
  if command -v "$1" >/dev/null 2>&1; then
    return 0
  fi
  local hint=""
  case "$1" in
    git) hint="install git (Debian: sudo apt-get install -y git)" ;;
    make) hint="install make (Debian: sudo apt-get install -y make)" ;;
    python3) hint="install Python 3.10+" ;;
  esac
  die "missing command: $1${hint:+; $hint}"
}

check_venv() {
  python3 -m venv --help >/dev/null 2>&1 || \
    die "python3 venv unavailable (Debian: sudo apt-get install -y python3-venv python3-pip)"
}

check_python() {
  python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ required, found %s" % sys.version.split()[0])
print("python", sys.version.split()[0], "ok")
PY
}

validate_skill() {
  local skill="$REPO_ROOT/skills/th-d75-tools/SKILL.md"
  if [ ! -f "$skill" ]; then
    note "request-only skill not present; skipping skill validation"
    return 0
  fi
  python3 - "$skill" <<'SKILLPY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text()
assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
head = text.split("---", 2)[1]
assert "name:" in head, "frontmatter missing name"
assert "description:" in head, "frontmatter missing description"
assert "Operating contract" in text, "missing operating contract"
assert "MUST NOT" in text, "missing MUST NOT rules"
print("SKILL.md frontmatter/contract ok")
SKILLPY
}

install_deps_if_needed() {
  local missing=0
  for cmd in python3 git make; do
    command -v "$cmd" >/dev/null 2>&1 || missing=1
  done
  python3 -m venv --help >/dev/null 2>&1 || missing=1

  if [ "$missing" -eq 0 ]; then
    return 0
  fi

  note "Missing build prerequisites detected."
  confirm "Install them with sudo now?" || \
    die "install git, make, python3-venv, python3-pip, ca-certificates, usbutils first"
  command -v sudo >/dev/null 2>&1 || die "sudo not found; install prerequisites manually"

  if command -v cloud-init >/dev/null 2>&1; then
    sudo cloud-init status --wait || true
  fi

  # shellcheck disable=SC1091
  . /etc/os-release
  case "${ID:-} ${ID_LIKE:-}" in
    *debian*|*ubuntu*)
      sudo apt-get update
      sudo apt-get install -y git make python3-venv python3-pip ca-certificates usbutils
      ;;
    *arch*)
      sudo pacman -S --needed --noconfirm git make python usbutils
      ;;
    *)
      die "unsupported distro '$ID'; install git, make, Python 3.10+, venv, usbutils"
      ;;
  esac

  need python3; need git; need make; check_python; check_venv
}

setup_udev() {
  local group="dialout" tmp=""
  # shellcheck disable=SC1091
  . /etc/os-release
  case "${ID:-} ${ID_LIKE:-}" in *arch*) group="uucp" ;; esac

  if [ -e /dev/thd75 ]; then
    note "/dev/thd75 already exists"
    return 0
  fi
  echo
  warn "The udev rule needs sudo and changes serial-device permissions."
  confirm "Install the /dev/thd75 udev rule now?" || {
    note "Skipped udev; set up the serial device later."
    return 0
  }
  tmp="$(mktemp)"
  cat >"$tmp" <<UDEV
SUBSYSTEM=="tty", ATTRS{idVendor}=="2166", ATTRS{idProduct}=="9023", MODE="0660", GROUP="$group", SYMLINK+="thd75"
UDEV
  sudo install -m 0644 "$tmp" /etc/udev/rules.d/99-kenwood-thd75.rules
  rm -f "$tmp"
  sudo udevadm control --reload-rules
  sudo udevadm trigger

  if ! id -nG "$USER" | tr ' ' '\n' | grep -qx "$group"; then
    confirm "Add $USER to the '$group' group? You must log out/in afterward." && \
      sudo usermod -aG "$group" "$USER" || warn "Group not changed; serial permission may fail."
  fi
  note "Reconnect the radio, then check: ls -l /dev/thd75"
}

setup_services() {
  local expected="$HOME/TH-D75-MCP"
  echo
  warn "This installs persistent systemd user units."
  confirm "Install and start d75mon + settings-ui as user services?" || {
    note "Skipped service installation."
    return 0
  }
  if [ "$REPO_ROOT" != "$expected" ]; then
    warn "Repo is not at $expected."
    warn "Edit the unit paths or clone there, then run with --print-service."
    return 0
  fi
  mkdir -p "$HOME/.config/systemd/user"
  cp "$REPO_ROOT/d75mon/systemd/d75mon.service.example" \
     "$HOME/.config/systemd/user/d75mon.service"
  cp "$REPO_ROOT/settings-ui/systemd/d75settings.service.example" \
     "$HOME/.config/systemd/user/d75settings.service"
  systemctl --user daemon-reload
  systemctl --user enable --now d75mon.service
  systemctl --user enable --now d75settings.service
  note "Services installed. Both bind to loopback by default."
}

setup_mode() {
  [ -t 0 ] || die "--setup is interactive; use --check for scripts/agents"
  note "Lazy setup: no radio settings are written by this script."
  install_deps_if_needed
  validate_skill

  note "Running non-privileged build checks"
  make -C "$REPO_ROOT" check

  setup_udev
  setup_services

  echo
  echo "------------------------------------------------------------"
  echo "Open (loopback):"
  echo "  settings: http://127.0.0.1:8098/"
  echo "  monitor:  http://127.0.0.1:8099/"
  echo
  echo "Settings mode still requires clicking Read / Apply in the UI."
  echo "No firmware or radio settings were written by this script."
  echo "See SECURITY.md: no auth; use an SSH tunnel for remote access."
  echo "------------------------------------------------------------"
}

if [ "$MODE" != "setup" ]; then
  note "repo: $REPO_ROOT"
  need python3
  need git
  need make
  check_python
  check_venv
  validate_skill
fi

case "$MODE" in
  check)
    note "running non-privileged build checks (no radio, sudo, udev, or systemd)"
    make -C "$REPO_ROOT" check
    note "check-only complete: 9 tests expected, no radio touched"
    ;;
  install)
    note "creating venv and installing requirements (no service/radio changes)"
    make -C "$REPO_ROOT" venv
    note "install complete. Next: run the monitor or settings UI from README."
    ;;
  setup)
    setup_mode
    ;;
  print-service)
    case "$TARGET" in
      settings)
        cat <<'EOF'
# Check the paths before running; do not paste blindly.
mkdir -p ~/.config/systemd/user
cp settings-ui/systemd/d75settings.service.example ~/.config/systemd/user/d75settings.service
# Edit WorkingDirectory/ExecStart if the repo is not at ~/TH-D75-MCP.
systemctl --user daemon-reload
systemctl --user enable --now d75settings.service
EOF
        ;;
      monitor)
        cat <<'EOF'
mkdir -p ~/.config/systemd/user
cp d75mon/systemd/d75mon.service.example ~/.config/systemd/user/d75mon.service
# Edit WorkingDirectory/ExecStart if the repo is not at ~/TH-D75-MCP.
systemctl --user daemon-reload
systemctl --user enable --now d75mon.service
EOF
        ;;
      *)
        die "unknown --target '$TARGET' (settings|monitor)"
        ;;
    esac
    note "printed service steps only; nothing installed"
    ;;
  *)
    die "unknown mode"
    ;;
esac
