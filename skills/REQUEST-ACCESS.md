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

## Request

Contact the repository maintainer through GitHub (open an issue in the tools
repo or use the maintainer contact on the profile) and include:

- your GitHub username;
- what you want to do (install only / monitor only / settings operation);
- the Linux distribution and radio connection type (USB or Bluetooth).

The maintainer grants read access to the private `TH-D75-agent-skill` repo on a
case-by-case basis.

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
