# Agent skills

`th-d75-tools/` is the **request-only** Agent Skill for installing, running, and
troubleshooting the TH-D75 tools.

## Access

The skill is not part of the public tools release and must not be redistributed.
See [REQUEST-ACCESS.md](REQUEST-ACCESS.md) for the request process.

The skill currently lives in this private tools repository. Before making the
tools repo public, move this directory to the private
**`TH-D75-agent-skill`** repository and leave only `REQUEST-ACCESS.md` in the
public repo. See `../docs/RELEASE.md`.

## Human-facing lazy path

See the repository root `LAZY.md` and `bootstrap.sh --setup`. The setup mode is
interactive and asks before udev, systemd, or package installation. Agents should
not run it unattended.

## Safety

The skill is human-directed and read-only by default. It requires explicit user
confirmation for `sudo`, udev, systemd, radio writes, LAN binding, and
power-cycling.

## Before cloning

The skill file is delivered first. Install `git make python3-venv python3-pip
ca-certificates usbutils` (Debian names), then clone the repo and follow
`SKILL.md` §0.

## Bootstrap helper

Inside the private skill checkout:

```bash
./scripts/bootstrap.sh --check
```

`--check` never touches the radio, `sudo`, udev, or systemd. `--print-service`
only prints service steps; it installs nothing.
