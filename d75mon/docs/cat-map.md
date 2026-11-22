# TH-D75 CAT control map (reverse-engineered, V1.03)

Source of truth: the stock CAT dispatch table in `FIRMWARE_0x00200000.bin`.

- CAT table: **flat `0x2E1E8` → runtime `0xC002E1E8`**, **56 entries × 8 bytes**
  (`[0..3]` handler pointer with Thumb bit, `[4..7]` two-character mnemonic +
  padding). The `CMP R4, #0x38` bound at flat `0x2E192` matches 56 entries.
  (Earlier note "table at 0x2E1C8" was 8 bytes of preceding data too early.)
- Dispatch: linear scan comparing two bytes, `BLX table[i].handler`; R2 points
  at a one-byte completion status (normal handlers store 2).

## Tokens (in table order)

| # | Token | # | Token | # | Token | # | Token |
|---|-------|---|-------|---|-------|---|-------|
| 0 | 0G | 14 | SH | 28 | GM | 42 | MS |
| 1 | 0E | 15 | TX | 29 | SM | 43 | PT |
| 2 | AI | 16 | UP | 30 | RA | 44 | AS |
| 3 | AG | 17 | VM | 31 | BT | 45 | DC |
| 4 | BC | 18 | FQ | 32 | FS | 46 | DS |
| 5 | BY | 19 | FO | 33 | FT | 47 | RT |
| 6 | DL | 20 | PS | 34 | MD | 48 | FR |
| 7 | DW | 21 | FV | 35 | SF | 49 | US |
| 8 | ME | 22 | BE | 36 | VD | 50 | GW |
| 9 | MR | 23 | ID | 37 | VG | 51 | SD |
| 10 | PC | 24 | CS | 38 | VX | 52 | 0M |
| 11 | RX | 25 | TN | 39 | IO | 53 | AE |
| 12 | SQ | 26 | BL | 40 | BS | 54 | TY |
| 13 | SR | 27 | GP | 41 | LC | 55 | (end) |

`GM` on stock V1.03 reboots into GPS-only mode; after `normal-gm-ddr-read` it is
repurposed as the DDR reader (`GM ooooooo,ll`).

## Query results (stock/patched V1.03, live probes)

Verified answers observed live: `AI 0`, `AG 192`, `BC 0`, `DL 0`, `DW DW`,
`PS`, `FV 1.03`, `ID TH-D75`, `CS N0CALL`, `TN 1,0`, `BL 4`, `GP 1,0`,
`BT 0`, `FS 0`, `FT 0`, `VD 1`, `VG 1`, `VX 1`, `IO 0`, `BS 1`, `LC 1`,
`GS 1,0,0,0,1,0`, `PT 2`, `AS 0`, `DS 1`, `RT <yymmddhhmmss>`, `FR 1`,
`GW 0`, `SD 1`, `TY K,2`, `AE C4410419,K01`, `RA`, `SM`.
Rejected as unsupported on stock: `BY ME MR PC SQ SR SH TX? UP? VM? FQ? FO?`
(several were earlier confirmed `?`; the ones marked `?` here are unverified
after the incident on 2026-11-21).

## Parameter-memory addresses (static candidate map)

Each handler calls a per-setting accessor layer; accessors that call the
parameter-read helper `0xC0011610` with small address literals reveal the
CAT parameter addresses. Candidates (verify dynamically before writing):

- `0x1002`, `0x1005`, `0x1008`, `0x1009`, `0x100A`, `0x1026`, `0x1078`,
  `0x1104`, `0x1105`, `0x1206`, `0x120B`, `0x120C`, `0x136A`
  (plus two RAM pointers `0xC23E4E30`, `0xC23E5E77` used by RT/FR-style code).

Per-token candidate sets (union of accessors called by the handler; walkers are
shared, so this is a superset — narrow down by testing get/set round-trips):

| Token | candidate params | Token | candidate params |
|---|---|---|---|
| AI | 0x1206 | AG | 0x1206 |
| BC DL DW ME | 0x1105 | MR | 0x1105, 0x120C, 0x136A |
| PC RX SQ | 0x1008-0x100A, 0x120B/0x120C, 0x136A | SR SH | 0x1002, 0x1008-0x100A, 0x1104, 0x120B |
| TX UP VM FQ | 0x1002, 0x1104 | PS FS | 0x1002, 0x1008-0x100A, 0x1026, 0x1104 |
| FV BE ID CS | 0x1002/0x1026/0x1104/0x1206/0x120B | TN | 0x1002, 0x1026, 0x1104, 0x120B |
| BL | 0x1002, 0x1008-0x100A, 0x1026, 0x1104, 0x120B | GP GM SM RA | 0x1002, 0x1008-0x100A, 0x1026, 0x1078, 0x1104, 0x120B, 0x136A |
| BT | 0x1002, 0x1008-0x100A, 0x1026, 0x1078, 0x1104, 0x136A | FT MD SF VD VG VX IO | 0x1002/0x1005/0x1026/0x1078/0x1104/0x136A |
| BS LC GS MS PT AS | 0x1005/0x1078/0x1105/0x120C/0x136A | 0M AE TY | 0x1005, 0x1078, 0x1105, 0x120C, 0x136A |

