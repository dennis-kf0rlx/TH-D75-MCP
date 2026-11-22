# Reading GPS altitude from the TH-D75

Live position/altitude is not exposed through CAT polling. `GP` is only
`gps_enabled,pc_output`; `GS` selects NMEA sentence types.

## One-shot capture

1. Stop the monitor, but keep CAT access.
2. Send `GP 1,1\r` to enable GPS PC output.
3. Do **not send further CAT commands**; NMEA and CAT share the same USB serial
   stream. Read `$GPGGA` / `$GPRMC` lines.
4. Restore with `GP 1,0\r`.

No USB reset is needed for this sequence (CAT-only).

`$GPGGA` fields:

| Index | Meaning |
|---|---|
| 6 | fix quality |
| 7 | satellites |
| 8 | HDOP |
| 9 | altitude above MSL |
| 10 | altitude unit (`M`) |
| 11 | geoid separation |

The altitude is MSL / orthometric, not survey-grade. With only 4 satellites and
HDOP 3.7, vertical error of tens of metres is possible; do not trust the radio's
altitude when the fix is weak. Horizontal position can still be usable.

## Keep CAT and NMEA separate

NMEA output and CAT command I/O compete on the same stream. Do not enable GPS PC
output while a CAT poller is running unless the poller can parse mixed traffic.
