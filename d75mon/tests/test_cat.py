"""Tests for the d75mon CAT parser and state helpers (no radio required)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import d75mon  # noqa: E402


class FakeSerial:
    """Minimal pyserial stand-in fed with canned responses."""

    def __init__(self, responses):
        self.responses = dict(responses)
        self.buf = b""
        self.is_open = True

    def reset_input_buffer(self):
        self.buf = b""

    def write(self, data):
        cmd = data.decode("ascii").strip()
        resp = self.responses.get(cmd, "?")
        self.buf += (resp + "\r").encode("ascii")

    def flush(self):
        pass

    def read(self, n=1):
        if not self.buf:
            return b""
        chunk, self.buf = self.buf[:n], self.buf[n:]
        return chunk

    def close(self):
        self.is_open = False


def make_client(responses):
    client = d75mon.CATClient("/dev/null")
    client.ser = FakeSerial(responses)
    return client


class CATClientTests(unittest.TestCase):
    def test_query_echo_and_value(self):
        c = make_client({"ID": "ID TH-D75", "FV": "FV 1.03"})
        self.assertEqual(c.send("ID"), "ID TH-D75")
        self.assertEqual(d75mon.split_value("ID", c.send("ID")), "TH-D75")
        self.assertEqual(c.send("FV"), "FV 1.03")

    def test_error_raises(self):
        c = make_client({"FA": "?"})
        with self.assertRaises(d75mon.CATError):
            c.send("FA")

    def test_value_split_without_space(self):
        self.assertEqual(d75mon.split_value("TN", "TN 0,0"), "0,0")
        self.assertEqual(d75mon.split_value("CS", "CS N0CALL"), "N0CALL")


class ParseTests(unittest.TestCase):
    def test_clock_parse(self):
        self.assertEqual(d75mon.parse_clock("261121193017"),
                         "2026-11-21T19:30:17")
        self.assertIsNone(d75mon.parse_clock("not-a-clock"))

    def test_state_snapshot_roundtrip(self):
        st = d75mon.State()
        st.update(ok=True, connected=True, transport="usb", port="/dev/thd75")
        st.set_field("model", "ID", "ID TH-D75")
        st.set_field("clock", "RT", "RT 261121193017")
        snap = st.snapshot()
        self.assertTrue(snap["connected"])
        self.assertEqual(snap["fields"]["model"]["value"], "TH-D75")
        self.assertEqual(snap["fields"]["clock"]["iso"], "2026-11-21T19:30:17")
        self.assertIn("version", snap)

    def test_rgb565_conversion(self):
        # little-endian RGB565: 0xF800 is red
        rgb = d75mon.rgb565_to_rgb(bytes([0x00, 0xF8]))
        self.assertEqual(tuple(rgb), (248, 0, 0))
        # 0x07E0 green
        rgb = d75mon.rgb565_to_rgb(bytes([0xE0, 0x07]))
        self.assertEqual(tuple(rgb), (0, 252, 0))

    def test_png_encoder_signature(self):
        png = d75mon.png_rgb(2, 1, bytes([255, 0, 0, 0, 255, 0]))
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IHDR", png)
        self.assertIn(b"IEND", png)

    def test_framebuffer_constants(self):
        self.assertEqual(d75mon.LCD_WIDTH, 240)
        self.assertEqual(d75mon.LCD_HEIGHT, 180)
        self.assertEqual(d75mon.LCD_WIDTH * d75mon.LCD_HEIGHT * 2, 86400)

    def test_state_error_field(self):
        st = d75mon.State()
        st.set_field("fr", "FR", None, error="radio rejected command")
        snap = st.snapshot()
        self.assertEqual(snap["fields"]["fr"]["error"], "radio rejected command")


if __name__ == "__main__":
    unittest.main()