Key accessor functions (walkers): `0xC002DABC`, `0xC002DB16`, `0xC002DBA4`,
`0xC002DBC0`, `0xC002DBE4`, `0xC002DC0A`, `0xC002DC30`, `0xC002DC60`,
`0xC002DCC4`, `0xC002DD1A`, `0xC002DD5E`, `0xC002DE34`, `0xC002DF1E`,
`0xC002DF50`, `0xC002F4AA`, `0xC002F4F8`, `0xC002F552`, `0xC002F592`,
`0xC002F5E8`, `0xC002F614`, `0xC002F690`, `0xC002F6F0`, `0xC002F768`,
`0xC002F7C0`, `0xC002F8A8`, `0xC002DFC8`.

## Live state (DDR, read-only, via `GM`)

| Field | Address | Type |
|---|---|---|
| VFO A record (freq, offset, flags) | `0xC23E3700` | 40 B, u32 Hz @ +0, offset @ +4, flags @ +8 |
| VFO B record | `0xC23E3728` | same |
| FM broadcast receiver freq/mode/rssi | `0xC23E4EC0` | u32 Hz @ +0, mode @ +8, rssi @ +0x18 |
| LCD framebuffer | `0xC2349A40` | 240×180 RGB565, stride 480, 86,400 B |

## Safety notes for live set-command probing

- Do not send bare `TX`, `UP`, `VM`, `FQ`, `FO` etc. in one stream without
  understanding them: on 2026-11-21 a full-token query sweep stopped getting
  replies after bare `TX`. Power-cycle recovers.
- `GM` is destroyed by the patch (GPS mode) and is repurposed.
- Any CAT write changes radio settings; read-modify-write with verification and
  restore is mandatory.

## Dynamic set-test map (2026-11-22)

Safe protocol after the 2026-11-21 CAT hang:

1. **Set `AI 0` first** and verify it. `AI 1` + CHIRP clone read left CAT
   unresponsive; never clone-read with auto-info on.
2. Clone read command (exit status 1 means success):
   `/usr/bin/python3 /usr/bin/chirpc -s /dev/thd75 -r Kenwood_TH-D75 --download-mmap --mmap <file>`
3. A clone read **re-enumerates the radio's USB**; `/dev/thd75` disappears for
   ~1-2 s. Wait for it, verify `ID TH-D75`, then continue. Queries sent during
   re-enumeration look like a hang but are not.
4. Set-test: clone before → CAT set → verify query → clone after → wait/re-verify
   → restore → clone restored; diff before/after and after/restored. A correct
   setting changes exactly one byte and restores to identical.

Mapped clone/eeprom offsets (single byte, values 0/1):

| Token | Offset | Values | Notes |
|---|---|---|---|
| BS | 0x1005 | 0 off, 1 on | battery saver; static candidate confirmed |
| VX | 0x101B | 0/1 | voice setting |
| VG | 0x101C | 0/1 | voice setting |
| VD | 0x101D | 0/1 | voice setting |
| AG | — | transient | resets to `AG 006` after USB re-enumeration; not persisted |
| BL | — | read-only | `BL 3` returns `?` |

The static candidate map predates this and was incomplete for the voice trio
(only BS/0x1005 was listed). Clone image size here is 500,645 bytes.

### Batch 2 (2026-11-22)

| Token | Offset | Values | Notes |
|---|---|---|---|
| BC | 0x0395 | 0/1 | |
| DL | 0x0396 | 0/1 | |
| FR | 0x1040 | 0/1 | |
| LC | 0x1060 | 0/1 | |
| MS | 0x11C0 | packed | query 0/1; byte 0x05 ↔ 0x00 |
| AS | 0x120C | 0/1 | matches static candidate |

Read-only/rejected: FS, FT, DS (`N`); BL, GW (`?`); SF (`?` query); AG
transient (resets to `AG 006` after re-enumeration). All settings restored and
verified after each test; final radio state verified with ID/AI/queries.

## Upstream MCP-D75 registry (2026-11-22)

Complete 400-setting map generated from swiftraccoon/kenwood:
see `~/bu/Kenwood D-75/fw-analysis/menu-map.tsv` and memory
`th-d75-menu-map.tsv`. Corrected meanings: BS=Bar Antenna (0x1005/menu 104),
VX/VG/VD=VOX/Gain/Delay (0x101B-0x101D/150-152), FR=FM Radio Mode
(0x1040/700), LC=Backlight Control (0x1060/900), MS=My Position Select
(0x11C0/401), AS=TNC Data Speed (0x120C/505).

Row map: `menu-rows.tsv` (162 setting rows mapped, 155 high-confidence; all 217 rows classified as setting/action/list/status/missing). See memory `th-d75-menu-rows.tsv`.
