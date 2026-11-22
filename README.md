# TH-D75 tools

Open-source tools and reverse-engineering notes for the **Kenwood TH-D75**
(amateur radio), focused on V1.03.

**Nothing here redistributes firmware images, clone images, or radio-private
data.** The bootloader and factory-calibration regions are deliberately never
written.

## Projects

### `settings-ui/` — web settings editor

A local web UI for the TH-D75's menu settings, with a persistent-MCP backend:

- search settings by name, not menu number;
- read current values from the radio;
- write only changed fields with read-back verification;
- hold one MCP session open for the whole editing session (no USB reset per
  save), then exit and restart the monitor once.

The backend keeps the MCP session alive with a 0.5 s page-read keepalive, then
exits cleanly on **Exit settings** or idle timeout.

![Settings UI](screenshots/settings-ui.png)

### `d75mon/` — read-only monitor widget

A small CAT monitor served as a "radio face" widget: status, monitor state, and
(with the documented firmware-assisted reader) live VFO/screen data. It is
read-only apart from `AI 0` at connect.

### `docs/` — findings

- `menu-map.tsv` — 400 MCP settings: ID, offset, menu number, firmware row/label
- `menu-rows.tsv` — 217 firmware menu rows: label, menu number, category,
  mapping status
- `firmware-findings.md` — menu/CAT/firmware-map summary and limitations
- `mcp-protocol.md` — MCP entry, page read/write, ACK, idle timeout and keepalive
- `gps-altitude.md` — reading live GPS altitude through NMEA PC output
- `PROVENANCE.md` — data sources and redistribution caveats

## Safety

- Settings writes are limited to the published catalog; bootloader,
  factory-calibration pages, blobs and non-MCP fields are rejected.
- High-risk settings require explicit confirmation.
- The settings service intentionally pauses `d75mon` while MCP mode is active.
- The radio can require a power cycle after a failed MCP session; the docs call
  this out.

## License

- Code: **GPL-2.0-or-later** (see `LICENSE`).
- Documentation and menu data: **CC BY-SA 4.0** (see `docs/LICENSE`).
- Upstream protocol/tooling credit: [swiftraccoon/kenwood](https://github.com/swiftraccoon/kenwood),
  which is GPL-2.0.

These are independent implementations; no upstream source code or firmware
images are included.
