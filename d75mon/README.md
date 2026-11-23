# d75mon — TH-D75 monitor widget (v0)

Read-only monitor for a Kenwood TH-D75, served as a small "radio face" web
widget. The host attaches to the radio over **USB-C CDC**
(`/dev/thd75` or `/dev/ttyACM0`) or **Bluetooth SPP** (`/dev/rfcomm0`); browsers
on the LAN open the widget.

v0 uses only the text-CAT command surface that stock V1.03 exposes. Frequency,
mode, S-meter and battery are **not** available on stock firmware — those are
the v1 fields that will come from a firmware-assisted live read (see the plan
in `docs/` in this repository). The UI labels them honestly.

## Layout

```
d75mon/
├── backend/d75mon.py     # transports, CAT client, state, HTTP+SSE server
├── web/index.html         # widget page
├── web/style.css
├── web/app.js             # SSE client (fallback polling)
├── config.json
├── systemd/d75mon.service.example # user unit template
├── tools/bt-bind.sh       # rfcomm bind helper (BT SPP)
└── tests/test_cat.py      # parser / state tests
```

## Install (from the repo root)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python d75mon/backend/d75mon.py --config d75mon/config.json --once
.venv/bin/python -m unittest discover -s d75mon/tests
```

Serve:

```bash
.venv/bin/python d75mon/backend/d75mon.py --config d75mon/config.json
# then open http://<host>:8099/
```

**ASK FIRST:** service installation is a persistent system change. Adjust paths
if you cloned outside `~/thd75-web-console`.

```bash
mkdir -p ~/.config/systemd/user
cp d75mon/systemd/d75mon.service.example ~/.config/systemd/user/d75mon.service
systemctl --user daemon-reload
systemctl --user enable --now d75mon.service
journalctl --user -u d75mon.service -f
```

## USB transport

Requires the udev rule from the top-level README. It uses `MODE="0660"`
and a serial group (`dialout`, or `uucp` on Arch); never `0666`.

```
/etc/udev/rules.d/99-kenwood-thd75.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="2166", ATTRS{idProduct}=="9023",
  MODE="0660", GROUP="dialout", SYMLINK+="thd75"
```

## Bluetooth transport (TH-D75 SPP, RFCOMM channel 2)

The D75 uses Bluetooth **Classic SPP**, not BLE.

```bash
# one-time: rfcomm tool
sudo pacman -S bluez-deprecated-tools

# pair the radio first: Menu 930 on, Menu 934 Pairing Mode, then
bluetoothctl pair <MAC> && bluetoothctl trust <MAC>

# bind the serial channel
tools/bt-bind.sh <MAC>
# -> /dev/rfcomm0 ; set "transport": "bluetooth" (or keep "auto")
```

Then the radio can be tethered by Bluetooth; USB is preferred when both exist.

## Live DDR fields (requires the flashed GM reader patch)

v1 reads exclusive state through `GM` (base `0xC2000000`):
- VFO A/B records at `0xC23E3700` / `0xC23E3728` (40 B each: u32 Hz, offset, flags)
- LCD framebuffer at `0xC2349A40` (240x180 RGB565, stride 480)

## Endpoints

- `GET /` — widget
- `GET /state` — JSON snapshot (including live VFO A/B)
- `GET /events` — Server-Sent Events stream (one `state` event per change)
- `GET /screen.png` — live 240x180 LCD screenshot (DDR capture, ~0.6 s)

The widget is **unauthenticated** and defaults to `127.0.0.1`; use an SSH
tunnel or firewall a deliberate LAN binding. The widget's **SHOW SCREEN** button renders `/screen.png` and refreshes it while
open. See `docs/cat-map.md` for the CAT table and parameter-address map.

## Safety / limits

- Read-only apart from `AI 0` at connect (disables unsolicited status).
- Only query forms of CAT commands are polled; no settings are written.
- Stock firmware cannot expose the screen; do not expect frequencies here.
- Long runs: the service reconnects on USB re-enumeration or BT drop.
