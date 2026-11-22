#!/usr/bin/env python3
"""d75mon — TH-D75 monitor service (v0, stock CAT telemetry).

Reads live status from a Kenwood TH-D75 over USB CDC or Bluetooth SPP and
serves a small "radio face" widget to LAN browsers over HTTP + SSE.

v0 only uses the text-CAT command surface that stock V1.03 exposes. It is
read-only apart from sending ``AI 0`` (auto-info off) so the radio does not
push unsolicited status that would corrupt query/response framing.
"""
from __future__ import annotations

import argparse
import json
import re
import signal
import struct
import sys
import threading
import time
import zlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

try:
    import serial
except Exception as exc:  # pragma: no cover - deployment sanity
    print("pyserial is required: %r" % (exc,), file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parent.parent
VERSION = "0.2.0"

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 8099,
    "transport": "auto",                      # auto | usb | bluetooth
    "usb_candidates": ["/dev/thd75", "/dev/ttyACM0"],
    "bluetooth": "/dev/rfcomm0",
    "baudrate": 9600,
    "fast_interval": 0.25,                    # live VFO DDR read cadence
    "framebuffer_addr": 0xC2349A40,            # 240x180 RGB565 LCD buffer
    "screen_cache_seconds": 0.4,
    "slow_interval": 5.0,                     # full CAT snapshot cadence
    "poll_interval": 2.0,
    "reconnect_interval": 3.0,
    "command_timeout": 0.6,
    "web_dir": "web",
    "asset_dir": "",                          # optional firmware-image dir
}

# (state key, CAT command).  All are query forms observed to answer on V1.03.
POLL_SET = [
    ("model", "ID"),
    ("firmware", "FV"),
    ("callsign", "CS"),
    ("clock", "RT"),
    ("audio_gain", "AG"),
    ("auto_info", "AI"),
    ("tnc", "TN"),
    ("gps", "GS"),
    ("priority", "PT"),
    ("backlight", "BL"),
    ("voice", "VG"),
    ("vox", "VX"),
    ("data_speed", "FS"),
    ("fr", "FR"),
    ("ft", "FT"),
    ("gateway", "GW"),
    ("sd", "SD"),
    ("bs", "BS"),
    ("lc", "LC"),
    ("ds", "DS"),
    ("io", "IO"),
    ("vd", "VD"),
    ("bt", "BT"),
    ("gps_dst", "GP"),
    ("ps", "PS"),
    ("ms", "MS"),
    ("as", "AS"),
    ("ty", "TY"),
    ("ae", "AE"),
]

# Extended probe list for `--probe` (one-shot diagnostics).
PROBE_SET = POLL_SET + [("bc", "BC"), ("bl2", "BL"), ("dl", "DL"),
                        ("dw", "DW"), ("up", "UP"), ("gm", "GM"),
                        ("vg2", "VG"), ("vx2", "VX")]

# Live state through the flashed `normal-gm-ddr-read`-family patch (read base
# 0xC2000000).  Each entry is (state key, GM command).  The 13 x 0x28 table at
# 0xC23E3700 holds per-band records: entry 0 = VFO A, entry 1 = VFO B;
# record layout: u32 frequency Hz @ +0, step/span @ +4, mode/flag words @ +8.
DDR_POLL = [
    ("ddr_vfo_a", "GM 3E3700,28"),
    ("ddr_vfo_b", "GM 3E3728,28"),
]


FRAMEBUFFER_BASE = 0xC2000000
LCD_WIDTH = 240
LCD_HEIGHT = 180
LCD_STRIDE = LCD_WIDTH * 2


