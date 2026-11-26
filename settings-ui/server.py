#!/usr/bin/env python3
"""d75settings — TH-D75 settings web service with a persistent MCP session.

Settings mode:
  stop d75mon -> enter MCP once -> sparse page reads/writes (no USB reset per
  operation) -> exit MCP once at release (single USB reset) -> restart d75mon.

This replaces the CHIRP clone path for normal use. The radio is held in MCP mode
while settings mode is active; the UI says so and can release it explicitly.
"""
from __future__ import annotations

import atexit
import json
import os
import signal
import shutil
import sys
import threading
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import urllib.request

import serial

BASE = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(BASE, "catalog.json")
VALUES_PATH = os.path.join(BASE, "values.json")
BACKUP_DIR = os.path.join(BASE, "backups")
if sys.platform == "darwin":
    _default_serial = "/dev/cu.TH-D75"
    _default_fallback = "/dev/cu.TH-D75"
else:
    _default_serial = "/dev/thd75"
    _default_fallback = "/dev/rfcomm0"
SERIAL = os.environ.get("D75_SERIAL", _default_serial)
# Auto path fallback: USB is preferred, but a bound Bluetooth SPP tty is usable
# when the USB device is absent.
if not os.path.exists(SERIAL):
    _fallback = os.environ.get("D75_SERIAL_FALLBACK", _default_fallback)
    if os.path.exists(_fallback):
        SERIAL = _fallback
TRANSPORT_ENV = os.environ.get("D75_TRANSPORT", "auto").strip().lower()


def _is_rfcomm(path: str) -> bool:
    name = os.path.basename(path).lower()
    return name.startswith("rfcomm") or (sys.platform == "darwin" and "th-d75" in name)


def _detect_transport(path: str) -> str:
    if TRANSPORT_ENV not in ("auto", "usb", "bluetooth"):
        raise SystemExit("D75_TRANSPORT must be auto, usb, or bluetooth")
    if TRANSPORT_ENV == "auto":
        return "bluetooth" if _is_rfcomm(path) else "usb"
    if TRANSPORT_ENV == "usb" and _is_rfcomm(path):
        raise SystemExit("D75_TRANSPORT=usb conflicts with an rfcomm D75_SERIAL")
    if TRANSPORT_ENV == "bluetooth" and not _is_rfcomm(path):
        raise SystemExit("D75_TRANSPORT=bluetooth requires an rfcomm D75_SERIAL")
    return TRANSPORT_ENV


TRANSPORT = _detect_transport(SERIAL)
AUTO_RELEASE = os.environ.get("D75_AUTO_RELEASE", "1").strip().lower() not in ("0", "false", "no")
MONITOR_UNIT = os.environ.get("D75_MONITOR_UNIT", "d75mon")
MONITOR_URL = os.environ.get("D75_MONITOR_URL", "http://127.0.0.1:8099").rstrip("/")
HOST = os.environ.get("D75SETTINGS_HOST", "127.0.0.1")
PORT = int(os.environ.get("D75SETTINGS_PORT", "8098"))
IDLE_RELEASE_SEC = int(os.environ.get("D75SETTINGS_IDLE", "300"))
KEEPALIVE_SEC = float(os.environ.get("D75SETTINGS_KEEPALIVE", "0.5"))
KEEPALIVE_PAGE = 0x0010
IMAGE_SIZE = 500_480

LOCK = threading.Lock()
LAST_ERROR: str | None = None
CATALOG: dict = {}
BY_ID: dict[str, dict] = {}
SESSION: "McpSession | None" = None
LAST_ACTIVITY = 0.0
CACHE: dict = {"model": "TH-D75", "firmware": "1.03", "values": {}}


def log(message: str) -> None:
    print(f"[d75settings] {message}", flush=True)


# ---------------------------------------------------------------------------
# Monitor / serial helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], timeout: int = 20):
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def monitor_active() -> bool:
    if shutil.which("systemctl") is None:
        return False
    p = run(["systemctl", "--user", "is-active", MONITOR_UNIT], timeout=5)
    return p.returncode == 0 and p.stdout.strip() == "active"


