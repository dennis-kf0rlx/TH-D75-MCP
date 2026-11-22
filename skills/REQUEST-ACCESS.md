# Request access to the Agent Skill

The TH-D75 Agent Skill is **request-only**. It is not installed by cloning the
tools repo and it is not licensed for redistribution.

## Why request-only

The skill can walk an agent through privileged installation and radio-settings
operations. Keeping it behind repository access:

- limits accidental autonomous radio writes;
- keeps the safety contract reviewed by a human;
- lets access be revoked if the skill is abused.

This is access control, not DRM. Do not paste the skill into public issues,
gists, or unlisted links.

## Before you begin (skill delivered first)

The requester receives `SKILL.md` before the repo. Install the minimum tools
first, then clone; a minimal Debian image lacks Git/Make/venv:

```bash
sudo apt-get update
sudo apt-get install -y git make python3-venv python3-pip ca-certificates usbutils
git clone git@github.com:dennis-kf0rlx/TH-D75-MCP.git
cd TH-D75-MCP
```

Then continue with `SKILL.md` §0/§1. Installation/build is valid with no radio
attached.

## Request

Contact the repository maintainer through GitHub (open an issue in the tools
repo or use the maintainer contact on the profile) and include:

- your GitHub username;
- what you want to do (install only / monitor only / settings operation);
- the Linux distribution and radio connection type (USB or Bluetooth).

Until the split, request read access to this private tools repository on a
case-by-case basis. After the public release, access is granted through the
private `TH-D75-agent-skill` repository.

## What you get

A `SKILL.md` with:

- read-only default and explicit consent gates;
- `sudo`/udev/systemd/power-cycle restrictions;
- install-only, monitor-only, and settings-operation modes;
- preflight, acceptance checks, and stop conditions;
- private-data handling.

## Safety

Never run a radio-writing step unattended. Do not expose the unauthenticated web
UI to the internet. See `SECURITY.md` and `docs/SAFETY.md`.
