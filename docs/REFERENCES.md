# Reference projects and resources

These were consulted while reverse-engineering the TH-D75 and building the
tools. They are **not** vendored here; each remains under its own licence.

| Reference | What it was used for | Licence / note |
|---|---|---|
| [swiftraccoon/kenwood](https://github.com/swiftraccoon/kenwood) | Rust TH-D75 library, TUI, `mcp_menu` example, generated MCP-D75 menu schema | GPL-2.0. Protocol and schema reference; no source copied |
| [CHIRP](https://github.com/chirp/chirp) / `chirp-next` | TH-D74/75 clone driver: MCP entry, page reads/writes, ACK timing, CHIRP clone path | GPL-3.0. Behavioural reference; no code copied |
| [LA3QMA/TH-D74-Kenwood](https://github.com/LA3QMA/TH-D74-Kenwood) | CAT command notes and TH-D74 command documentation | No explicit licence found; factual command reference |
| [LA3QMA/TH-D72-Kenwood](https://github.com/LA3QMA/TH-D72-Kenwood) | `0M PROGRAM` and CAT command notes | No explicit licence found; factual command reference |
| [xbenkozx/D75-CAT-Control](https://github.com/xbenkozx/D75-CAT-Control) | Desktop CAT-control UI prior art | GPL-3.0; reviewed, no code copied |
| Kenwood **TH-D75** user manual / in-depth manual | Menu numbers, labels, GPS/NMEA behaviour | Kenwood documentation; quoted as factual reference |
| Kenwood **MCP-D75** | Official menu schema/catalog reference | Proprietary installer/schema; not redistributed |

If you redistribute the generated `catalog.json`, review the Kenwood/MCP-D75
terms first. The menu-map and row-map TSVs are factual mapping tables; the
generated catalog is a projection of the official schema used to make the UI
usable.
