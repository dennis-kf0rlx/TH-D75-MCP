# TH-D75 tools

Open-source tools and reverse-engineering notes for the **Kenwood TH-D75**
amateur radio (V1.03), built and tested on Linux.

Two runnable tools:

- **`settings-ui/`** — web menu editor using a persistent MCP settings session
- **`d75mon/`** — read-only CAT monitor widget

Plus **`docs/`** with the menu map, MCP protocol notes, firmware findings, and
GPS-altitude method.

![Settings UI](screenshots/settings-ui.png)

## Mission

> **Make every TH-D75 menu setting discoverable, readable, and changeable on a
> scalable web interface — without the radio's tiny screen or keypad.**

The D75 hides hundreds of settings behind nested menus, a small display, and a
small keypad. This project replaces menu-number hunting with search,
plain-language labels, large controls, and verified writes. It is accessibility
engineering for people with low vision or other needs — and, yes, laziness
engineering for people like me who would rather operate the radio than memorize
its menu tree.

Accessibility and laziness are the same problem here: remove the tiny-screen
tax. Fewer taps, fewer nested menus, fewer numbers to remember.

### Design principles

- **Findability over memorization.** Search by name or keyword, browse by
  category, and keep menu numbers as optional advanced metadata.
- **Readability at any scale.** The interface is responsive, works with browser
  zoom, uses a high-contrast theme, and keeps controls comfortably sized.
- **Minimum friction.** Laziness is a feature. One **Read from radio**, edit,
  **Apply**; cached values; no USB reset per save; a few clicks instead of a
  menu-tree expedition.
- **Keyboard and assistive-tech friendly.** Native form controls, labels and
  ARIA state, `/` to focus search, `Esc` to clear.
- **Safe by default.** Only changed fields are written and read back; high-risk
  settings require confirmation; the bootloader and calibration stay untouched.

### Accessibility status

Current: scalable responsive layout, browser zoom support, high-contrast dark
theme, keyboard search shortcut, native labelled controls, and no requirement
to read or remember menu numbers.

Not yet independently audited: full screen-reader walkthrough and a light
high-contrast theme. Those are explicit hardening items, not afterthoughts.
Accessibility is part of the mission, not a separate mode.

> **Safety:** nothing here redistributes firmware or clone images. Settings
> writes are limited to the published catalog; the bootloader and factory
> calibration are never touched. MCP failures can require a radio power cycle.

## Requirements

- Linux with Python **3.10+**
- `pyserial` (installed into a venv below)
- systemd **user** units for service mode
- TH-D75 connected over USB CDC (`/dev/ttyACM*`; `/dev/thd75` recommended)
- No compiler, npm, or frontend build step is required

The radio exposes CAT/MCP over USB. A udev rule gives it a stable name:

```bash
sudo tee /etc/udev/rules.d/99-kenwood-thd75.rules >/dev/null <<'UDEV'
SUBSYSTEM=="tty", ATTRS{idVendor}=="2166", ATTRS{idProduct}=="9023", MODE="0666", SYMLINK+="thd75"
UDEV
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect the radio, then verify:

```bash
ls -l /dev/thd75
```

## Build

There is nothing to compile; “build” is the Python environment:

```bash
git clone git@github.com:dennis-kf0rlx/TH-D75-MCP.git
cd TH-D75-MCP

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Or use the included Makefile:

```bash
make venv       # create .venv and install pyserial
make check      # py_compile + d75mon unit tests
```

## Run: settings UI

```bash
.venv/bin/python settings-ui/server.py
```

Open **http://<host>:8098/**. The UI:

1. loads the catalog and cached values (no radio I/O on page load);
2. **Read from radio** pauses `d75mon`, enters MCP once, and reads all fields;
3. edits/Apply use the same persistent MCP session;
4. **Exit settings** leaves MCP (one USB reset), waits for re-enumeration, and
   restarts `d75mon`.

If you do not run `d75mon`, start settings-ui with a monitor unit that exists or
adjust `D75_MONITOR_UNIT`; the service expects the same user as the monitor.

### Service mode

```bash
mkdir -p ~/.config/systemd/user
cp settings-ui/systemd/d75settings.service.example \
   ~/.config/systemd/user/d75settings.service
# Edit WorkingDirectory/ExecStart if you cloned outside ~/TH-D75-MCP.
systemctl --user daemon-reload
systemctl --user enable --now d75settings.service
```

The example unit uses `%h/TH-D75-MCP` and `.venv`.

### Settings environment

| Variable | Default | Meaning |
|---|---|---|
| `D75SETTINGS_PORT` | `8098` | HTTP port |
| `D75_SERIAL` | `/dev/thd75` | radio serial device |
| `D75_MONITOR_UNIT` | `d75mon` | systemd user monitor unit |
| `D75SETTINGS_IDLE` | `300` | idle seconds before releasing MCP |
| `D75SETTINGS_KEEPALIVE` | `0.5` | MCP keepalive interval, seconds |

