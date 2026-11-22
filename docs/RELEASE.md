# Public-release checklist

The tools repo can be public; the Agent Skill is request-only. GitHub has no
per-file access control, so the skill must be moved out before the tools repo
becomes public.

## Before making the tools repo public

1. Move `skills/th-d75-tools/` to a **private** `TH-D75-agent-skill` repository.
2. Replace it in the public repo with `skills/REQUEST-ACCESS.md` (already
   present).
3. Remove `skills/README.md` instructions that imply the skill is bundled.
4. Search the public tree for:
   - `values.json`, `backups/`, clone images
   - firmware binaries or MCP-D75 installers
   - callsigns, coordinates, addresses, serials, API keys
   - hostnames/IPs from the author's lab
5. Confirm `README`, `SECURITY.md`, `docs/SAFETY.md`, and
   `docs/PROVENANCE.md` are present and linked.
6. Run `make check`.
7. Run the docs warning audit: every `sudo`, systemd, udev, or radio-write block
   has a warning immediately above it.
8. Make the tools repo public; keep the skill repo private and grant access to
   the private repo on request only.

## Skill access policy

- Do not paste the skill into public issues, gists, or unlisted links.
- Do not include credentials, private radio data, or lab hostnames in the skill.
- Access is granted by repository invitation/team membership; access can be
  revoked.
- Access control is the boundary. The skill text itself is not a secret and
  should not contain secrets.

## Agent safety

The skill must remain read-only by default. Before a public release, confirm it
contains:

- MUST/MUST NOT/STOP contract
- host/device verification
- explicit consent for `sudo`, systemd, udev, bind changes, settings writes, and
  power-cycling
- no `curl | bash`
- no unattended radio writes
- private-data handling

## Rollback

If a public release accidentally includes private data or the skill:

1. Make the repo private immediately.
2. Rotate any exposed key/token.
3. Remove the file from git history, not just the working tree.
4. Re-run the audit before republishing.