def rgb565_to_rgb(data: bytes) -> bytes:
    """Convert little-endian RGB565 pixel bytes to packed RGB888."""
    out = bytearray((len(data) // 2) * 3)
    for i in range(0, len(data) - 1, 2):
        v = data[i] | (data[i + 1] << 8)
        o = (i // 2) * 3
        out[o] = ((v >> 11) & 0x1F) << 3
        out[o + 1] = ((v >> 5) & 0x3F) << 2
        out[o + 2] = (v & 0x1F) << 3
    return bytes(out)


def png_rgb(width: int, height: int, rgb: bytes) -> bytes:
    """Encode packed RGB888 as a minimal PNG (filter 0 scanlines)."""
    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


class CATError(Exception):
    """Radio answered with an error or nothing at all."""


class CATClient:
    """Line-oriented text-CAT client (``CMD\\r`` -> ``CMD value\\r``)."""

    def __init__(self, port: str, baudrate: int = 9600,
                 timeout: float = 0.6):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self._lock = threading.Lock()

    def open(self) -> None:
        self.ser = serial.Serial(self.port, baudrate=self.baudrate,
                                 timeout=0.15, write_timeout=1.0)
        time.sleep(0.1)

    def close(self) -> None:
        ser, self.ser = self.ser, None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    @property
    def is_open(self) -> bool:
        return self.ser is not None and getattr(self.ser, "is_open", True)

    def send(self, cmd: str, timeout: float | None = None) -> str:
        if self.ser is None:
            raise CATError("port not open")
        with self._lock:
            try:
                self.ser.reset_input_buffer()
                self.ser.write(cmd.encode("ascii") + b"\r")
                self.ser.flush()
            except Exception as exc:
                raise CATError("write failed: %r" % (exc,))
            buf = bytearray()
            deadline = time.monotonic() + (timeout or self.timeout)
            while time.monotonic() < deadline:
                try:
                    chunk = self.ser.read(1)
                except Exception as exc:
                    raise CATError("read failed: %r" % (exc,))
                if not chunk:
                    continue
                buf += chunk
                if chunk == b"\r":
                    break
            text = buf.decode("ascii", "replace").strip("\r\n")
            if not text:
                raise CATError("no response")
            if text.startswith("?"):
                raise CATError("radio rejected command")
            return text


def split_value(cmd: str, response: str) -> str:
    """Return the value part of ``CMD value`` (tolerating missing space)."""
    if response.startswith(cmd):
        rest = response[len(cmd):]
        return rest.strip()
    return response.strip()


def parse_clock(value: str) -> str | None:
    """RT reports YYMMDDhhmmss (2-digit year). Return ISO-8601 or None."""
    m = re.fullmatch(r"(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", value)
    if not m:
        return None
    yy, mo, dd, hh, mi, ss = (int(x) for x in m.groups())
    try:
        return datetime(2000 + yy, mo, dd, hh, mi, ss).isoformat()
    except ValueError:
        return None


class State:
    """Thread-safe snapshot of radio + service state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data = {
            "ok": False,
            "connected": False,
            "transport": None,
            "port": None,
            "updated_at": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "errors": 0,
            "last_error": None,
            "fields": {},
        }
        self.version = 0

    def update(self, **kw) -> None:
        with self._lock:
            self._data.update(kw)
            self._data["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.version += 1

    def set_field(self, key: str, cmd: str, raw: str | None,
                  error: str | None = None) -> None:
        with self._lock:
            entry = {"cmd": cmd}
            if error is not None:
                entry.update({"raw": None, "value": None, "error": error})
            else:
                entry.update({"raw": raw, "value": split_value(cmd, raw or "")})
            self._data["fields"][key] = entry
            if key == "clock" and entry.get("value"):
                parsed = parse_clock(entry["value"])
                if parsed:
                    self._data["fields"]["clock"]["iso"] = parsed

    def snapshot(self) -> dict:
        with self._lock:
            snap = json.loads(json.dumps(self._data))
            snap["version"] = self.version
            if snap.get("updated_at"):
                try:
                    updated = datetime.fromisoformat(snap["updated_at"])
                    snap["age_seconds"] = round(
                        (datetime.now(timezone.utc) - updated).total_seconds(), 1)
                except ValueError:
                    snap["age_seconds"] = None
            return snap


class Monitor(threading.Thread):
    def __init__(self, cfg: dict, state: State) -> None:
        super().__init__(daemon=True, name="d75mon-monitor")
        self.cfg = cfg
        self.state = state
        self.stop_event = threading.Event()
        self.client: CATClient | None = None
        self._screen_lock = threading.Lock()
        self._screen_png: bytes | None = None
        self._screen_time = 0.0
        self.transport: str | None = None
        self.port: str | None = None

    def log(self, msg: str) -> None:
        print("%s %s" % (datetime.now().strftime("%H:%M:%S"), msg),
              flush=True)

    def _candidates(self) -> list[tuple[str, str]]:
        mode = self.cfg.get("transport", "auto")
        out: list[tuple[str, str]] = []
        if mode in ("auto", "usb"):
            for p in self.cfg.get("usb_candidates", []):
                out.append(("usb", p))
        if mode in ("auto", "bluetooth"):
            out.append(("bluetooth", self.cfg.get("bluetooth", "/dev/rfcomm0")))
        return out

    def _connect(self) -> bool:
        for transport, port in self._candidates():
            if not Path(port).exists():
                continue
            client = CATClient(port, baudrate=self.cfg.get("baudrate", 9600),
                               timeout=self.cfg.get("command_timeout", 0.6))
            try:
                client.open()
                client.send("ID", timeout=1.0)
            except (CATError, OSError, Exception) as exc:
                client.close()
                self.state.update(last_error="%s %s: %r" % (transport, port, exc))
                continue
            self.client = client
            self.transport = transport
            self.port = port
            self.log("connected via %s on %s" % (transport, port))
            self.state.update(ok=True, connected=True, transport=transport,
                              port=port, last_error=None)
            try:
                client.send("AI 0")   # disable unsolicited status spam
            except CATError:
                pass
            return True
        return False

    def _disconnect(self, err: str) -> None:
        if self.client is not None:
            self.client.close()
        self.client = None
        self.log("disconnected: %s" % err)
        self.state.update(ok=False, connected=False, transport=None, port=None,
                          last_error=err)
        with self.state._lock:  # keep counters consistent
            self.state._data["errors"] = self.state._data.get("errors", 0) + 1

    def _poll_cat(self) -> None:
        """Slow lane: full CAT snapshot (settings, clock, model...)."""
        assert self.client is not None
        for key, cmd in POLL_SET:
            if self.stop_event.is_set():
                return
            try:
                raw = self.client.send(cmd)
                self.state.set_field(key, cmd, raw)
            except CATError as exc:
                self.state.set_field(key, cmd, None, error=str(exc))

    def _poll_ddr(self) -> bool:
        """Fast lane: live VFO struct through the DDR patch (~4 Hz)."""
        assert self.client is not None
        for key, cmd in DDR_POLL:
            if self.stop_event.is_set():
                return True
            try:
                raw = self.client.send(cmd, timeout=2.0)
                self.state.set_field(key, cmd, raw)
            except CATError as exc:
                self.state.set_field(key, cmd, None, error=str(exc))
            except Exception as exc:
                self._disconnect("ddr poll failed: %r" % (exc,))
                return False
        self._parse_ddr()
        self.state.update(ok=True, connected=True)
        return True

    def _parse_ddr(self) -> None:
        """Decode the live VFO A/B band records read through the DDR patch."""
        with self.state._lock:
            entries = dict(self.state._data["fields"])

        def rec(key):
            entry = entries.get(key)
            raw = entry.get("raw") if entry else None
            if not raw or not raw.startswith("GM ") or "," not in raw:
                return None
            try:
                data = bytes.fromhex(raw.split(",", 1)[1])
            except ValueError:
                return None
            return data if len(data) >= 0x28 else None

        for band, key in (("a", "ddr_vfo_a"), ("b", "ddr_vfo_b")):
            data = rec(key)
            if data is None:
                continue
            hz = struct.unpack_from("<I", data, 0)[0]
            step = struct.unpack_from("<I", data, 4)[0]
            mode = struct.unpack_from("<I", data, 8)[0]
            self.state.set_field("vfo_%s_hz" % band, "", str(hz))
            self.state.set_field("vfo_%s_offset" % band, "", str(step))
            self.state.set_field("vfo_%s_mode" % band, "", str(mode))

    def capture_framebuffer(self) -> bytes:
        """Read the 240x180 RGB565 LCD buffer through the DDR patch."""
        if self.client is None:
            raise CATError("radio not connected")
        addr = int(self.cfg.get("framebuffer_addr", 0xC2349A40))
        size = LCD_WIDTH * LCD_HEIGHT * 2
        out = bytearray()
        off = 0
        while off < size:
            ln = min(0xFF, size - off)
            try:
                raw = self.client.send(
                    "GM %06X,%02X" % ((addr - FRAMEBUFFER_BASE) + off, ln),
                    timeout=3.0)
            except CATError as exc:
                raise CATError("framebuffer read 0x%06X: %s" % (addr + off, exc))
            if not raw.startswith("GM ") or "," not in raw:
                raise CATError("framebuffer read 0x%06X rejected" % (addr + off))
            try:
                data = bytes.fromhex(raw.split(",", 1)[1])
            except ValueError:
                raise CATError("framebuffer read 0x%06X bad hex" % (addr + off))
            if len(data) != ln:
                raise CATError("framebuffer read 0x%06X short" % (addr + off))
            out += data
            off += ln
        return bytes(out)

    def capture_png(self) -> bytes:
        """Capture the LCD once and return it as a PNG (small TTL cache)."""
        ttl = float(self.cfg.get("screen_cache_seconds", 0.4))
        now = time.monotonic()
        with self._screen_lock:
            if self._screen_png is not None and now - self._screen_time < ttl:
                return self._screen_png
            raw = self.capture_framebuffer()
            png = png_rgb(LCD_WIDTH, LCD_HEIGHT, rgb565_to_rgb(raw))
            self._screen_png = png
            self._screen_time = now
            return png

    def run(self) -> None:
        fast = float(self.cfg.get("fast_interval", 0.25))
        slow = float(self.cfg.get("slow_interval",
                                  self.cfg.get("poll_interval", 5.0)))
        next_cat = 0.0
        while not self.stop_event.is_set():
            if self.client is None:
                if self._connect():
                    next_cat = 0.0
                    continue
                self.state.update(ok=False, connected=False)
                self.stop_event.wait(self.cfg.get("reconnect_interval", 3.0))
                continue
            try:
                if not self._poll_ddr():
                    self.stop_event.wait(self.cfg.get("reconnect_interval", 3.0))
                    continue
                now = time.monotonic()
                if now >= next_cat:
                    self._poll_cat()
                    next_cat = time.monotonic() + slow
            except Exception as exc:
                self._disconnect("poll failed: %r" % (exc,))
                self.stop_event.wait(self.cfg.get("reconnect_interval", 3.0))
                continue
            self.stop_event.wait(fast)
        if self.client is not None:
            self.client.close()

    def stop(self) -> None:
        self.stop_event.set()


class Handler(BaseHTTPRequestHandler):
    server_version = "d75mon/" + VERSION
    state: State
    monitor: "Monitor"
    web_dir: Path
    asset_dir: Path | None
    stop_event: threading.Event

    CONTENT_TYPES = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".png": "image/png",
        ".svg": "image/svg+xml",
    }

    def log_message(self, fmt, *args):  # keep journal quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj) -> None:
        self._send(200, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def _static(self, path: str) -> None:
        if path in ("/", "/index.html"):
            path = "/index.html"
        root = self.web_dir
        candidate = (root / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            self._send(403, b"forbidden", "text/plain")
            return
        if not candidate.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = self.CONTENT_TYPES.get(candidate.suffix, "application/octet-stream")
        self._send(200, candidate.read_bytes(), ctype)

    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_version = -1
        last_send = 0.0
        try:
            while not self.stop_event.is_set():
                now = time.monotonic()
                snap = self.state.snapshot()
                if snap["version"] != last_version or now - last_send > 2.0:
                    payload = json.dumps(snap)
                    self.wfile.write(
                        ("event: state\ndata: %s\n\n" % payload).encode())
                    self.wfile.flush()
                    last_version = snap["version"]
                    last_send = now
                time.sleep(0.4)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self):  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/screen.png":
            try:
                png = self.monitor.capture_png()
            except Exception as exc:
                self._send(503, ("screen unavailable: %r" % (exc,)).encode(),
                           "text/plain; charset=utf-8")
                return
            self._send(200, png, "image/png")
            return
        if path == "/state":
            self._json(self.state.snapshot())
            return
        if path == "/events":
            self._sse()
            return
        if path.startswith("/assets/") and self.asset_dir is not None:
            root = self.asset_dir
            candidate = (root / path[len("/assets/"):]).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                self._send(403, b"forbidden", "text/plain")
                return
            if candidate.is_file():
                ctype = self.CONTENT_TYPES.get(candidate.suffix,
                                               "application/octet-stream")
                self._send(200, candidate.read_bytes(), ctype)
                return
        self._static(path)


def load_config(path: str | None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if path:
        user = json.loads(Path(path).read_text())
        cfg.update(user)
    cfg["web_dir"] = str((ROOT / cfg["web_dir"]).resolve())
    if cfg.get("asset_dir"):
        cfg["asset_dir"] = str(Path(cfg["asset_dir"]).expanduser().resolve())
    else:
        cfg["asset_dir"] = ""
    return cfg


def run_once(cfg: dict, probe: bool = False) -> int:
    client = CATClient(cfg["usb_candidates"][0],
                       baudrate=cfg.get("baudrate", 9600),
                       timeout=cfg.get("command_timeout", 0.6))
    port = None
    for t, p in (("usb", p) for p in cfg["usb_candidates"]):
        if Path(p).exists():
            client = CATClient(p, baudrate=cfg.get("baudrate", 9600),
                               timeout=cfg.get("command_timeout", 0.6))
            port = p
            break
    if port is None and Path(cfg["bluetooth"]).exists():
        client = CATClient(cfg["bluetooth"], baudrate=cfg.get("baudrate", 9600),
                           timeout=cfg.get("command_timeout", 0.6))
        port = cfg["bluetooth"]
    if port is None:
        print("no radio port found", file=sys.stderr)
        return 1
    client.open()
    try:
        client.send("AI 0")
    except CATError:
        pass
    result = {}
    for key, cmd in (PROBE_SET if probe else POLL_SET):
        try:
            result[key] = client.send(cmd)
        except CATError as exc:
            result[key] = "ERR: %s" % exc
    print(json.dumps({"port": port, "results": result}, indent=2))
    client.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TH-D75 monitor service (v0)")
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    ap.add_argument("--once", action="store_true",
                    help="poll once, print JSON, exit")
    ap.add_argument("--probe", action="store_true",
                    help="with --once: query the extended command list")
    args = ap.parse_args(argv)

    cfg = load_config(args.config if Path(args.config).exists() else None)
    if args.host:
        cfg["host"] = args.host
    if args.port:
        cfg["port"] = args.port

    if args.once:
        return run_once(cfg, probe=args.probe)

    state = State()
    stop_event = threading.Event()
    monitor = Monitor(cfg, state)
    monitor.start()

    Handler.state = state
    Handler.monitor = monitor
    Handler.web_dir = Path(cfg["web_dir"])
    Handler.asset_dir = Path(cfg["asset_dir"]) if cfg["asset_dir"] else None
    Handler.stop_event = stop_event

    server = ThreadingHTTPServer((cfg["host"], cfg["port"]), Handler)
    server.daemon_threads = True
    print("d75mon %s listening on http://%s:%i/ (transport=%s)"
          % (VERSION, cfg["host"], cfg["port"], cfg["transport"]), flush=True)

    def shutdown(signum, frame):
        stop_event.set()
        monitor.stop()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop_event.set()
        monitor.stop()
        monitor.join(timeout=2.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