Run from any directory; the server locates its own static files.

## Run: d75mon monitor

```bash
.venv/bin/python d75mon/backend/d75mon.py --config d75mon/config.json
```

Open **http://<host>:8099/**. The backend resolves `web_dir` relative to the
`d75mon/` directory, so no working-directory setup is needed.

### d75mon tests

```bash
.venv/bin/python -m unittest discover -s d75mon/tests
```

### d75mon service

```bash
mkdir -p ~/.config/systemd/user
cp d75mon/systemd/d75mon.service.example ~/.config/systemd/user/d75mon.service
# Edit paths if needed, then:
systemctl --user daemon-reload
systemctl --user enable --now d75mon.service
```

### d75mon configuration

Edit `d75mon/config.json`:

```json
{
  "host": "0.0.0.0",
  "port": 8099,
  "transport": "auto",
  "usb_candidates": ["/dev/thd75", "/dev/ttyACM0"],
  "bluetooth": "/dev/rfcomm0",
  "baudrate": 9600,
  "web_dir": "web",
  "asset_dir": ""
}
```

- `transport`: `auto`, `usb`, or `bluetooth`
- `asset_dir`: optional directory for firmware-image assets
- Live VFO/screen fields require the documented firmware-assisted `GM` reader;
  stock V1.03 exposes only the text-CAT status fields. The unpatched monitor
  labels missing fields honestly.

## Verify the build

```bash
make check
```

Equivalent:

```bash
.venv/bin/python -m py_compile \
  settings-ui/server.py settings-ui/generate_catalog.py \
  d75mon/backend/d75mon.py d75mon/tests/test_cat.py
.venv/bin/python -m unittest discover -s d75mon/tests
```

## Regenerate the settings catalog

`settings-ui/catalog.json` is committed, so this is optional. Inputs are the
upstream MCP-D75 menu schema, this repo's `docs/*.tsv`, and the upstream menu
number index:

```bash
.venv/bin/python settings-ui/generate_catalog.py \
  --schema /path/to/mcp_d75_menu_schema.json \
  --menu-map docs/menu-map.tsv \
  --menu-rows docs/menu-rows.tsv \
  --swift-index /path/to/THD75MenuNumberIndex.swift \
  --out settings-ui/catalog.json
```

## Repo layout

```text
settings-ui/          web settings editor + backend
  server.py
  index.html / styles.css / app.js / catalog.js
  catalog.json
  generate_catalog.py
  systemd/d75settings.service.example
d75mon/               read-only monitor widget
  backend/d75mon.py
  web/
  config.json
  systemd/d75mon.service.example
  tests/
docs/                 menu map, row map, MCP protocol, firmware findings, GPS
screenshots/
Makefile
requirements.txt
```

## MCP notes

- Entry is `0M PROGRAM\r` — **no leading CR**. A leading CR produces `?\r` and
  breaks strict upstream implementations.
- Page read/write frames are documented in `docs/mcp-protocol.md`.
- The MCP session times out after roughly **2 s of idle**. A **0.5 s**
  keepalive page read keeps it open without a USB reset.
- Entry does not reset USB; exit does. Expect exactly one reset when leaving
  settings mode.
- CHIRP's clone path works but performs a full image transfer and multiple USB
  resets; the persistent MCP session is the interactive path.

## Troubleshooting

- **`/dev/thd75` missing** — check `lsusb | grep 2166`, the udev rule, cable, and
  radio power. A failed MCP session may require a physical power cycle.
- **`Permission denied` on serial** — add the user to the serial group or use
  the udev rule; confirm `ls -l /dev/thd75`.
- **MCP short read / CAT unresponsive** — power-cycle the radio. Do not loop
  MCP entries on a wedged session.
- **`d75mon` stopped in settings mode** — intentional; Exit settings restarts it.
- **HTTP 409** — another read/apply is in flight; retry after it finishes.
- **GPS altitude jumps** — NMEA altitude is only as good as the fix; 4-satellite
  fixes can be tens of metres off vertically.

## Documentation

- `docs/menu-map.md` / `docs/menu-map.tsv` — 400 settings
- `docs/menu-rows.tsv` — 217 firmware menu rows
- `docs/firmware-findings.md` — menu/string/CAT findings
- `docs/mcp-protocol.md` — entry, page frames, ACKs, keepalive
- `docs/gps-altitude.md` — NMEA altitude capture
- `docs/REFERENCES.md` — upstream projects consulted
- `docs/PROVENANCE.md` — data sources and redistribution caveats

## License

Original code and docs are **MIT** licensed (see `LICENSE`). Third-party
references remain under their own licenses; see `docs/REFERENCES.md`.
