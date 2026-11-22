# Provenance and redistribution notes

- Menu numbers, labels, and setting names were derived from the TH-D75 user
  manual, the official MCP-D75 menu schema/catalog, and the author's own
  reverse-engineering work.
- `menu-map.tsv` and `menu-rows.tsv` are factual mapping tables; they do not
  contain firmware code or images.
- `settings-ui/catalog.json` is a generated projection of the MCP-D75 menu
  schema used to make the UI usable. It contains setting names, offsets, value
  domains, and default values — no live radio data.
- No Kenwood firmware binary, MCP-D75 installer, clone image, calibration page,
  radio serial, callsign, location, or private settings are included.
- Upstream Rust tooling: [swiftraccoon/kenwood](https://github.com/swiftraccoon/kenwood), GPL-2.0.
  This repository does not copy its source code.
- If you redistribute the generated catalog, review the Kenwood/MCP-D75 terms
  first; the code and factual findings are independent work.

Docs are CC BY-SA 4.0. Code is GPL-2.0-or-later.
