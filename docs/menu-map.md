# TH-D75 menu / MCP map

Two TSV files are included:

## `menu-map.tsv`

Columns:

| Column | Meaning |
|---|---|
| `setting_id` | generated MCP field ID, e.g. `radio.BacklightControl` |
| `offset_hex` | MCP/clone-image byte offset |
| `menu_numbers` | handheld menu number(s), where known |
| `firmware_rows` | row index in the firmware menu-label table |
| `firmware_labels` | label(s) recovered from the firmware table |

Coverage: **400 settings**, **388 with handheld menu numbers**. The web settings
UI exposes the **255 scalar fields** (`settings-ui/catalog.json`); the rest are
lists, actions, and status rows.

## `menu-rows.tsv`

Columns:

| Column | Meaning |
|---|---|
| `row` | firmware menu-table row |
| `label` | label text |
| `menu` | handheld menu number |
| `setting_id` | best matching MCP field |
| `offset` | MCP offset, if mapped |
| `score` | string-match confidence |
| `status` | `mapped`, `unmapped`, `non-mcp`, `review` |
| `category` | `setting`, `action`, `list`, `status`, `non-mcp` |

Classification of the **217 menu rows**:

- 165 setting rows mapped
- 30 action rows
- 16 list-editor rows
- 4 non-MCP/hidden strings
- 2 status rows

The four non-MCP labels are documented in `firmware-findings.md`; they are most
likely legacy/sibling-model strings rather than active TH-D75 settings.
