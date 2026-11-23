# Testing the installer locally

The public release exists, but this loop tests a local release fixture so you
do not depend on GitHub or publish a tag to check installer changes.

## One command

```bash
make test-installer
```

This:

1. builds a **temporary** public-style release fixture
2. serves it on a free loopback port
3. runs `install.sh --check` against that local mirror
4. verifies checksum, extraction, install report, and the 9 build tests
5. cleans up, including the fixture and temporary install

No GitHub release, sudo, services, radio, or leftover `dist/` are involved.

`make dist` is the explicit command when you want a persistent local release
artifact; `make dist-clean` removes it.

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
  --setup --prefix ~/thd75-web-console
```

This exercises package installation, udev, services, and the report redirect.
Do this only in a throwaway VM or a machine where those changes are acceptable.
