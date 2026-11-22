# Security policy

## Threat model

This project provides a **local administrative interface to a radio**. It is
not a multi-user service and it is not hardened for hostile networks.

- `settings-ui` can change stored radio settings.
- `d75mon` can display radio status and, with firmware-assisted fields, screen
  content.
- Neither service implements authentication, authorization, CSRF protection, or
  transport encryption.
- Anyone who can reach the HTTP port can use the interface.

## Network rules

- Default bind address is **127.0.0.1**.
- Remote access should use an SSH tunnel:
  `ssh -L 8098:127.0.0.1:8098 user@radio-host`
- Do **not** expose either port to the internet, a public reverse proxy, or an
  untrusted LAN.
- If LAN access is unavoidable, bind explicitly, restrict source addresses in
  the host firewall, and keep the radio on a trusted network.
- `D75SETTINGS_HOST=0.0.0.0` and `d75mon/config.json` `"host": "0.0.0.0"` are
  explicit opt-ins that log a warning.

## Serial-device security

The TH-D75 serial port controls a transmitter-capable radio.

- udev rule uses `MODE="0660"` and a serial group (`dialout` on
  Debian/Ubuntu, commonly `uucp` on Arch/CachyOS).
- Do not use `MODE="0666"`.
- Keep the device name stable with the `/dev/thd75` symlink.
- Verify the device with `lsusb` / `udevadm` before writing.
- Do not run two tools against the serial port at once.

## Private data

These files and responses can contain private information:

- `settings-ui/values.json`
- `settings-ui/backups/`
- clone images and firmware-analysis artifacts
- `/api/values` and `/api/read` responses
- APRS messages, callsigns, GPS coordinates, and Bluetooth names

They are gitignored and should stay local. Do not paste them into issues, logs,
or public chats.

## Reporting

Open a security issue in the repository, or contact the maintainer privately if
the report includes radio data, credentials, or location information.

## Scope

No authentication or encryption is claimed. The security boundary is the host
and the trusted network it runs on. This project is provided without warranty;
see [LICENSE](LICENSE) and [docs/SAFETY.md](docs/SAFETY.md).
