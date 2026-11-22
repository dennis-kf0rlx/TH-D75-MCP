# Agent skills

- `th-d75-tools/SKILL.md` — end-to-end workflow for cloning, building, running,
  verifying, and troubleshooting the TH-D75 tools on a Linux host connected to
  the radio.

## Using it

Portable: point your agent at `skills/th-d75-tools/SKILL.md`.

DSH-style skill directory:

```bash
mkdir -p ~/.dsh/skills
ln -sfn "$PWD/skills/th-d75-tools" ~/.dsh/skills/th-d75-tools
```

Other frameworks: copy the `th-d75-tools/` directory into their skills folder.

The skill explicitly contains the safety gates: no firmware/bootloader writes,
stop the monitor before settings mode, one expected USB reset on exit, and a
power-cycle rule for a wedged MCP session.
