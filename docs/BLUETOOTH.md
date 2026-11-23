# Bluetooth (Classic SPP) connectivity

The TH-D75 exposes CAT/MCP over **Bluetooth Classic SPP**, RFCOMM channel 2.
This is the same CAT transport used over USB, not BLE and not Bluetooth audio.

`d75mon` already supports it. The settings UI now treats it as a first-class
transport when `D75_SERIAL` is an rfcomm device.

## Scope

Supported:

- CAT/monitor data
- MCP settings read/write through the settings UI
- `/dev/rfcomm0` as the serial device

Not included:

- Bluetooth audio/headset/PTT
- BLE
- changing the radio's Bluetooth pairing protocol

## Radio setup

On the TH-D75:

1. **Menu 930 → Bluetooth On**
2. **Menu 934 → Pairing Mode**
3. Optionally **Menu 936 → Auto Connect** for reconnect
4. Menu 935 sets the advertised device name

The pairing mode is a physical-menu step; the web UI cannot enter it.

## Pair and bind on Linux

```bash
# BlueZ tools
sudo pacman -S --needed bluez bluez-utils bluez-deprecated-tools

bluetoothctl scan on
# wait for the TH-D75 name/MAC
bluetoothctl pair <MAC>
bluetoothctl trust <MAC>

# Bind RFCOMM channel 2 to /dev/rfcomm0
/home/p6/TH-D75-MCP/d75mon/tools/bt-bind.sh <MAC>
ls -l /dev/rfcomm0
```

When invoked via `sudo`, `bt-bind.sh` hands `/dev/rfcomm0` to the invoking
user. If you bind manually, `sudo chown "$USER:$USER" /dev/rfcomm0` is required;
otherwise the settings UI runs as your user and gets permission denied.

`bt-bind.sh` releases a stale binding first. It needs root because `rfcomm` is
deprecated BlueZ tooling.

## Monitor

`d75mon` config:

```json
"transport": "auto",
"usb_candidates": ["/dev/thd75", "/dev/ttyACM0"],
"bluetooth": "/dev/rfcomm0"
```

Auto prefers USB when both exist; set `"transport": "bluetooth"` to force
Bluetooth. Restart the monitor after binding:

```bash
systemctl --user restart d75mon
curl -s http://127.0.0.1:8099/state
```

Expect `"transport":"bluetooth"` and `"port":"/dev/rfcomm0"`.

## Settings UI

Run with an explicit Bluetooth transport:

```bash
D75_TRANSPORT=bluetooth D75_SERIAL=/dev/rfcomm0 \
  .venv/bin/python settings-ui/server.py
```

`D75_TRANSPORT=auto` also infers Bluetooth from an rfcomm serial path.

For a systemd user service, edit your existing unit:

```bash
systemctl --user edit d75settings.service
```

Add:

```ini
[Service]
Environment=D75_TRANSPORT=bluetooth
Environment=D75_SERIAL=/dev/rfcomm0
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user restart d75settings
```

A full template is in
`settings-ui/systemd/d75settings-bluetooth.service.example`.

## Behavior differences

USB:

- entry does not reset USB
- exit performs one USB reset and waits for re-enumeration
- monitor restarts after the device returns

Bluetooth:

- entry/exit use the open rfcomm stream
- exit closes the link and **does not wait for USB re-enumeration**
- `/dev/rfcomm0` normally remains bound
- monitor restarts and reconnects over Bluetooth

## Guardrail

Applying **Bluetooth On/Off = Off** while the settings session itself is running
over Bluetooth is rejected. It would disconnect the session and potentially
leave the radio held in MCP. Use USB to disable Bluetooth, or leave it on.

## Troubleshooting

| Symptom | Check |
|---|---|
| no `/dev/rfcomm0` | `rfcomm -a`; rerun `bt-bind.sh <MAC>` |
| `rfcomm: command not found` | install `bluez-deprecated-tools` |
| pair fails | radio in Pairing Mode, Menu 930 on, adapter powered |
| CAT works in monitor but not settings | startup env; `/api/status` should show `transport:"bluetooth"` |
| session hangs after exit | confirm you are not on an old build; BT exit skips USB wait |
| radio disappears | out of range/off; release settings session, re-bind, retry |

## Security

- Pairing mode makes the radio discoverable; turn it off afterward.
- Trust only the intended host.
- `rfcomm` binding is privileged; do not expose it to untrusted users.
- The web UI still has no authentication; keep it loopback/SSH-tunneled.

See `d75mon/README.md` for the original SPP notes and `SECURITY.md` for the web
service boundary.
