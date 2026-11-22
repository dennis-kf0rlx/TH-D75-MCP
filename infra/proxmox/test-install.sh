#!/usr/bin/env bash
# Guarded Proxmox install-test runner. Dry-run by default.
# Runs on the Proxmox host (needs `qm`) and never touches radio/USB devices.
set -euo pipefail

TEMPLATE=""
VMID=""
IP=""
SSH_USER="d75test"
SSH_KEY="${D75_TEST_SSH_KEY:-}"
KEEP=0
EXECUTE=0

usage() {
  cat <<'USAGE'
Usage (on the Proxmox host, from a checkout of TH-D75-MCP):
  ./infra/proxmox/test-install.sh --template 9000 --vmid 201 [options]

Default is dry-run. Required with --execute:
  --ip <vm-ip>          guest IP reachable from the Proxmox host
  D75_TEST_SSH_KEY      private key path for the guest's d75test user

Options:
  --execute             actually clone/start/test/destroy
  --keep                keep the VM after the test
  --ssh-user <user>     default d75test
  --help

The runner copies a clean repo tar to the VM, runs
`skills/th-d75-tools/scripts/bootstrap.sh --check`, and destroys the clone on
success/failure unless --keep. It does not test radio/MCP behavior.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --template) TEMPLATE="${2:-}"; shift 2 ;;
    --vmid) VMID="${2:-}"; shift 2 ;;
    --ip) IP="${2:-}"; shift 2 ;;
    --ssh-user) SSH_USER="${2:-}"; shift 2 ;;
    --execute) EXECUTE=1; shift ;;
    --keep) KEEP=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[ -n "$TEMPLATE" ] && [ -n "$VMID" ] || die "--template and --vmid are required"
command -v qm >/dev/null 2>&1 || die "qm not found; run this on the Proxmox host"

if [ "$EXECUTE" -eq 0 ]; then
  cat <<EOF
DRY RUN — no VM created.
  template: $TEMPLATE
  target VMID: $VMID
  guest IP: ${IP:-<discover via qm guest cmd>}
  ssh user: $SSH_USER
  keep: $KEEP
  repo: $(pwd)
Re-run with --execute and --ip <vm-ip> plus D75_TEST_SSH_KEY=<private-key>.
EOF
  exit 0
fi

[ -n "$IP" ] || die "--ip is required with --execute"
[ -n "$SSH_KEY" ] && [ -f "$SSH_KEY" ] || die "D75_TEST_SSH_KEY must point to a private key"
qm status "$TEMPLATE" >/dev/null 2>&1 || die "template $TEMPLATE not found"
qm status "$VMID" >/dev/null 2>&1 && die "VMID $VMID already exists"

TARBALL="$(mktemp /tmp/d75-repo.XXXXXX.tar.gz)"
cleanup() {
  rm -f "$TARBALL"
  if [ "$KEEP" -eq 0 ] && qm status "$VMID" >/dev/null 2>&1; then
    qm stop "$VMID" --skiplock 2>/dev/null || true
    qm destroy "$VMID" --purge 2>/dev/null || true
  fi
}
trap cleanup EXIT

tar --exclude=.git --exclude=.venv --exclude=__pycache__ \
  -czf "$TARBALL" -C "$(pwd)" .

qm clone "$TEMPLATE" "$VMID" --name "d75-test-$VMID" --full 0
qm start "$VMID"
for _ in $(seq 1 60); do
  if ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
      -o ConnectTimeout=3 "$SSH_USER@$IP" true 2>/dev/null; then break; fi
  sleep 3
done
ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
  "$SSH_USER@$IP" true || die "SSH to guest failed"

scp -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
  "$TARBALL" "$SSH_USER@$IP:/tmp/d75-repo.tar.gz"
ssh -i "$SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
  "$SSH_USER@$IP" '
    set -euo pipefail
    rm -rf ~/TH-D75-MCP
    mkdir -p ~/TH-D75-MCP
    tar -xzf /tmp/d75-repo.tar.gz -C ~/TH-D75-MCP
    rm -f /tmp/d75-repo.tar.gz
    cd ~/TH-D75-MCP
    ./skills/th-d75-tools/scripts/bootstrap.sh --check
  '
echo "VM install test passed: VMID $VMID (keep=$KEEP)"
