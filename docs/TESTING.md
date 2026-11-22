# Testing the installer without a public release

## One command

```bash
make test-installer
```

This:

1. builds `dist/` with the public-style release layout
2. serves it on a free loopback port
3. runs `install.sh --check` against that local mirror
4. verifies checksum, extraction, install report, and the 9 build tests
5. cleans up

No GitHub release, sudo, services, or radio are involved.

## Exact curl-style test

```bash
make dist
python3 -m http.server 8097 --bind 127.0.0.1 --directory dist
```

In another terminal:

```bash
THD75_RELEASE_BASE=http://127.0.0.1:8097 \
  bash install.sh --check --no-browser --prefix /tmp/thd75-local-test
```

The installer uses the same `latest/download/` path as the real release.

## Desktop browser preview

On a graphical desktop, omit `--no-browser`:

```bash
THD75_RELEASE_BASE=http://127.0.0.1:8097 \
  bash install.sh --check --prefix /tmp/thd75-preview
```

It runs checks, writes `/tmp/thd75-preview/install-report.html`, and opens the
install-notes page. Check mode does not redirect to the settings UI because the
services are not started.

To preview the real post-setup report, run the installer in a disposable VM or
test host and choose the setup prompts.

## Disposable VM full path

```bash
bash install.sh \
  --local-tarball dist/latest/download/thd75-tools.tar.gz \
  --sha256 dist/latest/download/thd75-tools.tar.gz.sha256 \
  --setup --prefix ~/TH-D75-MCP
```

This exercises package installation, udev, services, and the report redirect.
Do this only in a throwaway VM or a machine where those changes are acceptable.
