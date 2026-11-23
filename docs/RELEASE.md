# Release and skill-split checklist

The tools repo is **public** (first public release `v0.1.0`, 2026-11-22; current
`v0.1.9`). The Agent Skill is request-only: GitHub has no per-file access
control, so the skill lives in the private `TH-D75-agent-skill` repository, and
the public tree keeps only `skills/REQUEST-ACCESS.md` + `skills/README.md`.

## Public-release state (completed 2026-11-22)

1. `skills/th-d75-tools/` moved to the private `TH-D75-agent-skill` repository.
2. Public tree replaced it with `skills/REQUEST-ACCESS.md` + `skills/README.md`.
3. Public tree audited for `values.json`, `backups/`, clone images, firmware
   binaries/installers, callsigns, coordinates, serials, API keys, and
   author lab hostnames/IPs (only the author's own radio MAC appears, as an
   editable example in `infra/systemd/`).
4. `README`, `SECURITY.md`, `docs/SAFETY.md`, and `docs/PROVENANCE.md` present
   and linked.
5. `make check` (9 tests) and `scripts/test-installer.sh` pass.
6. `v0.1.0` tagged and released; later `v0.1.x` releases follow the checklist
   below.

## Checklist for each new release

1. `make check` and `make test-installer` pass locally.
2. Working tree clean; no `__pycache__`, `.venv`, `dist/`, `values.json`, or
   `backups/` in the tree.
3. Docs still match the code and the current release state (public repo, latest
   tag, ports, endpoints, paths).
4. Push a `v*` tag. `.github/workflows/release.yml` re-runs `make check`,
   refuses to publish if `skills/th-d75-tools/SKILL.md` is in the tree, builds
   the tarball/checksum/installer with `infra/` included, rejects
   `__pycache__`/private artifacts, and creates the GitHub release.
5. Verify the published assets: `thd75-tools-vX.Y.Z.tar.gz` (+ `.sha256`),
   `thd75-tools.tar.gz` (+ `.sha256`) as the latest alias, `install.sh`.
6. Quick public-path test: `bash install.sh --check --no-browser --prefix /tmp/x`
   against the real release.

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
