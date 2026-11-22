# The lazy path

**For hams who would rather operate the radio than memorize 400 menu numbers.**

This is the shortest honest path. It still needs a Linux machine attached to
the radio, but it removes most terminal archaeology.

## You need

- Linux host physically connected to the TH-D75 via USB
- Repo/skill access (request-only skill)
- About five minutes
- An agent, or a terminal if you are feeling brave

## Path A — let an agent do it

Give your agent this prompt:

```text
Install the TH-D75 tools on this Linux host.

Repo: git@github.com:dennis-kf0rlx/TH-D75-MCP.git
Skill: skills/th-d75-tools/SKILL.md

Follow the skill. Start with bootstrap.sh --check. If this is an interactive
human session, run bootstrap.sh --setup and ask me before sudo, udev, systemd,
or radio operations. Do not write radio settings. No radio attached is OK for
install/build.
```

The agent may ask you to approve:

1. installing packages
2. a udev rule (and a serial group, usually `dialout` or `uucp`)
3. two systemd **user** services

Those are the only privileged parts. Say yes if you want the lazy path.

## Fast path — curl installer (once released)

When the tools release is public:

```bash
curl -fsSL -o thd75-install.sh \
  https://github.com/dennis-kf0rlx/TH-D75-MCP/releases/latest/download/install.sh
less thd75-install.sh
bash thd75-install.sh
```

It verifies the release checksum, extracts to `~/TH-D75-MCP`, and asks before
udev/systemd setup. In a graphical terminal it opens an install-report page in
your browser, then redirects to the settings UI. Do not pipe `curl` to Bash as
the default.

## Path B — do it yourself from a clone

```bash
git clone git@github.com:dennis-kf0rlx/TH-D75-MCP.git
cd TH-D75-MCP
./scripts/bootstrap.sh --setup
```

It runs the build checks first, then asks before udev/services. Nothing is
written to the radio.

## Then

Open locally:

- Settings: **http://127.0.0.1:8098/**
- Monitor: **http://127.0.0.1:8099/**

The settings UI does not read the radio until you click **Read from radio**.
Settings mode intentionally pauses the monitor and takes one USB reset on exit.
If MCP wedges, the radio may need a physical power cycle — the UI/agent cannot
press the button for you.

## What “lazy” does not mean

- No authentication: keep both ports on localhost or a trusted LAN, preferably
  behind an SSH tunnel.
- No firmware flashing, bootloader, or calibration work.
- No automatic settings changes: you still choose the setting and confirm the
  write.
- No support for random menu-number guessing; the catalog is the boundary.

## If it fails

```bash
./scripts/bootstrap.sh --check
```

That path never uses sudo, udev, systemd, or the radio and should isolate build
problems. Then read `SECURITY.md`, `docs/SAFETY.md`, and the skill’s stop
conditions. If the agent says the radio is wedged, power-cycle it and continue.