def wait_monitor(active: bool, timeout: float = 10.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if monitor_active() == active:
            return True
        time.sleep(0.3)
    return monitor_active() == active


def stop_monitor() -> None:
    if monitor_active():
        run(["systemctl", "--user", "stop", MONITOR_UNIT])
    wait_monitor(False, 10.0)


def start_monitor() -> None:
    if shutil.which("systemctl") is None:
        return
    for _ in range(3):
        run(["systemctl", "--user", "start", MONITOR_UNIT])
        if wait_monitor(True, 8.0):
            return
        time.sleep(2.0)
    log("warning: d75mon did not stay active after restart")


def serial_present() -> bool:
    return os.path.exists(SERIAL)


def wait_serial_cycle(timeout: float = 30.0) -> bool:
    if TRANSPORT == "bluetooth":
        # RFCOMM does not disappear/reappear like USB CDC after MCP exit.
        end = time.time() + min(timeout, 2.0)
        while time.time() < end:
            if serial_present():
                return True
            time.sleep(0.2)
        return serial_present()
    start = time.time()
    saw_absent = False
    while time.time() - start < timeout:
        if not serial_present():
            saw_absent = True
        elif saw_absent:
            time.sleep(0.5)
            return True
        elif time.time() - start > 3.0:
            time.sleep(0.5)
            return True
        time.sleep(0.2)
    return serial_present()


# ---------------------------------------------------------------------------
# MCP session
# ---------------------------------------------------------------------------

class McpSession:
    def __init__(self):
        self.port: serial.Serial | None = None
        self.pages: dict[int, bytes] = {}
        self.active = False

    def _read_exact(self, n: int, timeout: float = 3.0) -> bytes:
        assert self.port is not None
        out = b""
        end = time.time() + timeout
        while len(out) < n and time.time() < end:
            chunk = self.port.read(n - len(out))
            if chunk:
                out += chunk
        if len(out) != n:
            raise RuntimeError(f"MCP short read {len(out)}/{n}: {out!r}")
        return out

    def enter(self) -> None:
        self.port = serial.Serial(SERIAL, 9600, timeout=0.5)
        self.port.reset_input_buffer()
        # CHIRP enters MCP without the leading CR; the leading CR makes this
        # firmware answer with a stray '?\r' before '0M\r'.
        self.port.write(b"0M PROGRAM\r")
        entry = b""
        end = time.time() + 4.0
        while time.time() < end and b"0M" not in entry:
            chunk = self.port.read(64)
            if chunk:
                entry += chunk
        if b"0M" not in entry:
            self.port.close()
            raise RuntimeError(f"MCP entry failed: {entry!r}")
        self.active = True
        log(f"MCP entered (entry={entry!r})")

    def read_page(self, page: int) -> bytes:
        assert self.port is not None
        self.port.write(b"R" + page.to_bytes(2, "big") + b"\x00\x00")
        time.sleep(0.08)
        resp = self._read_exact(261)
        if resp[0:1] != b"W":
            raise RuntimeError(f"MCP page {page:#06x}: bad marker {resp[:8]!r}")
        echoed = int.from_bytes(resp[1:3], "big")
        if echoed != page:
            raise RuntimeError(f"MCP page echo {echoed:#06x} != {page:#06x}")
        data = resp[5:261]
        self.port.write(b"\x06")
        ack = self._read_exact(1, 1.5)
        if ack != b"\x06":
            raise RuntimeError(f"MCP page {page:#06x}: bad ACK {ack!r}")
        return data

    def write_page(self, page: int, data: bytes) -> None:
        assert self.port is not None and len(data) == 256
        self.port.write(b"W" + page.to_bytes(2, "big") + b"\x00\x00" + data)
        # CHIRP tolerates up to 10 bytes looking for the ACK; mirror that.
        ack = b""
        end = time.time() + 2.0
        while len(ack) < 10 and time.time() < end:
            chunk = self.port.read(1)
            if chunk:
                ack += chunk
                if chunk == b"\x06":
                    break
        if not ack.endswith(b"\x06"):
            raise RuntimeError(f"MCP write page {page:#06x}: bad ACK {ack!r}")

    def ensure_pages(self, pages: set[int], force: bool = False) -> None:
        for page in sorted(pages):
            if force or page not in self.pages:
                self.pages[page] = self.read_page(page)

    def image_for_pages(self, pages: set[int]) -> bytearray:
        image = bytearray(IMAGE_SIZE)
        for page in pages:
            image[page * 256:(page + 1) * 256] = self.pages[page]
        return image

    def exit(self) -> None:
        if not self.active:
            return
        try:
            if self.port is not None:
                self.port.write(b"E")
                time.sleep(0.2)
                try:
                    self.port.read(8)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            try:
                if self.port is not None:
                    self.port.close()
            except Exception:
                pass
            self.active = False
            self.port = None
            if TRANSPORT == "bluetooth":
                log("MCP exited; Bluetooth link released (no USB reset)")
            else:
                log("MCP exited; waiting for USB re-enumeration")
                wait_serial_cycle(30.0)


def page_span(offset: int, size: int) -> set[int]:
    start = offset // 256
    end = (offset + max(size, 1) - 1) // 256
    return set(range(start, end + 1))


def item_size(item: dict) -> int:
    meta = item.get("meta") or {}
    kind = meta.get("kind", "byte")
    if kind == "unsigned_le":
        return int(meta.get("width", 2))
    if kind == "fixed_string":
        return int(meta.get("length", 16))
    return 1


def all_pages() -> set[int]:
    pages: set[int] = set()
    for item in CATALOG.get("settings", []):
        pages |= page_span(int(item["offset"], 16), item_size(item))
    return pages


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def acquire_session() -> McpSession:
    global SESSION, LAST_ACTIVITY
    if SESSION is not None and SESSION.active:
        LAST_ACTIVITY = time.time()
        return SESSION
    stop_monitor()
    session = McpSession()
    session.enter()
    SESSION = session
    LAST_ACTIVITY = time.time()
    return session


def release_session(restart_monitor: bool = True) -> None:
    global SESSION, LAST_ERROR
    session = SESSION
    SESSION = None
    if session is not None:
        try:
            session.exit()
        except Exception as exc:  # noqa: BLE001
            LAST_ERROR = f"session exit: {exc}"
            log(f"MCP exit error: {exc}")
    if restart_monitor:
        start_monitor()


def idle_loop() -> None:
    while True:
        time.sleep(10.0)
        try:
            with LOCK:
                if SESSION is not None and time.time() - LAST_ACTIVITY > IDLE_RELEASE_SEC:
                    log(f"idle timeout after {IDLE_RELEASE_SEC}s; releasing settings mode")
                    release_session()
        except Exception as exc:  # noqa: BLE001
            log(f"idle loop error: {exc}")


def keepalive_loop() -> None:
    """Keep the radio's MCP session alive while settings mode is active.

    This firmware stops answering MCP commands after roughly 10 seconds without
    traffic. A single-page read every half second keeps the session responsive without
    causing a USB reset.
    """
    global LAST_ERROR
    while True:
        time.sleep(KEEPALIVE_SEC)
        try:
            with LOCK:
                if SESSION is not None and SESSION.active:
                    SESSION.read_page(KEEPALIVE_PAGE)
        except Exception as exc:  # noqa: BLE001
            LAST_ERROR = f"keepalive: {type(exc).__name__}: {exc}"
            log(LAST_ERROR)
            try:
                with LOCK:
                    if SESSION is not None:
                        release_session(restart_monitor=True)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Value conversion
# ---------------------------------------------------------------------------

def decode_value(item: dict, image: bytes):
    meta = item.get("meta") or {}
    off = int(item["offset"], 16)
    kind = meta.get("kind")
    if kind == "bit":
        return bool((image[off] >> int(meta.get("bit", 0))) & 1)
    if kind == "bool":
        return bool(image[off])
    if kind == "byte":
        return image[off]
    if kind == "unsigned_le":
        return int.from_bytes(image[off:off + int(meta.get("width", 2))], "little")
    if kind == "fixed_string":
        length = int(meta.get("length", 16))
        raw = image[off:off + length].split(b"\x00", 1)[0]
        enc = meta.get("encoding") or "utf8"
        if enc in ("memory_map", "utf8", "utf-8", "ascii"):
            enc = "utf-8"
        elif enc in ("shift_jis", "shift-jis"):
            enc = "shift_jis"
        try:
            return raw.decode(enc, "replace")
        except LookupError:
            return raw.decode("utf-8", "replace")
    raise ValueError(f"unsupported kind {kind} for {item['id']}")


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in ("1", "true", "on", "yes"):
        return True
    if text in ("0", "false", "off", "no"):
        return False
    raise ValueError(f"invalid boolean value {value!r}")


def validate_value(item: dict, value):
    meta = item.get("meta") or {}
    kind = meta.get("kind")
    if kind in ("bool", "bit"):
        return _to_bool(value)
    if kind == "byte":
        if item.get("type") == "select":
            for raw, label in item.get("options") or []:
                if str(raw) == str(value) or label == value:
                    return int(raw)
            raise ValueError(f"{value!r} is not a valid option for {item['id']}")
        try:
            ivalue = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{item['id']} requires an integer")
        allowed = item.get("allowed_values")
        if allowed and ivalue not in allowed:
            raise ValueError(f"{ivalue} not in allowed values for {item['id']}")
        lo, hi = int(item.get("min", 0)), int(item.get("max", 255))
        if not lo <= ivalue <= hi:
            raise ValueError(f"{item['id']} must be {lo}..{hi}")
        return ivalue
    if kind == "unsigned_le":
        ivalue = int(value)
        lo, hi = int(item.get("min", 0)), int(item.get("max", 65535))
        if not lo <= ivalue <= hi:
            raise ValueError(f"{item['id']} must be {lo}..{hi}")
        return ivalue
    if kind == "fixed_string":
        text = str(value)
        length = int(meta.get("length", 16))
        enc = meta.get("encoding") or "utf8"
        if enc in ("memory_map", "utf8", "utf-8", "ascii"):
            enc = "utf-8"
        elif enc in ("shift_jis", "shift-jis"):
            enc = "shift_jis"
        if len(text.encode(enc, "replace")) > length:
            raise ValueError(f"{item['id']} is limited to {length} bytes")
        return text
    raise ValueError(f"unsupported field {item['id']}")


def apply_value(item: dict, image: bytearray, value) -> None:
    meta = item.get("meta") or {}
    off = int(item["offset"], 16)
    kind = meta.get("kind")
    if kind == "bit":
        bit = int(meta.get("bit", 0))
        byte = image[off]
        image[off] = (byte | (1 << bit)) if value else (byte & ~(1 << bit))
    elif kind == "bool":
        image[off] = 1 if value else 0
    elif kind == "byte":
        image[off] = int(value) & 0xFF
    elif kind == "unsigned_le":
        width = int(meta.get("width", 2))
        image[off:off + width] = int(value).to_bytes(width, "little")
    elif kind == "fixed_string":
        length = int(meta.get("length", 16))
        enc = meta.get("encoding") or "utf8"
        if enc in ("memory_map", "utf8", "utf-8", "ascii"):
            enc = "utf-8"
        elif enc in ("shift_jis", "shift-jis"):
            enc = "shift_jis"
        raw = str(value).encode(enc, "replace")[:length]
        image[off:off + length] = raw.ljust(length, b"\x00")
    else:
        raise ValueError(f"unsupported field {item['id']}")


def values_from_image(image: bytes) -> dict:
    values = {}
    for item in CATALOG.get("settings", []):
        try:
            values[item["id"]] = decode_value(item, image)
        except Exception as exc:  # noqa: BLE001
            log(f"decode {item['id']}: {exc}")
    return values


def save_cache(values: dict) -> None:
    global CACHE
    CACHE = {"model": "TH-D75", "firmware": "1.03",
             "values": values, "updatedAt": datetime.now().isoformat(timespec="seconds")}
    fd = os.open(VALUES_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(CACHE, fh, indent=1)


def backup_values(values: dict) -> str:
    os.makedirs(BACKUP_DIR, mode=0o700, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(BACKUP_DIR, f"{stamp}-values.json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(values, fh, indent=1)
    return path


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def read_values() -> dict:
    global LAST_ERROR, LAST_ACTIVITY
    session = acquire_session()
    pages = all_pages()
    session.ensure_pages(pages, force=True)
    image = session.image_for_pages(pages)
    values = values_from_image(image)
    save_cache(values)
    LAST_ACTIVITY = time.time()
    LAST_ERROR = None
    return {"model": "TH-D75", "firmware": "1.03", "values": values,
            "readAt": datetime.now().isoformat(timespec="seconds"),
            "settingsMode": True}


def apply_changes(changes: list[dict], confirm_high_risk: bool = False) -> dict:
    global LAST_ERROR, LAST_ACTIVITY
    plan = []
    seen = set()
    for change in changes:
        sid = change.get("id")
        if not isinstance(sid, str) or sid in seen:
            raise ValueError("invalid or duplicate setting id")
        seen.add(sid)
        item = BY_ID.get(sid)
        if not item:
            raise ValueError(f"unknown setting {sid}")
        if item.get("risk") == "high" and not confirm_high_risk:
            raise ValueError(f"{sid} is high-risk; explicit confirmation required")
        value = validate_value(item, change.get("value"))
        if (TRANSPORT == "bluetooth" and sid == "radio.BluetoothOnOff"
                and value is False):
            raise ValueError(
                "radio.BluetoothOnOff=false would disconnect the active "
                "Bluetooth settings session; use USB or keep Bluetooth on")
        plan.append((item, value))
    if not plan:
        return {"ok": True, "written": 0, "verified": 0, "values": {}, "settingsMode": True}

    session = acquire_session()
    pages: set[int] = set()
    for item, _ in plan:
        pages |= page_span(int(item["offset"], 16), item_size(item))
    # Reuse pages already loaded by /api/read; re-reading immediately is both
    # unnecessary and apparently unreliable on this firmware.
    session.ensure_pages(pages, force=False)
    before_image = session.image_for_pages(pages)
    before_values = values_from_image(before_image)
    backup = backup_values(before_values)

    image = bytearray(before_image)
    for item, value in plan:
        apply_value(item, image, value)

    changed_pages = {p for p in pages if bytes(image[p * 256:(p + 1) * 256]) != session.pages[p]}
    for page in sorted(changed_pages):
        session.write_page(page, bytes(image[page * 256:(page + 1) * 256]))
    session.ensure_pages(changed_pages, force=True)
    after_values = values_from_image(session.image_for_pages(pages))

    for item, expected in plan:
        actual = after_values.get(item["id"])
        if isinstance(expected, bool):
            ok = actual == expected
        elif isinstance(expected, str):
            ok = actual == expected
        else:
            ok = int(actual) == int(expected)
        if not ok:
            raise RuntimeError(f"verify failed for {item['id']}: expected {expected!r}, got {actual!r}")

    # refresh cache for all fields we can decode
    session.ensure_pages(all_pages())
    save_cache(values_from_image(session.image_for_pages(all_pages())))
    LAST_ACTIVITY = time.time()
    LAST_ERROR = None
    settings_mode = True
    if AUTO_RELEASE:
        try:
            release_session(restart_monitor=True)
            settings_mode = False
            log("apply complete; auto-released settings mode")
        except Exception as exc:  # noqa: BLE001
            LAST_ERROR = f"settings mode release failed: {exc}"
            log(LAST_ERROR)
    return {"ok": True, "written": len(plan), "verified": len(plan),
            "values": {item["id"]: after_values[item["id"]] for item, _ in plan},
            "backup": backup, "settingsMode": settings_mode}


def release_settings() -> dict:
    global LAST_ERROR
    release_session(restart_monitor=True)
    LAST_ERROR = None
    return {"ok": True, "settingsMode": False, "monitorActive": monitor_active()}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE, **kwargs)

    def log_message(self, fmt, *args):
        log(fmt % args)

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _proxy_monitor(self, path: str, content_type: str, timeout: float = 3.0) -> None:
        try:
            with urllib.request.urlopen(MONITOR_URL + path, timeout=timeout) as resp:
                body = resp.read()
        except Exception as exc:  # noqa: BLE001
            return self._json(503, {"error": f"monitor unavailable: {exc}"})
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _status(self) -> dict:
        return {"sessionActive": SESSION is not None and SESSION.active,
                "monitorActive": monitor_active(),
                "serialPresent": serial_present(),
                "transport": TRANSPORT,
                "serialPath": SERIAL,
                "busy": LOCK.locked(),
                "lastError": LAST_ERROR}

    def do_GET(self):  # noqa: N802
        global LAST_ERROR
        path = urlparse(self.path).path
        if path == "/api/monitor/state":
            return self._proxy_monitor("/state", "application/json; charset=utf-8")
        if path == "/api/monitor/screen.png":
            return self._proxy_monitor("/screen.png", "image/png", timeout=45.0)
        if path == "/api/status":
            return self._json(200, self._status())
        if path == "/api/catalog":
            return self._json(200, CATALOG)
        if path == "/api/values":
            return self._json(200, CACHE)
        if path == "/api/read":
            # Keepalive holds this lock briefly (~0.1s); wait rather than
            # returning 409 while the user is trying to read/apply.
            if not LOCK.acquire(timeout=15):
                return self._json(409, {"error": "another operation is running"})
            try:
                LAST_ERROR = None
                return self._json(200, read_values())
            except Exception as exc:  # noqa: BLE001
                LAST_ERROR = f"{type(exc).__name__}: {exc}"
                log(f"read error: {LAST_ERROR}")
                try:
                    release_session(restart_monitor=True)
                except Exception:
                    pass
                return self._json(500, {"error": LAST_ERROR})
            finally:
                LOCK.release()
        allowed = {"/", "/index.html", "/styles.css", "/app.js", "/catalog.js"}
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path not in allowed:
            return self._json(404, {"error": "not found"})
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        global LAST_ERROR
        path = urlparse(self.path).path
        if path not in ("/api/apply", "/api/session/stop"):
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json(400, {"error": "invalid JSON body"})
        if not LOCK.acquire(timeout=15):
            return self._json(409, {"error": "another operation is running"})
        try:
            LAST_ERROR = None
            if path == "/api/session/stop":
                return self._json(200, release_settings())
            changes = payload.get("changes") or []
            if not isinstance(changes, list):
                return self._json(400, {"error": "changes must be a list"})
            result = apply_changes(changes, bool(payload.get("confirmHighRisk")))
            return self._json(200, result)
        except Exception as exc:  # noqa: BLE001
            LAST_ERROR = f"{type(exc).__name__}: {exc}"
            log(f"operation error: {LAST_ERROR}")
            try:
                release_session(restart_monitor=True)
            except Exception:
                pass
            return self._json(500, {"error": LAST_ERROR})
        finally:
            LOCK.release()


def cleanup() -> None:
    try:
        with LOCK:
            if SESSION is not None:
                release_session(restart_monitor=True)
    except Exception:
        pass


def main() -> int:
    global CATALOG, BY_ID, CACHE
    if not os.path.exists(CATALOG_PATH):
        log(f"missing {CATALOG_PATH}")
        return 2
    CATALOG = json.load(open(CATALOG_PATH))
    BY_ID = {item["id"]: item for item in CATALOG.get("settings", [])}
    if os.path.exists(VALUES_PATH):
        try:
            CACHE = json.load(open(VALUES_PATH))
        except Exception as exc:  # noqa: BLE001
            log(f"values cache load failed: {exc}")
    threading.Thread(target=idle_loop, daemon=True).start()
    threading.Thread(target=keepalive_loop, daemon=True).start()
    atexit.register(cleanup)
    signal.signal(signal.SIGTERM, lambda *_: (cleanup(), os._exit(0)))
    signal.signal(signal.SIGINT, lambda *_: (cleanup(), os._exit(0)))
    log(f"loaded {len(BY_ID)} settings; transport={TRANSPORT} serial={SERIAL}; "
        f"auto_release={AUTO_RELEASE}; listening on {HOST}:{PORT}")
    if HOST not in ("127.0.0.1", "localhost", "::1"):
        log("WARNING: no authentication; do not expose this port to the internet")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
