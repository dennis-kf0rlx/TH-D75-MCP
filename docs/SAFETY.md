# Safety and limitations

This project talks to real radio hardware. Read this before using settings mode.

## Hard stops

**Never:**

- flash firmware, the bootloader, or factory-calibration regions;
- write to a serial device you have not positively identified as the TH-D75;
- expose the unauthenticated web UI to the internet;
- run settings mode unattended;
- retry a wedged MCP session in a loop.

**Ask the user first before:**

- `sudo`, udev, or systemd changes;
- entering settings mode or applying any setting;
- changing a bind address to a non-loopback interface;
- power-cycling the radio.

## Radio writes

- Settings writes are limited to generated catalog fields.
- Only changed bytes/bits/strings are written; pages are read back and verified.
- High-risk settings require explicit confirmation.
- Backups can contain callsigns, coordinates, APRS messages, and Bluetooth
  names; they are private.
- Firmware-updater, bootloader, calibration, clone-image, and factory-reset
  operations are **out of scope**.

## MCP session behavior

- MCP entry is clean-only: `0M PROGRAM\r` without a leading CR.
- Entry does not reset USB; exit does. Expect exactly one reset when leaving
  settings mode.
- The session times out after roughly two seconds of idle. The service keeps it
  open with a 0.5 s page-read keepalive.
- A failed/partially interrupted MCP session can leave CAT unresponsive. The
  recovery is a **physical radio power cycle**, which only the user can perform.
- Do not use the upstream TUI MCP panel or `mcp_menu` unchanged on this
  firmware; their leading-CR entry can wedge the radio.

## USB resets and monitor

Settings mode deliberately stops `d75mon` and holds the radio in MCP mode. The
monitor does not run during that time. Exit settings releases MCP, waits for USB
re-enumeration, and restarts the monitor.

## GPS altitude

- `GP 1,1` changes a radio setting and stops working as soon as a CAT command is
  accepted.
- NMEA and CAT share the stream; do not poll CAT while capturing NMEA.
- Weak fixes (few satellites, high HDOP) can have tens of metres of vertical
  error. Never present GPS altitude as survey data.
- Restore `GP 1,0` and restart the monitor when done.

## Warranty / affiliation

This is independent interoperability research. It is not affiliated with or
endorsed by Kenwood/JVCKenwood. Modifying settings or firmware behavior can void
warranty or violate local rules; you are responsible for your radio and
licence. No warranty is provided; see [LICENSE](LICENSE).
