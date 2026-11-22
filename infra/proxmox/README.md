# Disposable Proxmox VM runway

Purpose: test **clone → bootstrap → make check → optional service install** on a
clean Linux VM without touching the radio host.

This is maintainer tooling. It does **not** test MCP/radio behavior. Snapshots
reset the VM, not the radio. Radio acceptance stays on the physical host, and
only the user power-cycles a wedged radio.

## Target layout

- Proxmox VE host: `prox`
- Debian 13 genericcloud image (2 vCPU, 2 GiB RAM, 16 GiB disk)
- Template: `9000`, name `d75-test-template`
- Per test: linked clone, e.g. `201`, then destroy
- No radio USB passthrough
- Egress allowed for apt/git; inbound SSH only from the lab host
- Do not expose ports 8098/8099

## Build the template (once)

On `prox`, with a Debian 13 genericcloud qcow2 downloaded to a scratch path:

```bash
# Example; verify the current image name/URL.
IMG=/var/lib/vz/template/iso/debian-13-genericcloud-amd64.qcow2
qm create 9000 --name d75-test-template --memory 2048 --cores 2 \
  --net0 virtio,bridge=vmbr0 --scsihw virtio-scsi-pci --ostype l26 \
  --serial0 socket --vga serial0 --agent enabled=1
qm importdisk 9000 "$IMG" local-lvm
qm set 9000 --scsi0 local-lvm:vm-9000-disk-0 --boot order=scsi0
qm set 9000 --ide2 local-lvm:cloudinit
qm set 9000 --ciuser d75test --sshkeys /root/d75-test-key.pub \
  --ipconfig0 ip=dhcp
qm template 9000
```

`cloud-init.yaml` in this directory is a reference for package/user setup.

## Run an install-only test

```bash
./infra/proxmox/test-install.sh --template 9000 --vmid 201 --execute
```

Default is dry-run. `--execute` clones, starts, waits for SSH, copies a clean
repo tar, runs `bootstrap.sh --check`, then destroys the clone. It refuses a
running/config-existing target and does not touch USB devices.

For a persistent test:

```bash
./infra/proxmox/test-install.sh --template 9000 --vmid 201 --execute --keep
```

Then clean up with `qm destroy 201`.

## Validated 2026-11-22

- Template `9000` (`d75-test-template`, Debian 13.7) created on `prox`.
- A linked clone booted, installed `git make python3-venv`, copied a clean repo
  tar, and ran `skills/th-d75-tools/scripts/bootstrap.sh --check`.
- Result: Python 3.13.5, skill frontmatter/contract valid, 9 d75mon tests passed.
- The clone was destroyed; the template remains for repeat tests.
- No radio, USB passthrough, settings writes, or service exposure was involved.
- The full clean-room result is in [`docs/CLEANROOM.md`](../../docs/CLEANROOM.md).

## Why not test the radio here?

- USB passthrough + QEMU reset/re-enumeration during MCP exit is not equivalent
  to bare metal.
- A VM snapshot cannot recover a radio left in a wedged MCP/CAT state.
- The real radio remains on the physical host; do not automate power-cycling.

## Alternatives considered

| Option | Verdict |
|---|---|
| LXC | fast, but udev/systemd user-service behavior differs |
| container/CI | good for `make check`, no systemd realism |
| GitHub Actions | recommended public CI for `make check` |
| cloud VM | good for install, no radio |
| physical spare host | best for real radio acceptance |

Recommended combination: **Proxmox VM for install/systemd tests + GitHub Actions
or container for build tests + physical host for radio acceptance.**
