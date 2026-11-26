# macOS installation and compatibility

The foreground web console and USB CAT were tested on Apple Silicon with
macOS 26.5.2 and Python 3.12. The project requires Python 3.10 or later.
A suitable Python installation is enough for the build checks.

## Install and check

```bash
git clone https://github.com/dennis-kf0rlx/thd75-web-console.git
cd thd75-web-console
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
make check
```

macOS does not use udev, `/dev/ttyACM*`, BlueZ `rfcomm`, or systemd. Do not run
the Linux bootstrap/service setup. Run the two processes directly, or create
LaunchAgents separately if persistent services are desired.

## Serial devices

USB CDC devices normally appear as `/dev/cu.usbmodem*`. Bluetooth Classic SPP
appears as `/dev/cu.TH-D75` after the radio has been paired in macOS System
Settings. Prefer `/dev/cu.*` over `/dev/tty.*` for an outgoing connection.

At startup, the monitor looks for outgoing USB ports with the Kenwood USB ID
`2166:9023` and defaults to `/dev/cu.TH-D75` for Bluetooth. Connect the
radio before starting the monitor, or restart the monitor after connecting USB.
To select a port explicitly, copy `d75mon/config.json`, set `usb_candidates`
or `bluetooth`, and pass that file with `--config`.

Bluetooth CAT is unverified. During testing, the paired serial port opened,
but the radio did not answer the `ID` query while USB was connected.

## Run the read-only monitor

Run the monitor only if the radio already has the GM reader firmware patch.
The monitor sends `GM` automatically, which can reboot a stock TH-D75 into
GPS-only mode. On stock firmware, run the settings interface by itself.

```bash
.venv/bin/python d75mon/backend/d75mon.py --config d75mon/config.json
# open http://127.0.0.1:8099/
```

The monitor sends CAT queries and `AI 0` (disable unsolicited status) but does
not write settings or memories.

## Run the settings interface

```bash
.venv/bin/python settings-ui/server.py
# open http://127.0.0.1:8098/
```

On macOS the settings server defaults to `/dev/cu.TH-D75`. Override it for USB:

```bash
D75_TRANSPORT=usb D75_SERIAL=/dev/cu.usbmodem1234 \
  .venv/bin/python settings-ui/server.py
```

On macOS, stop the monitor manually before entering settings mode and restart
it after exiting. The settings UI can load the catalog and status without an
MCP session. **Read from radio** enters MCP settings mode and reads memory
pages. **Apply** writes them. The macOS web UI test stopped at catalog and
status checks, without entering settings mode.

Keep both web servers bound to `127.0.0.1`. Neither interface has
authentication.
