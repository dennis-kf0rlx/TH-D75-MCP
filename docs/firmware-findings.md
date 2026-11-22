# TH-D75 V1.03 firmware findings

Scope: static and live analysis of the author's own radio. No firmware image,
MCP-D75 installer, clone image, or calibration data is included in this repo.

## Menu / settings map

- 400 user-facing MCP menu settings were enumerated; 388 have handheld menu
  numbers.
- The firmware menu-label table contains **217 rows**: 165 mapped setting rows,
  30 action rows, 16 list-editor rows, 2 status rows, and 4 non-MCP/hidden
  labels.
- The last ambiguous rows were resolved as Data Frame Output (menu 618),
  Break Call (619), Select Type (620), Digital Code (621), and the Position
  Accuracy list field.
- Four labels — **Break-In**, **Delay Time**, **CW on FM**, **Power-on
  Password** — are absent from the TH-D75 manual menu table and the MCP-D75
  schema. They sit among CW/DTMF/security strings and are treated as
  legacy/sibling-model UI strings or hidden service-menu entries, not active
  TH-D75 settings.

## CAT / MCP

- 56-entry CAT dispatch table; 35+ tokens answered on stock V1.03.
- MCP entry is `0M PROGRAM` (no leading CR). A leading CR causes a `?\r`
  response on this firmware.
- MCP page transfer uses `R`/`W` frames with a 256-byte payload and `0x06`
  ACKs. Entry does not reset USB; exit does.
- The upstream `mcp_menu` example/ TUI MCP path failed on this unit because it
  prepends CR and requires an immediate `0M\r`. A tolerant, clean-entry
  implementation works.
- The MCP session drops after roughly 2 seconds of inactivity. A page read
  every 0.5 seconds keeps it alive; this is the basis of the persistent
  settings-mode backend.

## Flash / bootloader

- The firmware updater writes the main firmware and overlay images; the
  bootloader and factory calibration are intentionally left untouched.
- Low-NOR bootloader bytes were captured for analysis but are not redistributed
  here. The exact boot validation/copy/entry mechanics remain unconfirmed.
- Do not flash bootloader or calibration regions; a failed write can brick the
  unit.

## GPS altitude

See `gps-altitude.md`. GPS NMEA output and CAT share the same serial stream;
enable PC output with `GP 1,1`, listen without sending CAT commands, then
restore `GP 1,0`.
