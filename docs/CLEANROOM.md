# Clean-room test record

Purpose: verify that the request-only Agent Skill is sufficient for an agent
with **no prior context** to install and validate the project on a minimal
Linux host.

## Protocol

- Fresh Debian 13 cloud VM, 2 vCPU / 2 GiB, no git/make/pip/usbutils installed
- Skill file delivered out-of-band **before** the repo existed locally
- Fresh-context subagent with no session history
- Only instructions: `SKILL.md`
- Private repo access pre-arranged (SSH key); no credentials in the skill
- No radio, USB, udev, systemd, settings mode, or service installation
- Sudo/package install pre-authorized **inside the disposable VM only**
- VM destroyed after the test

## Results

| Run | Result | Finding |
|---|---|---|
| 1 | **FAIL** | Skill was only in the repo (chicken-and-egg), and preflight did not cover `make`/venv/pip/usbutils |
| 2 | **PASS** after installing prereqs | Install/build/check worked; found cloud-init apt-lock and known_hosts caveats |
| 3 | **PASS** | Skill self-sufficient with the fixed §0 prerequisites; 9/9 tests |

Run 3 details:

- Debian 13.7, Python 3.13.5; started with no git/make/pip/lsusb
- Followed §0: waited for cloud-init, installed packages, seeded GitHub host key,
  cloned the private repo
- §1 preflight passed, including `sudo`, venv, and pip checks
- `bootstrap.sh --check` passed: venv + pyserial, py_compile, 9/9 unit tests
- `make check` passed again; `git status` clean; no push
- No radio or service action was performed

## Lazy setup path

The interactive `bootstrap.sh --setup` path was exercised separately on a fresh
Debian 13 VM with no git/make:

- prompt-driven package install
- udev rule creation
- user serial group check
- both systemd user services enabled and started
- `d75mon` and `d75settings` bound **127.0.0.1:8099/8098**
- no radio, settings writes, or LAN exposure

This was a human-interactive flow driven through a pty, not a fresh agent.

## Limitations

This validates **install/build/check** and the interactive install path only. It does not validate udev, monitor
operation, settings mode, MCP write behavior, GPS capture, or real-radio
recovery. Those require a physical host and explicit user confirmation.

## Aftermath

The disposable VM was destroyed. The maintainer template remains for repeat
tests. A repo-access test key was used only inside the disposable VM and removed
afterward.

The audit does not make the skill public. Access remains request-only; see
`skills/REQUEST-ACCESS.md`.
