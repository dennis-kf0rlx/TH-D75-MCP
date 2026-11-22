# Agent skills

The request-only TH-D75 Agent Skill is **not** in this tools repository.

## Access

The skill lives in the private `TH-D75-agent-skill` repository and is granted by
request only. See [REQUEST-ACCESS.md](REQUEST-ACCESS.md).

Do not redistribute the skill or paste it into public issues/gists.

## Human-facing tools

The public tools repo contains the installer, bootstrap helper, settings UI, and
monitor. See the repository root `LAZY.md` and `docs/INSTALL.md`.

The installer's `scripts/bootstrap.sh --setup` is the human-facing entry point;
the skill is only the agent workflow around it.

## Safety

The tools are read-only by default. They require explicit user confirmation for
`sudo`, udev, systemd, radio writes, LAN binding, and power-cycling.
