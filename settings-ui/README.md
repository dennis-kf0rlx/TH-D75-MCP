# TH-D75 Settings UI

A searchable, scalable web settings editor for the TH-D75 — built to replace
the radio's tiny screen and keypad for menu work, and to make obscure settings
findable without memorizing menu numbers. Accessibility and low-friction
workflows are design goals, not add-ons.

- **Backend:** Python 3 + `pyserial`; no npm or other runtime dependencies.
- **Frontend:** plain HTML/CSS/JS served by the backend.
- **Catalog:** 255 scalar MCP menu fields from the generated MCP-D75 catalog.
- **Default endpoint:** `http://<host>:8098/`.

## How it works

The radio resets USB every time it leaves MCP programming mode, so the backend
does not use CHIRP per operation. It:

1. stops the `d75mon` monitor and enters MCP **once** (no USB reset on entry);
2. reads/writes sparse MCP pages over one persistent session — no reset per read
   or save;
3. keeps the session alive with a single-page read every **0.5 s** (this
   firmware drops it after ~2 s of silence);
4. exits MCP on **Exit settings** or after 5 minutes idle — exactly one USB
   reset — then restarts the monitor.

While settings mode is active the radio is held in MCP mode and the monitor is
stopped deliberately. The UI says so.

## Apply transaction

1. Validate staged values against the catalog.
2. Reuse pages already read in the session.
3. Patch only changed bytes/bits/strings; write only changed pages.
4. Read those pages back and verify by value.
5. Save a private values snapshot in `backups/` (`0600`).

No bootloader, factory-calibration pages, blobs, or non-MCP fields are written.
High-risk settings require explicit confirmation.

## API

```text
GET  /api/status        -> {sessionActive, monitorActive, serialPresent, busy, lastError}
GET  /api/catalog       -> {generated, schema_version, settings:[...]}
GET  /api/values        -> {model, firmware, values:{id:value}, updatedAt}
GET  /api/read          -> enter/read settings mode; {values, readAt, settingsMode}
POST /api/apply         -> {changes:[{id,value}], confirmHighRisk}
POST /api/session/stop  -> leave settings mode; one USB reset, monitor restarted
```

A process lock serializes operations; a second request gets HTTP 409.

## Configuration

Environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `D75SETTINGS_PORT` | `8098` | HTTP port |
| `D75_SERIAL` | `/dev/thd75` | radio serial device |
| `D75_MONITOR_UNIT` | `d75mon` | systemd **user** monitor unit to pause/restart |
| `D75SETTINGS_IDLE` | `300` | idle seconds before releasing MCP |
| `D75SETTINGS_KEEPALIVE` | `0.5` | MCP keepalive interval, seconds |

The service must run as the same user as the monitor unit and needs permission to
open the radio's serial device.

## Install (from the repo root)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
D75_SERIAL=/dev/thd75 .venv/bin/python settings-ui/server.py
```

Then open `http://<host>:8098/`. A systemd user unit is included as
`systemd/d75settings.service.example`; the README at the repository root has the
full service setup.

## Catalog generation

`catalog.json` is included so the UI runs out of the box. It was generated from
the upstream MCP-D75 menu schema plus the menu-map/row maps in `../docs/`.
To rebuild it:

```bash
python3 generate_catalog.py \
  --schema /path/to/mcp_d75_menu_schema.json \
  --menu-map ../docs/menu-map.tsv \
  --menu-rows ../docs/menu-rows.tsv \
  --swift-index /path/to/THD75MenuNumberIndex.swift \
  --out catalog.json
```

## MCP protocol notes

- **Entry must not prepend CR.** Send `0M PROGRAM\r`; this firmware answers a
  leading CR with a stray `?\r`. Accept `0M\r`.
- Entry leaves the USB device number unchanged; only exit resets USB.
- MCP idle timeout is ~2 s; the 0.5 s keepalive is what makes a persistent
  settings session possible.
- Immediate repeated page reads are fine; the failure mode was idle timeout.
- CHIRP switches to 57600 baud after entry; this implementation stays at 9600.

## Files

- `index.html`, `styles.css`, `app.js`, `catalog.js` — UI
- `catalog.json` — generated catalog
- `generate_catalog.py` — catalog generator
- `server.py` — backend
- `systemd/d75settings.service.example` — user unit template

`values.json` and `backups/` are generated at runtime and gitignored.
